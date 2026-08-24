"""HTTP-Client fuer das SFV-Matchcenter.

Das Matchcenter hat keine offizielle API, liefert aber server-gerendertes HTML
mit stabilen URL-Parametern:

    default.aspx?oid=<Verband>&lng=<Sprache>&s=<Saison>&ln=<Liga>
    default.aspx?oid=<Verband>&lng=<Sprache>&v=<Verein>
    default.aspx?oid=<Verband>&lng=<Sprache>&v=<Verein>&t=<Team>&a=trr
    default.aspx?oid=<Verband>&lng=<Sprache>&tg=<Spiel>      (Telegramm)

Der Client haelt sich bewusst zurueck: fester Mindestabstand zwischen den
Requests und ein Disk-Cache, damit ein Sync nicht dutzende Seiten neu zieht,
die sich seit zehn Minuten nicht geaendert haben.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .. import config

log = logging.getLogger(__name__)

# Wartezeiten in Sekunden, wenn der Server drosselt (403/429).
THROTTLE_BACKOFF = (30, 60, 120, 240)


class _Throttled(Exception):
    """Der Server hat gedrosselt - kein echter Fehler, nur zu schnell gewesen."""

    def __init__(self, status: int) -> None:
        super().__init__(f"gedrosselt (HTTP {status})")


@dataclass
class Response:
    url: str
    html: str
    from_cache: bool


class MatchcenterClient:
    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        delay: float | None = None,
        offline: bool = False,
    ) -> None:
        self.cache_dir = cache_dir or config.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.offline = offline
        self._last_request = 0.0
        self._client = httpx.Client(
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-CH,de;q=0.9",
            },
        )

    # -- oeffentliche API ---------------------------------------------------

    def get(self, params: dict, *, ttl: int | None = None) -> Response:
        """Holt eine Matchcenter-Seite, bevorzugt aus dem Cache."""
        full = {"oid": config.ORG_ID, "lng": config.LANG_ID, **params}
        # None-Werte rausfiltern, damit die Cache-Keys stabil bleiben.
        full = {k: v for k, v in full.items() if v is not None}
        url = f"{config.MATCHCENTER_URL}?{urlencode(full)}"
        ttl = config.CACHE_TTL_DEFAULT if ttl is None else ttl

        cached = self._read_cache(url, ttl)
        if cached is not None:
            return Response(url=url, html=cached, from_cache=True)

        if self.offline:
            raise RuntimeError(f"Offline-Modus, aber nicht im Cache: {url}")

        html = self._fetch(url)
        self._write_cache(url, html)
        return Response(url=url, html=html, from_cache=False)

    def club(self, club_id: int | None = None, *, ttl: int | None = None) -> Response:
        return self.get({"v": club_id or config.CLUB_ID}, ttl=ttl)

    def team(self, team_id: int, club_id: int | None = None, *, ttl: int | None = None) -> Response:
        """Team-Seite mit Tabelle, Resultaten und Spielplan ("trr")."""
        return self.get(
            {"v": club_id or config.CLUB_ID, "t": team_id, "a": "trr"}, ttl=ttl
        )

    def league(self, league_id: int, season: int | None = None, *, ttl: int | None = None) -> Response:
        return self.get({"s": season or config.SEASON, "ln": league_id}, ttl=ttl)

    def group(self, season_id: int, group_id: int, action: str, *, ttl: int | None = None) -> Response:
        """Eine Gruppe in einer bestimmten Ansicht.

        action: "mrr" Resultate+Rangliste | "msp" ganzer Spielplan | "mtg" Torschuetzenliste
        ln wird nicht gebraucht - ls und sg adressieren die Gruppe eindeutig.
        """
        return self.get(
            {"s": config.SEASON, "ls": season_id, "sg": group_id, "a": action}, ttl=ttl
        )

    def schedule(self, season_id: int, group_id: int, *, ttl: int | None = None) -> Response:
        return self.group(season_id, group_id, "msp", ttl=ttl)

    def scorers(self, season_id: int, group_id: int, *, ttl: int | None = None) -> Response:
        return self.group(season_id, group_id, "mtg", ttl=ttl)

    def telegram(self, match_id: int, *, ttl: int | None = None) -> Response:
        """Spieldetail mit Ereignisliste (Tore, Karten, Wechsel)."""
        return self.get({"tg": match_id}, ttl=ttl)

    def overview(self, *, ttl: int | None = None) -> Response:
        """Matchcenter-Startseite - enthaelt die Liga-Navigation des Verbands."""
        return self.get({"s": config.SEASON}, ttl=ttl)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MatchcenterClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- intern -------------------------------------------------------------

    def _fetch(self, url: str) -> str:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                resp = self._client.get(url)
                self._last_request = time.monotonic()
                if resp.status_code in (403, 429):
                    # Das Matchcenter drosselt ueber Cloudflare. Kein Grund zur
                    # Panik - nur ein Signal, deutlich langsamer zu machen.
                    raise _Throttled(resp.status_code)
                resp.raise_for_status()
                # Der Server schickt utf-8, deklariert es aber nicht immer
                # konsistent - httpx' Autodetection liegt hier gelegentlich daneben.
                return resp.content.decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001 - bewusst breit, wir loggen
                last_error = exc
                self._last_request = time.monotonic()
                # Bei Drosselung lange warten, bei Netzfehlern kurz.
                backoff = THROTTLE_BACKOFF[min(attempt, len(THROTTLE_BACKOFF) - 1)] \
                    if isinstance(exc, _Throttled) else 2 ** attempt
                log.warning("Request fehlgeschlagen (%s/4): %s - warte %ss", attempt + 1, exc, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"Konnte {url} nicht laden") from last_error

    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode()).hexdigest()[:20]
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, url: str, ttl: int) -> str | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if self.offline:
            return payload["html"]
        if time.time() - payload.get("ts", 0) > ttl:
            return None
        return payload["html"]

    def _write_cache(self, url: str, html: str) -> None:
        path = self._cache_path(url)
        path.write_text(
            json.dumps({"url": url, "ts": time.time(), "html": html}),
            encoding="utf-8",
        )

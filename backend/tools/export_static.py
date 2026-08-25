"""Schreibt die komplette API als statische JSON-Dateien.

Warum statisch statt Server?

Die Daten aendern sich ein paar Mal pro Woche, und jede Anfrage der App ist ein
reines GET ohne Parameter, die der Server auswerten muesste. Ein laufender
Webserver waere also reine Verschwendung - und auf Gratis-Stufen ausserdem
fragil: Render loescht bei jedem Neustart die Festplatte (SQLite weg), und der
Scraper wuerde aus einem Rechenzentrum laufen, wo Cloudflare blockt.

Deshalb: Sync laeuft lokal, dieses Skript friert das Ergebnis ein, GitHub Pages
liefert es aus. Kostenlos, ohne Kaltstart, ohne Ausfall.

    python -m app.sync --details 40
    python -m tools.export_static
    git add docs && git commit -m "Daten aktualisiert" && git push

Die Dateien landen unter `docs/api/` und spiegeln die Pfade der FastAPI-Routen,
nur mit `.json` am Ende - die App haengt das im Produktionsmodus selbst an.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db  # noqa: E402
from app.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "docs" / "api"

# Grosszuegige Zeitfenster: die App filtert danach selbst, damit sie nicht fuer
# jede Ansicht eine eigene Datei braucht.
UPCOMING_DAYS = 180
RECENT_LIMIT = 60
TOURNAMENT_DAYS = 180


class Exporter:
    def __init__(self, client: TestClient, out_dir: Path) -> None:
        self.client = client
        self.out_dir = out_dir
        self.written = 0
        self.bytes = 0

    def dump(self, api_path: str, query: str = "") -> object | None:
        """Ruft eine Route auf und legt die Antwort als <pfad>.json ab."""
        url = f"{api_path}?{query}" if query else api_path
        response = self.client.get(url)
        if response.status_code != 200:
            print(f"  uebersprungen {url} -> HTTP {response.status_code}")
            return None

        target = self.out_dir / (api_path.removeprefix("/api/") + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(response.json(), ensure_ascii=False, separators=(",", ":"))
        target.write_text(payload, encoding="utf-8")

        self.written += 1
        self.bytes += len(payload.encode("utf-8"))
        return response.json()


def export() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    client = TestClient(app)
    ex = Exporter(client, OUT_DIR)

    print("Allgemein")
    ex.dump("/api/health")
    club = ex.dump("/api/club")
    ex.dump("/api/teams")
    ex.dump("/api/stats/overview")
    ex.dump("/api/stats/players")

    print("Spiele")
    upcoming = ex.dump("/api/matches/upcoming", f"days={UPCOMING_DAYS}") or []
    recent = ex.dump("/api/matches/recent", f"limit={RECENT_LIMIT}") or []
    ex.dump("/api/tournaments/upcoming", f"days={TOURNAMENT_DAYS}")

    print("Teams")
    teams = (club or {}).get("teams", [])
    for team in teams:
        tid = team["team_id"]
        ex.dump(f"/api/teams/{tid}")
        ex.dump(f"/api/teams/{tid}/matches")
        ex.dump(f"/api/teams/{tid}/table")
        ex.dump(f"/api/teams/{tid}/stats")
    print(f"  {len(teams)} Teams")

    # Spieldetails nur fuer Partien, die die App auch verlinkt.
    print("Spieldetails")
    match_ids = {m["match_id"] for m in upcoming} | {m["match_id"] for m in recent}
    with db.session() as conn:
        for row in db.rows(
            conn,
            "SELECT DISTINCT m.match_id FROM matches m "
            "JOIN team_matches tm ON tm.match_id = m.match_id",
        ):
            match_ids.add(row["match_id"])
    for match_id in sorted(match_ids):
        ex.dump(f"/api/matches/{match_id}")
    print(f"  {len(match_ids)} Spiele")

    # Ein Zeitstempel, an dem die App erkennt, wie frisch die Daten sind.
    (OUT_DIR / "meta.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "club": config.CLUB_NAME,
                "season": config.SEASON,
                "files": ex.written + 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n{ex.written + 1} Dateien, {ex.bytes / 1024:.0f} KB -> {OUT_DIR}")
    print("Jetzt:  git add docs && git commit -m \"Daten aktualisiert\" && git push")


if __name__ == "__main__":
    export()

"""Holt die Daten aus dem Matchcenter in die lokale Datenbank.

Aufruf:

    python -m app.sync                # Verein + alle Teams
    python -m app.sync --details 20    # zusaetzlich 20 Spiel-Telegramme
    python -m app.sync --reset         # Datenbank vorher leeren

Der Sync ist bewusst langsam (Standard 6s zwischen zwei Requests). Das
Matchcenter antwortet bei schnelleren Zugriffen mit einer Bot-Pruefung, und
ein Verbandsserver ist kein CDN. Die App fragt nie direkt beim AFV an -
sie sieht nur diese Datenbank.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import datetime, timezone

from . import config, db
from .matchcenter import parsers as P
from .matchcenter.client import MatchcenterClient

log = logging.getLogger("sync")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_club_match(match: P.MatchRow) -> bool:
    needle = config.CLUB_MATCH_NAME.lower()
    return needle in match.home.lower() or needle in match.away.lower()


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


def _save_matches(conn: sqlite3.Connection, matches: list[P.MatchRow], group_id: int | None) -> int:
    saved = 0
    for m in matches:
        if m.match_id is None:
            continue  # Zeile ohne Telegramm-Link (z.B. abgesagt) - nicht referenzierbar
        conn.execute(
            """
            INSERT INTO matches (match_id, group_id, kickoff_date, kickoff_time, home, away,
                                 home_goals, away_goals, forfait, venue, competition, match_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                group_id     = COALESCE(excluded.group_id, matches.group_id),
                kickoff_date = COALESCE(excluded.kickoff_date, matches.kickoff_date),
                kickoff_time = COALESCE(excluded.kickoff_time, matches.kickoff_time),
                home         = excluded.home,
                away         = excluded.away,
                home_goals   = excluded.home_goals,
                away_goals   = excluded.away_goals,
                forfait      = excluded.forfait,
                -- Ortsangaben stehen nicht auf jeder Seite: vorhandene nicht ueberschreiben.
                venue        = CASE WHEN excluded.venue        != '' THEN excluded.venue        ELSE matches.venue        END,
                competition  = CASE WHEN excluded.competition  != '' THEN excluded.competition  ELSE matches.competition  END,
                match_number = CASE WHEN excluded.match_number != '' THEN excluded.match_number ELSE matches.match_number END
            """,
            (
                m.match_id, group_id, m.kickoff_date, m.kickoff_time, m.home, m.away,
                m.home_goals, m.away_goals, int(m.forfait), m.venue, m.competition, m.match_number,
            ),
        )
        saved += 1
    return saved


def _save_standings(conn: sqlite3.Connection, group_id: int, rows: list[P.StandingRow]) -> None:
    conn.execute("DELETE FROM standings WHERE group_id = ?", (group_id,))
    conn.executemany(
        """
        INSERT INTO standings (group_id, team, rank, played, won, drawn, lost,
                               goals_for, goals_against, goal_diff, points, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(group_id, team) DO NOTHING
        """,
        [
            (group_id, r.team, r.rank, r.played, r.won, r.drawn, r.lost,
             r.goals_for, r.goals_against, r.goal_diff, r.points, r.note)
            for r in rows
        ],
    )


def _save_scorers(conn: sqlite3.Connection, group_id: int, rows: list[P.ScorerRow]) -> None:
    conn.execute("DELETE FROM scorers WHERE group_id = ?", (group_id,))
    conn.executemany(
        "INSERT INTO scorers (group_id, player, team, goals) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(group_id, player, team) DO UPDATE SET goals = excluded.goals",
        [(group_id, r.player, r.team, r.goals) for r in rows],
    )


# ---------------------------------------------------------------------------
# Sync-Schritte
# ---------------------------------------------------------------------------


def sync_club(conn: sqlite3.Connection, client: MatchcenterClient) -> list[dict]:
    """Schritt 1: Welche Teams hat der Verein?"""
    html = client.club().html
    teams = P.parse_club_teams(html)
    log.info("Verein %s: %d Teams gefunden", config.CLUB_NAME, len(teams))
    for t in teams:
        conn.execute(
            """
            INSERT INTO teams (team_id, club_id, name, sort_order)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                name = excluded.name, sort_order = excluded.sort_order
            """,
            (t.team_id, config.CLUB_ID, t.name, t.sort_order),
        )
    conn.commit()
    return db.rows(conn, "SELECT * FROM teams ORDER BY sort_order")


def sync_team(conn: sqlite3.Connection, client: MatchcenterClient, team: dict) -> None:
    """Schritt 2: Liga, Tabelle, ganzer Spielplan und Torschuetzen eines Teams."""
    name = team["name"]

    # 2a) Team-Seite: Liganame, Gruppen-Ids, aktuelle Tabelle.
    html = client.team(team["team_id"]).html
    ref = P.parse_group_ref(html)
    league_name = P.parse_league_title(html)
    standings = P.parse_standings(html)

    conn.execute(
        "UPDATE teams SET league_name = ?, league_id = ?, season_id = ?, group_id = ?, synced_at = ? "
        "WHERE team_id = ?",
        (league_name, ref.league_id, ref.season_id, ref.group_id, _now(), team["team_id"]),
    )

    if not ref.complete:
        # Juniorenturniere ohne Rangliste haben keine Gruppen-Ids.
        log.info("  %-28s keine Gruppe (Turnierform) - nur Teamseite", name)
        _save_matches(conn, P.parse_matches(html), None)
        conn.commit()
        return

    group_id = ref.group_id
    if standings:
        _save_standings(conn, group_id, standings)

    # 2b) Ganzer Saison-Spielplan der Gruppe.
    schedule = P.parse_matches(client.schedule(ref.season_id, group_id).html)
    saved = _save_matches(conn, schedule, group_id)

    # 2c) Zuordnung Team -> Spiele des Vereins in dieser Gruppe.
    club_matches = [m for m in schedule if _is_club_match(m) and m.match_id]
    conn.executemany(
        "INSERT INTO team_matches (team_id, match_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
        [(team["team_id"], m.match_id) for m in club_matches],
    )

    # 2d) Torschuetzenliste (gibt es nicht in jeder Kategorie).
    scorers = P.parse_scorers(client.scorers(ref.season_id, group_id).html)
    if scorers:
        _save_scorers(conn, group_id, scorers)

    log.info(
        "  %-28s %-24s %2d Tabelle | %3d Spiele (%2d eigene) | %3d Torschuetzen",
        name, league_name[:24], len(standings), saved, len(club_matches), len(scorers),
    )
    conn.commit()


def sync_match_details(conn: sqlite3.Connection, client: MatchcenterClient, limit: int) -> int:
    """Schritt 3: Telegramme der eigenen, bereits gespielten Spiele nachladen.

    Nur Spiele des Vereins - alles andere waeren tausende Requests fuer Daten,
    die die App nie zeigt.
    """
    todo = db.rows(
        conn,
        """
        SELECT m.match_id FROM matches m
        JOIN team_matches tm ON tm.match_id = m.match_id
        WHERE m.home_goals IS NOT NULL
          AND (m.detail_synced_at IS NULL OR m.detail_synced_at = '')
        ORDER BY m.kickoff_date DESC
        LIMIT ?
        """,
        (limit,),
    )
    if not todo:
        return 0

    log.info("Telegramme: %d Spiele nachladen", len(todo))
    done = 0
    for item in todo:
        match_id = item["match_id"]
        # Abgeschlossene Spiele aendern sich nicht mehr - lange im Cache halten.
        html = client.telegram(match_id, ttl=config.CACHE_TTL_FINISHED).html
        head = P.parse_telegram_header(html)
        events = P.parse_telegram(html)

        conn.execute(
            """
            UPDATE matches SET
                halftime  = ?, home_logo = ?, away_logo = ?,
                venue     = CASE WHEN ? != '' THEN ? ELSE venue END,
                competition = CASE WHEN ? != '' THEN ? ELSE competition END,
                detail_synced_at = ?
            WHERE match_id = ?
            """,
            (head.halftime, head.home_logo, head.away_logo,
             head.venue, head.venue, head.competition, head.competition, _now(), match_id),
        )
        conn.execute("DELETE FROM match_events WHERE match_id = ?", (match_id,))
        conn.executemany(
            """
            INSERT INTO match_events (match_id, ord, minute, kind, team, player, player_id,
                                      player_in, player_in_id, score, label, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (match_id, e.order, e.minute, e.kind, e.team, e.player, e.player_id,
                 e.player_in, e.player_in_id, e.score, e.label, e.text)
                for e in events
            ],
        )
        conn.commit()
        done += 1
        log.info("  Spiel %s: %d Ereignisse", match_id, len(events))
    return done


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def run(*, details: int = 0, reset: bool = False, offline: bool = False) -> None:
    with db.session() as conn:
        if reset:
            for table in ("team_matches", "match_events", "matches", "standings", "scorers", "teams"):
                conn.execute(f"DELETE FROM {table}")
            log.info("Datenbank geleert")

        with MatchcenterClient(offline=offline) as client:
            teams = sync_club(conn, client)
            failed = 0
            for team in teams:
                # Ein einzelnes Team soll den ganzen Lauf nicht kippen: der
                # Sync ist wiederaufsetzbar, beim naechsten Mal wird nachgeholt.
                try:
                    sync_team(conn, client, team)
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    log.warning("  %-28s uebersprungen: %s", team["name"], exc)
            if failed:
                log.warning("%d von %d Teams uebersprungen", failed, len(teams))
            if details:
                try:
                    sync_match_details(conn, client, details)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Telegramme abgebrochen: %s", exc)

        db.set_meta(conn, "last_sync", _now())
        db.set_meta(conn, "club_name", config.CLUB_NAME)
        db.set_meta(conn, "season", str(config.SEASON))

        counts = {
            t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in ("teams", "matches", "team_matches", "standings", "scorers", "match_events")
        }
        log.info("Fertig: %s", ", ".join(f"{k}={v}" for k, v in counts.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description="AFV-Matchcenter in die lokale Datenbank spiegeln")
    ap.add_argument("--details", type=int, default=0, metavar="N",
                    help="zusaetzlich N Spiel-Telegramme laden (Tore, Karten, Wechsel)")
    ap.add_argument("--reset", action="store_true", help="Datenbank vorher leeren")
    ap.add_argument("--offline", action="store_true",
                    help="nur aus dem Cache lesen, keine Requests")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(details=args.details, reset=args.reset, offline=args.offline)


if __name__ == "__main__":
    main()

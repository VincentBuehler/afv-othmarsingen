"""JSON-API fuer die Handy-App.

Die API liest ausschliesslich aus der lokalen Datenbank. Sie stellt nie eine
Verbindung zum Matchcenter her - das macht nur der Sync (`python -m app.sync`).
Dadurch antwortet sie in Millisekunden und der Verbandsserver merkt nichts
davon, wie viele Leute die App benutzen.

Start:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, stats

app = FastAPI(
    title=f"{config.CLUB_NAME} - Matchcenter-API",
    description=(
        "Inoffizielle API rund um den " + config.CLUB_NAME + ". "
        "Datenquelle: Matchcenter des Aargauer Fussballverbands."
    ),
    version="1.0.0",
)

# Die App laeuft im Expo-Client unter wechselnden Ports - fuer ein
# Portfolio-Projekt ohne Anmeldung ist das unkritisch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


SOURCE_NOTE = {
    "quelle": "Matchcenter Aargauer Fussballverband (matchcenter.afv.ch)",
    "hinweis": "Inoffizielle App. Keine Gewaehr fuer Richtigkeit der Daten.",
}


# ---------------------------------------------------------------------------
# Allgemein
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["Allgemein"])
def health(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    counts = {
        t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        for t in ("teams", "matches", "standings", "scorers", "match_events", "tournaments")
    }
    return {
        "status": "ok",
        "club": config.CLUB_NAME,
        "season": config.SEASON,
        "last_sync": db.get_meta(conn, "last_sync"),
        "counts": counts,
        **SOURCE_NOTE,
    }


@app.get("/api/club", tags=["Verein"])
def club(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Stammdaten des Vereins mit allen Mannschaften."""
    teams = db.rows(
        conn,
        """
        SELECT t.*,
               (SELECT COUNT(*) FROM team_matches tm WHERE tm.team_id = t.team_id) AS match_count
        FROM teams t ORDER BY t.sort_order
        """,
    )
    return {
        "club_id": config.CLUB_ID,
        "name": config.CLUB_NAME,
        "season": config.SEASON,
        "last_sync": db.get_meta(conn, "last_sync"),
        "teams": teams,
        **SOURCE_NOTE,
    }


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


def _team_or_404(conn: sqlite3.Connection, team_id: int) -> dict:
    team = db.row(conn, "SELECT * FROM teams WHERE team_id = ?", (team_id,))
    if team is None:
        raise HTTPException(404, f"Team {team_id} nicht gefunden")
    return team


@app.get("/api/teams", tags=["Teams"])
def list_teams(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.rows(conn, "SELECT * FROM teams ORDER BY sort_order")


@app.get("/api/teams/{team_id}", tags=["Teams"])
def team_detail(team_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Alles zu einer Mannschaft: Liga, Tabellenplatz, Form, naechstes Spiel."""
    team = _team_or_404(conn, team_id)
    group_id = team["group_id"]

    standings = db.rows(
        conn, "SELECT * FROM standings WHERE group_id = ? ORDER BY rank", (group_id,)
    ) if group_id else []

    own_row = next(
        (r for r in standings if config.CLUB_MATCH_NAME.lower() in r["team"].lower()), None
    )
    upcoming = stats.team_matches(conn, team_id, played=False)
    played = stats.team_matches(conn, team_id, played=True)

    return {
        "team": team,
        "standings": standings,
        "position": own_row,
        "summary": stats.team_summary(conn, team_id),
        "next_match": upcoming[0] if upcoming else None,
        "last_match": played[-1] if played else None,
        "match_count": {"played": len(played), "upcoming": len(upcoming)},
        "tournaments": _tournaments(
            conn,
            "SELECT t.*, tm.name AS team_name FROM tournaments t "
            "LEFT JOIN teams tm ON tm.team_id = t.team_id "
            "WHERE t.team_id = ? ORDER BY t.date",
            (team_id,),
        ),
    }


def _tournaments(conn: sqlite3.Connection, sql: str, params: tuple) -> list[dict]:
    """Turniere laden und das JSON-Feld "teams" wieder zur Liste machen."""
    rows = db.rows(conn, sql, params)
    for r in rows:
        try:
            r["teams"] = json.loads(r["teams"])
        except (json.JSONDecodeError, TypeError):
            r["teams"] = []
    return rows


@app.get("/api/tournaments/upcoming", tags=["Spiele"])
def upcoming_tournaments(
    days: int = Query(30, ge=1, le=400),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """Kommende Turniere im Kinderfussball (Junioren E/F/G)."""
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=days)).isoformat()
    return _tournaments(
        conn,
        """
        SELECT t.*, tm.name AS team_name FROM tournaments t
        LEFT JOIN teams tm ON tm.team_id = t.team_id
        WHERE t.date BETWEEN ? AND ?
        ORDER BY t.date, t.time
        """,
        (today, until),
    )


@app.get("/api/teams/{team_id}/matches", tags=["Teams"])
def team_matches(
    team_id: int,
    played: bool | None = Query(None, description="true = nur gespielt, false = nur kommend"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    _team_or_404(conn, team_id)
    return stats.team_matches(conn, team_id, played=played)


@app.get("/api/teams/{team_id}/table", tags=["Teams"])
def team_table(team_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    team = _team_or_404(conn, team_id)
    if not team["group_id"]:
        return {"league_name": team["league_name"], "rows": [],
                "hinweis": "Diese Kategorie wird ohne Rangliste gespielt."}
    return {
        "league_name": team["league_name"],
        "rows": db.rows(
            conn, "SELECT * FROM standings WHERE group_id = ? ORDER BY rank", (team["group_id"],)
        ),
    }


@app.get("/api/teams/{team_id}/stats", tags=["Statistik"])
def team_stats(team_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Statistik einer Mannschaft - inklusive dem, was der Verband nicht anbietet."""
    team = _team_or_404(conn, team_id)
    group_id = team["group_id"]
    return {
        "team": team,
        "summary": stats.team_summary(conn, team_id),
        "goal_minutes": stats.goal_minutes(conn, team_id),
        "players": stats.club_players(conn, team_id),
        "league_scorers": db.rows(
            conn,
            "SELECT * FROM scorers WHERE group_id = ? ORDER BY goals DESC, player LIMIT 30",
            (group_id,),
        ) if group_id else [],
        "fairplay": stats.fairplay(conn, group_id) if group_id else [],
    }


# ---------------------------------------------------------------------------
# Spiele
# ---------------------------------------------------------------------------


@app.get("/api/matches/upcoming", tags=["Spiele"])
def upcoming(
    days: int = Query(14, ge=1, le=400),
    club_only: bool = Query(True, description="nur Spiele des eigenen Vereins"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=days)).isoformat()
    join = "JOIN team_matches tm ON tm.match_id = m.match_id" if club_only else ""
    return db.rows(
        conn,
        f"""
        SELECT DISTINCT m.*, t.name AS team_name, t.team_id
        FROM matches m
        {join}
        LEFT JOIN teams t ON t.team_id = {"tm.team_id" if club_only else "NULL"}
        WHERE m.kickoff_date BETWEEN ? AND ? AND m.home_goals IS NULL
        ORDER BY m.kickoff_date, m.kickoff_time
        """,
        (today, until),
    )


@app.get("/api/matches/recent", tags=["Spiele"])
def recent(
    limit: int = Query(20, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """Die letzten Resultate des Vereins, ueber alle Mannschaften."""
    return db.rows(
        conn,
        """
        SELECT DISTINCT m.*, t.name AS team_name, t.team_id
        FROM matches m
        JOIN team_matches tm ON tm.match_id = m.match_id
        JOIN teams t ON t.team_id = tm.team_id
        WHERE m.home_goals IS NOT NULL
        ORDER BY m.kickoff_date DESC, m.kickoff_time DESC
        LIMIT ?
        """,
        (limit,),
    )


@app.get("/api/matches/{match_id}", tags=["Spiele"])
def match_detail(match_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Spieldetail mit Telegramm: Tore, Karten, Wechsel."""
    match = db.row(conn, "SELECT * FROM matches WHERE match_id = ?", (match_id,))
    if match is None:
        raise HTTPException(404, f"Spiel {match_id} nicht gefunden")

    events = db.rows(
        conn,
        "SELECT * FROM match_events WHERE match_id = ? ORDER BY ord",
        (match_id,),
    )
    return {
        "match": match,
        "events": events,
        "has_details": bool(match["detail_synced_at"]),
        "hinweis": None if events else "Telegramm noch nicht geladen (python -m app.sync --details N).",
    }


# ---------------------------------------------------------------------------
# Statistik ueber den ganzen Verein
# ---------------------------------------------------------------------------


@app.get("/api/stats/players", tags=["Statistik"])
def club_players(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    """Torschuetzen und Karten aller Vereinsspieler, aus den Telegrammen."""
    return stats.club_players(conn)


@app.get("/api/stats/head-to-head", tags=["Statistik"])
def head_to_head(
    opponent: str = Query(..., min_length=2, description="Name des Gegners"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return stats.head_to_head(conn, opponent)


@app.get("/api/stats/overview", tags=["Statistik"])
def overview(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Zahlen fuer den Startbildschirm der App."""
    teams = db.rows(conn, "SELECT * FROM teams ORDER BY sort_order")
    total = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
    per_team: list[dict[str, Any]] = []

    for t in teams:
        summary = stats.team_summary(conn, t["team_id"])
        for key in total:
            total[key] += summary["total"][key]
        position = db.row(
            conn,
            "SELECT rank, points, played FROM standings "
            "WHERE group_id = ? AND LOWER(team) LIKE '%' || ? || '%'",
            (t["group_id"], config.CLUB_MATCH_NAME.lower()),
        ) if t["group_id"] else None
        per_team.append({
            "team_id": t["team_id"],
            "name": t["name"],
            "league_name": t["league_name"],
            "position": position,
            "form_string": summary["form_string"],
            "summary": summary["total"],
        })

    total["goal_diff"] = total["goals_for"] - total["goals_against"]
    return {
        "club": config.CLUB_NAME,
        "season": config.SEASON,
        "last_sync": db.get_meta(conn, "last_sync"),
        "total": total,
        "teams": per_team,
        **SOURCE_NOTE,
    }

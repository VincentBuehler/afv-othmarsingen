"""Statistiken, die das Matchcenter selbst nicht anbietet.

Die Rangliste und die Torschuetzenliste kommen fertig vom Verband. Alles hier
wird aus den gespiegelten Spielen und Telegramm-Ereignissen berechnet:
Formkurve, Heim-/Auswaertsbilanz, Tore nach Spielabschnitt, Kartenstatistik.
"""
from __future__ import annotations

import sqlite3
from collections import Counter

from . import config, db


def _club_side(match: dict, club: str | None = None) -> str:
    """Steht der Verein zu Hause oder auswaerts?"""
    club = (club or config.CLUB_MATCH_NAME).lower()
    if club in match["home"].lower():
        return "home"
    if club in match["away"].lower():
        return "away"
    return ""


def result_for(match: dict, side: str) -> str | None:
    """W / D / L aus Sicht der angegebenen Seite."""
    if match["home_goals"] is None or match["away_goals"] is None or not side:
        return None
    own = match["home_goals"] if side == "home" else match["away_goals"]
    other = match["away_goals"] if side == "home" else match["home_goals"]
    if own > other:
        return "W"
    if own < other:
        return "L"
    return "D"


def team_matches(conn: sqlite3.Connection, team_id: int, *, played: bool | None = None) -> list[dict]:
    where = ""
    if played is True:
        where = "AND m.home_goals IS NOT NULL"
    elif played is False:
        where = "AND m.home_goals IS NULL"
    return db.rows(
        conn,
        f"""
        SELECT m.* FROM matches m
        JOIN team_matches tm ON tm.match_id = m.match_id
        WHERE tm.team_id = ? {where}
        ORDER BY m.kickoff_date, m.kickoff_time
        """,
        (team_id,),
    )


def team_summary(conn: sqlite3.Connection, team_id: int, *, form_length: int = 5) -> dict:
    """Bilanz eines Teams: Form, Heim/Auswaerts, Tore, Serien."""
    played = team_matches(conn, team_id, played=True)

    tally = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
    home = dict(tally)
    away = dict(tally)
    form: list[dict] = []

    for m in played:
        side = _club_side(m)
        res = result_for(m, side)
        if res is None:
            continue
        own = m["home_goals"] if side == "home" else m["away_goals"]
        other = m["away_goals"] if side == "home" else m["home_goals"]

        for bucket in (tally, home if side == "home" else away):
            bucket["played"] += 1
            bucket["goals_for"] += own
            bucket["goals_against"] += other
            bucket["won" if res == "W" else "lost" if res == "L" else "drawn"] += 1

        form.append({
            "match_id": m["match_id"],
            "date": m["kickoff_date"],
            "opponent": m["away"] if side == "home" else m["home"],
            "side": side,
            "score": f"{own}:{other}",
            "result": res,
        })

    for bucket in (tally, home, away):
        bucket["points"] = bucket["won"] * 3 + bucket["drawn"]
        bucket["goal_diff"] = bucket["goals_for"] - bucket["goals_against"]

    recent = form[-form_length:][::-1]  # neuestes zuerst
    return {
        "total": tally,
        "home": home,
        "away": away,
        "form": recent,
        "form_string": "".join(f["result"] for f in reversed(recent)),
        "streak": _streak(form),
    }


def _streak(form: list[dict]) -> dict:
    """Aktuelle Serie, z.B. 3 Siege in Folge."""
    if not form:
        return {"kind": "", "count": 0}
    last = form[-1]["result"]
    count = 0
    for f in reversed(form):
        if f["result"] != last:
            break
        count += 1
    return {"kind": last, "count": count}


def goal_minutes(conn: sqlite3.Connection, team_id: int) -> dict:
    """Wann fallen die Tore? Nur aus Spielen mit geladenem Telegramm."""
    buckets = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
    scored = Counter()
    conceded = Counter()
    club = config.CLUB_MATCH_NAME.lower()

    events = db.rows(
        conn,
        """
        SELECT e.minute, e.team FROM match_events e
        JOIN team_matches tm ON tm.match_id = e.match_id
        WHERE tm.team_id = ? AND e.kind = 'goal' AND e.minute IS NOT NULL
        """,
        (team_id,),
    )
    for e in events:
        idx = min((max(e["minute"], 1) - 1) // 15, 5)
        target = scored if club in e["team"].lower() else conceded
        target[buckets[idx]] += 1

    return {
        "buckets": buckets,
        "scored": [scored[b] for b in buckets],
        "conceded": [conceded[b] for b in buckets],
        "sample_size": len({m["match_id"] for m in db.rows(
            conn,
            "SELECT DISTINCT e.match_id FROM match_events e "
            "JOIN team_matches tm ON tm.match_id = e.match_id WHERE tm.team_id = ?",
            (team_id,),
        )}),
    }


def club_players(conn: sqlite3.Connection, team_id: int | None = None) -> list[dict]:
    """Spieler des Vereins aus den Telegrammen: Tore und Karten.

    Gruppiert wird ueber player_id (die Rollen-Id des Verbands) - damit zaehlen
    zwei Spieler mit gleichem Namen nicht zusammen.
    """
    scope = "AND tm.team_id = ?" if team_id else ""
    params: tuple = (config.CLUB_MATCH_NAME.lower(),)
    if team_id:
        params = params + (team_id,)

    rows = db.rows(
        conn,
        f"""
        SELECT e.player, e.player_id, e.kind, COUNT(*) AS n
        FROM match_events e
        JOIN team_matches tm ON tm.match_id = e.match_id
        WHERE LOWER(e.team) LIKE '%' || ? || '%'
          AND e.kind IN ('goal', 'yellow_card', 'second_yellow', 'red_card')
          AND e.player != ''
          {scope}
        GROUP BY e.player_id, e.player, e.kind
        """,
        params,
    )

    players: dict = {}
    for r in rows:
        key = r["player_id"] or r["player"]
        p = players.setdefault(key, {
            "player": r["player"], "player_id": r["player_id"],
            "goals": 0, "yellow_cards": 0, "second_yellows": 0, "red_cards": 0,
        })
        field = {
            "goal": "goals", "yellow_card": "yellow_cards",
            "second_yellow": "second_yellows", "red_card": "red_cards",
        }[r["kind"]]
        p[field] += r["n"]

    result = sorted(players.values(), key=lambda p: (-p["goals"], p["player"]))
    return result


def head_to_head(conn: sqlite3.Connection, opponent: str, club: str | None = None) -> dict:
    """Direktvergleich des Vereins gegen einen Gegner ueber alle gespiegelten Spiele."""
    club = club or config.CLUB_MATCH_NAME
    matches = db.rows(
        conn,
        """
        SELECT * FROM matches
        WHERE home_goals IS NOT NULL
          AND ( (LOWER(home) LIKE '%'||LOWER(?)||'%' AND LOWER(away) LIKE '%'||LOWER(?)||'%')
             OR (LOWER(away) LIKE '%'||LOWER(?)||'%' AND LOWER(home) LIKE '%'||LOWER(?)||'%') )
        ORDER BY kickoff_date DESC
        """,
        (club, opponent, club, opponent),
    )
    won = drawn = lost = 0
    for m in matches:
        res = result_for(m, _club_side(m, club))
        won += res == "W"
        drawn += res == "D"
        lost += res == "L"
    return {
        "opponent": opponent,
        "matches": matches,
        "won": won, "drawn": drawn, "lost": lost,
    }


def fairplay(conn: sqlite3.Connection, group_id: int) -> list[dict]:
    """Kartenstatistik pro Team einer Gruppe - nur aus geladenen Telegrammen."""
    rows = db.rows(
        conn,
        """
        SELECT e.team, e.kind, COUNT(*) AS n
        FROM match_events e
        JOIN matches m ON m.match_id = e.match_id
        WHERE m.group_id = ? AND e.kind IN ('yellow_card', 'second_yellow', 'red_card')
        GROUP BY e.team, e.kind
        """,
        (group_id,),
    )
    teams: dict = {}
    for r in rows:
        t = teams.setdefault(r["team"], {
            "team": r["team"], "yellow_cards": 0, "second_yellows": 0, "red_cards": 0,
        })
        t[{"yellow_card": "yellow_cards", "second_yellow": "second_yellows",
           "red_card": "red_cards"}[r["kind"]]] += r["n"]
    for t in teams.values():
        # Fairplay-Punkte nach gaengiger Gewichtung: gelb 1, gelb-rot 3, rot 5.
        t["points"] = t["yellow_cards"] + t["second_yellows"] * 3 + t["red_cards"] * 5
    return sorted(teams.values(), key=lambda t: t["points"])

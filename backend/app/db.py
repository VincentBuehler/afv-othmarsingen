"""SQLite-Zugriff und Schema.

Die Datenbank ist bewusst ein reiner Spiegel des Matchcenters: der Sync
schreibt rein, die API liest nur. Dadurch ist ein kompletter Neuaufbau
jederzeit gefahrlos moeglich (`python -m app.sync --reset`).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Ein Team = eine Mannschaft des Vereins (z.B. "3. Liga", "Junioren E rot").
CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY,
    club_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    league_name TEXT    NOT NULL DEFAULT '',
    league_id   INTEGER,
    season_id   INTEGER,          -- ls
    group_id    INTEGER,          -- sg
    synced_at   TEXT
);

-- Tabellenstand einer Gruppe.
CREATE TABLE IF NOT EXISTS standings (
    group_id      INTEGER NOT NULL,
    team          TEXT    NOT NULL,
    rank          INTEGER,
    played        INTEGER,
    won           INTEGER,
    drawn         INTEGER,
    lost          INTEGER,
    goals_for     INTEGER,
    goals_against INTEGER,
    goal_diff     INTEGER,
    points        INTEGER,
    note          TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (group_id, team)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id         INTEGER PRIMARY KEY,
    group_id         INTEGER,
    kickoff_date     TEXT,
    kickoff_time     TEXT,
    home             TEXT NOT NULL,
    away             TEXT NOT NULL,
    home_goals       INTEGER,
    away_goals       INTEGER,
    halftime         TEXT NOT NULL DEFAULT '',
    forfait          INTEGER NOT NULL DEFAULT 0,
    venue            TEXT NOT NULL DEFAULT '',
    competition      TEXT NOT NULL DEFAULT '',
    match_number     TEXT NOT NULL DEFAULT '',
    home_logo        TEXT NOT NULL DEFAULT '',
    away_logo        TEXT NOT NULL DEFAULT '',
    detail_synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_date  ON matches (kickoff_date);
CREATE INDEX IF NOT EXISTS idx_matches_group ON matches (group_id);

-- Welches Vereinsteam spielt in welchem Spiel? (Alle Teams heissen in der
-- Paarung "FC Othmarsingen" - erst die Gruppe macht sie unterscheidbar.)
CREATE TABLE IF NOT EXISTS team_matches (
    team_id  INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    PRIMARY KEY (team_id, match_id)
);

-- Ereignisse aus dem Spiel-Telegramm.
CREATE TABLE IF NOT EXISTS match_events (
    match_id     INTEGER NOT NULL,
    ord          INTEGER NOT NULL,
    minute       INTEGER,
    kind         TEXT NOT NULL,
    team         TEXT NOT NULL DEFAULT '',
    player       TEXT NOT NULL DEFAULT '',
    player_id    INTEGER,
    player_in    TEXT NOT NULL DEFAULT '',
    player_in_id INTEGER,
    score        TEXT NOT NULL DEFAULT '',
    label        TEXT NOT NULL DEFAULT '',
    text         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (match_id, ord)
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON match_events (kind);

-- Offizielle Torschuetzenliste des Verbands, pro Gruppe.
CREATE TABLE IF NOT EXISTS scorers (
    group_id INTEGER NOT NULL,
    player   TEXT    NOT NULL,
    team     TEXT    NOT NULL,
    goals    INTEGER NOT NULL,
    PRIMARY KEY (group_id, player, team)
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None

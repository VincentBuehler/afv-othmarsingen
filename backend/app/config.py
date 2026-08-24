"""Zentrale Konfiguration des Backends.

Alle Werte lassen sich per Umgebungsvariable ueberschreiben, damit die App
spaeter ohne Codeaenderung auf einen anderen Verein oder Verband zeigen kann.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Datenquelle -----------------------------------------------------------
# Das Matchcenter des SFV. oid=5 ist der Aargauer Fussballverband.
MATCHCENTER_URL = os.getenv("AFV_MATCHCENTER_URL", "https://matchcenter.afv.ch/default.aspx")
ORG_ID = int(os.getenv("AFV_ORG_ID", "5"))
LANG_ID = int(os.getenv("AFV_LANG_ID", "1"))  # 1 = Deutsch

# Saison im Matchcenter: die Saison 2026/27 laeuft dort unter "2027".
SEASON = int(os.getenv("AFV_SEASON", "2027"))

# --- Der Verein, um den sich die App dreht ---------------------------------
CLUB_ID = int(os.getenv("AFV_CLUB_ID", "269"))
CLUB_NAME = os.getenv("AFV_CLUB_NAME", "FC Othmarsingen")
# Wie der Verein in Spielpaarungen geschrieben wird (fuer "spielt mein Team?").
CLUB_MATCH_NAME = os.getenv("AFV_CLUB_MATCH_NAME", "Othmarsingen")

# --- HTTP ------------------------------------------------------------------
# Der User-Agent nennt bewusst Projekt und Zweck, damit man beim AFV sieht,
# wer da anfragt. Die Kontaktadresse kommt aus der Umgebung, damit sie nicht
# im oeffentlichen Repository steht - setze AFV_CONTACT in deiner .env.
CONTACT = os.getenv("AFV_CONTACT", "")
USER_AGENT = os.getenv(
    "AFV_USER_AGENT",
    f"FCOthmarsingenApp/1.0 (inoffizielle Vereins-App, Portfolio-Projekt{'; Kontakt: ' + CONTACT if CONTACT else ''})",
)
# Mindestabstand zwischen zwei Requests in Sekunden. Bewusst defensiv:
# das Matchcenter ist ein kleiner Verbandsserver, kein CDN.
REQUEST_DELAY = float(os.getenv("AFV_REQUEST_DELAY", "6.0"))
REQUEST_TIMEOUT = float(os.getenv("AFV_REQUEST_TIMEOUT", "20"))

# --- Cache & Datenbank -----------------------------------------------------
DATA_DIR = Path(os.getenv("AFV_DATA_DIR", BASE_DIR / "data"))
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = Path(os.getenv("AFV_DB_PATH", DATA_DIR / "afv.sqlite3"))

# Wie lange eine heruntergeladene Seite als frisch gilt (Sekunden).
CACHE_TTL_DEFAULT = int(os.getenv("AFV_CACHE_TTL", "600"))       # 10 Minuten
CACHE_TTL_FINISHED = int(os.getenv("AFV_CACHE_TTL_FINISHED", "604800"))  # 7 Tage

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- HTTP-Transport --------------------------------------------------------
# "auto" (Standard) nimmt curl, wenn vorhanden - siehe Kommentar in
# matchcenter/client.py, warum das noetig ist. "httpx" oder "curl" erzwingen.
HTTP_BACKEND = os.getenv("AFV_HTTP_BACKEND", "auto")

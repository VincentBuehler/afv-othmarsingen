"""Legt bereits heruntergeladene Matchcenter-Seiten in den Client-Cache.

Damit laesst sich die ganze Pipeline (Parsen -> Datenbank -> API) offline
durchspielen, ohne den Verbandsserver auch nur einmal anzufragen:

    python -m tools.seed_cache seiten/
    python -m app.sync --offline

Erwartet wird eine Datei `index.json` neben den HTML-Dateien:

    { "oth.html": {"v": 269}, "team.html": {"v": 269, "t": 30201, "a": "trr"} }
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.matchcenter.client import MatchcenterClient  # noqa: E402


def seed(folder: Path) -> int:
    index_path = folder / "index.json"
    if not index_path.exists():
        raise SystemExit(f"Keine index.json in {folder}")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    client = MatchcenterClient()
    count = 0

    for filename, params in index.items():
        path = folder / filename
        if not path.exists():
            print(f"  fehlt: {filename}")
            continue
        full = {"oid": config.ORG_ID, "lng": config.LANG_ID, **params}
        url = f"{config.MATCHCENTER_URL}?{urlencode(full)}"
        html = path.read_bytes().decode("utf-8", errors="replace")
        client._write_cache(url, html)  # noqa: SLF001 - Dev-Werkzeug
        print(f"  {filename:<16} -> {url}")
        count += 1

    client.close()
    return count


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "seiten")
    print(f"Cache befuellen aus {folder.resolve()}")
    n = seed(folder)
    print(f"{n} Seiten im Cache. Jetzt: python -m app.sync --offline")

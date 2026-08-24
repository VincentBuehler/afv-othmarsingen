# FC Othmarsingen — Resultate & Statistiken

Eine Handy-App für den FC Othmarsingen: Resultate, Tabellen und Statistiken aller
14 Mannschaften, gezogen aus dem Matchcenter des Aargauer Fussballverbands.

> **Inoffizielles Projekt.** Nicht vom FC Othmarsingen oder vom AFV beauftragt
> oder autorisiert. Alle Daten stammen vom AFV, keine Gewähr für Richtigkeit.

---

## Was die App kann

| | |
|---|---|
| **Übersicht** | Nächste Spiele, letzte Resultate und der Stand aller 14 Mannschaften auf einem Bildschirm |
| **Spiele** | Kompletter Spielplan und alle Resultate des Vereins, nach Datum gruppiert |
| **Spieldetail** | Der ganze Verlauf: Tore mit Torschütze und Minute, Karten, Ein- und Auswechslungen |
| **Tabelle** | Rangliste der Liga, die eigene Mannschaft hervorgehoben |
| **Statistik** | Formkurve, Heim-/Auswärtsvergleich, Torminuten-Verteilung, Torschützen, Fairplay |
| **Turniere** | Termine der Junioren E/F/G, die nach «play more football» ohne Resultate spielen |

Der Verband selbst bietet Tabelle, Spielplan und eine Torschützenliste. **Formkurve,
Heim-/Auswärtsanalyse, Torminuten und die vereinsweite Spielerstatistik gibt es dort
nicht** — die rechnet dieses Projekt aus den gespiegelten Spieldaten.

---

## Aufbau

```
┌──────────────────┐   3 Requests/Team    ┌──────────────────────┐
│  matchcenter     │◄─────────────────────│  Sync (Python)       │
│  .afv.ch         │   6s Pause, Cache    │  scraped & parst     │
└──────────────────┘                      └──────────┬───────────┘
                                                     │ schreibt
                                          ┌──────────▼───────────┐
┌──────────────────┐    JSON, lokal       │  SQLite              │
│  App (Expo/RN)   │◄─────────────────────│  + FastAPI           │
│  iPhone/Android  │                      │                      │
└──────────────────┘                      └──────────────────────┘
```

Die App spricht **nie** direkt mit dem AFV. Der Sync läuft als eigener Prozess und
legt alles in SQLite ab; die API liest nur daraus. Egal wie viele Leute die App
benutzen — beim Verband kommt immer nur der eine, langsame Sync an.

---

## Die Datenquelle

Das Matchcenter hat keine offizielle API, aber server-gerendertes HTML mit stabilen
URL-Parametern und sprechenden CSS-Klassen:

| URL | Inhalt |
|---|---|
| `default.aspx?oid=5&v=269` | Vereinsseite → alle Mannschaften (`t=`) |
| `default.aspx?oid=5&v=269&t=30201&a=trr` | Team: Liga, Rangliste, Gruppen-Ids (`ls`/`sg`) |
| `default.aspx?oid=5&ls=25788&sg=70224&a=msp` | Kompletter Saison-Spielplan der Gruppe |
| `default.aspx?oid=5&ls=25788&sg=70224&a=mtg` | Offizielle Torschützenliste |
| `default.aspx?oid=5&tg=4322039` | Telegramm: Tore, Karten, Wechsel mit Minute |

`oid=5` = AFV · `v=269` = FC Othmarsingen (Vereinsnummer 1033)

Geparst wird über CSS-Klassen (`ranCrang`, `ranCteam`, `ranCpt`, `.row.spiel`,
`ul.bnEventsList > li[data-eid]`), nicht über Spaltenpositionen — das überlebt ein
Redesign eher.

Im Telegramm ist `data-rid` eine stabile Spieler-Id. Dadurch werden zwei Spieler mit
gleichem Namen in der Statistik nicht zusammengezählt.

---

## Fairer Umgang mit dem Verbandsserver

Das war der aufwendigste Teil des Projekts und ist bewusst so gelöst:

* **6 Sekunden Pause** zwischen zwei Requests, fest eingebaut.
* **Disk-Cache** mit TTL: abgeschlossene Spiele werden 7 Tage nicht neu geladen.
* **Ein voller Sync sind ~45 Requests** für den ganzen Verein — einmal täglich reicht.
* **Ehrlicher User-Agent** mit Projektname und Kontaktadresse.
* `robots.txt` des Matchcenters erlaubt `User-agent: * → Allow: /`.

**Cloudflare-Hinweis:** Der Server blockt Python-HTTP-Clients (httpx, requests,
urllib) am TLS-Fingerprint mit HTTP 403 — unabhängig von Tempo und User-Agent.
Deshalb läuft der Transport über `curl` (siehe `backend/app/matchcenter/client.py`).
Es wird **kein** Browser vorgetäuscht, keine JS-Challenge gelöst und keine
TLS-Impersonation verwendet. Sollte der AFV signalisieren, dass ihm das nicht recht
ist, gehört dort ein Schalter auf „aus" — kein weiterer Trick hinein.

---

## Starten

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
python -m app.sync --details 30
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` ist wichtig: sonst erreicht das iPhone den Laptop nicht.
API-Dokumentation läuft dann unter <http://localhost:8000/docs>.

### App

```bash
cd mobile
npm install
npx expo start
```

QR-Code mit der Kamera scannen, [Expo Go](https://expo.dev/go) öffnet die App auf
dem iPhone. Die Backend-Adresse leitet die App automatisch aus dem Expo-Dev-Server
ab — im gleichen WLAN muss nichts konfiguriert werden.

### Ohne Netz entwickeln

```bash
python -m tools.seed_cache seiten   # gespeicherte Seiten in den Cache
python -m app.sync --offline        # Pipeline ohne einen einzigen Request
```

---

## Konfiguration

Alles über Umgebungsvariablen, kein Code-Eingriff nötig:

| Variable | Standard | Bedeutung |
|---|---|---|
| `AFV_CONTACT` | – | Kontaktadresse für den User-Agent (siehe `backend/.env.example`) |
| `AFV_CLUB_ID` | `269` | Vereins-Id im Matchcenter |
| `AFV_CLUB_NAME` | `FC Othmarsingen` | Anzeigename |
| `AFV_CLUB_MATCH_NAME` | `Othmarsingen` | Wie der Verein in Paarungen steht |
| `AFV_ORG_ID` | `5` | Verband (5 = AFV) |
| `AFV_SEASON` | `2027` | Saison 2026/27 |
| `AFV_REQUEST_DELAY` | `6.0` | Sekunden zwischen zwei Requests |
| `AFV_HTTP_BACKEND` | `auto` | `curl`, `httpx` oder `auto` |

Für einen anderen Verein reicht also `AFV_CLUB_ID` und `AFV_CLUB_NAME`.

---

## Technisch gelöste Knackpunkte

**Zwei Mannschaften in derselben Gruppe.** Die Junioren D-7 a und b spielen in der
gleichen Gruppe und heissen beide „FC Othmarsingen" — mit Suffix „a" bzw. „b" in der
Paarung. Ohne Auflösung bekämen beide identische (und falsche) Statistiken.
`map_team_matches()` verbindet Teamname und Paarung über dieses Kürzel.

**Drei verschiedene Datenformen.** Meisterschaft (Rangliste + Paarungen), Cup
(Paarungen ohne Rangliste) und Kinderfussball (Turniere ohne Resultat) sehen im HTML
unterschiedlich aus. Alle drei werden erkannt und getrennt dargestellt — statt für
die Junioren E/F/G leere Tabellen zu zeigen.

**Wiederaufsetzbarer Sync.** Ein Team, das der Server gerade nicht ausliefert, kippt
nicht den ganzen Lauf: der Sync überspringt es, loggt das und holt es beim nächsten
Mal nach.

---

## Stack

Python 3.11 · FastAPI · SQLite · BeautifulSoup + lxml ·
React Native (Expo SDK 57) · TypeScript · React Navigation

## Datenquelle

Aargauer Fussballverband — <https://matchcenter.afv.ch>

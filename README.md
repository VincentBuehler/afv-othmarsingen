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
                                          │  SQLite   + FastAPI  │
                                          └──────────┬───────────┘
                                        export_static │
                                          ┌──────────▼───────────┐
┌──────────────────┐   statisches JSON    │  docs/api/*.json     │
│  App (Expo/RN)   │◄─────────────────────│  auf GitHub Pages    │
│  iPhone/Android  │                      └──────────────────────┘
└──────────────────┘
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

**SDK-Version:** Das Projekt liegt bewusst auf **Expo SDK 54**, weil Expo Go immer nur
genau eine SDK-Version unterstützt und auf älteren iPhones keine neuere Expo-Go-App
installierbar ist. Wer eine aktuellere Expo-Go-Version hat, kann mit
`npx expo install expo@^57.0.0` und `npx expo install --fix` hochziehen.

**Firewall unter Windows:** iPhone und Laptop müssen im selben WLAN sein, und die Ports
8081 (Metro) und 8000 (Backend) müssen eingehend erlaubt sein. Wurde die Windows-Abfrage
einmal mit „Abbrechen" beantwortet, legt Windows eine dauerhafte *Block*-Regel an, die
man von Hand entfernen muss.

### Ohne Netz entwickeln

```bash
python -m tools.seed_cache seiten   # gespeicherte Seiten in den Cache
python -m app.sync --offline        # Pipeline ohne einen einzigen Request
```

---

## Veröffentlichen

Die App soll ohne laufenden Laptop funktionieren. Beide Hälften gehen dafür getrennte Wege.

### Daten → GitHub Pages

Ein Server wäre hier Verschwendung: Die Daten ändern sich ein paar Mal pro Woche, und
jeder Aufruf der App ist ein reines GET ohne Parameter. Also friert der Export den Stand
als statische Dateien ein.

```bash
cd backend
python -m app.sync --details 40      # frische Daten holen
python -m tools.export_static        # nach docs/api/*.json schreiben
cd .. && git add docs && git commit -m "Daten aktualisiert" && git push
```

Ergebnis: rund 150 Dateien, ~200 KB, ausgeliefert unter
`https://<user>.github.io/afv-othmarsingen/api/`. Kostenlos, ohne Kaltstart, kann nicht
ausfallen.

**Warum kein Render oder Fly.io?** Auf deren Gratis-Stufen ist die Festplatte flüchtig —
die SQLite-Datenbank wäre nach jedem Neustart weg. Und der Scraper liefe aus einem
Rechenzentrum, wo Cloudflare zuverlässig blockt; von einem Wohnanschluss aus geht er durch.
Der Sync gehört deshalb auf den eigenen Rechner.

### App-Code → EAS Update

```bash
npm install --global eas-cli
cd mobile
eas login                            # kostenloser Expo-Account
eas update:configure
eas update --branch production --message "Erste Version" --environment production
```

Danach erscheint das Projekt in Expo Go unter *Projects* und lässt sich ohne laufenden
Dev-Server öffnen. Zwei Bedingungen:

* In Expo Go muss **derselbe Account** eingeloggt sein, dem das Projekt gehört — seit
  Mai 2026 lädt Expo Go nur noch eigene Projekte.
* In `app.json` darf **kein `runtimeVersion`** stehen. Setzt `eas update:configure` eines,
  muss es wieder raus, sonst verweigert Expo Go das Laden.

Die Adresse der Daten-API kommt aus `eas.json` (`updates.production.env`) und landet beim
Build im Bundle. Beim lokalen Entwickeln ist sie nicht gesetzt, dann sucht sich die App
das FastAPI-Backend im WLAN — siehe `mobile/src/api.ts`.

### Alternative: als Web-App

```bash
cd mobile && npx expo export --platform web --output-dir ../docs/app
```

Dann liegt die App neben den Daten auf GitHub Pages, lässt sich per Link teilen und über
Safaris «Zum Home-Bildschirm» wie eine App installieren — ohne Expo Go und ohne
Apple-Developer-Account.

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
React Native (Expo SDK 54) · TypeScript · React Navigation

## Datenquelle

Aargauer Fussballverband — <https://matchcenter.afv.ch>

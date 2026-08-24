"""Parser fuer die HTML-Seiten des Matchcenters.

Das Matchcenter rendert serverseitig und vergibt sprechende CSS-Klassen.
Darauf stuetzen sich die Parser hier - nicht auf Spaltenpositionen, die sich
mit dem naechsten Redesign verschieben wuerden.

    Rangliste : table.nisRanglisteRD  ->  td.ranCrang / .ranCteam / .ranCpt ...
    Spiele    : div.row.spiel         ->  .teamA / .teamB / .torA / .torB
    Telegramm : ul.bnEventsList > li[data-eid]
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

# --- Ereignistypen im Telegramm -------------------------------------------
# data-eid ist der Code des Verbands, das Icon ist die verlaesslichere Quelle.
EVENT_KIND_BY_ICON = {
    "tor": "goal",
    "gelb": "yellow_card",
    "gelbrot": "second_yellow",
    "rot": "red_card",
    "out_in": "substitution",
}
EVENT_KIND_BY_EID = {
    1: "goal",
    2: "substitution",
    3: "yellow_card",
    4: "second_yellow",
    5: "red_card",
}

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_MINUTE_RE = re.compile(r"(\d+)")
_SCORER_RE = re.compile(r"Torsch(?:ü|ue)tze[n]?\s+(.+)", re.I)
_CARD_RE = re.compile(
    r"^(?:Verwarnung|Gelb-Rote Karte|Rote Karte|Ausschluss)\s+(.+?)\s*\((.+?)\)\s*$", re.I
)
_SUB_RE = re.compile(r"^(.+?)\s+ersetzt durch\s+(.+?)$", re.I)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _int(value: str) -> int | None:
    m = re.search(r"-?\d+", value or "")
    return int(m.group()) if m else None


# ---------------------------------------------------------------------------
# Vereinsseite: welche Teams hat der Verein?
# ---------------------------------------------------------------------------


@dataclass
class TeamRef:
    team_id: int
    name: str
    sort_order: int


def parse_club_teams(html: str) -> list[TeamRef]:
    """Liest die Teamliste einer Vereinsseite (default.aspx?v=<id>)."""
    teams: list[TeamRef] = []
    seen: set[int] = set()
    for idx, a in enumerate(_soup(html).select('a[href*="t="]')):
        href = a.get("href", "")
        m = re.search(r"[?&]t=(\d+)", href)
        if not m:
            continue
        team_id = int(m.group(1))
        name = _text(a)
        if team_id in seen or not name:
            continue
        seen.add(team_id)
        teams.append(TeamRef(team_id=team_id, name=name, sort_order=idx))
    return teams


# ---------------------------------------------------------------------------
# Rangliste
# ---------------------------------------------------------------------------


@dataclass
class StandingRow:
    rank: int | None
    team: str
    played: int | None
    won: int | None
    drawn: int | None
    lost: int | None
    goals_for: int | None
    goals_against: int | None
    goal_diff: int | None
    points: int | None
    note: str = ""


def parse_standings(html: str) -> list[StandingRow]:
    rows: list[StandingRow] = []
    for tr in _soup(html).select("table.nisRanglisteRD tr"):
        team_cell = tr.select_one("td.ranCteam")
        if team_cell is None:
            continue  # Kopfzeile
        rows.append(
            StandingRow(
                rank=_int(_text(tr.select_one("td.ranCrang"))),
                team=_text(team_cell),
                played=_int(_text(tr.select_one("td.ranCsp"))),
                won=_int(_text(tr.select_one("td.ranCs"))),
                drawn=_int(_text(tr.select_one("td.ranCu"))),
                lost=_int(_text(tr.select_one("td.ranCn"))),
                goals_for=_int(_text(tr.select_one("td.ranCtg"))),
                goals_against=_int(_text(tr.select_one("td.ranCte"))),
                goal_diff=_int(_text(tr.select_one("td.ranCtdf"))),
                points=_int(_text(tr.select_one("td.ranCpt"))),
                note=_text(tr.select_one("td.ranCstrp")),
            )
        )
    return rows


# Ueberschriften, die keine Liga benennen, sondern nur die Ansicht.
_GENERIC_HEADINGS = {"team-spielplan", "spielplan", "match center", "resultate", "info"}


def parse_league_title(html: str) -> str:
    """Der Liganame steht in der Panel-Ueberschrift ueber der Tabelle.

    Hat ein Team gar keinen Spielbetrieb, steht dort nur "Team-Spielplan" -
    das ist kein Liganame und wird deshalb verworfen.
    """
    soup = _soup(html)
    table = soup.select_one("table.nisRanglisteRD")
    if table is not None:
        panel = table.find_parent(class_="panel")
        if panel is not None:
            heading = panel.select_one(".panel-heading h4") or panel.select_one(".panel-heading")
            if heading is not None and _text(heading):
                return _text(heading)

    title = _text(soup.select_one("h4"))
    return "" if title.lower() in _GENERIC_HEADINGS else title


# ---------------------------------------------------------------------------
# Spiele (Resultate + Spielplan)
# ---------------------------------------------------------------------------


@dataclass
class MatchRow:
    match_id: int | None
    kickoff_date: str | None  # ISO YYYY-MM-DD
    kickoff_time: str | None  # HH:MM
    home: str
    away: str
    home_goals: int | None
    away_goals: int | None
    forfait: bool = False
    venue: str = ""
    competition: str = ""
    match_number: str = ""

    @property
    def played(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None


def _date_from_classes(node: Tag) -> str | None:
    """Die Startseite haengt das Datum als Klasse an: class="... dt-24.08.2026"."""
    for cls in node.get("class", []):
        if cls.startswith("dt-"):
            m = _DATE_RE.search(cls)
            if m:
                d, mo, y = m.groups()
                return f"{y}-{mo}-{d}"
    return None


def _iso_date(text: str) -> str | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"


def parse_matches(html: str) -> list[MatchRow]:
    """Liest alle Spielzeilen einer Seite.

    Das Datum steht in einer vorangestellten Kopfzeile (.sppTitel), gilt also
    fuer alle folgenden Zeilen bis zur naechsten Kopfzeile. Auf der Startseite
    haengt es zusaetzlich als CSS-Klasse an der Zeile selbst.
    """
    soup = _soup(html)
    matches: list[MatchRow] = []
    current_date: str | None = None

    # Dokumentreihenfolge beibehalten: Kopfzeilen und Spielzeilen gemischt.
    for node in soup.select(".sppTitel, .row.spiel"):
        classes = node.get("class", [])
        if "sppTitel" in classes:
            current_date = _iso_date(_text(node)) or current_date
            continue

        row_date = _date_from_classes(node) or current_date
        home = _text(node.select_one(".teamA"))
        away = _text(node.select_one(".teamB"))
        if not home or not away:
            continue

        # Die Zeile steckt in einem <a href="...tg=NNN">.
        match_id = None
        link = node.find_parent("a")
        if link is not None:
            m = re.search(r"[?&]tg=(\d+)", link.get("href", ""))
            if m:
                match_id = int(m.group(1))

        time_text = _text(node.select_one(".time"))
        kickoff_time = time_text if _TIME_RE.match(time_text) else None

        venue = competition = match_number = ""
        info = node.select_one(".col-md-11")
        if info is not None:
            parts = [p.strip() for p in info.get_text("\n", strip=True).split("\n") if p.strip()]
            for part in parts:
                if part.lower().startswith("spielnummer"):
                    match_number = part.split(maxsplit=1)[-1]
                elif not venue:
                    venue = part
                elif not competition:
                    competition = part

        matches.append(
            MatchRow(
                match_id=match_id,
                kickoff_date=row_date,
                kickoff_time=kickoff_time,
                home=home,
                away=away,
                home_goals=_int(_text(node.select_one(".torA"))),
                away_goals=_int(_text(node.select_one(".torB"))),
                forfait="forfait" in _text(node).lower(),
                venue=venue,
                competition=competition,
                match_number=match_number,
            )
        )
    return matches


# ---------------------------------------------------------------------------
# Turniere (Junioren E, F, G)
# ---------------------------------------------------------------------------
#
# Im Schweizer Kinderfussball wird bewusst ohne Resultate und Rangliste
# gespielt ("play more football"). Statt Paarungen stehen dort Turniere:
# ein Termin, ein Platz, ein Organisator und eine Liste teilnehmender Teams.


@dataclass
class Tournament:
    tournament_id: str
    date: str | None
    time: str = ""
    title: str = ""
    category: str = ""
    series: str = ""
    organiser: str = ""
    venue: str = ""
    teams: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.teams is None:
            self.teams = []


def parse_tournaments(html: str) -> list[Tournament]:
    soup = _soup(html)
    tournaments: list[Tournament] = []

    for header in soup.select(".list-group-item.sppTitel"):
        cells = header.select(".row.spiel > div")
        if len(cells) < 2:
            continue  # normale Spieltag-Ueberschrift, kein Turnierkopf
        when, title = _text(cells[0]), _text(cells[1])
        if "turnier" not in title.lower():
            continue

        body = header.find_next_sibling("div", class_="list-group-item")
        lines = [_text(d) for d in body.select(".font-small > div")] if body else []

        t = Tournament(
            tournament_id="",
            date=_iso_date(when),
            time=(re.search(r"(\d{1,2}:\d{2})", when) or [None, ""])[1]
            if re.search(r"(\d{1,2}:\d{2})", when) else "",
            title=title,
        )
        for line in lines:
            low = line.lower()
            if low.startswith("turniernummer"):
                t.tournament_id = line.split(":", 1)[-1].strip()
            elif low.startswith("organisator"):
                t.organiser = line.split(":", 1)[-1].strip()
            elif low.startswith("teams:"):
                t.teams = [x.strip() for x in line.split(":", 1)[-1].split(",") if x.strip()]
            elif low.startswith("turnier "):
                t.series = line
            elif _DATE_RE.search(line):
                # "15.08.2026 10:00 - 12:00" - genauere Zeitangabe als der Kopf
                span = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", line)
                if span:
                    t.time = f"{span.group(1)}–{span.group(2)}"
            elif not t.category:
                t.category = line
            elif not t.venue:
                t.venue = line

        if t.tournament_id:
            tournaments.append(t)

    return tournaments


# ---------------------------------------------------------------------------
# Telegramm: Ereignisse eines einzelnen Spiels
# ---------------------------------------------------------------------------


@dataclass
class MatchEvent:
    order: int
    minute: int | None
    kind: str  # goal | yellow_card | second_yellow | red_card | substitution | phase
    team: str = ""
    player: str = ""
    player_id: int | None = None
    player_in: str = ""
    player_in_id: int | None = None
    score: str = ""
    label: str = ""
    text: str = ""


def parse_telegram(html: str) -> list[MatchEvent]:
    soup = _soup(html)
    events: list[MatchEvent] = []

    for order, li in enumerate(soup.select("ul.bnEventsList > li")):
        eid = _int(li.get("data-eid", "")) or 0
        icon = ""
        img = li.select_one("img.fileicon")
        if img is not None:
            m = re.search(r"/([\w\-]+)\.gif", img.get("src", ""))
            icon = m.group(1) if m else ""

        kind = EVENT_KIND_BY_ICON.get(icon) or EVENT_KIND_BY_EID.get(eid, "phase")

        label_node = li.select_one(".eventlabel")
        label = _text(label_node)
        # Der Beschreibungstext steht im selben Container nach dem Label.
        detail = ""
        if label_node is not None and label_node.parent is not None:
            detail = _text(label_node.parent).replace(label, "", 1).strip()

        minute = None
        time_text = _text(li.select_one("time.timeline-time"))
        if time_text:
            m = _MINUTE_RE.search(time_text)
            if m:
                minute = int(m.group(1))

        ev = MatchEvent(
            order=order,
            minute=minute,
            kind=kind,
            label=label,
            text=detail,
            player_id=_int(li.get("data-rid", "")),
        )

        if kind == "goal":
            # Label: "Tor   <Team>"  /  Detail: "Torschuetze <Name>"
            ev.team = re.sub(r"^Tor\s*", "", label).strip()
            scorer = _SCORER_RE.search(detail)
            ev.player = scorer.group(1).strip() if scorer else detail
            # Zwischenstand steht neben dem Icon, z.B. "4:2".
            if img is not None and img.parent is not None:
                m = re.search(r"\d+\s*:\s*\d+", _text(img.parent))
                ev.score = m.group().replace(" ", "") if m else ""

        elif kind in ("yellow_card", "second_yellow", "red_card"):
            m = _CARD_RE.match(label or _text(li))
            if m:
                ev.player, ev.team = m.group(1).strip(), m.group(2).strip()

        elif kind == "substitution":
            ev.team = re.sub(r"^Aus-/Einwechslung\s*", "", label).strip()
            m = _SUB_RE.match(detail)
            if m:
                ev.player, ev.player_in = m.group(1).strip(), m.group(2).strip()
                # data-rid1 = ausgewechselt, data-rid = eingewechselt
                ev.player_id = _int(li.get("data-rid1", ""))
                ev.player_in_id = _int(li.get("data-rid", ""))

        events.append(ev)

    return events


@dataclass
class TelegramHeader:
    home: str = ""
    away: str = ""
    home_goals: int | None = None
    away_goals: int | None = None
    halftime: str = ""
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_logo: str = ""
    away_logo: str = ""
    kickoff_date: str | None = None
    kickoff_time: str | None = None
    competition: str = ""
    league_name: str = ""
    venue: str = ""
    match_number: str = ""


def _flag(soup: BeautifulSoup, selector: str) -> tuple[int | None, str]:
    img = soup.select_one(f"{selector} img")
    if img is None:
        return None, ""
    return _int(img.get("data-tid", "")), img.get("src", "")


def parse_telegram_header(html: str) -> TelegramHeader:
    """Paarung, Resultat und Rahmendaten aus dem Kopf des Telegramms.

    Die Zeile .shortSpielort buendelt alles in einem String, z.B.
    "Meisterschaft - 2. Liga - 21.08.2026 20:15 - Spielnummer: 111275 - Badmatte, Villmergen"
    """
    soup = _soup(html)
    head = TelegramHeader(
        home=_text(soup.select_one(".shortTeamHeim")),
        away=_text(soup.select_one(".shortTeamGast")),
        halftime=_text(soup.select_one('[id$="divToreHz"]')),
    )

    result = _text(soup.select_one(".shortResults"))
    m = re.match(r"(\d+)\s*:\s*(\d+)", result)
    if m:
        head.home_goals, head.away_goals = int(m.group(1)), int(m.group(2))

    head.home_team_id, head.home_logo = _flag(soup, ".shortTeamFlagHeim")
    head.away_team_id, head.away_logo = _flag(soup, ".shortTeamFlagGast")

    info = _text(soup.select_one(".shortSpielort"))
    parts = [p.strip() for p in info.split(" - ") if p.strip()]
    for part in parts:
        if part.lower().startswith("spielnummer"):
            head.match_number = part.split(":", 1)[-1].strip()
        elif _DATE_RE.search(part):
            head.kickoff_date = _iso_date(part)
            t = re.search(r"(\d{1,2}:\d{2})", part)
            head.kickoff_time = t.group(1) if t else None
        elif not head.competition:
            head.competition = part
        elif not head.league_name:
            head.league_name = part
        else:
            # Alles Weitere ist der Spielort (kann selbst " - " enthalten).
            head.venue = f"{head.venue} - {part}".strip(" -") if head.venue else part
    return head


# ---------------------------------------------------------------------------
# Torschuetzenliste (a=mtg)
# ---------------------------------------------------------------------------


@dataclass
class ScorerRow:
    goals: int
    player: str
    team: str


def parse_scorers(html: str) -> list[ScorerRow]:
    """Liest die offizielle Torschuetzenliste einer Liga.

    Die Torzahl steht nur in der ersten Zeile einer Gruppe; alle weiteren
    Spieler mit gleicher Anzahl haben eine leere Zelle. Der Wert wird deshalb
    nach unten weitergereicht.
    """
    scorers: list[ScorerRow] = []
    for table in _soup(html).select("table"):
        headers = [_text(th).lower() for th in table.select("thead th")]
        # Nur die echte Torschuetzentabelle - eine Rangliste hat andere Spalten.
        if not (headers[:1] == ["tore"] and "verein" in headers):
            continue
        current = 0
        for tr in table.select("tbody tr"):
            cells = tr.select("td")
            if len(cells) < 3:
                continue
            goals = _int(_text(cells[0]))
            if goals is not None:
                current = goals
            player, team = _text(cells[1]), _text(cells[2])
            if not player or current <= 0:
                continue
            scorers.append(ScorerRow(goals=current, player=player, team=team))
    return scorers


# ---------------------------------------------------------------------------
# Gruppenreferenz: ln / ls / sg
# ---------------------------------------------------------------------------


@dataclass
class GroupRef:
    league_id: int | None = None  # ln
    season_id: int | None = None  # ls
    group_id: int | None = None  # sg

    @property
    def complete(self) -> bool:
        return self.season_id is not None and self.group_id is not None


def parse_group_ref(html: str) -> GroupRef:
    """Fischt ln/ls/sg aus den Aktionslinks einer Liga- oder Teamseite.

    Diese drei Ids zusammen adressieren eine konkrete Gruppe einer Saison und
    sind noetig, um Spielplan (a=msp) und Torschuetzenliste (a=mtg) zu laden.
    """
    ref = GroupRef()
    for a in _soup(html).select('a[href*="sg="]'):
        href = a.get("href", "")
        sg = re.search(r"[?&]sg=(\d+)", href)
        if not sg or sg.group(1) == "0":
            continue
        ref.group_id = int(sg.group(1))
        ls = re.search(r"[?&]ls=(\d+)", href)
        if ls:
            ref.season_id = int(ls.group(1))
        ln = re.search(r"[?&]ln=(\d+)", href)
        if ln:
            ref.league_id = int(ln.group(1))
        if ref.complete:
            break
    return ref


# ---------------------------------------------------------------------------
# Verbandsnavigation: alle Ligen
# ---------------------------------------------------------------------------


@dataclass
class LeagueRef:
    league_id: int
    name: str
    kind: str = "meisterschaft"  # meisterschaft | cup


def parse_leagues(html: str) -> list[LeagueRef]:
    """Liest die Liga- und Cup-Navigation der Matchcenter-Startseite."""
    leagues: list[LeagueRef] = []
    seen: set[tuple[int, str]] = set()
    for a in _soup(html).select('a[href*="ln="], a[href*="cp="]'):
        href = a.get("href", "")
        if "matchcenter.football.ch" in href:
            continue  # andere Verbaende ignorieren
        m = re.search(r"[?&](ln|cp)=(\d+)", href)
        name = _text(a)
        if not m or not name:
            continue
        kind = "meisterschaft" if m.group(1) == "ln" else "cup"
        league_id = int(m.group(2))
        if (league_id, kind) in seen:
            continue
        seen.add((league_id, kind))
        leagues.append(LeagueRef(league_id=league_id, name=name, kind=kind))
    return leagues

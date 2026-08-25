/**
 * Zugriff auf die Daten. Zwei Betriebsarten, gleiche Aufrufe.
 *
 * Die App spricht nie direkt mit dem Matchcenter des AFV.
 *
 * 1. Entwicklung: das lokale FastAPI-Backend. Die Adresse wird aus dem
 *    Expo-Dev-Server abgeleitet - laeuft die App per Expo Go auf dem iPhone,
 *    kennt Expo bereits die IP des Laptops im WLAN. Beim Netzwechsel muss
 *    also nichts angepasst werden.
 *
 * 2. Veroeffentlicht: statische JSON-Dateien auf GitHub Pages, erzeugt von
 *    `python -m tools.export_static`. Kein Server, keine Kaltstarts, gratis.
 *    Dann haengt jeder Pfad ein ".json" an und die Query entfaellt - deshalb
 *    fragt die App immer die volle Liste ab und filtert selbst (siehe
 *    `withinDays`). So verhalten sich beide Modi identisch.
 *
 * Welcher Modus gilt, entscheidet `__DEV__`: in einem Entwicklungs-Bundle das
 * lokale Backend, in einem veroeffentlichten Bundle die statischen Daten.
 * Damit braucht `eas update` keinerlei Konfiguration - und der Fallstrick
 * entfaellt, dass Metro Umgebungsvariablen fest einbackt und cacht.
 *
 * Zum Ueberschreiben (etwa um lokal gegen die veroeffentlichten Daten zu
 * testen) gibt es weiterhin:
 *    EXPO_PUBLIC_API_URL=http://localhost:8083/api
 *    EXPO_PUBLIC_API_MODE=static
 */
import Constants from 'expo-constants';

const PORT = 8000;

/** Die veroeffentlichten Daten - erzeugt von `python -m tools.export_static`. */
const PUBLISHED_API = 'https://vincentbuehler.github.io/afv-othmarsingen/api';

const CONFIGURED_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;

const CONFIGURED_MODE =
  process.env.EXPO_PUBLIC_API_MODE ??
  (Constants.expoConfig?.extra as { apiMode?: string } | undefined)?.apiMode;

/** Statischer Modus: Pfade bekommen ".json", Query-Parameter entfallen. */
export const IS_STATIC = CONFIGURED_MODE
  ? CONFIGURED_MODE === 'static'
  : !CONFIGURED_URL && !__DEV__;

function resolveBaseUrl(): string {
  if (CONFIGURED_URL) return CONFIGURED_URL.replace(/\/$/, '');

  // Veroeffentlichtes Bundle (eas update, Store-Build): feste Adresse, denn
  // hier gibt es keinen Laptop im WLAN, den man fragen koennte.
  if (!__DEV__) return PUBLISHED_API;

  // Entwicklung: hostUri sieht aus wie "192.168.1.42:8081"
  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants.expoGoConfig as { debuggerHost?: string } | undefined)?.debuggerHost;

  const host = hostUri?.split(':')[0];
  if (host) return `http://${host}:${PORT}/api`;

  // Letzter Ausweg (Simulator auf dem gleichen Rechner)
  return `http://localhost:${PORT}/api`;
}

export const API_BASE = resolveBaseUrl();

/** "/matches/upcoming?days=400" -> ".../matches/upcoming.json" im statischen Modus. */
function buildUrl(path: string): string {
  if (!IS_STATIC) return `${API_BASE}${path}`;
  const [bare] = path.split('?');
  return `${API_BASE}${bare}.json`;
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = buildUrl(path);
  let response: Response;
  try {
    response = await fetch(url, { signal });
  } catch {
    throw new ApiError(
      IS_STATIC
        ? `Daten nicht erreichbar (${API_BASE}). Besteht eine Internetverbindung?`
        : `Backend nicht erreichbar (${API_BASE}). Läuft "uvicorn app.main:app --host 0.0.0.0"?`,
    );
  }
  if (!response.ok) {
    throw new ApiError(`Server antwortet mit ${response.status}`, response.status);
  }
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Filter, die im statischen Modus die Query-Parameter ersetzen
// ---------------------------------------------------------------------------

/** Behaelt Eintraege, deren Datum hoechstens `days` Tage in der Zukunft liegt. */
export function withinDays<T extends { kickoff_date?: string | null; date?: string | null }>(
  items: T[] | null,
  days: number,
): T[] {
  if (!items) return [];
  const limit = new Date();
  limit.setHours(23, 59, 59, 999);
  limit.setDate(limit.getDate() + days);
  const cutoff = limit.toISOString().slice(0, 10);

  return items.filter((item) => {
    const d = item.kickoff_date ?? item.date;
    return !d || d <= cutoff;
  });
}

// ---------------------------------------------------------------------------
// Typen - Spiegel der Antworten aus backend/app/main.py
// ---------------------------------------------------------------------------

export type Team = {
  team_id: number;
  name: string;
  league_name: string;
  group_id: number | null;
  sort_order: number;
  match_count?: number;
};

export type Match = {
  match_id: number;
  kickoff_date: string | null;
  kickoff_time: string | null;
  home: string;
  away: string;
  home_goals: number | null;
  away_goals: number | null;
  halftime: string;
  forfait: number;
  venue: string;
  competition: string;
  team_name?: string;
  team_id?: number;
};

export type StandingRow = {
  rank: number | null;
  team: string;
  played: number | null;
  won: number | null;
  drawn: number | null;
  lost: number | null;
  goals_for: number | null;
  goals_against: number | null;
  goal_diff: number | null;
  points: number | null;
};

export type Tally = {
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  points: number;
  goal_diff: number;
};

export type FormEntry = {
  match_id: number;
  date: string | null;
  opponent: string;
  side: 'home' | 'away';
  score: string;
  result: 'W' | 'D' | 'L';
};

export type Summary = {
  total: Tally;
  home: Tally;
  away: Tally;
  form: FormEntry[];
  form_string: string;
  streak: { kind: string; count: number };
};

export type MatchEvent = {
  ord: number;
  minute: number | null;
  kind: string;
  team: string;
  player: string;
  player_in: string;
  score: string;
  label: string;
  text: string;
};

export type PlayerStat = {
  player: string;
  player_id: number | null;
  goals: number;
  yellow_cards: number;
  second_yellows: number;
  red_cards: number;
};

export type Tournament = {
  tournament_id: string;
  team_id: number;
  team_name?: string;
  date: string | null;
  time: string;
  title: string;
  category: string;
  organiser: string;
  venue: string;
  teams: string[];
};

export type Overview = {
  club: string;
  season: number;
  last_sync: string;
  total: Tally;
  teams: {
    team_id: number;
    name: string;
    league_name: string;
    position: { rank: number; points: number; played: number } | null;
    form_string: string;
    summary: Tally;
  }[];
  quelle: string;
  hinweis: string;
};

export type TeamDetail = {
  team: Team;
  standings: StandingRow[];
  position: StandingRow | null;
  summary: Summary;
  next_match: Match | null;
  last_match: Match | null;
  match_count: { played: number; upcoming: number };
  tournaments: Tournament[];
};

export type TeamStats = {
  team: Team;
  summary: Summary;
  goal_minutes: { buckets: string[]; scored: number[]; conceded: number[]; sample_size: number };
  players: PlayerStat[];
  league_scorers: { player: string; team: string; goals: number }[];
  fairplay: { team: string; yellow_cards: number; red_cards: number; points: number }[];
};

export type MatchDetail = {
  match: Match;
  events: MatchEvent[];
  has_details: boolean;
  hinweis: string | null;
};

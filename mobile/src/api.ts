/**
 * Zugriff auf das eigene Backend.
 *
 * Die App spricht nie direkt mit dem Matchcenter des AFV - nur mit dem
 * FastAPI-Backend, das die Daten gespiegelt hat.
 *
 * Die Adresse wird zur Laufzeit aus dem Expo-Dev-Server abgeleitet: laeuft die
 * App per Expo Go auf dem iPhone, kennt Expo bereits die IP des Laptops im
 * WLAN. Damit muss beim Wechsel des Netzwerks nichts von Hand angepasst werden.
 * Ueber app.json -> extra.apiUrl laesst sich eine feste Adresse erzwingen.
 */
import Constants from 'expo-constants';

const PORT = 8000;

function resolveBaseUrl(): string {
  const configured = (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;
  if (configured) return configured.replace(/\/$/, '');

  // hostUri sieht aus wie "192.168.1.42:8081"
  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants.expoGoConfig as { debuggerHost?: string } | undefined)?.debuggerHost;

  const host = hostUri?.split(':')[0];
  if (host) return `http://${host}:${PORT}`;

  // Letzter Ausweg (Simulator auf dem gleichen Rechner)
  return `http://localhost:${PORT}`;
}

export const API_BASE = resolveBaseUrl();

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { signal });
  } catch {
    throw new ApiError(
      `Backend nicht erreichbar (${API_BASE}). Laeuft "uvicorn app.main:app --host 0.0.0.0"?`,
    );
  }
  if (!response.ok) {
    throw new ApiError(`Server antwortet mit ${response.status}`, response.status);
  }
  return (await response.json()) as T;
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

/** Wiederverwendbare Bausteine der Oberflaeche. */
import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from 'react-native';

import { Match, Tournament } from './api';
import { colors, formatDate, radius, relativeDay, resultColor, spacing } from './theme';

const CLUB = 'Othmarsingen';

export const isClub = (name: string): boolean => name.toLowerCase().includes(CLUB.toLowerCase());

// ---------------------------------------------------------------------------

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <View style={s.sectionRow}>
      <Text style={s.section}>{children}</Text>
      {hint ? <Text style={s.sectionHint}>{hint}</Text> : null}
    </View>
  );
}

export function Loading({ label = 'Lade Daten…' }: { label?: string }) {
  return (
    <View style={s.center}>
      <ActivityIndicator color={colors.accent} />
      <Text style={s.muted}>{label}</Text>
    </View>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <View style={s.center}>
      <Text style={s.errorTitle}>Keine Verbindung</Text>
      <Text style={[s.muted, { textAlign: 'center' }]}>{error}</Text>
      {onRetry ? (
        <Pressable style={s.retry} onPress={onRetry}>
          <Text style={s.retryText}>Nochmal versuchen</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <View style={s.center}>
      <Text style={s.muted}>{children}</Text>
    </View>
  );
}

/** Formkurve als farbige Punkte: neueste Spiele zuerst. */
export function FormDots({ form }: { form: string }) {
  if (!form) return <Text style={s.faint}>–</Text>;
  return (
    <View style={s.formRow}>
      {form.split('').map((r, i) => (
        <View key={i} style={[s.dot, { backgroundColor: resultColor(r) }]}>
          <Text style={s.dotText}>{r === 'W' ? 'S' : r === 'L' ? 'N' : 'U'}</Text>
        </View>
      ))}
    </View>
  );
}

/**
 * Eine Spielzeile. Der eigene Verein wird fett gesetzt, damit man auf einen
 * Blick sieht, ob Othmarsingen heim oder auswaerts spielt.
 */
export function MatchRow({ match, onPress }: { match: Match; onPress?: () => void }) {
  const played = match.home_goals !== null && match.away_goals !== null;
  const won =
    played && isClub(match.home)
      ? match.home_goals! > match.away_goals!
      : played && isClub(match.away)
        ? match.away_goals! > match.home_goals!
        : false;
  const lost =
    played && isClub(match.home)
      ? match.home_goals! < match.away_goals!
      : played && isClub(match.away)
        ? match.away_goals! < match.home_goals!
        : false;

  const relative = relativeDay(match.kickoff_date);

  return (
    <Pressable style={s.matchRow} onPress={onPress} disabled={!onPress}>
      <View style={s.matchWhen}>
        <Text style={s.matchDate}>{formatDate(match.kickoff_date)}</Text>
        <Text style={s.faint}>{relative || match.kickoff_time || ''}</Text>
      </View>

      <View style={s.matchTeams}>
        <Text numberOfLines={1} style={[s.team, isClub(match.home) && s.teamOwn]}>
          {match.home}
        </Text>
        <Text numberOfLines={1} style={[s.team, isClub(match.away) && s.teamOwn]}>
          {match.away}
        </Text>
        {match.team_name ? <Text style={s.faint}>{match.team_name}</Text> : null}
      </View>

      <View style={s.matchScore}>
        {played ? (
          <>
            <Text
              style={[
                s.score,
                won && { color: colors.win },
                lost && { color: colors.loss },
              ]}
            >
              {match.home_goals}
            </Text>
            <Text
              style={[
                s.score,
                won && { color: colors.win },
                lost && { color: colors.loss },
              ]}
            >
              {match.away_goals}
            </Text>
          </>
        ) : (
          <Text style={s.kickoff}>{match.kickoff_time ?? '–'}</Text>
        )}
      </View>
    </Pressable>
  );
}

/** Kleine Kennzahl, z.B. "12  Tore" */
export function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <View style={s.stat}>
      <Text style={s.statValue}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  sectionRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginHorizontal: spacing.lg,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  section: {
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    color: colors.textMuted,
  },
  sectionHint: { fontSize: 12, color: colors.textFaint },

  center: { padding: spacing.xl, alignItems: 'center', gap: spacing.sm },
  muted: { color: colors.textMuted, fontSize: 14 },
  faint: { color: colors.textFaint, fontSize: 12 },
  errorTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  retry: {
    marginTop: spacing.sm,
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  retryText: { color: '#fff', fontWeight: '600' },

  formRow: { flexDirection: 'row', gap: 4 },
  dot: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  dotText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  matchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  matchWhen: { width: 74 },
  matchDate: { fontSize: 13, fontWeight: '600', color: colors.text },
  matchTeams: { flex: 1, gap: 2 },
  team: { fontSize: 15, color: colors.textMuted },
  teamOwn: { color: colors.text, fontWeight: '700' },
  matchScore: { width: 30, alignItems: 'flex-end', gap: 2 },
  score: { fontSize: 15, fontWeight: '700', color: colors.text, lineHeight: 20 },
  kickoff: { fontSize: 13, color: colors.textFaint },
  tournamentVenue: { fontSize: 15, color: colors.text, fontWeight: '600' },

  stat: { alignItems: 'center', flex: 1 },
  statValue: { fontSize: 22, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
});

/**
 * Ein Turnier des Kinderfussballs. Bewusst ohne Resultat: die Junioren E/F/G
 * spielen nach "play more football" ohne Rangliste und ohne Ergebnisliste.
 */
export function TournamentRow({ tournament }: { tournament: Tournament }) {
  const relative = relativeDay(tournament.date);
  return (
    <View style={s.matchRow}>
      <View style={s.matchWhen}>
        <Text style={s.matchDate}>{formatDate(tournament.date)}</Text>
        <Text style={s.faint}>{relative || tournament.time}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.tournamentVenue} numberOfLines={1}>
          {tournament.venue || tournament.title}
        </Text>
        <Text style={s.faint} numberOfLines={2}>
          {tournament.teams.filter((t) => !isClub(t)).join(' · ') || tournament.category}
        </Text>
        {tournament.team_name ? <Text style={s.faint}>{tournament.team_name}</Text> : null}
      </View>
    </View>
  );
}

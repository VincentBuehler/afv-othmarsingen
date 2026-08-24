/** Ein Spiel im Detail: Resultat und der Verlauf aus dem Telegramm. */
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { MatchDetail, MatchEvent } from '../api';
import { Card, Empty, ErrorBox, Loading, SectionTitle, isClub } from '../components';
import { colors, formatDate, radius, spacing } from '../theme';
import { useApi } from '../useApi';

const KIND_LABEL: Record<string, string> = {
  goal: 'Tor',
  yellow_card: 'Gelb',
  second_yellow: 'Gelb-Rot',
  red_card: 'Rot',
  substitution: 'Wechsel',
};

export default function MatchScreen({ route }: { route: any }) {
  const { matchId } = route.params;
  const { data, loading, error, reload } = useApi<MatchDetail>(`/api/matches/${matchId}`);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;

  const { match, events, hinweis } = data!;
  const played = match.home_goals !== null;
  // Der Verlauf kommt neueste-zuerst aus dem Matchcenter; genau so wollen wir ihn.
  const timeline = events.filter((e) => e.kind !== 'phase');

  return (
    <ScrollView style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.meta}>
          {match.competition || 'Spiel'} · {formatDate(match.kickoff_date, true)}
          {match.kickoff_time ? ` · ${match.kickoff_time}` : ''}
        </Text>

        <View style={styles.scoreRow}>
          <Text numberOfLines={2} style={[styles.team, isClub(match.home) && styles.teamOwn]}>
            {match.home}
          </Text>
          <View style={styles.scoreBox}>
            {played ? (
              <Text style={styles.score}>
                {match.home_goals}:{match.away_goals}
              </Text>
            ) : (
              <Text style={styles.scoreSoon}>{match.kickoff_time ?? '–'}</Text>
            )}
            {match.halftime ? <Text style={styles.halftime}>{match.halftime}</Text> : null}
          </View>
          <Text numberOfLines={2} style={[styles.team, isClub(match.away) && styles.teamOwn]}>
            {match.away}
          </Text>
        </View>

        {match.venue ? <Text style={styles.venue}>{match.venue}</Text> : null}
        {match.forfait ? <Text style={styles.forfait}>Forfait-Resultat</Text> : null}
      </View>

      <SectionTitle hint={timeline.length ? `${timeline.length} Ereignisse` : undefined}>
        Spielverlauf
      </SectionTitle>
      <Card>
        {timeline.length ? (
          timeline.map((e) => <EventRow key={e.ord} event={e} />)
        ) : (
          <Empty>{hinweis ?? 'Für dieses Spiel gibt es kein Telegramm.'}</Empty>
        )}
      </Card>

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function EventRow({ event }: { event: MatchEvent }) {
  const isGoal = event.kind === 'goal';
  const dotColor =
    event.kind === 'goal'
      ? colors.accent
      : event.kind === 'yellow_card'
        ? colors.yellowCard
        : event.kind === 'second_yellow' || event.kind === 'red_card'
          ? colors.redCard
          : colors.textFaint;

  // Bei einer Auswechslung ist `player` der Spieler, der rausgeht, und
  // `player_in` der, der reinkommt. In der Zeile gehoert der Eingewechselte
  // nach vorne - sonst liest es sich genau verkehrt herum.
  const isSub = event.kind === 'substitution';
  const headline = isSub ? event.player_in || event.player : event.player || event.label;
  const detail = isSub && event.player_in ? ` · für ${event.player}` : '';

  return (
    <View style={styles.event}>
      <Text style={styles.minute}>{event.minute !== null ? `${event.minute}'` : ''}</Text>
      <View style={[styles.eventDot, { backgroundColor: dotColor }]} />
      <View style={styles.eventBody}>
        <Text style={[styles.eventPlayer, isGoal && styles.eventPlayerGoal]}>{headline}</Text>
        <Text style={styles.eventMeta}>
          {KIND_LABEL[event.kind] ?? event.kind}
          {event.team ? ` · ${event.team}` : ''}
          {detail}
        </Text>
      </View>
      {isGoal && event.score ? <Text style={styles.eventScore}>{event.score}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: { backgroundColor: colors.dark, padding: spacing.lg, paddingBottom: spacing.xl },
  meta: { color: colors.accentSoft, fontSize: 12, opacity: 0.8, textAlign: 'center' },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  team: { flex: 1, color: '#fff', fontSize: 15, textAlign: 'center', opacity: 0.8 },
  teamOwn: { fontWeight: '800', opacity: 1 },
  scoreBox: {
    minWidth: 84,
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: radius.sm,
    paddingVertical: spacing.sm,
  },
  score: { color: '#fff', fontSize: 28, fontWeight: '800' },
  scoreSoon: { color: '#fff', fontSize: 20, fontWeight: '700' },
  halftime: { color: colors.accentSoft, fontSize: 11, opacity: 0.7 },
  venue: { color: colors.accentSoft, fontSize: 12, textAlign: 'center', marginTop: spacing.md, opacity: 0.7 },
  forfait: { color: colors.yellowCard, fontSize: 12, textAlign: 'center', marginTop: 4 },

  event: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  minute: { width: 34, fontSize: 13, fontWeight: '700', color: colors.textMuted },
  eventDot: { width: 8, height: 8, borderRadius: 4 },
  eventBody: { flex: 1 },
  eventPlayer: { fontSize: 15, color: colors.text },
  eventPlayerGoal: { fontWeight: '700' },
  eventMeta: { fontSize: 12, color: colors.textFaint, marginTop: 1 },
  eventScore: { fontSize: 15, fontWeight: '800', color: colors.accent },
});

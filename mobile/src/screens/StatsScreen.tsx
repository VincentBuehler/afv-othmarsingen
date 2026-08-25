/**
 * Statistik-Tab.
 *
 * Oben die Mannschaft waehlen, darunter alles, was sich aus den gespiegelten
 * Daten rechnen laesst - inklusive der Auswertungen, die das Matchcenter
 * selbst nicht anbietet (Torminuten, Heim-/Auswaertsvergleich).
 */
import React, { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Overview, TeamStats } from '../api';
import { Card, Empty, ErrorBox, Loading, SectionTitle, isClub } from '../components';
import { colors, radius, spacing } from '../theme';
import { useApi } from '../useApi';

export default function StatsScreen() {
  const overview = useApi<Overview>('/stats/overview');
  const [teamId, setTeamId] = useState<number | null>(null);

  // Standardmaessig die erste Mannschaft, sobald die Teamliste da ist.
  const selected = teamId ?? overview.data?.teams[0]?.team_id ?? null;
  const stats = useApi<TeamStats>(selected ? `/teams/${selected}/stats` : null);

  if (overview.loading) return <Loading />;
  if (overview.error) return <ErrorBox error={overview.error} onRetry={overview.reload} />;

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={stats.refreshing} onRefresh={stats.refresh} />}
    >
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.picker}>
        {overview.data!.teams.map((t) => (
          <Pressable
            key={t.team_id}
            style={[styles.chip, selected === t.team_id && styles.chipActive]}
            onPress={() => setTeamId(t.team_id)}
          >
            <Text style={[styles.chipText, selected === t.team_id && styles.chipTextActive]}>{t.name}</Text>
          </Pressable>
        ))}
      </ScrollView>

      {stats.loading ? <Loading /> : null}
      {stats.error ? <ErrorBox error={stats.error} onRetry={stats.reload} /> : null}
      {stats.data ? <TeamStatsBody stats={stats.data} /> : null}

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function TeamStatsBody({ stats }: { stats: TeamStats }) {
  const { summary, goal_minutes, players, league_scorers, fairplay } = stats;
  const clubPlayers = players.filter((p) => p.goals > 0 || p.yellow_cards > 0 || p.red_cards > 0);

  return (
    <>
      <SectionTitle>Heim gegen Auswärts</SectionTitle>
      <Card>
        <SplitBar
          label="Punkte pro Spiel"
          home={summary.home.played ? summary.home.points / summary.home.played : 0}
          away={summary.away.played ? summary.away.points / summary.away.played : 0}
          format={(v) => v.toFixed(2)}
        />
        <SplitBar
          label="Tore pro Spiel"
          home={summary.home.played ? summary.home.goals_for / summary.home.played : 0}
          away={summary.away.played ? summary.away.goals_for / summary.away.played : 0}
          format={(v) => v.toFixed(1)}
        />
        <SplitBar
          label="Gegentore pro Spiel"
          home={summary.home.played ? summary.home.goals_against / summary.home.played : 0}
          away={summary.away.played ? summary.away.goals_against / summary.away.played : 0}
          format={(v) => v.toFixed(1)}
          invert
        />
        <Text style={styles.note}>
          {summary.home.played} Heimspiele · {summary.away.played} Auswärtsspiele
        </Text>
      </Card>

      <SectionTitle hint={goal_minutes.sample_size ? `${goal_minutes.sample_size} Spiele` : 'keine Daten'}>
        Wann fallen die Tore?
      </SectionTitle>
      <Card>
        {goal_minutes.sample_size ? (
          <MinuteChart data={goal_minutes} />
        ) : (
          <Empty>Dafür müssen erst Spiel-Telegramme geladen werden.</Empty>
        )}
      </Card>

      <SectionTitle hint="aus den Telegrammen">Eigene Spieler</SectionTitle>
      <Card style={{ paddingHorizontal: spacing.sm }}>
        {clubPlayers.length ? (
          <>
            <View style={[styles.tr, styles.thead]}>
              <Text style={[styles.th, { flex: 1 }]}>Spieler</Text>
              <Text style={[styles.th, styles.colNum]}>Tore</Text>
              <Text style={[styles.th, styles.colNum]}>🟨</Text>
              <Text style={[styles.th, styles.colNum]}>🟥</Text>
            </View>
            {clubPlayers.map((p) => (
              <View key={`${p.player_id}-${p.player}`} style={styles.tr}>
                <Text numberOfLines={1} style={[styles.td, { flex: 1, color: colors.text }]}>
                  {p.player}
                </Text>
                <Text style={[styles.td, styles.colNum, styles.tdBold]}>{p.goals || '–'}</Text>
                <Text style={[styles.td, styles.colNum]}>{p.yellow_cards || '–'}</Text>
                <Text style={[styles.td, styles.colNum]}>
                  {p.red_cards + p.second_yellows || '–'}
                </Text>
              </View>
            ))}
          </>
        ) : (
          <Empty>Noch keine Telegramme geladen (python -m app.sync --details 30).</Empty>
        )}
      </Card>

      <SectionTitle hint="offiziell vom AFV">Torschützen der Liga</SectionTitle>
      <Card style={{ paddingHorizontal: spacing.sm }}>
        {league_scorers.length ? (
          league_scorers.slice(0, 15).map((sc, i) => (
            <View key={`${sc.player}-${i}`} style={[styles.tr, isClub(sc.team) && styles.trOwn]}>
              <Text style={[styles.td, styles.colGoals, styles.tdBold]}>{sc.goals}</Text>
              <Text numberOfLines={1} style={[styles.td, { flex: 1, color: colors.text }]}>
                {sc.player}
              </Text>
              <Text numberOfLines={1} style={[styles.td, { flex: 1, textAlign: 'right' }]}>
                {sc.team}
              </Text>
            </View>
          ))
        ) : (
          <Empty>Für diese Kategorie führt der Verband keine Torschützenliste.</Empty>
        )}
      </Card>

      {fairplay.length ? (
        <>
          <SectionTitle hint="je weniger, desto fairer">Fairplay</SectionTitle>
          <Card style={{ paddingHorizontal: spacing.sm }}>
            {fairplay.map((f) => (
              <View key={f.team} style={[styles.tr, isClub(f.team) && styles.trOwn]}>
                <Text numberOfLines={1} style={[styles.td, { flex: 1, color: colors.text }]}>
                  {f.team}
                </Text>
                <Text style={[styles.td, styles.colNum]}>{f.yellow_cards}</Text>
                <Text style={[styles.td, styles.colNum]}>{f.red_cards}</Text>
                <Text style={[styles.td, styles.colNum, styles.tdBold]}>{f.points}</Text>
              </View>
            ))}
          </Card>
        </>
      ) : null}
    </>
  );
}

/** Zwei Balken nebeneinander: heim links, auswaerts rechts. */
function SplitBar({
  label,
  home,
  away,
  format,
  invert = false,
}: {
  label: string;
  home: number;
  away: number;
  format: (v: number) => string;
  invert?: boolean;
}) {
  const max = Math.max(home, away, 0.01);
  const better = invert ? (home < away ? 'home' : 'away') : home > away ? 'home' : 'away';

  return (
    <View style={styles.split}>
      <Text style={styles.splitLabel}>{label}</Text>
      <View style={styles.splitRow}>
        <Text style={styles.splitValue}>{format(home)}</Text>
        <View style={styles.splitTrack}>
          <View
            style={[
              styles.splitFill,
              { width: `${(home / max) * 100}%`, backgroundColor: better === 'home' ? colors.accent : colors.border },
            ]}
          />
        </View>
        <Text style={styles.splitSide}>Heim</Text>
      </View>
      <View style={styles.splitRow}>
        <Text style={styles.splitValue}>{format(away)}</Text>
        <View style={styles.splitTrack}>
          <View
            style={[
              styles.splitFill,
              { width: `${(away / max) * 100}%`, backgroundColor: better === 'away' ? colors.accent : colors.border },
            ]}
          />
        </View>
        <Text style={styles.splitSide}>Ausw.</Text>
      </View>
    </View>
  );
}

/** Balkendiagramm der Torminuten in 15-Minuten-Bloecken. */
function MinuteChart({ data }: { data: TeamStats['goal_minutes'] }) {
  const max = Math.max(1, ...data.scored, ...data.conceded);
  return (
    <View>
      <View style={styles.chart}>
        {data.buckets.map((bucket, i) => (
          <View key={bucket} style={styles.chartCol}>
            <View style={styles.chartBars}>
              <View
                style={[styles.bar, { height: `${(data.scored[i] / max) * 100}%`, backgroundColor: colors.accent }]}
              />
              <View
                style={[styles.bar, { height: `${(data.conceded[i] / max) * 100}%`, backgroundColor: colors.loss }]}
              />
            </View>
            <Text style={styles.chartLabel}>{bucket}</Text>
          </View>
        ))}
      </View>
      <View style={styles.legend}>
        <View style={[styles.legendDot, { backgroundColor: colors.accent }]} />
        <Text style={styles.legendText}>eigene Tore</Text>
        <View style={[styles.legendDot, { backgroundColor: colors.loss }]} />
        <Text style={styles.legendText}>Gegentore</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  picker: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, flexGrow: 0 },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    marginRight: spacing.sm,
  },
  chipActive: { backgroundColor: colors.dark, borderColor: colors.dark },
  chipText: { fontSize: 13, color: colors.textMuted, fontWeight: '600' },
  chipTextActive: { color: '#fff' },

  note: { fontSize: 12, color: colors.textFaint, marginTop: spacing.sm },

  split: { marginBottom: spacing.md },
  splitLabel: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: spacing.xs },
  splitRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 3 },
  splitValue: { width: 34, fontSize: 13, fontWeight: '700', color: colors.text },
  splitTrack: { flex: 1, height: 10, backgroundColor: colors.bg, borderRadius: 5, overflow: 'hidden' },
  splitFill: { height: '100%', borderRadius: 5 },
  splitSide: { width: 38, fontSize: 11, color: colors.textFaint },

  chart: { flexDirection: 'row', height: 120, alignItems: 'flex-end', gap: spacing.sm },
  chartCol: { flex: 1, alignItems: 'center' },
  chartBars: { flexDirection: 'row', alignItems: 'flex-end', height: 100, gap: 2 },
  bar: { width: 10, borderTopLeftRadius: 3, borderTopRightRadius: 3, minHeight: 2 },
  chartLabel: { fontSize: 9, color: colors.textFaint, marginTop: 4 },
  legend: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.md },
  legendDot: { width: 8, height: 8, borderRadius: 4, marginLeft: spacing.sm },
  legendText: { fontSize: 11, color: colors.textMuted },

  thead: { borderBottomWidth: 1, borderBottomColor: colors.border },
  th: { fontSize: 11, color: colors.textFaint, fontWeight: '700', textTransform: 'uppercase' },
  tr: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    gap: spacing.sm,
  },
  trOwn: { backgroundColor: colors.accentSoft },
  td: { fontSize: 14, color: colors.textMuted },
  tdBold: { fontWeight: '700', color: colors.text },
  colNum: { width: 34, textAlign: 'right' },
  colGoals: { width: 24, textAlign: 'right' },
});

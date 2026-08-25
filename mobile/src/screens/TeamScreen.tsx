/** Eine Mannschaft im Detail: Tabelle, Spiele, Bilanz. */
import React, { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Match, TeamDetail } from '../api';
import {
  Card, Empty, ErrorBox, FormDots, Loading, MatchRow, SectionTitle, TournamentRow, isClub,
} from '../components';
import { colors, radius, spacing } from '../theme';
import { useApi } from '../useApi';

type Tab = 'tabelle' | 'turniere' | 'spiele' | 'bilanz';

export default function TeamScreen({ route, navigation }: { route: any; navigation: any }) {
  const { teamId } = route.params;
  const detail = useApi<TeamDetail>(`/teams/${teamId}`);
  const matches = useApi<Match[]>(`/teams/${teamId}/matches`);
  const [tab, setTab] = useState<Tab | null>(null);

  if (detail.loading) return <Loading />;
  if (detail.error) return <ErrorBox error={detail.error} onRetry={detail.reload} />;

  const d = detail.data!;
  // Kinderfussball hat keine Rangliste, dafuer Turniere - dann ist das der
  // sinnvolle erste Tab.
  const hasTournaments = d.tournaments.length > 0 && d.standings.length === 0;
  const tabs: Tab[] = hasTournaments ? ['turniere', 'spiele', 'bilanz'] : ['tabelle', 'spiele', 'bilanz'];
  const active = tab ?? tabs[0];
  const openMatch = (m: Match) => navigation.navigate('Spiel', { matchId: m.match_id });

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={
        <RefreshControl
          refreshing={detail.refreshing}
          onRefresh={() => {
            detail.refresh();
            matches.refresh();
          }}
        />
      }
    >
      <View style={styles.header}>
        <Text style={styles.league}>{d.team.league_name || 'Ohne Rangliste'}</Text>
        {d.position ? (
          <Text style={styles.position}>
            {d.position.rank}. Platz · {d.position.points} Punkte · {d.position.played} Spiele
          </Text>
        ) : (
          <Text style={styles.position}>Diese Kategorie wird ohne Rangliste gespielt.</Text>
        )}
        <View style={styles.formRow}>
          <Text style={styles.formLabel}>Form</Text>
          <FormDots form={d.summary.form_string} />
          {d.summary.streak.count > 1 ? (
            <Text style={styles.streak}>
              {d.summary.streak.count}×{' '}
              {d.summary.streak.kind === 'W' ? 'Sieg' : d.summary.streak.kind === 'L' ? 'Niederlage' : 'Remis'} in Folge
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.tabs}>
        {tabs.map((t) => (
          <Pressable key={t} style={[styles.tab, active === t && styles.tabActive]} onPress={() => setTab(t)}>
            <Text style={[styles.tabText, active === t && styles.tabTextActive]}>
              {t === 'tabelle' ? 'Tabelle' : t === 'turniere' ? 'Turniere' : t === 'spiele' ? 'Spiele' : 'Bilanz'}
            </Text>
          </Pressable>
        ))}
      </View>

      {active === 'tabelle' ? <StandingsTable rows={d.standings} /> : null}

      {active === 'turniere' ? (
        <>
          <Card>
            {d.tournaments.map((t) => (
              <TournamentRow key={t.tournament_id} tournament={t} />
            ))}
          </Card>
          <Text style={styles.pmfNote}>
            Im Kinderfussball wird nach «play more football» ohne Resultate und ohne Rangliste
            gespielt. Der Verband veröffentlicht deshalb nur Termine und Teilnehmer.
          </Text>
        </>
      ) : null}

      {active === 'spiele' ? (
        <Card>
          {matches.loading ? (
            <Loading label="…" />
          ) : matches.data?.length ? (
            matches.data.map((m) => <MatchRow key={m.match_id} match={m} onPress={() => openMatch(m)} />)
          ) : (
            <Empty>Für dieses Team sind keine Spiele erfasst.</Empty>
          )}
        </Card>
      ) : null}

      {active === 'bilanz' ? <Balance summary={d.summary} /> : null}

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function StandingsTable({ rows }: { rows: TeamDetail['standings'] }) {
  if (!rows.length) return <Empty>Für diese Kategorie gibt es keine Rangliste.</Empty>;
  return (
    <Card style={{ paddingHorizontal: spacing.sm }}>
      <View style={[styles.tr, styles.thead]}>
        <Text style={[styles.th, styles.colRank]}>#</Text>
        <Text style={[styles.th, styles.colTeam]}>Team</Text>
        <Text style={[styles.th, styles.colNum]}>Sp</Text>
        <Text style={[styles.th, styles.colGoals]}>Tore</Text>
        <Text style={[styles.th, styles.colNum]}>Pkt</Text>
      </View>
      {rows.map((r) => {
        const own = isClub(r.team);
        return (
          <View key={r.team} style={[styles.tr, own && styles.trOwn]}>
            <Text style={[styles.td, styles.colRank, own && styles.tdOwn]}>{r.rank}</Text>
            <Text numberOfLines={1} style={[styles.td, styles.colTeam, own && styles.tdOwn]}>
              {r.team}
            </Text>
            <Text style={[styles.td, styles.colNum, own && styles.tdOwn]}>{r.played}</Text>
            <Text style={[styles.td, styles.colGoals, own && styles.tdOwn]}>
              {r.goals_for}:{r.goals_against}
            </Text>
            <Text style={[styles.td, styles.colNum, styles.tdBold, own && styles.tdOwn]}>{r.points}</Text>
          </View>
        );
      })}
    </Card>
  );
}

function Balance({ summary }: { summary: TeamDetail['summary'] }) {
  const rows = [
    { label: 'Gesamt', t: summary.total },
    { label: 'Heim', t: summary.home },
    { label: 'Auswärts', t: summary.away },
  ];
  return (
    <>
      <Card style={{ paddingHorizontal: spacing.sm }}>
        <View style={[styles.tr, styles.thead]}>
          <Text style={[styles.th, styles.colTeam]} />
          <Text style={[styles.th, styles.colNum]}>Sp</Text>
          <Text style={[styles.th, styles.colNum]}>S</Text>
          <Text style={[styles.th, styles.colNum]}>U</Text>
          <Text style={[styles.th, styles.colNum]}>N</Text>
          <Text style={[styles.th, styles.colGoals]}>Tore</Text>
          <Text style={[styles.th, styles.colNum]}>Pkt</Text>
        </View>
        {rows.map((r) => (
          <View key={r.label} style={styles.tr}>
            <Text style={[styles.td, styles.colTeam, styles.tdBold]}>{r.label}</Text>
            <Text style={[styles.td, styles.colNum]}>{r.t.played}</Text>
            <Text style={[styles.td, styles.colNum]}>{r.t.won}</Text>
            <Text style={[styles.td, styles.colNum]}>{r.t.drawn}</Text>
            <Text style={[styles.td, styles.colNum]}>{r.t.lost}</Text>
            <Text style={[styles.td, styles.colGoals]}>
              {r.t.goals_for}:{r.t.goals_against}
            </Text>
            <Text style={[styles.td, styles.colNum, styles.tdBold]}>{r.t.points}</Text>
          </View>
        ))}
      </Card>

      <SectionTitle>Letzte Spiele</SectionTitle>
      <Card>
        {summary.form.length ? (
          summary.form.map((f) => (
            <View key={f.match_id} style={styles.formEntry}>
              <View
                style={[
                  styles.formBadge,
                  {
                    backgroundColor:
                      f.result === 'W' ? colors.win : f.result === 'L' ? colors.loss : colors.draw,
                  },
                ]}
              >
                <Text style={styles.formBadgeText}>
                  {f.result === 'W' ? 'S' : f.result === 'L' ? 'N' : 'U'}
                </Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.formOpponent}>
                  {f.side === 'home' ? 'gegen' : 'bei'} {f.opponent}
                </Text>
                <Text style={styles.formDate}>{f.date}</Text>
              </View>
              <Text style={styles.formScore}>{f.score}</Text>
            </View>
          ))
        ) : (
          <Empty>Noch keine Spiele gespielt.</Empty>
        )}
      </Card>
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: { backgroundColor: colors.dark, padding: spacing.lg },
  league: { color: '#fff', fontSize: 20, fontWeight: '800' },
  position: { color: colors.accentSoft, fontSize: 13, marginTop: 4, opacity: 0.85 },
  formRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  formLabel: { color: '#fff', fontSize: 12, opacity: 0.7 },
  streak: { color: colors.accentSoft, fontSize: 12, opacity: 0.85 },

  tabs: {
    flexDirection: 'row',
    margin: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.border,
    borderRadius: radius.sm,
    padding: 3,
  },
  tab: { flex: 1, paddingVertical: spacing.sm, alignItems: 'center', borderRadius: radius.sm - 2 },
  tabActive: { backgroundColor: colors.surface },
  tabText: { fontSize: 14, color: colors.textMuted, fontWeight: '600' },
  tabTextActive: { color: colors.text },

  thead: { borderBottomWidth: 1, borderBottomColor: colors.border },
  th: { fontSize: 11, color: colors.textFaint, fontWeight: '700', textTransform: 'uppercase' },
  tr: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  trOwn: { backgroundColor: colors.accentSoft },
  td: { fontSize: 14, color: colors.textMuted },
  tdOwn: { color: colors.text, fontWeight: '700' },
  tdBold: { fontWeight: '700', color: colors.text },
  colRank: { width: 24 },
  colTeam: { flex: 1, paddingRight: spacing.sm },
  colNum: { width: 30, textAlign: 'right' },
  colGoals: { width: 46, textAlign: 'right' },

  formEntry: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  formBadge: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  formBadgeText: { color: '#fff', fontWeight: '800', fontSize: 12 },
  formOpponent: { fontSize: 15, color: colors.text },
  formDate: { fontSize: 12, color: colors.textFaint },
  formScore: { fontSize: 16, fontWeight: '700', color: colors.text },
  pmfNote: {
    fontSize: 12,
    color: colors.textFaint,
    lineHeight: 17,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.md,
  },
});

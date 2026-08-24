/**
 * Startbildschirm: alles Wichtige zum FC Othmarsingen auf einen Blick.
 *
 * Reihenfolge nach dem, was man am Wochenende wirklich wissen will:
 * naechste Spiele -> letzte Resultate -> Stand aller Mannschaften.
 */
import React from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';

import { Match, Overview, Tournament } from '../api';
import {
  Card, Empty, ErrorBox, FormDots, Loading, MatchRow, SectionTitle, Stat, TournamentRow,
} from '../components';
import { colors, radius, spacing } from '../theme';
import { useApi } from '../useApi';

export default function HomeScreen({ navigation }: { navigation: any }) {
  const overview = useApi<Overview>('/api/stats/overview');
  const upcoming = useApi<Match[]>('/api/matches/upcoming?days=14');
  const recent = useApi<Match[]>('/api/matches/recent?limit=6');
  const tournaments = useApi<Tournament[]>('/api/tournaments/upcoming?days=21');

  const refreshAll = () => {
    overview.refresh();
    upcoming.refresh();
    recent.refresh();
    tournaments.refresh();
  };

  if (overview.loading) return <Loading />;
  if (overview.error) return <ErrorBox error={overview.error} onRetry={overview.reload} />;

  const data = overview.data!;
  const openMatch = (m: Match) => navigation.navigate('Spiel', { matchId: m.match_id });

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={overview.refreshing} onRefresh={refreshAll} />}
    >
      <View style={styles.hero}>
        <Text style={styles.heroClub}>{data.club}</Text>
        <Text style={styles.heroSeason}>Saison {data.season - 1}/{String(data.season).slice(2)}</Text>
        <View style={styles.heroStats}>
          <Stat value={data.total.played} label="Spiele" />
          <Stat value={data.total.won} label="Siege" />
          <Stat value={data.total.drawn} label="Remis" />
          <Stat value={data.total.lost} label="Nieder." />
          <Stat value={`${data.total.goals_for}:${data.total.goals_against}`} label="Tore" />
        </View>
      </View>

      <SectionTitle hint="nächste 14 Tage">Kommende Spiele</SectionTitle>
      <Card>
        {upcoming.loading ? (
          <Loading label="…" />
        ) : upcoming.data?.length ? (
          upcoming.data.map((m) => <MatchRow key={m.match_id} match={m} onPress={() => openMatch(m)} />)
        ) : (
          <Empty>In den nächsten 14 Tagen ist kein Spiel angesetzt.</Empty>
        )}
      </Card>

      <SectionTitle>Letzte Resultate</SectionTitle>
      <Card>
        {recent.loading ? (
          <Loading label="…" />
        ) : recent.data?.length ? (
          recent.data.map((m) => <MatchRow key={m.match_id} match={m} onPress={() => openMatch(m)} />)
        ) : (
          <Empty>Noch keine Resultate erfasst.</Empty>
        )}
      </Card>

      {tournaments.data?.length ? (
        <>
          <SectionTitle hint="Junioren E/F/G">Kommende Turniere</SectionTitle>
          <Card>
            {tournaments.data.map((t) => (
              <TournamentRow key={`${t.tournament_id}-${t.team_id}`} tournament={t} />
            ))}
          </Card>
        </>
      ) : null}

      <SectionTitle hint={`${data.teams.length} Mannschaften`}>Alle Teams</SectionTitle>
      {data.teams.map((t) => (
        <Pressable key={t.team_id} onPress={() => navigation.navigate('Team', { teamId: t.team_id, title: t.name })}>
          <Card style={styles.teamCard}>
            <View style={styles.teamInfo}>
              <Text style={styles.teamName}>{t.name}</Text>
              <Text style={styles.teamLeague}>{t.league_name || 'ohne Rangliste'}</Text>
            </View>
            <View style={styles.teamRight}>
              {t.position ? (
                <Text style={styles.rank}>
                  {t.position.rank}. <Text style={styles.rankPoints}>{t.position.points} Pkt</Text>
                </Text>
              ) : (
                <Text style={styles.rankNone}>–</Text>
              )}
              <FormDots form={t.form_string} />
            </View>
          </Card>
        </Pressable>
      ))}

      <Text style={styles.footer}>
        {data.quelle}
        {'\n'}
        {data.hinweis}
        {data.last_sync ? `\nStand: ${new Date(data.last_sync).toLocaleString('de-CH')}` : ''}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  hero: {
    backgroundColor: colors.dark,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  heroClub: { color: '#fff', fontSize: 26, fontWeight: '800' },
  heroSeason: { color: colors.accentSoft, fontSize: 13, marginTop: 2, opacity: 0.75 },
  heroStats: {
    flexDirection: 'row',
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
  },
  teamCard: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md },
  teamInfo: { flex: 1 },
  teamName: { fontSize: 16, fontWeight: '700', color: colors.text },
  teamLeague: { fontSize: 13, color: colors.textMuted, marginTop: 1 },
  teamRight: { alignItems: 'flex-end', gap: spacing.sm },
  rank: { fontSize: 15, fontWeight: '700', color: colors.accent },
  rankPoints: { fontSize: 13, fontWeight: '500', color: colors.textMuted },
  rankNone: { fontSize: 15, color: colors.textFaint },
  footer: {
    fontSize: 11,
    color: colors.textFaint,
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xl,
    lineHeight: 16,
  },
});

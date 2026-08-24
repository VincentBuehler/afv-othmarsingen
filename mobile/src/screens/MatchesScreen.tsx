/** Alle Spiele des Vereins - umschaltbar zwischen kommend und gespielt. */
import React, { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Match } from '../api';
import { Card, Empty, ErrorBox, Loading, MatchRow } from '../components';
import { colors, radius, spacing } from '../theme';
import { useApi } from '../useApi';

export default function MatchesScreen({ navigation }: { navigation: any }) {
  const [mode, setMode] = useState<'kommend' | 'resultate'>('kommend');
  const path =
    mode === 'kommend' ? '/api/matches/upcoming?days=60' : '/api/matches/recent?limit=50';
  const { data, loading, refreshing, error, reload, refresh } = useApi<Match[]>(path);

  // Spiele nach Datum gruppieren, damit man die Wochenenden erkennt.
  const groups = new Map<string, Match[]>();
  for (const m of data ?? []) {
    const key = m.kickoff_date ?? 'ohne Datum';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  return (
    <View style={styles.screen}>
      <View style={styles.switch}>
        {(['kommend', 'resultate'] as const).map((m) => (
          <Pressable
            key={m}
            style={[styles.switchItem, mode === m && styles.switchActive]}
            onPress={() => setMode(m)}
          >
            <Text style={[styles.switchText, mode === m && styles.switchTextActive]}>
              {m === 'kommend' ? 'Kommende Spiele' : 'Resultate'}
            </Text>
          </Pressable>
        ))}
      </View>

      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
        {loading ? <Loading /> : null}
        {error ? <ErrorBox error={error} onRetry={reload} /> : null}
        {!loading && !error && groups.size === 0 ? (
          <Empty>
            {mode === 'kommend'
              ? 'In den nächsten 60 Tagen ist kein Spiel angesetzt.'
              : 'Noch keine Resultate erfasst.'}
          </Empty>
        ) : null}

        {[...groups.entries()].map(([date, matches]) => (
          <Card key={date}>
            {matches.map((m) => (
              <MatchRow
                key={`${m.match_id}-${m.team_id}`}
                match={m}
                onPress={() => navigation.navigate('Spiel', { matchId: m.match_id })}
              />
            ))}
          </Card>
        ))}

        <View style={{ height: spacing.xl }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  switch: {
    flexDirection: 'row',
    margin: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.border,
    borderRadius: radius.sm,
    padding: 3,
  },
  switchItem: { flex: 1, paddingVertical: spacing.sm, alignItems: 'center', borderRadius: radius.sm - 2 },
  switchActive: { backgroundColor: colors.surface },
  switchText: { fontSize: 14, color: colors.textMuted, fontWeight: '600' },
  switchTextActive: { color: colors.text },
});

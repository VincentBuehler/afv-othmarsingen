/** Kleiner Hook fuer GET-Aufrufe mit Ladezustand, Fehler und Pull-to-Refresh. */
import { useCallback, useEffect, useState } from 'react';

import { api } from './api';

export type ApiState<T> = {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  reload: () => void;
  refresh: () => void;
};

export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        const result = await api<T>(path, controller.signal);
        if (!active) return;
        setData(result);
        setError(null);
      } catch (e) {
        // Ein abgebrochener Request ist kein Fehler, den der Nutzer sehen soll.
        if (!active || controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : 'Unbekannter Fehler');
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [path, tick]);

  const reload = useCallback(() => {
    setLoading(true);
    setTick((t) => t + 1);
  }, []);

  const refresh = useCallback(() => {
    setRefreshing(true);
    setTick((t) => t + 1);
  }, []);

  return { data, loading, refreshing, error, reload, refresh };
}

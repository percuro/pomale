import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { cacheGet, cacheSet } from '../lib/offline-store';
import { overlay } from '../lib/overlay';
import { syncEngine } from '../lib/sync-engine';
import type { DaysResponse } from '../lib/types';
import { useSession } from './useSession';
import { useSync } from './useSync';

export const DAYS_KEY = ['days'] as const;

async function fetchDays(from: string, to: string): Promise<DaysResponse> {
  const cacheKey = `days:${from}:${to}`;
  try {
    const data = await apiFetch<DaysResponse>(`/v1/days?from=${from}&to=${to}`);
    void cacheSet(cacheKey, data);
    return data;
  } catch (error) {
    // Offline: show the last loaded state
    if (error instanceof TypeError) {
      const cached = await cacheGet<DaysResponse>(cacheKey);
      if (cached) return { ...cached, offline: true };
    }
    throw error;
  }
}

/** Server data with pending local changes on top. */
export function useDays(from: string, to: string) {
  const { today } = useSession();
  const { ops } = useSync();
  const query = useQuery({
    queryKey: [...DAYS_KEY, from, to],
    queryFn: () => fetchDays(from, to),
    networkMode: 'always',
  });
  const data = useMemo(
    () => (query.data ? overlay(query.data, ops, today) : undefined),
    [query.data, ops, today],
  );
  return { ...query, data };
}

/** Set a state (never toggle); always goes through the change queue. */
export function setDay(habitId: number, date: string, done: boolean, knownVersion: number) {
  void syncEngine.setDay(habitId, date, done, knownVersion);
}

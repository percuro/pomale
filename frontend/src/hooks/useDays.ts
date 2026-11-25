import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { cacheGet, cacheSet, daysCacheKey } from '../lib/offline-store';
import { overlay } from '../lib/overlay';
import { syncEngine, type DayChange } from '../lib/sync-engine';
import type { DaysResponse } from '../lib/types';
import { useSession } from './useSession';
import { useSync } from './useSync';

export const DAYS_KEY = ['days'] as const;

async function fetchDays(userId: number, from: string, to: string): Promise<DaysResponse> {
  const cacheKey = daysCacheKey(userId, from, to);
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
  const { me, today } = useSession();
  const { ops } = useSync();
  const query = useQuery({
    queryKey: [...DAYS_KEY, me.id, from, to],
    queryFn: () => fetchDays(me.id, from, to),
    networkMode: 'always',
  });
  const data = useMemo(
    () => (query.data ? overlay(query.data, ops, today) : undefined),
    [query.data, ops, today],
  );
  return { ...query, data };
}

/** Set a state (never toggle); always goes through the change queue. */
export function setDay(habitId: number, date: string, change: boolean | DayChange, knownVersion: number) {
  void syncEngine.setDay(habitId, date, change, knownVersion);
}

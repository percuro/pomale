import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { HistoryResponse } from '../lib/types';
import { useSession } from './useSession';

export const HISTORY_KEY = ['history'] as const;

/** Quota and weekly values (all habits) or every day (one habit); needs the server. */
export function useHistory(from: string, to: string, habitId: number | null) {
  const { me } = useSession();
  const params = new URLSearchParams({ from, to });
  if (habitId !== null) params.set('habit_id', String(habitId));
  return useQuery({
    queryKey: [...HISTORY_KEY, me.id, from, to, habitId],
    queryFn: () => apiFetch<HistoryResponse>(`/v1/history?${params}`),
  });
}

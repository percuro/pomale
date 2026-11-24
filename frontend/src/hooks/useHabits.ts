import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Habit } from '../lib/types';
import { DAYS_KEY } from './useDays';

export const HABITS_KEY = ['habits'] as const;

export function useHabits() {
  return useQuery({
    queryKey: HABITS_KEY,
    queryFn: () => apiFetch<Habit[]>('/v1/habits?include_archived=true'),
  });
}

export interface HabitInput {
  name: string;
  cue: string | null;
  weekdays: number;
  start_on?: string;
}

type Action =
  | { type: 'create'; body: HabitInput }
  | { type: 'update'; id: number; body: { name?: string; cue?: string | null; sort_order?: number } }
  | { type: 'schedule'; id: number; body: { weekdays: number; valid_from?: string } }
  | { type: 'archive'; id: number }
  | { type: 'unarchive'; id: number };

function request(action: Action): Promise<Habit> {
  switch (action.type) {
    case 'create':
      return apiFetch<Habit>('/v1/habits', { method: 'POST', body: JSON.stringify(action.body) });
    case 'update':
      return apiFetch<Habit>(`/v1/habits/${action.id}`, { method: 'PATCH', body: JSON.stringify(action.body) });
    case 'schedule':
      return apiFetch<Habit>(`/v1/habits/${action.id}/schedule`, { method: 'PUT', body: JSON.stringify(action.body) });
    case 'archive':
      return apiFetch<Habit>(`/v1/habits/${action.id}/archive`, { method: 'POST' });
    case 'unarchive':
      return apiFetch<Habit>(`/v1/habits/${action.id}/unarchive`, { method: 'POST' });
  }
}

export function useHabitAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: HABITS_KEY });
      await queryClient.invalidateQueries({ queryKey: DAYS_KEY });
    },
  });
}

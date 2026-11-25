import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { GoalType, Habit, HabitColor } from '../lib/types';
import { DAYS_KEY } from './useDays';
import { HISTORY_KEY } from './useHistory';

export const HABITS_KEY = ['habits'] as const;

export function useHabits() {
  return useQuery({
    queryKey: HABITS_KEY,
    queryFn: () => apiFetch<Habit[]>('/v1/habits?include_archived=true'),
  });
}

export interface Goal {
  goal_type: GoalType;
  target: number | null;
  weekdays: number;
}

export interface HabitInput extends Goal {
  name: string;
  cue: string | null;
  unit: string | null;
  color: HabitColor | null;
  group_id: number | null;
  reminders: string[];
  start_on?: string;
}

export interface HabitUpdate {
  name?: string;
  cue?: string | null;
  unit?: string | null;
  color?: HabitColor | null;
  group_id?: number | null;
  reminders?: string[];
}

type Action =
  | { type: 'create'; body: HabitInput }
  | { type: 'update'; id: number; body: HabitUpdate }
  | { type: 'schedule'; id: number; body: Goal & { valid_from?: string } }
  | { type: 'order'; items: { id: number; group_id: number | null }[] }
  | { type: 'archive'; id: number }
  | { type: 'unarchive'; id: number };

function request(action: Action): Promise<Habit | Habit[]> {
  switch (action.type) {
    case 'create':
      return apiFetch<Habit>('/v1/habits', { method: 'POST', body: JSON.stringify(action.body) });
    case 'update':
      return apiFetch<Habit>(`/v1/habits/${action.id}`, { method: 'PATCH', body: JSON.stringify(action.body) });
    case 'schedule':
      return apiFetch<Habit>(`/v1/habits/${action.id}/schedule`, { method: 'PUT', body: JSON.stringify(action.body) });
    case 'order':
      return apiFetch<Habit[]>('/v1/habits/order', { method: 'PUT', body: JSON.stringify({ habits: action.items }) });
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
      await queryClient.invalidateQueries({ queryKey: HISTORY_KEY });
    },
  });
}

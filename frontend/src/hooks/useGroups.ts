import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Group, Pause } from '../lib/types';
import { DAYS_KEY } from './useDays';
import { HABITS_KEY } from './useHabits';
import { HISTORY_KEY } from './useHistory';

export const GROUPS_KEY = ['groups'] as const;
export const PAUSES_KEY = ['pauses'] as const;

export function useGroups() {
  return useQuery({ queryKey: GROUPS_KEY, queryFn: () => apiFetch<Group[]>('/v1/groups') });
}

export function usePauses() {
  return useQuery({ queryKey: PAUSES_KEY, queryFn: () => apiFetch<Pause[]>('/v1/pauses') });
}

export type PauseInput = Omit<Pause, 'id'>;

type Action =
  | { type: 'createGroup'; name: string }
  | { type: 'renameGroup'; id: number; name: string }
  | { type: 'deleteGroup'; id: number }
  | { type: 'orderGroups'; ids: number[] }
  | { type: 'createPause'; body: PauseInput }
  | { type: 'deletePause'; id: number };

function request(action: Action): Promise<unknown> {
  const json = (body: unknown) => JSON.stringify(body);
  switch (action.type) {
    case 'createGroup':
      return apiFetch('/v1/groups', { method: 'POST', body: json({ name: action.name }) });
    case 'renameGroup':
      return apiFetch(`/v1/groups/${action.id}`, { method: 'PATCH', body: json({ name: action.name }) });
    case 'deleteGroup':
      return apiFetch(`/v1/groups/${action.id}`, { method: 'DELETE' });
    case 'orderGroups':
      return apiFetch('/v1/groups/order', { method: 'PUT', body: json({ ids: action.ids }) });
    case 'createPause':
      return apiFetch('/v1/pauses', { method: 'POST', body: json(action.body) });
    case 'deletePause':
      return apiFetch(`/v1/pauses/${action.id}`, { method: 'DELETE' });
  }
}

/** Groups and pauses change what today, week and history show: reload them all. */
export function useGroupAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSettled: async () => {
      await Promise.all(
        [GROUPS_KEY, PAUSES_KEY, HABITS_KEY, DAYS_KEY, HISTORY_KEY].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
    },
  });
}

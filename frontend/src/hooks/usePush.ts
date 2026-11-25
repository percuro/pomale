import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { PushConfig, PushDevice } from '../lib/types';

export const PUSH_CONFIG_KEY = ['push', 'config'] as const;
export const PUSH_DEVICES_KEY = ['push', 'devices'] as const;

export function usePushConfig() {
  return useQuery({
    queryKey: PUSH_CONFIG_KEY,
    queryFn: () => apiFetch<PushConfig>('/v1/push/config'),
    staleTime: Infinity,
  });
}

export function usePushDevices(enabled: boolean) {
  return useQuery({
    queryKey: PUSH_DEVICES_KEY,
    queryFn: () => apiFetch<PushDevice[]>('/v1/push/subscriptions'),
    enabled,
  });
}

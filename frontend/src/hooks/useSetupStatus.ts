import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';

/** Whether the instance still needs its first account (first-run setup). */
export function useSetupStatus() {
  return useQuery({
    queryKey: ['setup'],
    queryFn: () => apiFetch<{ needed: boolean }>('/v1/setup'),
    retry: false,
    staleTime: Infinity,
  });
}

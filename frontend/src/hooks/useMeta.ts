import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Meta } from '../lib/types';

/** Public facts: version, registration mode, whether the first-run setup is still needed. */
export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: () => apiFetch<Meta>('/v1/meta'),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

/** A public demo (DEMO_MODE): actions that would spoil it for the next visitor are hidden. */
export function useDemo(): boolean {
  return useMeta().data?.demo != null;
}

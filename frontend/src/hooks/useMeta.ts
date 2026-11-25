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

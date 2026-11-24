import { useQuery } from '@tanstack/react-query';
import { ApiError, apiFetch } from '../lib/api';
import { cacheGet, cacheSet } from '../lib/offline-store';
import type { Me } from '../lib/types';

export const ME_KEY = ['me'] as const;

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        const me = await apiFetch<Me>('/v1/auth/me');
        void cacheSet('me', me);
        return me;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        // Offline: start with the last logged-in account
        if (error instanceof TypeError) {
          const cached = await cacheGet<Me>('me');
          if (cached) return cached;
        }
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
    networkMode: 'always',
  });
}

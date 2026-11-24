import { useQuery, type QueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch } from '../lib/api';
import { cacheGet, cacheSet, clearAccountCache } from '../lib/offline-store';
import { syncEngine } from '../lib/sync-engine';
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

/** After login, setup, accepting an invitation or registering: start clean for this account. */
export async function signedIn(queryClient: QueryClient, me: Me): Promise<void> {
  // Day lists of another account that used this device are dropped; its unsent changes stay queued
  await clearAccountCache(me.id);
  await cacheSet('me', me);
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
  queryClient.setQueryData(ME_KEY, me);
}

/** After logout: forget the account on this device, but keep its unsent changes. */
export async function signedOut(queryClient: QueryClient): Promise<void> {
  await clearAccountCache();
  syncEngine.setOwner(null);
  queryClient.clear();
  queryClient.setQueryData(ME_KEY, null);
}

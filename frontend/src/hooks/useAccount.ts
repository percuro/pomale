import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { cacheSet } from '../lib/offline-store';
import type { Locale, Me } from '../lib/types';
import { ME_KEY } from './useMe';

export interface AccountUpdate {
  display_name?: string | null;
  timezone?: string | null;
  locale?: Locale | null;
  day_end_hour?: number;
}

/** PATCH /account; the new "me" replaces the cached one (time zone and language apply at once). */
export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AccountUpdate) => apiFetch<Me>('/v1/account', { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: async (me) => {
      void cacheSet('me', me);
      queryClient.setQueryData(ME_KEY, me);
      // "Today" may have moved with the time zone or the day end
      await queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
    },
  });
}

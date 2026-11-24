import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      // Refetch when returning to the app (changes from other devices)
      refetchOnWindowFocus: true,
    },
  },
});

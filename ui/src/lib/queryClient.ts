import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,          // D-09: user controls freshness via Refresh button
      refetchOnWindowFocus: false,  // D-09: no auto-refresh on focus
    },
  },
});

import { useQuery } from '@tanstack/react-query';
import { fetchResources, type Resource } from '../lib/api';

export function useResources(team: string | null) {
  return useQuery<Resource[]>({
    queryKey: ['resources', team],
    queryFn: () => fetchResources(team!),
    enabled: !!team,
  });
}

import { useQuery } from '@tanstack/react-query';
import { fetchTeams, type Team } from '../lib/api';

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ['teams'],
    queryFn: fetchTeams,
  });
}

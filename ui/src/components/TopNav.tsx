import { RefreshCw } from 'lucide-react';
import { useQueryClient, useIsFetching } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTeams } from '../hooks/useTeams';

interface TopNavProps {
  selectedTeam: string | null;
  onTeamChange: (team: string | null) => void;
  activeTabQueryKey: unknown[];
}

export function TopNav({ selectedTeam, onTeamChange, activeTabQueryKey }: TopNavProps) {
  const queryClient = useQueryClient();
  const { data: teams, isLoading: teamsLoading } = useTeams();
  const isFetching = useIsFetching({ queryKey: activeTabQueryKey as string[] }) > 0;

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: activeTabQueryKey as string[] });
  };

  return (
    <header className="h-14 border-b border-border bg-card flex items-center px-6 gap-4">
      {/* Logo */}
      <span className="text-xl font-semibold select-none">PECP</span>

      {/* Team dropdown */}
      <div className="flex items-center gap-2">
        <Select
          value={selectedTeam ?? undefined}
          onValueChange={onTeamChange}
          disabled={teamsLoading}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder={teamsLoading ? 'Loading teams...' : 'Select a team'} />
          </SelectTrigger>
          <SelectContent>
            {(teams ?? []).map((team) => (
              <SelectItem key={team.id} value={team.name}>
                {team.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Refresh button */}
      <Button onClick={handleRefresh} disabled={isFetching} variant="default">
        <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
        Refresh
      </Button>
    </header>
  );
}

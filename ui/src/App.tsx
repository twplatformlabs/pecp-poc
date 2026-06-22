import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TopNav } from './components/TopNav';
import { InventoryTable } from './components/InventoryTable';
import { DeploymentsTable } from './components/DeploymentsTable';
import { useTeams } from './hooks/useTeams';
import { useResources } from './hooks/useResources';

function App() {
  const [activeTab, setActiveTab] = useState<'inventory' | 'deployments'>('inventory');
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);

  const { data: teams } = useTeams();
  const { data: resources, isLoading, isError } = useResources(selectedTeam);

  // Auto-select the first team alphabetically on initial load (UI-SPEC Interaction Contract)
  useEffect(() => {
    if (teams && teams.length > 0 && selectedTeam === null) {
      const sorted = [...teams].sort((a, b) => a.name.localeCompare(b.name));
      setSelectedTeam(sorted[0].name);
    }
  }, [teams, selectedTeam]);

  const activeTabQueryKey = ['resources', selectedTeam];

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <TopNav
        selectedTeam={selectedTeam}
        onTeamChange={setSelectedTeam}
        activeTabQueryKey={activeTabQueryKey}
      />

      <div className="flex-1 p-6 max-w-screen-xl mx-auto w-full">
        {/* No-team-selected state */}
        {!selectedTeam && (
          <div className="flex items-center justify-center h-64">
            <p className="text-sm text-muted-foreground">
              Select a team from the dropdown to view its resources.
            </p>
          </div>
        )}

        {selectedTeam && (
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as 'inventory' | 'deployments')}
          >
            <TabsList className="mb-4">
              <TabsTrigger value="inventory">Inventory</TabsTrigger>
              <TabsTrigger value="deployments">Deployments</TabsTrigger>
            </TabsList>

            <TabsContent value="inventory">
              <InventoryTable
                resources={resources ?? []}
                isLoading={isLoading}
                isError={isError}
              />
            </TabsContent>

            <TabsContent value="deployments">
              <DeploymentsTable
                resources={resources ?? []}
                isLoading={isLoading}
                isError={isError}
              />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </div>
  );
}

export default App;

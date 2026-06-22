// TypeScript types matching the FastAPI response shapes
export interface Team {
  id: string;
  name: string;
}

export interface Resource {
  id: string;
  team: string;
  kind: string;
  name: string;
  status: string;
  env: string | null;
  project: string | null;
  created_at?: string;
}

// All fetch calls use relative /api path — Vite proxy strips prefix (Pitfall 2)

export async function fetchTeams(): Promise<Team[]> {
  const res = await fetch('/api/teams?limit=50');
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchResources(team: string): Promise<Resource[]> {
  const res = await fetch(`/api/resources?team=${encodeURIComponent(team)}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

# Phase 5: Account Flow + UI + Demo Readiness - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 11 new/modified files
**Analogs found:** 8 / 11 (3 UI files are greenfield with no codebase analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pecp/cli/main.py` | CLI command group | request-response | `src/pecp/cli/main.py` lines 558–602 (`project_app`) | exact |
| `src/pecp/api/main.py` | config/middleware | request-response | `src/pecp/api/main.py` (existing) | exact |
| `src/pecp/api/routes/teams.py` | route handler | CRUD | `src/pecp/api/routes/resources.py` `list_resources` (lines 76–110) | exact |
| `scripts/seed.py` | utility/script | batch | `src/pecp/api/routes/teams.py` `create_team` (lines 48–76) + `src/pecp/persistence/database.py` | role-match |
| `ui/src/App.tsx` | component | request-response | no analog (greenfield React) | none |
| `ui/src/components/TopNav.tsx` | component | event-driven | no analog (greenfield React) | none |
| `ui/src/components/StatusBadge.tsx` | component | transform | no analog (greenfield React) | none |
| `ui/src/components/InventoryTable.tsx` | component | request-response | no analog (greenfield React) | none |
| `ui/src/components/DeploymentsTable.tsx` | component | request-response | no analog (greenfield React) | none |
| `ui/src/hooks/useTeams.ts` | hook | request-response | no analog (greenfield React) | none |
| `ui/src/hooks/useResources.ts` | hook | request-response | no analog (greenfield React) | none |
| `ui/src/lib/queryClient.ts` | config | — | no analog (greenfield React) | none |
| `ui/src/lib/api.ts` | utility | request-response | no analog (greenfield React) | none |

---

## Pattern Assignments

### `src/pecp/cli/main.py` — add `account_app` sub-Typer (CLI command group, request-response)

**Analog:** `src/pecp/cli/main.py` — `project_app` pattern (lines 558–602)

**Sub-app declaration pattern** (lines 558–602):
```python
project_app = typer.Typer(help="Manage PECP projects")

@project_app.command("create")
def project_create(
    name: str = typer.Argument(..., help="Project name"),
    team: str = typer.Option(..., "--team", help="Team that owns this project"),
    envs: str = typer.Option(..., "--env", help="Comma-separated list of environments"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
    api_url: str | None = typer.Option(None, "--api-url", help="..."),
) -> None:
    """Create a new project for a team (D-06)."""
    base = _resolve_base_url(api_url)
    # ... build body, POST, handle response
    console.print(f"Project {data['name']} created (id: {data['id']})")

app.add_typer(project_app, name="project")
```

**URL resolution pattern** (lines 50–53) — copy verbatim for all new commands:
```python
def _resolve_base_url(api_url: str | None) -> str:
    base = api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"
    return base.rstrip("/")
```

**HTTP POST with error handling** (lines 92–112) — template for `account_create`:
```python
try:
    response = httpx.post(
        f"{base}/resources",
        params=params,
        headers={"Content-Type": "application/x-yaml"},
        content=yaml_bytes,
        timeout=10.0,
    )
except httpx.RequestError as exc:
    console.print(f"[red]Connection error[/red]: {exc}")
    raise typer.Exit(code=1) from exc

if response.status_code == 202:
    result = response.json()
    console.print(
        f"[green]Applied[/green] {result['kind']} {result['name']}"
        f" → id={result['id']} status={result['status']}"
    )
else:
    console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
    raise typer.Exit(code=1)
```

**Two-step list-then-detail lookup pattern** (lines 182–214) — template for `account_status` and `account_login`:
```python
# Step 1: list lookup to find the resource id
list_response = httpx.get(
    f"{base}/resources",
    params={"team": team, "kind": kind},
    timeout=10.0,
)
records = list_response.json()
record_id: str | None = None
for record in records:
    if record["name"] == name and record["kind"] == kind:
        record_id = record["id"]
        break

if record_id is None:
    console.print(f"[red]Not found[/red]: {kind} {name} in team {team}")
    raise typer.Exit(code=1)

# Step 2: fetch full detail
detail_response = httpx.get(f"{base}/resources/{record_id}", timeout=10.0)
detail = detail_response.json()
```

**`status_badge` and Rich table pattern** (lines 220–239) — copy for `account_status` status panel:
```python
table = Table(title=f"{kind}: {name}")
table.add_column("Field")
table.add_column("Value")

for field in ["id", "kind", "name", "status", "env", "created_at"]:
    value = detail.get(field)
    if field == "status":
        table.add_row(field, status_badge(str(detail["status"])))
    elif value is None:
        table.add_row(field, "—")
    else:
        table.add_row(field, str(value))

console.print(table)

notes = detail.get("notes", [])
if notes:
    console.print("\n[bold]Notes:[/bold]")
    for note in notes:
        console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")
```

**`--json` flag pattern** (lines 144–147) — copy to all data-returning account commands:
```python
if json_output:
    print(json.dumps(resources))
    return
```

**Registration line** (line 602) — new command group registers as `create` (verified safe: no existing `@app.command("create")`):
```python
app.add_typer(account_app, name="create")
```

**Key differences for `account_app` vs `project_app`:**
- No `_TeamDefaultGroup` override needed — all three commands take explicit `--team` flag
- `account_create`: builds YAML internally if `-f` not provided (name defaults to `pecp-<team>`)
- `account_status`: adds `--watch` flag with `time.sleep(2)` polling loop
- `account_login`: reads `provider_metadata` from detail, prints env-var export lines, exits with code 2 if not ready
- Import `import time` and `from datetime import datetime` needed for `--watch` polling

---

### `src/pecp/api/main.py` — add CORS middleware (config, request-response)

**Analog:** `src/pecp/api/main.py` (existing, lines 1–33)

**Existing app structure** (lines 23–33) — CORS middleware inserts between `app = FastAPI(...)` and `app.include_router(...)` calls:
```python
app = FastAPI(
    title="PECP Control Plane",
    version="0.1.0",
    lifespan=lifespan,
)

# ADD CORS HERE — before all include_router calls (Pitfall 7)
app.include_router(resources.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(deployments.router)
```

**CORS middleware to add** (pattern from RESEARCH.md, `fastapi.middleware.cors`):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### `src/pecp/api/routes/teams.py` — add `GET /teams` list endpoint (route handler, CRUD)

**Analog:** `src/pecp/api/routes/resources.py` — `list_resources` (lines 76–110)

**Imports already in `teams.py`** (lines 1–20) — reuse all, no new imports needed:
```python
from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select
from pecp.api.dependencies import ContextDep
from pecp.persistence.database import SessionDep
from pecp.persistence.models import TeamRecord
```

**List handler pattern from `resources.py`** (lines 76–110) — adapt for teams:
```python
@router.get("")
async def list_resources(
    team: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    stmt = select(ResourceRecord).where(...)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [{"id": row.id, ...} for row in rows]
```

**Adapted for `GET /teams`** — insert BEFORE existing `@router.get("/{name}")` handler (line 79 in teams.py):
```python
@router.get("")
async def list_teams(
    limit: int = 50,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    """Return all teams for dashboard dropdown. GET /teams?limit=50."""
    result = await session.execute(select(TeamRecord).limit(limit))
    rows = result.scalars().all()
    return [{"id": r.id, "name": r.name} for r in rows]
```

**Note:** Return only `id` and `name` — the dashboard dropdown only needs these. No members list (avoids N+1 query).

---

### `scripts/seed.py` — new standalone async seed script (utility/batch)

**Analog:** `src/pecp/api/routes/teams.py` `create_team` (lines 48–76) + `src/pecp/persistence/database.py` `AsyncSessionLocal`

**Session factory import** (from `src/pecp/persistence/database.py`, lines 26–28):
```python
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
```

**ORM row construction pattern** (from `teams.py` lines 60–69):
```python
team_id = uuid.uuid4().hex
now = datetime.now(timezone.utc)
team = TeamRecord(id=team_id, name=body.name, owner_id=body.owner, created_at=now)
member = TeamMemberRecord(
    team_id=team_id,
    user_id=body.owner,
    role="owner",
    joined_at=now,
)
session.add(team)
session.add(member)
await session.commit()
```

**Idempotency check pattern** (from `teams.py` lines 90–93 and `resources.py` lines 148–156):
```python
result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
existing = result.scalar_one_or_none()
if existing:
    return existing  # skip — already seeded
```

**`asyncio.run` entry point pattern** — standard Python async script:
```python
import asyncio
import sys
from pathlib import Path

# Ensure src/ on path when run from repo root without pip install -e .
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pecp.persistence.database import AsyncSessionLocal
from pecp.persistence.models import (
    DeploymentRecord, ProjectRecord, ResourceRecord, TeamMemberRecord, TeamRecord,
)
from sqlalchemy.future import select

async def main() -> None:
    async with AsyncSessionLocal() as session:
        # ... idempotent inserts ...
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
```

**Notes column pattern** (from `resources.py` lines 353–361) — inject notes directly as JSON:
```python
import json

notes = [
    {"author": "pe-admin", "timestamp": "2026-06-22 09:00", "text": "[PE team] Account provisioning request received — routing to AWS Organizations"},
    {"author": "pe-admin", "timestamp": "2026-06-22 09:05", "text": "[PE team] Account creation in progress, expected 10-15 min"},
]
record.notes = json.dumps(notes)
```

**`provider_metadata` shape** (from `src/pecp/adapters/mock/aws_account.py` lines 25–33) — must match exactly for `pecp login awsaccount` to work:
```python
provider_metadata = {
    "account_id": "123456789012",
    "account_email": "aws+customer-product-app@example.com",
    "account_name": "pecp-customer-product-app",
    "management_console_url": "https://console.aws.amazon.com/switch-role?account=123456789012",
}
record.provider_metadata = json.dumps(provider_metadata)
```

**`ResourceRecord` field list** (from `src/pecp/persistence/models.py` lines 24–52) — all required fields for direct insert:
```python
record = ResourceRecord(
    id=uuid.uuid4().hex,
    team="customer-product-app",
    kind="PECPAccount",
    name="pecp-customer-product-app",
    status="provisioning",          # D-14: seeded in provisioning for demo
    spec_json='{"apiVersion":"pecp/v1","kind":"PECPAccount","metadata":{"name":"pecp-customer-product-app","team":"customer-product-app"},"spec":{}}',
    env="prod",
    project="cpa-core",
    notes=json.dumps([...]),        # D-13: PE notes
    provider_metadata=json.dumps({}),
    activity_log=json.dumps([]),
)
```

---

## UI Files — Greenfield (No Codebase Analog)

All UI files are new React/TypeScript. Patterns come from RESEARCH.md and UI-SPEC.md.

### `ui/src/lib/queryClient.ts` (config)

**Pattern source:** RESEARCH.md Pattern 3 (lines 347–360)

```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,         // D-09: user controls freshness via Refresh button
      refetchOnWindowFocus: false, // D-09: no auto-refresh on focus
    },
  },
});
```

---

### `ui/src/lib/api.ts` (utility, request-response)

**Pattern source:** RESEARCH.md Code Examples (lines 606–628)

```typescript
// All fetch calls use relative /api path — Vite proxy strips prefix (Pitfall 2)
export async function fetchResources(team: string): Promise<Resource[]> {
  const res = await fetch(`/api/resources?team=${encodeURIComponent(team)}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchTeams(): Promise<Team[]> {
  const res = await fetch('/api/teams?limit=50');
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

---

### `ui/src/hooks/useResources.ts` (hook, request-response)

**Pattern source:** RESEARCH.md Pattern 3 (lines 362–378) — v5 object-only signature:

```typescript
import { useQuery } from '@tanstack/react-query';

export function useResources(team: string | null) {
  return useQuery<Resource[]>({
    queryKey: ['resources', team],   // invalidate by ['resources', team] on refresh
    queryFn: async () => {
      const res = await fetch(`/api/resources?team=${encodeURIComponent(team!)}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    },
    enabled: !!team,    // do not fetch until team is selected
  });
}
```

---

### `ui/src/hooks/useTeams.ts` (hook, request-response)

**Pattern source:** RESEARCH.md Pattern 3 — same v5 object form as `useResources`:

```typescript
import { useQuery } from '@tanstack/react-query';

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ['teams'],
    queryFn: async () => {
      const res = await fetch('/api/teams?limit=50');
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    },
  });
}
```

---

### `ui/src/components/StatusBadge.tsx` (component, transform)

**Pattern source:** RESEARCH.md Code Examples (lines 631–650) + UI-SPEC.md Status Badge Color Palette

```typescript
// Colors match CLI STATUS_COLORS exactly (CONTEXT.md code_context)
const STATUS_CLASSES: Record<string, string> = {
  pending:      'bg-amber-100 text-amber-700',
  provisioning: 'bg-blue-100 text-blue-700',
  ready:        'bg-green-100 text-green-700',
  failed:       'bg-red-100 text-red-700',
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_CLASSES[status] ?? 'bg-slate-100 text-slate-600';
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
```

**Do NOT use shadcn `<Badge variant=...>` — use className override or inline span** (UI-SPEC.md badge anatomy section).

---

### `ui/src/components/InventoryTable.tsx` (component, request-response)

**Pattern source:** UI-SPEC.md Inventory Tab Layout + RESEARCH.md Standard Stack

Shadcn components to import:
```typescript
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from './StatusBadge';
```

Column order per UI-SPEC: Name, Kind, Status, Environment, Project

Loading state: 3 skeleton rows using `<Skeleton className="h-4 w-full" />`

Empty state: centered `PackageOpen` icon (48px, `text-muted-foreground`) + "No resources found" heading

Error state: centered `AlertCircle` icon (48px, `text-destructive`) + "Failed to load resources" heading

---

### `ui/src/components/DeploymentsTable.tsx` (component, request-response)

**Pattern source:** UI-SPEC.md Deployments Tab Layout — same table as InventoryTable plus env filter

Client-side filter pattern:
```typescript
const [envFilter, setEnvFilter] = useState<string>('All');
const filtered = resources.filter(r =>
  envFilter === 'All' || r.env === envFilter
);
```

Shadcn Select for environment filter:
```typescript
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
```

---

### `ui/src/components/TopNav.tsx` (component, event-driven)

**Pattern source:** UI-SPEC.md Interaction Contract (Team Dropdown + Refresh Button)

Refresh button pattern (from RESEARCH.md Pattern 3 lines 373–377):
```typescript
import { useQueryClient } from '@tanstack/react-query';
const queryClient = useQueryClient();
const handleRefresh = () => {
  queryClient.invalidateQueries({ queryKey: ['resources', selectedTeam] });
};
```

Refresh button spin during fetch:
```typescript
<Button onClick={handleRefresh} disabled={isFetching}>
  <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
  Refresh
</Button>
```

---

### `ui/src/App.tsx` (component, request-response)

**Pattern source:** UI-SPEC.md Layout Structure + RESEARCH.md Architecture Patterns

Outer layout:
```typescript
// min-h-screen flex flex-col bg-background
// TopNav fixed at top (h-14 border-b)
// Tabs component below nav (h-10 border-b)
// Content area: flex-1 p-6 max-w-screen-xl mx-auto w-full
```

Tab state — local `useState`, NOT React Router (D-07):
```typescript
const [activeTab, setActiveTab] = useState<'inventory' | 'deployments'>('inventory');
```

QueryClientProvider wrapping in `main.tsx`:
```typescript
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
```

---

## Shared Patterns

### Error handling — CLI commands
**Source:** `src/pecp/cli/main.py` lines 100–112
**Apply to:** `account_create`, `account_status`, `account_login`
```python
except httpx.RequestError as exc:
    console.print(f"[red]Connection error[/red]: {exc}")
    raise typer.Exit(code=1) from exc

if response.status_code != 200:  # or 202 for POST
    console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
    raise typer.Exit(code=1)
```

### `--json` flag pattern
**Source:** `src/pecp/cli/main.py` lines 144–147
**Apply to:** `account_status`, `account_login`
```python
json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout")
# ...
if json_output:
    print(json.dumps(data))
    return
```

### `--api-url` flag pattern
**Source:** `src/pecp/cli/main.py` lines 77–81 (every command)
**Apply to:** all three account commands
```python
api_url: str | None = typer.Option(
    None,
    "--api-url",
    help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
)
```

### Async route handler signature
**Source:** `src/pecp/api/routes/teams.py` lines 48–53, `src/pecp/api/routes/resources.py` lines 76–82
**Apply to:** new `GET /teams` list endpoint
```python
async def handler_name(
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> ...:
```

### SQLAlchemy select + scalars pattern
**Source:** `src/pecp/api/routes/teams.py` lines 90–93
**Apply to:** `list_teams`, `scripts/seed.py` idempotency checks
```python
result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
team = result.scalar_one_or_none()
```

### ORM row creation + commit
**Source:** `src/pecp/api/routes/teams.py` lines 60–76
**Apply to:** `scripts/seed.py` all inserts
```python
session.add(record)
await session.commit()
```

### Vite proxy configuration
**Source:** RESEARCH.md Code Examples (lines 562–587) — no codebase analog exists
**Apply to:** `ui/vite.config.ts`
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
},
```

---

## No Analog Found

Files with no close match in the codebase (use RESEARCH.md patterns and UI-SPEC.md):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `ui/src/App.tsx` | component | request-response | No React code in codebase — first UI file |
| `ui/src/components/TopNav.tsx` | component | event-driven | No React code in codebase |
| `ui/src/components/StatusBadge.tsx` | component | transform | No React code in codebase |
| `ui/src/components/InventoryTable.tsx` | component | request-response | No React code in codebase |
| `ui/src/components/DeploymentsTable.tsx` | component | request-response | No React code in codebase |
| `ui/src/hooks/useTeams.ts` | hook | request-response | No React code in codebase |
| `ui/src/hooks/useResources.ts` | hook | request-response | No React code in codebase |
| `ui/src/lib/queryClient.ts` | config | — | No React code in codebase |
| `ui/src/lib/api.ts` | utility | request-response | No React code in codebase |

**Resolution:** UI-SPEC.md is the implementation contract for all visual/interaction decisions. RESEARCH.md Code Examples section (lines 347–650) provides the TypeScript patterns. No additional codebase research needed.

---

## Critical Constraints to Carry Forward

1. **`STATUS_COLORS` mapping** — `src/pecp/cli/main.py` lines 37–42. UI badge colors must match: pending=amber, provisioning=blue, ready=green, failed=red.
2. **`provider_metadata` field names** — `src/pecp/adapters/mock/aws_account.py` lines 25–33: `account_id`, `account_email`, `account_name`, `management_console_url`. These are the exact keys `pecp status awsaccount` and `pecp login awsaccount` must read.
3. **No `app.add_typer(account_app, name="create")` conflict** — verified: current `main.py` has no top-level `create` command; safe to register.
4. **CORS before routers** — `app.add_middleware(CORSMiddleware, ...)` must appear before all `app.include_router(...)` calls in `main.py`.
5. **TanStack Query v5 object form** — `useQuery({ queryKey, queryFn })` only. Positional form is v4 and will throw TypeScript error.
6. **`yaml.safe_load` only** — enforced throughout codebase. `account_create` internal YAML build uses `yaml.dump()` on client side; server receives and parses with existing `safe_load` in `create_resource`.
7. **`scripts/seed.py` must be run from repo root** — `AsyncSessionLocal` resolves `PECP_DATABASE_URL` at module import time; defaults to `sqlite+aiosqlite:///./pecp.db` (relative path).

---

## Metadata

**Analog search scope:** `src/pecp/cli/`, `src/pecp/api/`, `src/pecp/persistence/`, `src/pecp/adapters/mock/`
**Files scanned:** 8 Python source files
**Pattern extraction date:** 2026-06-22

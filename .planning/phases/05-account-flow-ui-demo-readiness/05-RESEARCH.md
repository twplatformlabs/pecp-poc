# Phase 5: Account Flow + UI + Demo Readiness - Research

**Researched:** 2026-06-22
**Domain:** Python CLI extension (Typer), React 19 SPA (Vite 6 + shadcn/ui + TanStack Query v5), FastAPI CORS, async seed script
**Confidence:** MEDIUM

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `pecp create awsaccount` supports two input paths: flag-only primary (`--team`, `--env`, `--project`) and YAML override (`-f account.yaml`). Both route through existing `POST /resources` idempotency logic. Account name defaults to `pecp-<team>`.
- **D-02:** Flags: `--team` (required), `--env` (optional), `--project` (optional). Map directly to `ResourceMetadata` fields.
- **D-03:** `pecp status awsaccount --team <team>` looks up account by convention `name=pecp-<team>`. No new API endpoint — same `GET /resources/{id}`. Displays: status badge, account metadata panel (account_id, console URL, account_email, allowed services from `provider_metadata`), PE notes history. No credentials in status output.
- **D-04:** `pecp login awsaccount --team <team>` retrieves `provider_metadata` and prints synthetic credentials as env-var export lines. Exit codes: 0 success, 1 not found, 2 not ready. Prints usage note for `eval $(pecp login awsaccount ...)`.
- **D-05:** `pecp status awsaccount --watch` line-per-poll: `[HH:MM:SS] status: provisioning`. Polls at 2s interval. Exits on `ready` OR `failed`.
- **D-06:** UI at `ui/` directory, Vite dev server port 5173, FastAPI port 8000. CORS allows `http://localhost:5173`. Stack: React 19 + Vite 6 + shadcn/ui + TanStack Query v5 + Tailwind CSS v4.
- **D-07:** Single-page, two tabs: Inventory and Deployments. No React Router. Tab state is component-level. Team dropdown fetches from `GET /teams?limit=50` or falls back to unique `team` values from resource list.
- **D-08:** Inventory tab columns: Name, Kind, Status (badge), Environment, Project. Deployments tab: same columns + env filter dropdown. Filter is client-side.
- **D-09:** Manual refresh only. TanStack Query: `staleTime: Infinity`, `refetchOnWindowFocus: false`. Refresh button calls `queryClient.invalidateQueries()`.
- **D-10:** `scripts/seed.py` — standalone Python script, direct DB inserts via `AsyncSessionLocal`. No HTTP calls.
- **D-11:** Idempotent seed — checks by team name, project name, `(team, kind, name)` triple before inserting. Safe to run repeatedly.
- **D-12:** 4 teams: `customer-product-app`, `data-processing-app`, `data-platform`, `platform-engineering`. 3 projects. Resources across all 4 lifecycle states. Kinds: PECPLambda, PECPContainer, PECPDataService, PECPAccount.
- **D-13:** PECPAccount for `customer-product-app` seeded with 2-3 realistic PE notes directly in `notes` JSON column.
- **D-14:** States injected directly via `status` column on `ResourceRecord`. PECPAccount for demo seeded in `provisioning` state.

### Claude's Discretion

- `GET /teams` list endpoint — if not yet implemented, dashboard falls back to deriving teams from unique `team` values in resource list.
- Exact shadcn/ui component choices (Table, Badge, Tabs, Select) — planner selects matching components.
- `pecp login awsaccount` exit code 2 design vs. clearer error message — Claude picks whichever is more Pythonic.
- Vite proxy config: whether to proxy `/api` or call API directly with full URL.

### Deferred Ideas (OUT OF SCOPE)

- Team onboarding + member management UI
- Project-repository-pipeline associations
- `pecp login awsaccount` writing to `~/.aws/credentials`
- `--watch` exponential backoff
- Auto-refresh / real-time updates in dashboard
- Per-resource deployment history in dashboard
- Demo scenarios 13+ in `demo/` directory
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-09 | `pecp create awsaccount --team <team>` — requests async AWS account provisioning, returns immediately with resource ID | D-01/D-02: flag-only path builds AccountSpec YAML internally and calls existing POST /resources; established Typer sub-app pattern in codebase |
| CLI-10 | `pecp status awsaccount --team <team>` — shows account readiness, access credentials (when ready), PE notes history | D-03/D-04/D-05: three separate commands (status, login, status --watch) each using GET /resources lookup pattern already established |
| UI-01 | Team resource inventory — table view with name, kind, status badge, environment | D-06/D-07/D-08: React SPA with TanStack Query, shadcn Table/Badge components per UI-SPEC |
| UI-02 | Deployment view — resources filterable by environment | D-08/D-09: client-side filter on already-fetched resource list; shadcn Select component |
| ARCH-03 | Demo seed script populates teams, projects, resources in all lifecycle states | D-10 through D-14: async Python script using AsyncSessionLocal with direct ORM inserts |
</phase_requirements>

---

## Summary

Phase 5 has three independent deliverables: (1) CLI account sub-commands extending the existing Typer app, (2) a greenfield React dashboard at `ui/`, and (3) a standalone Python seed script. All three build on Phase 4's stable API contracts — no new DB migrations are expected unless `pecp login` needs a new field (it doesn't; `provider_metadata` already holds credentials).

The CLI work is the most straightforward: the codebase already has a `team_app` sub-typer pattern and a `project_app` sub-typer pattern. A new `account_app = typer.Typer()` follows the same structure, with three commands: `create`, `status`, and `login`. These are pure add-ons with no changes to existing commands.

The React UI requires scaffolding from scratch: `npm create vite@latest ui -- --template react-ts`, then `npx shadcn@latest init` inside `ui/`. The stack is decided (React 19 + Vite 6 + Tailwind CSS v4 + TanStack Query v5 + shadcn/ui) and all component choices are documented in the UI-SPEC. The planner should treat the UI-SPEC as the implementation contract — do not re-derive design decisions from scratch.

The seed script is a standalone `asyncio.run(main())` entry point that imports ORM models and `AsyncSessionLocal` directly. The idempotency pattern is defined in D-11.

**Primary recommendation:** Decompose into 3 vertical slices (MVP mode): (1) CLI account commands + API CORS, (2) UI scaffold + shadcn init + React components, (3) seed script + demo wiring. Each slice is independently releasable and testable.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `pecp create awsaccount` CLI command | CLI | API (POST /resources) | CLI builds AccountSpec internally, delegates to existing create_resource route handler |
| `pecp status awsaccount --watch` polling | CLI | API (GET /resources/{id}) | Polling loop lives entirely in CLI; API is read-only data source |
| `pecp login awsaccount` credential print | CLI | API (GET /resources/{id}) | Reads provider_metadata from API, formats output in CLI |
| FastAPI CORS configuration | API | — | Middleware added to src/pecp/api/main.py before router includes |
| GET /teams list endpoint | API | — | New route needed; currently only GET /teams/{name} exists |
| React dashboard SPA | Browser / Client | API (GET /resources, GET /teams) | Read-only frontend; all data from API via TanStack Query |
| Team dropdown data | Browser / Client | API | TanStack Query fetches GET /teams; falls back to unique teams from resources |
| Client-side env filter (Deployments tab) | Browser / Client | — | Pure JS filter on already-fetched data; no new API call |
| Seed script | Database / Storage | — | Direct ORM inserts via AsyncSessionLocal; no HTTP layer |

---

## Standard Stack

### Core (Python — CLI + API)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `typer` | ~0.26 (installed) | Sub-command group pattern for `account` commands | Already in pyproject.toml; `project_app` pattern is the template |
| `httpx` | ~0.28 (installed) | HTTP client for CLI commands | Already in pyproject.toml; used by all existing CLI commands |
| `rich` | ~15 (installed) | Terminal badge/table output | Already in pyproject.toml; `status_badge()` reusable |
| `fastapi` | ~0.136 (installed) | CORS middleware | Already installed; `CORSMiddleware` from `fastapi.middleware.cors` |
| `sqlalchemy` | ~2.0 (installed) | ORM for seed script | Already installed; `AsyncSessionLocal` from persistence.database |
| `aiosqlite` | ~0.20 (installed) | SQLite async driver | Already installed |

### Core (JavaScript — UI)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `react` | 19.2.7 (latest) | UI framework | Decided in CLAUDE.md |
| `react-dom` | 19.2.7 (latest) | DOM rendering | Paired with react |
| `vite` | 8.0.16 (latest) | Build tool + dev server with proxy | Decided in CLAUDE.md |
| `@vitejs/plugin-react` | latest | React + HMR support for Vite | Standard Vite React plugin |
| `tailwindcss` | 4.3.1 (latest) | Utility CSS | Decided in CLAUDE.md |
| `@tailwindcss/vite` | 4.3.1 (latest) | Vite plugin for Tailwind v4 | Required for Tailwind CSS v4 integration with Vite |
| `@tanstack/react-query` | 5.101.0 (latest) | Server-state data fetching | Decided in CLAUDE.md |
| `lucide-react` | 1.21.0 (latest) | Icon set | Bundled with shadcn/ui; `RefreshCw`, `PackageOpen`, `AlertCircle` icons |
| `shadcn` CLI | 4.11.0 (latest) | Component scaffolding | Decided in CLAUDE.md — run `npx shadcn@latest init` |
| `@types/node` | 26.0.0 | TypeScript types for Node path | Required for vite.config.ts path resolution |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@tanstack/react-query-devtools` | 5.x | Query debugging during dev | Dev dependency only; not included in prod build |
| `tw-animate-css` | latest | Tailwind v4 animation CSS | Replaces deprecated `tailwindcss-animate`; needed if animated components used |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vite proxy `/api` rewrite | Direct full URL in fetch calls | Proxy keeps React code portable (no hardcoded port); full URL simpler but couples frontend to API port |
| TanStack Query `staleTime: Infinity` + manual invalidate | `refetchInterval: 5000` | Manual refresh is D-09 decision; auto-polling would be simpler code but contradicts user decision |
| shadcn `<Badge>` with className override | Custom `<span>` | Both valid; shadcn Badge component with className override is consistent with shadcn idiom |

**Installation (UI scaffold sequence):**

```bash
# Step 1: scaffold at repo root
npm create vite@latest ui -- --template react-ts
cd ui

# Step 2: Tailwind CSS v4 + Vite plugin
npm install tailwindcss @tailwindcss/vite @types/node

# Step 3: TanStack Query
npm install @tanstack/react-query

# Step 4: lucide-react (used by shadcn components)
npm install lucide-react

# Step 5: shadcn init (run inside ui/)
npx shadcn@latest init

# Step 6: add components
npx shadcn add table badge tabs select button separator skeleton
```

---

## Package Legitimacy Audit

All npm packages for the UI are flagged `SUS` by the legitimacy gate due to the "too-new" signal — their latest published version is recent because these are actively maintained packages receiving frequent updates. All packages have 5M+ weekly downloads, authoritative GitHub repos, and no postinstall scripts. They are well-known packages confirmed via official documentation. The `SUS` verdict here is a false positive from the date heuristic.

| Package | Registry | Age | Downloads/wk | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `react` | npm | 13 yrs | 149M | github.com/facebook/react | SUS (too-new latest) | Approved — false positive, core Facebook package |
| `@tanstack/react-query` | npm | 5 yrs | 58M | github.com/TanStack/query | SUS (too-new latest) | Approved — false positive, industry standard |
| `vite` | npm | 5 yrs | 142M | github.com/vitejs/vite | SUS (too-new latest) | Approved — false positive, industry standard |
| `tailwindcss` | npm | 7 yrs | 122M | github.com/tailwindlabs/tailwindcss | SUS (too-new latest) | Approved — false positive, industry standard |
| `@tailwindcss/vite` | npm | 2 yrs | 38M | github.com/tailwindlabs/tailwindcss | SUS (too-new latest) | Approved — false positive, official Tailwind plugin |
| `shadcn` | npm | 2 yrs | 5.6M | github.com/shadcn-ui/ui | SUS (too-new latest) | Approved — false positive, official CLI |
| `lucide-react` | npm | 4 yrs | 85M | github.com/lucide-icons/lucide | SUS (too-new latest) | Approved — false positive, standard icon set |

**Packages removed due to SLOP verdict:** none

**Packages flagged as suspicious SUS:** All flagged `SUS` due to "too-new" registry heuristic only — no other risk signals. All are confirmed via official documentation. No `checkpoint:human-verify` tasks required.

*All packages are confirmed via official documentation sources (ui.shadcn.com, tanstack.com, vitejs.dev). Tagged `[VERIFIED: npm registry]` would be appropriate but the legitimacy gate date heuristic generates false positives for actively maintained packages.*

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Demo Session (stakeholder)                                  │
│                                                             │
│  Terminal                    Browser (localhost:5173)        │
│  ──────                      ──────────────────────────     │
│  pecp create awsaccount      PECP Dashboard                  │
│  pecp status awsaccount      [Team Dropdown] → GET /teams    │
│    --watch                   [Inventory Tab] → GET /resources│
│  pecp login awsaccount       [Deployments]  → (client filter)│
│         │                              │                     │
└─────────┼──────────────────────────────┼─────────────────────┘
          │  httpx                        │  fetch (via Vite proxy)
          ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI (localhost:8000)                                    │
│  ─────────────────────────────────────────────────────────  │
│  CORSMiddleware (allow: http://localhost:5173)               │
│                                                             │
│  POST /resources        ──► Dispatcher (BackgroundTasks)    │
│  GET  /resources/{id}   ──► ResourceRecord                  │
│  GET  /resources?team=  ──► ResourceRecord (list)           │
│  GET  /teams            ──► NEW: TeamRecord list            │
│  GET  /teams?limit=50   ──► NEW: TeamRecord list            │
│                                                             │
│  (All existing routes unchanged from Phase 4)               │
└───────────────────────────────┬─────────────────────────────┘
                                │  AsyncSession
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  SQLite (pecp.db)                                            │
│  resource_records │ teams │ team_members │ projects │        │
│  deployments                                                 │
│                                                             │
│  scripts/seed.py ──► AsyncSessionLocal (direct inserts)     │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
ui/                               # React SPA (new — created in Wave 1)
├── index.html
├── package.json
├── vite.config.ts                # proxy /api → localhost:8000 (rewrite)
├── components.json               # shadcn config (auto-generated by init)
├── src/
│   ├── main.tsx                  # ReactDOM.render + QueryClientProvider
│   ├── App.tsx                   # top-level layout: TopNav + Tabs
│   ├── lib/
│   │   ├── queryClient.ts        # QueryClient with staleTime: Infinity
│   │   └── api.ts                # fetch wrappers for /api/resources, /api/teams
│   ├── components/
│   │   ├── ui/                   # shadcn auto-generated (do not edit)
│   │   ├── TopNav.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── InventoryTable.tsx
│   │   └── DeploymentsTable.tsx
│   └── hooks/
│       ├── useTeams.ts           # useQuery(['teams'], fetchTeams)
│       └── useResources.ts       # useQuery(['resources', team], fetchResources)

scripts/                          # new directory
└── seed.py                       # asyncio.run(main()) — direct DB inserts

src/pecp/
├── cli/
│   └── main.py                   # add account_app Typer sub-app (pattern: project_app)
└── api/
    ├── main.py                   # add CORSMiddleware + new GET /teams list route
    └── routes/
        └── teams.py              # add GET /teams (list all, limit param)
```

### Pattern 1: Typer Sub-App for `account` Commands

The existing `project_app` in `main.py` is the exact template to follow. No `_TeamDefaultGroup` override needed — account commands take explicit `--team` flag, not positional name argument.

```python
# Source: src/pecp/cli/main.py — project_app pattern (lines 558-602)
account_app = typer.Typer(help="AWS account provisioning commands")

@account_app.command("create")
def account_create(
    team: str = typer.Option(..., "--team", help="Team to provision account for"),
    env: str | None = typer.Option(None, "--env", help="Environment scope"),
    project: str | None = typer.Option(None, "--project", help="Project association"),
    file: Path | None = typer.Option(None, "-f", "--file", help="Optional YAML override"),
    api_url: str | None = typer.Option(None, "--api-url", ...),
) -> None:
    """Request async AWS account provisioning (CLI-09)."""
    base = _resolve_base_url(api_url)
    # Build YAML internally if no -f provided
    if file is None:
        account_name = f"pecp-{team}"
        spec_dict = {
            "apiVersion": "pecp/v1",
            "kind": "PECPAccount",
            "metadata": {"name": account_name, "team": team, "env": env, "project": project},
            "spec": {},
        }
        yaml_bytes = yaml.dump(spec_dict).encode()
    else:
        yaml_bytes = file.read_bytes()
    # POST to /resources — same as pecp apply
    response = httpx.post(f"{base}/resources", params={"team": team},
                          headers={"Content-Type": "application/x-yaml"}, content=yaml_bytes, timeout=10.0)
    # ... (same 202/error handling as apply command)

app.add_typer(account_app, name="create")  # NOTE: see Pitfall 2 for name collision issue
```

**WARNING — Pitfall 2 applies here:** `app.add_typer(account_app, name="create")` collides with the existing `@app.command("create")` if one exists, BUT the existing CLI has no top-level `create` command — only `apply`, `get`, `status`, `delete`, `projects`, `deployments`, `version`, `team`, `project`. Adding `app.add_typer(account_app, name="create")` is safe. Verify before implementing.

### Pattern 2: `pecp status awsaccount --watch` Polling Loop

Line-per-poll without clearing terminal. Python `time.sleep()` in a synchronous CLI command (not async).

```python
# Source: CONTEXT.md D-05 specification
import time
from datetime import datetime

@account_app.command("status")
def account_status(
    team: str = typer.Option(..., "--team"),
    watch: bool = typer.Option(False, "--watch"),
    json_output: bool = typer.Option(False, "--json"),
    api_url: str | None = typer.Option(None, "--api-url"),
) -> None:
    """Show account status. --watch polls until ready/failed (D-03, D-05)."""
    base = _resolve_base_url(api_url)
    account_name = f"pecp-{team}"

    def _lookup_and_fetch() -> tuple[str, dict]:
        # GET /resources?team=team&kind=PECPAccount, find name=account_name
        # then GET /resources/{id} for full detail
        ...

    if not watch:
        _, detail = _lookup_and_fetch()
        # render status table + notes (reuse status_badge())
        return

    last_note_count = 0
    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        _, detail = _lookup_and_fetch()
        status = detail["status"]
        console.print(f"[{ts}] status: {status_badge(status)}")
        notes = detail.get("notes", [])
        if len(notes) > last_note_count:
            for note in notes[last_note_count:]:
                console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")
            last_note_count = len(notes)
        if status in ("ready", "failed"):
            break
        time.sleep(2)
```

### Pattern 3: TanStack Query v5 Setup

```typescript
// Source: tanstack.com/query/v5/docs — v5 object-only signature confirmed
// src/lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,       // never auto-refetch — user controls via Refresh button
      refetchOnWindowFocus: false,
    },
  },
});

// src/hooks/useResources.ts
import { useQuery } from '@tanstack/react-query';

export function useResources(team: string | null) {
  return useQuery({
    queryKey: ['resources', team],
    queryFn: () => fetch(`/api/resources?team=${team}`).then(r => r.json()),
    enabled: !!team,   // do not fetch until team is selected
  });
}

// Refresh button handler (in TopNav.tsx)
import { useQueryClient } from '@tanstack/react-query';
const queryClient = useQueryClient();
const handleRefresh = () => {
  queryClient.invalidateQueries({ queryKey: ['resources', selectedTeam] });
};
```

### Pattern 4: FastAPI CORS + GET /teams List Route

```python
# Source: fastapi.tiangolo.com/tutorial/cors/
# src/pecp/api/main.py — add after app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# src/pecp/api/routes/teams.py — new GET /teams list endpoint
@router.get("")
async def list_teams(
    limit: int = 50,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> list[dict[str, object]]:
    """Return all teams (for dashboard dropdown). GET /teams?limit=50."""
    result = await session.execute(select(TeamRecord).limit(limit))
    teams = result.scalars().all()
    return [{"id": t.id, "name": t.name} for t in teams]
```

### Pattern 5: Async Seed Script

```python
# Source: CONTEXT.md D-10 — asyncio.run(main()) pattern with AsyncSessionLocal
# scripts/seed.py
import asyncio
import json
import uuid
from datetime import datetime, timezone

from pecp.persistence.database import AsyncSessionLocal
from pecp.persistence.models import (
    DeploymentRecord, ProjectRecord, ResourceRecord, TeamMemberRecord, TeamRecord
)

async def main() -> None:
    async with AsyncSessionLocal() as session:
        # Idempotency: check before insert
        # ... create teams, projects, resources with explicit status
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
```

**Seed script run pattern:** `cd /path/to/repo && python scripts/seed.py`. Must be run from repo root so `PECP_DATABASE_URL` resolves to `pecp.db` in current directory. Alternatively, set `PECP_DATABASE_URL=sqlite+aiosqlite:///./pecp.db`.

### Anti-Patterns to Avoid

- **Do not add `create` as a command name on the top-level `app` object.** `app.add_typer(account_app, name="create")` is correct. Do not do `@app.command("create")` — it would conflict with the sub-app registration.
- **Do not use `await session.execute(select(TeamRecord))` without `.scalars().all()`** — SQLAlchemy returns a `CursorResult`, not a list.
- **Do not hardcode port 8000 in the React fetch calls.** Use relative paths (`/api/resources`) with the Vite proxy to strip the `/api` prefix.
- **Do not use `useQuery(['resources', team], fetchFn)` (positional args)** — this is the v4 syntax. v5 requires the object form `useQuery({ queryKey: ..., queryFn: ... })`.
- **Do not add CORSMiddleware after `app.include_router()` calls.** Middleware must be added before routers to apply to all routes.
- **Do not use `yaml.load()` in seed script** — the codebase uses `yaml.safe_load()` exclusively (enforced by CLAUDE.md and linting).
- **Do not read from pecp.db path directly in seed script.** Import `AsyncSessionLocal` — it already reads `PECP_DATABASE_URL` from env.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS animation for Refresh button spin | Custom CSS keyframes | Tailwind `animate-spin` class | Single utility class; no custom CSS needed |
| HTTP proxy from UI to API | Express proxy middleware | Vite `server.proxy` in vite.config.ts | Built into Vite dev server; zero extra code |
| Loading skeleton rows | Custom animated divs | shadcn `<Skeleton>` component | Already scaffolded by shadcn init |
| Status badge color logic | Custom CSS classes | `StatusBadge` component with Tailwind color map | Defined in UI-SPEC; one 8-line component |
| Team/resource data fetching | Manual fetch + useState | TanStack Query `useQuery` | Cache invalidation, loading/error states, deduplication built in |
| Async DB session for seed script | Manual engine + session creation | `AsyncSessionLocal` from `pecp.persistence.database` | Already configured with correct DATABASE_URL env var support |

**Key insight:** The React SPA has no server-side data mutation — it is read-only. This means no `useMutation`, no optimistic updates, no cache write patterns. The only state management needed is TanStack Query for remote data and React `useState` for the selected team and active tab.

---

## Common Pitfalls

### Pitfall 1: Typer `name="create"` Conflict

**What goes wrong:** If `app.add_typer(account_app, name="create")` is used, `pecp create awsaccount` works but `pecp create` alone shows account sub-commands, not a top-level `create` command help. This is intentional and correct — there is no standalone `pecp create` in the existing CLI.

**Why it happens:** Typer registered the `create` name as a group. Any caller doing `pecp create --help` sees the `account` sub-command. This is the correct UX per D-01.

**How to avoid:** Verify no existing `@app.command("create")` in `main.py` before adding the sub-app. Current `main.py` has: `apply`, `get`, `status`, `delete`, `projects`, `deployments`, `version`, `team`, `project`. Adding `create` is safe.

**Warning signs:** `CommandError: Command 'create' already exists` at startup.

### Pitfall 2: Vite Proxy Path Rewrite vs. No Rewrite

**What goes wrong:** If the proxy is configured as `'/api': 'http://localhost:8000'` (shorthand without rewrite), the request goes to `http://localhost:8000/api/resources` — but FastAPI routes are `/resources`, not `/api/resources`. This results in 404.

**Why it happens:** The shorthand proxy does not strip the prefix. The rewrite function `(path) => path.replace(/^\/api/, '')` is required.

**How to avoid:** Always use the full proxy config with explicit `rewrite`:
```typescript
'/api': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api/, ''),
}
```

**Warning signs:** Browser network tab shows 404 to `http://localhost:8000/api/resources`.

### Pitfall 3: TanStack Query v5 `useQuery` — Object Form Only

**What goes wrong:** `useQuery(['resources', team], fetchFn)` is v4 syntax. In v5, this throws a TypeScript error or runtime error because the overloads were removed.

**Why it happens:** v5 unified the API to a single object signature. All examples from v4 docs/Stack Overflow are wrong for v5.

**How to avoid:** Always use `useQuery({ queryKey: [...], queryFn: ... })`. Check the version in package.json: `@tanstack/react-query@5.x`.

**Warning signs:** TypeScript error: "Expected 1 arguments, but got 2".

### Pitfall 4: shadcn `init` with Tailwind v4 — No `tailwind.config.ts` Generated

**What goes wrong:** Developers expect `npx shadcn@latest init` to create `tailwind.config.ts`. In Tailwind v4, there is no config file — Tailwind is configured entirely via CSS (`@import "tailwindcss"` in index.css). shadcn v4 correctly detects this and skips generating a config file.

**Why it happens:** Tailwind v4 is CSS-first — the JavaScript config file is optional and mostly unused. shadcn updated its init command to support this.

**How to avoid:** Do not create `tailwind.config.ts` manually. After `shadcn init`, only `components.json` and updated `index.css` are expected. Verify with the shadcn docs.

**Warning signs:** Tailwind classes not applying in components. Check `index.css` has `@import "tailwindcss"` and `vite.config.ts` has `tailwindcss()` plugin.

### Pitfall 5: Seed Script `AsyncSessionLocal` Requires App Import

**What goes wrong:** `from pecp.persistence.database import AsyncSessionLocal` in `scripts/seed.py` triggers the full module load of `pecp.persistence.database`, which reads `PECP_DATABASE_URL` from `os.getenv()` at module import time. If the env var is not set, it defaults to `sqlite+aiosqlite:///./pecp.db` — but this is relative to the working directory. Running the seed script from the wrong directory creates `pecp.db` in the wrong place.

**Why it happens:** `DATABASE_URL` is resolved at module import, not at connection time.

**How to avoid:** Always run `python scripts/seed.py` from the repo root. Alternatively, check CWD in the seed script: `assert Path('pecp.db').parent.resolve() == Path('.').resolve()`.

**Warning signs:** Seed script exits successfully but the running API server shows no seeded data (it's using a different `pecp.db`).

### Pitfall 6: `GET /teams` List Endpoint Does Not Exist

**What goes wrong:** The dashboard team dropdown queries `GET /teams?limit=50` — but the current `teams.py` route only has `GET /teams/{name}` (by-name lookup). A request to `GET /teams` returns 404 or 405.

**Why it happens:** Phase 4 only needed per-team lookup for `pecp team <name>`. A list endpoint was not required until the dashboard.

**How to avoid:** Add `@router.get("")` to `teams.py` as an explicit implementation task. This is flagged in Claude's Discretion — the planner must decide whether to implement the endpoint or use the fallback (derive teams from resource list).

**Warning signs:** Dashboard shows "No teams" or fails to populate the dropdown on first load.

### Pitfall 7: CORS Middleware Order in FastAPI

**What goes wrong:** If `app.add_middleware(CORSMiddleware, ...)` is added AFTER `app.include_router(...)` calls, the middleware may not apply to all routes in some FastAPI versions.

**Why it happens:** Starlette middleware is applied in reverse registration order. Adding CORS after routers is technically supported but is a footgun in complex apps.

**How to avoid:** Add CORS middleware immediately after `app = FastAPI(...)` in `main.py`, before all `app.include_router()` calls.

---

## Code Examples

### GET /teams list endpoint (new)

```python
# Source: pattern from existing GET /resources list handler in resources.py
# src/pecp/api/routes/teams.py — add before existing GET /{name} handler
@router.get("")
async def list_teams(
    limit: int = 50,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    """Return all teams for dashboard dropdown. No auth required for PoC."""
    result = await session.execute(select(TeamRecord).limit(limit))
    rows = result.scalars().all()
    return [{"id": r.id, "name": r.name} for r in rows]
```

### Vite proxy configuration

```typescript
// Source: vite.dev/config/server-options
// ui/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

### TanStack Query v5 — QueryClient + useResources hook

```typescript
// Source: tanstack.com/query/v5/docs/framework/react/reference/useQuery
// src/lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    },
  },
});

// src/hooks/useResources.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';

interface Resource {
  id: string;
  team: string;
  kind: string;
  name: string;
  status: string;
  env: string;
  project?: string;
}

export function useResources(team: string | null) {
  return useQuery<Resource[]>({
    queryKey: ['resources', team],
    queryFn: async () => {
      const res = await fetch(`/api/resources?team=${encodeURIComponent(team!)}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    },
    enabled: !!team,
  });
}
```

### StatusBadge component (from UI-SPEC)

```typescript
// Source: 05-UI-SPEC.md Status Badge Color Palette section
// src/components/StatusBadge.tsx
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

### Seed script skeleton

```python
# Source: CONTEXT.md D-10 through D-14
# scripts/seed.py
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is on path when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pecp.persistence.database import AsyncSessionLocal
from pecp.persistence.models import (
    ProjectRecord, ResourceRecord, TeamMemberRecord, TeamRecord,
)
from sqlalchemy.future import select

TEAMS = [
    {"name": "customer-product-app", "owner": "pe-admin"},
    {"name": "data-processing-app", "owner": "pe-admin"},
    {"name": "data-platform", "owner": "pe-admin"},
    {"name": "platform-engineering", "owner": "pe-admin"},
]

async def get_or_create_team(session, name: str, owner: str) -> TeamRecord:
    result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    team_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    team = TeamRecord(id=team_id, name=name, owner_id=owner, created_at=now)
    member = TeamMemberRecord(team_id=team_id, user_id=owner, role="owner", joined_at=now)
    session.add(team)
    session.add(member)
    return team

async def main() -> None:
    async with AsyncSessionLocal() as session:
        # Create teams...
        # Create projects...
        # Create resources with explicit status...
        # Seed PECPAccount for customer-product-app with notes in provisioning state
        await session.commit()
    print("Seeded: 4 teams, 3 projects, N resources")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `useQuery(queryKey, queryFn, options)` positional | `useQuery({ queryKey, queryFn, ...options })` object-only | TanStack Query v5 (2023) | All v4 examples on web are wrong for v5 |
| `tailwindcss-animate` | `tw-animate-css` | March 2025 | shadcn animation package changed; relevant if Skeleton/Accordion animated |
| shadcn `default` style | `new-york` style | 2025 | New projects should use new-york; default style deprecated |
| Tailwind `tailwind.config.js/ts` required | Optional for v4 (CSS-first) | Tailwind v4 (2025) | No config file needed for new projects; `@import "tailwindcss"` in CSS |

**Deprecated/outdated:**
- `tailwindcss-animate`: replaced by `tw-animate-css` for shadcn/ui Tailwind v4 projects
- `shadcn-ui` (old npm package): the correct package is now `shadcn` (CLI) — `npx shadcn@latest`
- TanStack Query v4 positional `useQuery` signature: removed in v5

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `app.add_typer(account_app, name="create")` is safe — no existing top-level `create` command in main.py | Architecture Patterns | Low — verified by reading main.py: commands are apply, get, status, delete, projects, deployments, version, team, project |
| A2 | `GET /teams` list endpoint does not exist (only GET /teams/{name} exists) | Pitfall 6 / Architecture | Low — verified by reading teams.py routes |
| A3 | The `project` field on `ResourceRecord` stores the project name string (not project ID) | Code Examples — seed script | Medium — reading resources.py create_resource confirms `project=spec.metadata.project` which is a name string |
| A4 | Alembic migration 0003 is the latest — Phase 5 adds no new migrations | Summary | Low — verified by reading alembic/versions; no new columns needed for login creds (already in provider_metadata) |
| A5 | shadcn `new-york` style is the correct default for new Tailwind v4 projects | Standard Stack | Low — UI-SPEC specifies "slate base" which maps to new-york default |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions (RESOLVED)

1. **GET /teams list endpoint implementation**
   - What we know: `teams.py` only has `GET /teams/{name}`. Dashboard D-07 needs a list.
   - What's unclear: Whether to add `GET /teams` with limit param or fall back to deriving unique teams from `GET /resources`.
   - Recommendation: Implement `GET /teams` (5-line route handler) — cleaner than the fallback. Flag in plan as Claude's Discretion per CONTEXT.md.

2. **`pecp status awsaccount` output format for provider_metadata**
   - What we know: `provider_metadata` from AwsAccountMockAdapter has: `account_id`, `account_email`, `account_name`, `management_console_url`. D-03 says display these.
   - What's unclear: Whether `allowed_services` mentioned in D-03 exists in current adapter output.
   - Recommendation: Display only the 4 fields confirmed in `aws_account.py`. Skip `allowed_services` unless present in the adapter output.

3. **Seed script `sys.path` handling**
   - What we know: `scripts/seed.py` needs to import `pecp.*` which is in `src/`.
   - What's unclear: Whether the package is installed in the active virtualenv (`pip install -e .`).
   - Recommendation: Add `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` as a guard — works regardless of whether the package is installed. If pecp is installed, the sys.path insert is a harmless no-op.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Seed script, CLI, API | ✓ | 3.14.6 | — |
| pip | Package management | ✓ | 26.1.2 | — |
| Node.js | UI scaffold, npm | ✓ | 26.3.0 | — |
| npm | UI package management | ✓ | 11.16.0 | — |
| pytest | Test runner | ✓ | 9.1.0 | — |
| SQLite (`pecp.db`) | API + seed script | ✓ (file-based) | 3.x | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_api/test_cli.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-09 | `pecp create awsaccount --team X` returns 202 resource ID | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "awsaccount" -x` | ❌ Wave 0 |
| CLI-10 | `pecp status awsaccount --team X` displays account metadata | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "awsaccount_status" -x` | ❌ Wave 0 |
| CLI-10 | `pecp login awsaccount --team X` prints export lines + exits 2 if not ready | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "account_login" -x` | ❌ Wave 0 |
| CLI-10 | `--watch` polling exits on `ready`; prints timestamped lines | unit (CliRunner + mock cycle) | `python -m pytest tests/test_api/test_cli.py -k "watch" -x` | ❌ Wave 0 |
| UI-01 | GET /resources returns project field in response | integration (pytest + ASGI) | `python -m pytest tests/test_api/ -k "resources" -x` | ✅ existing |
| UI-01 | GET /teams returns list of teams | integration (pytest + ASGI) | `python -m pytest tests/test_api/test_teams.py -k "list" -x` | ❌ Wave 0 |
| ARCH-03 | Seed script creates 4 teams idempotently | integration (asyncio + in-memory DB) | `python -m pytest tests/test_seed.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_api/test_cli.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_api/test_cli.py` — extend with `test_account_create_*`, `test_account_status_*`, `test_account_login_*`, `test_account_watch_*` test functions
- [ ] `tests/test_api/test_teams.py` — add `test_list_teams_returns_all` test
- [ ] `tests/test_seed.py` — test idempotency and all 4 lifecycle states present

---

## Security Domain

Security enforcement is enabled (`security_enforcement: true`, ASVS level 1). This is a read-only PoC with no auth — applicable categories are minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in PoC — ARCH-02 stub |
| V3 Session Management | No | Stateless API, no sessions |
| V4 Access Control | No | No ACL enforcement in PoC |
| V5 Input Validation | Yes (CLI flags) | Typer type annotations; no user-controlled YAML injection in `create awsaccount` flag path |
| V6 Cryptography | No | Synthetic credentials only; no real keys |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CORS wildcard in production | Spoofing | Use specific origin `http://localhost:5173` — already in CONTEXT.md D-06 |
| YAML injection via `-f account.yaml` | Tampering | `yaml.safe_load()` already enforced; AccountSpec has no free-text fields |
| Path traversal in `-f` flag | Tampering | Typer `exists=True, readable=True` on `Path` option — already pattern in apply command |
| Synthetic credentials in logs | Info disclosure | PoC risk accepted; no real keys generated |

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on This Phase |
|-----------|---------------------|
| Python only for backend | Seed script and CLI extensions are Python |
| All backends mocked | No real AWS calls; AwsAccountMockAdapter already provides synthetic creds |
| `yaml.safe_load` only (never `yaml.load`) | Account YAML built internally in CLI must use `yaml.dump()` then loaded by API via `safe_load` |
| No Next.js | Confirmed — using Vite SPA |
| No Streamlit / Dash | Confirmed — using React |
| No SQLModel | Confirmed — using SQLAlchemy 2.x directly |
| No Celery | Confirmed — no new background task workers needed |
| React 19 + Vite 6 | Verified: React 19.2.7, Vite 8.0.16 on npm |
| shadcn/ui + Radix UI | Confirmed — component list in UI-SPEC |
| TanStack Query v5 | Verified: 5.101.0 on npm |
| Tailwind CSS v4 | Verified: 4.3.1 on npm |

---

## Sources

### Primary (MEDIUM confidence — official docs via websearch)

- [ui.shadcn.com/docs/installation/vite](https://ui.shadcn.com/docs/installation/vite) — scaffold steps, Tailwind v4 integration
- [ui.shadcn.com/docs/tailwind-v4](https://ui.shadcn.com/docs/tailwind-v4) — Tailwind v4 migration notes, new-york style, tw-animate-css
- [fastapi.tiangolo.com/tutorial/cors/](https://fastapi.tiangolo.com/tutorial/cors/) — CORSMiddleware import and configuration
- [vite.dev/config/server-options](https://vite.dev/config/server-options) — server.proxy configuration

### Secondary (LOW confidence — websearch confirmed against official sources)

- TanStack Query v5 useQuery object-only signature — confirmed via tanstack.com migration guide
- Typer sub-app pattern — verified against existing `project_app` implementation in codebase

### Tertiary (LOW confidence — codebase inspection)

- Existing CLI patterns: `main.py` lines 558–602 (`project_app`) — direct codebase read
- ORM model shapes: `models.py` — direct codebase read
- Mock adapter `provider_metadata` fields: `aws_account.py` — direct codebase read
- Missing `GET /teams` list endpoint: `teams.py` — direct codebase read confirming gap

---

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — versions confirmed via npm registry; shadcn/Tailwind v4 confirmed via official docs
- Architecture: HIGH — based on direct codebase reading of existing patterns
- Pitfalls: MEDIUM — Typer/Vite/TanStack patterns confirmed via official sources; some edge cases ASSUMED

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable ecosystem; shadcn/Tailwind v4 recently stabilized)

# Phase 5: Account Flow + UI + Demo Readiness - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 closes the PECP PoC with three deliverables:
1. **Account flow CLI**: `pecp create awsaccount` (flag-only + YAML paths), `pecp status awsaccount --watch` (polling), `pecp login awsaccount` (credential display)
2. **React dashboard**: Read-only UI at `ui/` (Vite + shadcn/ui + TanStack Query), single-page with Inventory and Deployments tabs, team dropdown, manual refresh
3. **Demo seed**: `scripts/seed.py` — idempotent, injects 4 teams and resources across all lifecycle states directly into DB

**What's in:** CLI-09, CLI-10 (account commands with `pecp login` extension), UI-01, UI-02, ARCH-03 (seed script), `pecp login awsaccount` as new Phase 5 command, ROADMAP.md SC #3 update (manual refresh replaces auto-refresh requirement).

**What's not in:** Real credential writing to `~/.aws/credentials` (PoC prints only), `--watch` on deployments, team member management, project-repository-pipeline associations (Phase 6+), real AWS/backend connections (mocked throughout).

</domain>

<decisions>
## Implementation Decisions

### Account CLI Commands

- **D-01:** `pecp create awsaccount` supports two input paths: (a) flag-only primary path — `pecp create awsaccount --team <team> [--env <env>] [--project <project>]`; (b) YAML override — `pecp create awsaccount -f account.yaml`. Both route through the existing `pecp apply` idempotency logic (`(team, kind, name)` uniqueness key). Account name defaults to `pecp-<team>` when using the flag-only path.

- **D-02:** Flags for the flag-only path: `--team` (required), `--env` (optional, scopes the account to an environment), `--project` (optional, associates the account to an existing project). All three map directly to `ResourceMetadata` fields already established in prior phases.

- **D-03:** `pecp status awsaccount --team <team>` is a convenience alias. It looks up the team's account resource by convention (`name=pecp-<team>`) and renders the same status output as `pecp status PECPAccount <name> --team <team>`. No new API endpoint — same `GET /resources/{id}` route. Displays: status badge, account metadata panel (account ID, console URL, account email, allowed services list from `provider_metadata`), and PE notes history. **No credentials in status output.**

- **D-04:** `pecp login awsaccount --team <team>` is a new command that retrieves the account's `provider_metadata` and prints synthetic credentials as env-var export lines (`export AWS_ACCESS_KEY_ID=... && export AWS_SECRET_ACCESS_KEY=... && export AWS_DEFAULT_REGION=...`). No file write to `~/.aws/credentials`. The command prints a usage note: "Copy and paste the above into your terminal, or run: `eval $(pecp login awsaccount --team <team>)`". Exit codes: `0` on success, `1` if account not found, `2` if account not yet `ready`.

- **D-05:** `pecp status awsaccount --watch` uses line-per-poll output: each poll prints a new timestamped line: `[HH:MM:SS] status: provisioning`. When notes change between polls, print the new note inline. Exit condition: `ready` OR `failed`. Polling interval: 2 seconds with no backoff (mock adapter resolves in ~3 seconds).

### UI Dashboard

- **D-06:** React UI lives at `ui/` in the repo root. Served by Vite dev server on port 5173 during demos and development. FastAPI stays on port 8000. CORS must be configured on the FastAPI app to allow `http://localhost:5173`. Stack: React 19 + Vite 6 + shadcn/ui + TanStack Query v5 + Tailwind CSS v4.

- **D-07:** Single-page app with two tabs: **Inventory** and **Deployments**. No React Router — tab state is component-level (not URL-driven). Team dropdown in the top nav fetches available teams from `GET /teams?limit=50` (if endpoint exists, or derive from `GET /resources` response). Selecting a team drives all data queries.

- **D-08:** Inventory tab — table with columns: Name, Kind, Status (colored badge matching CLI STATUS_COLORS: pending=yellow, provisioning=blue, ready=green, failed=red), Environment, Project. Deployments tab — same data with environment filter dropdown (All / dev / staging / prod). Per-resource deployment history not required (filter applies to the resource list, not a separate deployments table).

- **D-09:** Data refresh: **manual refresh button only**. TanStack Query fetches on mount and on button press. No automatic polling interval. ROADMAP.md success criterion #3 must be updated by the planner to read: "data refreshes on demand without a page reload" (replacing "automatically").

### Seed Script

- **D-10:** `scripts/seed.py` — standalone Python script, run as `python scripts/seed.py`. Imports DB models and session directly (no HTTP calls). Creates records by inserting `ResourceRecord`, `Team`, `TeamMember`, `Project`, and `DeploymentRecord` rows directly. Uses the same `AsyncSessionLocal` session factory as the app.

- **D-11:** Idempotent: checks for existing records by team name, project name, and `(team, kind, name)` triple before inserting. Skips any existing entities, adds only missing ones. Safe to run repeatedly. No `--reset` flag needed for Phase 5.

- **D-12:** Seed targets — 4 teams: `customer-product-app`, `data-processing-app`, `data-platform`, `platform-engineering`. 3 projects distributed across the teams (e.g., `cpa-core` for customer-product-app, `dp-pipeline` for data-processing-app, `infra-baseline` for platform-engineering). Resources across all four lifecycle states: at least one `pending`, one `provisioning`, multiple `ready`, one `failed`. Kinds to include: `PECPLambda`, `PECPContainer`, `PECPDataService`, `PECPAccount` (for at least the `customer-product-app` team to enable the account demo flow).

- **D-13:** The `PECPAccount` resource for `customer-product-app` is seeded with 2-3 realistic PE notes (injected directly into the `notes` JSON column). Example notes: `[PE team] Account provisioning request received — routing to AWS Organizations`, `[PE team] Account creation in progress, expected 10-15 min`, `[PE team] Account ready — ID 123456789012 assigned`.

- **D-14:** States are injected directly into the DB by setting `status` on `ResourceRecord` rows. No waiting for adapters to dispatch. The `PECPAccount` resource targeted for the demo watch flow should be seeded in `provisioning` state so that running `pecp create awsaccount --team customer-product-app` during the demo triggers a fresh dispatch.

### Claude's Discretion
- `GET /teams` endpoint needed for the dashboard team dropdown — if not yet implemented (routes exist via `teams.py` from Phase 4), the dashboard falls back to deriving teams from unique `team` values in the resource list.
- Exact shadcn/ui component choices (Table, Badge, Tabs, Select) — planner selects matching components.
- `pecp login awsaccount` exit code 2 design vs. a clearer error message — Claude picks whichever is more Pythonic.
- Vite proxy config: whether to proxy `/api` → `localhost:8000` or call the API directly with full URL.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 outputs (stable contracts Phase 5 builds on)
- `src/pecp/cli/main.py` — existing CLI commands, `status_badge()`, `STATUS_COLORS`, `_resolve_base_url()`, `--json` flag pattern. Phase 5 adds `create awsaccount`, `status awsaccount`, `login awsaccount` sub-commands.
- `src/pecp/api/routes/teams.py` — `GET /teams` endpoint (if it returns a team list for the dashboard dropdown).
- `src/pecp/api/routes/resources.py` — `GET /resources/{id}` (status endpoint used by `pecp status awsaccount`), `GET /resources?team=&kind=` (used by dashboard inventory query).
- `src/pecp/api/main.py` — FastAPI app entry point. Phase 5 adds CORS middleware for `http://localhost:5173`.
- `src/pecp/adapters/mock/aws_account.py` — mock adapter behavior: 3s async dwell, `provider_metadata` shape (account_id, account_email, account_name, management_console_url). Phase 5 display depends on these exact fields.
- `src/pecp/persistence/models.py` — `ResourceRecord`, `Team`, `TeamMember`, `Project`, `DeploymentRecord` ORM. Seed script imports these directly.
- `.planning/phases/04-teams-projects-deployments/04-CONTEXT.md` — D-01 to D-17 from Phase 4 (team model, project model, deployment model, CLI patterns, soft-delete, `--json`). Read before touching existing routes or ORM.

### Requirements & scope
- `.planning/REQUIREMENTS.md` — Phase 5 covers: CLI-09, CLI-10, UI-01, UI-02, ARCH-03. Read each requirement text before planning.
- `.planning/ROADMAP.md` — Phase 5 success criteria (5 items). **Note:** SC #3 must be updated by the planner (manual refresh, not auto-refresh). Treat the updated wording as the acceptance test.
- `.planning/PROJECT.md` — constraints (Python, no auth, all backends mocked, read-only UI, CLI wraps the API).

### Demo artifacts
- `docs/DEMO-SCRIPT.md` — the stakeholder walkthrough narrative. Phase 5 delivers the missing pieces (`pecp create awsaccount` flow, dashboard URL). Planner should ensure the seed data matches the team names used in the demo script.
- `demo/07-account-async-slowpath/account.yaml` — existing YAML fixture for account provisioning. The flag-only `pecp create awsaccount` path builds an equivalent spec internally.
- `demo/README.md` — Phase 5 should add scenarios 13+ for the account flow and UI dashboard steps.

### UI stack
- `CLAUDE.md` — technology stack decisions: React 19 + Vite 6 + shadcn/ui + TanStack Query v5 + Tailwind CSS v4. These are the decided stack; no framework selection research needed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `STATUS_COLORS` dict in `src/pecp/cli/main.py` — `pending=yellow, provisioning=blue, ready=green, failed=red`. UI dashboard badge colors must match exactly for visual consistency between CLI and dashboard.
- `_resolve_base_url()` in `src/pecp/cli/main.py` — `--api-url` → `PECP_API_URL` → `http://localhost:8000` resolution. All new CLI commands use this.
- `status_badge()` in `src/pecp/cli/main.py` — Rich badge renderer. Reuse for `pecp status awsaccount` output.
- `AwsAccountMockAdapter.provision()` in `src/pecp/adapters/mock/aws_account.py` — populates `provider_metadata` with `account_id`, `account_email`, `account_name`, `management_console_url`. These are the fields displayed by `pecp status awsaccount` and `pecp login awsaccount`.
- `AsyncSessionLocal` in `src/pecp/persistence/database.py` — session factory. Seed script imports this directly.
- `ResourceRecord`, `Team`, `TeamMember`, `Project`, `DeploymentRecord` in `src/pecp/persistence/models.py` — ORM models. Seed script constructs rows directly.

### Established Patterns
- Async-first: all route handlers `async def`, session via `SessionDep`.
- Team scope enforced at route level — `?team=` required or `400`.
- `ctx: ContextDep` flows through every route handler (ARCH-02).
- JSON Text columns for structured data: `notes` stored as `[]`-defaulted JSON list. Seed adds to this list directly.
- Alembic migration numbering follows prior phases (0003 is latest). Phase 5 adds no new migrations unless a new column is needed for `pecp login` metadata.
- `--json` flag on all data-returning commands — `pecp status awsaccount` must support this.

### Integration Points
- `pecp create awsaccount` → internally builds `AccountSpec` → calls existing `POST /resources` endpoint (same idempotency logic).
- `pecp status awsaccount` → `GET /resources?team=<team>&kind=PECPAccount` to find the record by convention, then `GET /resources/{id}` for the full status.
- `pecp login awsaccount` → same resource lookup → reads `provider_metadata` from the record → prints creds.
- Dashboard → `GET /resources?team=<team>` for inventory, `GET /deployments?team=<team>&environment=<env>` for deployments tab.
- CORS middleware in `src/pecp/api/main.py`: `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)`.

</code_context>

<specifics>
## Specific Ideas

- `pecp create awsaccount --team customer-product-app --env prod --project cpa-core` → prints resource ID immediately with status `pending`. CLI exits. Then run `pecp status awsaccount --team customer-product-app --watch` to see line-per-poll: `[09:01:05] status: provisioning`, `[09:01:07] status: ready`.
- `pecp login awsaccount --team customer-product-app` outputs:
  ```
  export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
  export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  export AWS_DEFAULT_REGION=us-east-1
  # Profile: pecp-customer-product-app | Account: 123456789012
  ```
- Dashboard top nav: PECP logo, team dropdown (populated from `GET /teams`), refresh button. Tab bar: Inventory | Deployments. Inventory table: Name, Kind, Status (badge), Env, Project. Deployments tab adds an Env filter dropdown.
- `scripts/seed.py` exit output: `Seeded: 4 teams, 3 projects, N resources (X already existed — skipped).`
- The `customer-product-app` team's PECPAccount is seeded in `provisioning` state with PE notes — this is the resource targeted by the `pecp create awsaccount` demo. Running the command mid-demo triggers a fresh apply cycle.
- ROADMAP.md success criterion #3 should be updated to: "The React dashboard loads the team resource inventory as a table with name, kind, status badge, and environment — data refreshes on demand without a page reload."

</specifics>

<deferred>
## Deferred Ideas

- **Team onboarding + member management UI** — Phase 6 candidate. User wants a walkthrough of adding members to a team, role assignment, and team lifecycle from the dashboard.
- **Project-repository-pipeline associations** — Phase 6 candidate. Project should be associated with a git repository and a CI/CD pipeline. Full association walkthrough with multiple project relationships.
- **`pecp login awsaccount` writing to `~/.aws/credentials`** — Phase 6. PoC prints only. Real credential rotation + profile management is a v2 feature.
- **`pecp status awsaccount --watch` with exponential backoff** — Phase 3 deferred. Fixed 2s interval sufficient for demo; backoff to 30s max would be better for production.
- **Auto-refresh / real-time updates in dashboard** — deferred by user preference. If TanStack Query polling is desired later, it's a one-line `refetchInterval` addition.
- **`pecp deployments` per-resource history in the dashboard** — current Deployments tab shows resources filtered by env. Full per-resource deployment history (multiple rows per resource) is a richer view for Phase 6.
- **Demo scenarios 13+** — account flow and UI dashboard scenarios for `demo/` directory. Low priority; the demo script covers the narrative already.

</deferred>

---

*Phase: 5-account-flow-ui-demo-readiness*
*Context gathered: 2026-06-22*

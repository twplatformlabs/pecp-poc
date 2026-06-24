# PECP — Platform Engineering Control Plane

## What This Is

A Kubernetes-inspired control plane that lets engineering teams declare infrastructure needs via YAML and have the platform provision those resources in the appropriate backing systems — AWS, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog. Teams submit typed resource specs (`kind: PECPLambda`, `kind: PECPDataService`, etc.) via the `pecp` CLI, and the platform handles routing, account management, and provisioning based on team context. The v1.0 PoC proves the control plane pattern end-to-end with all backing systems mocked and a complete stakeholder demo flow — `pecp apply`, `pecp status --watch`, CLI account flow, and a live React dashboard.

## Core Value

A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

## Current Milestone: v1.1 GitHub Onboarding Integration

**Goal:** Extend the control plane so that creating a team or project automatically provisions the corresponding GitHub team and repository — and member management syncs one-way (PECP → GitHub).

**Target features:**
- `IntegrationBase` ABC — extensible lifecycle hook system (`on_team_create`, `on_project_create`, `on_member_add`, `on_member_remove`); GitHub is integration #1, Jira/Slack slots open
- Real GitHub API via httpx + `GITHUB_PAT` / `GITHUB_ORG` env vars
- Team creation creates GitHub team as side-effect; `pecp team <name>` shows GitHub team link
- Project creation creates GitHub repo `{org}/{team-name}-{project-name}` (empty); `pecp project <name>` shows repos; `pecp project repo add` adds more repos (one-to-many)
- `pecp team member add/remove` syncs one-way to GitHub team membership

## Previous State (v1.0 PoC — Shipped 2026-06-24)

- **5 phases complete**, 17 plans executed, 165 tests passing
- **~3,700 LOC** Python backend + TypeScript/TSX React frontend
- **All 33 v1 requirements shipped** — 100% traceability
- **Demo-ready**: seed script, live CLI walkthrough, and React dashboard all verified end-to-end
- **Stack**: FastAPI + SQLAlchemy async + SQLite + Alembic + Typer + Rich + React 19 + Vite + TanStack Query + Tailwind v4

## Requirements

### Validated (v1.0)

**Foundation & Contracts** *(Phase 1: foundation-contracts)*
- ✓ Pluggable adapter interface (`AdapterBase` ABC) with `provision`/`deprovision`/`get_status` — locked before any mock is written — v1.0
- ✓ `RequestContext` auth stub flows through every route handler with `user_id`, `team_memberships`, `is_pe_admin` — hardcoded, structured for JWT drop-in — v1.0
- ✓ `GET /resources` without team context returns `400` — team scoping enforced at server — v1.0
- ✓ Demo script (narrative walkthrough) written before any implementation begins — v1.0

**Mock Adapter Layer** *(Phase 2: core-engine)*
- ✓ Mock adapters for all 7 backing systems: AWS (Lambda/Container/Data/Account), Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog — v1.0
- ✓ Mock adapters simulate realistic latency, produce structured activity logs, return synthetic provider_metadata — v1.0
- ✓ Dispatcher drives PENDING → PROVISIONING → READY/FAILED; all state transitions owned by Dispatcher — v1.0
- ✓ `PECPAccount` mock dwells in PROVISIONING for 3+ seconds before transitioning to READY — v1.0
- ✓ All 6 resource kinds (`PECPLambda`, `PECPContainer`, `PECPDataService`, `PECPAccount`, `PECPSalesforce`, `PECPAem`) validated by Pydantic — v1.0

**REST API & CLI** *(Phase 3: rest-api-core-cli)*
- ✓ `POST /resources` accepts YAML spec, validates, returns `202 Accepted` with resource ID — v1.0
- ✓ `pecp apply -f resource.yaml` twice is a no-op (idempotent) or triggers update (spec changed) — v1.0
- ✓ Append-only PE notes log via `POST /resources/{id}/notes`, visible on status queries — v1.0
- ✓ `pecp apply/get/status/delete` CLI with Rich tables, color-coded status badges, notes block — v1.0
- ✓ CLI respects `--api-url` flag and `PECP_API_URL` env var — v1.0

**Teams, Projects & Deployments** *(Phase 4: teams-projects-deployments)*
- ✓ Team creation/query with members, roles (owner/contributor), and metadata — v1.0
- ✓ Resources grouped into named projects with environment targeting and resource_count — v1.0
- ✓ Deployment status queryable per environment (`pecp deployments --team <team> --environment dev`) — v1.0
- ✓ Soft-delete on resources; atomic DeploymentRecord audit rows on every resource mutation — v1.0
- ✓ `pecp team create/show`, `pecp projects`, `pecp deployments`, `pecp apply --project` — v1.0

**Account Flow, UI & Demo Readiness** *(Phase 5: account-flow-ui-demo-readiness)*
- ✓ `pecp create awsaccount --team <team>` — async provisioning, returns resource ID immediately — v1.0
- ✓ `pecp status awsaccount --watch` — polls every 2s, shows PE notes live, exits on ready/failed — v1.0
- ✓ `pecp login awsaccount` — prints `export AWS_*` lines, exit code 0/1/2 for ready/not-found/not-ready — v1.0
- ✓ React dashboard: team inventory table with name/kind/status badge/environment — v1.0
- ✓ Deployment view: client-side environment filter (dev/staging/prod), no auto-polling, manual refresh — v1.0
- ✓ Demo seed script: 4 teams, 3 projects, resources in all lifecycle states, idempotent — v1.0

### Active (v1.1)

**GitHub Onboarding Integration**
- [ ] `IntegrationBase` ABC with `on_team_create`, `on_project_create`, `on_member_add`, `on_member_remove` lifecycle hooks — registered in an `INTEGRATION_REGISTRY`, fired after successful team/project/member DB writes
- [ ] `GitHubIntegration` implementing `IntegrationBase` with real httpx calls to GitHub API (`GITHUB_PAT`, `GITHUB_ORG` env vars)
- [ ] `pecp team create` fires `on_team_create` → creates GitHub team in org; `pecp team <name>` displays GitHub team slug/URL
- [ ] `pecp project create` fires `on_project_create` → creates GitHub repo `{org}/{team-name}-{project-name}` (empty); `pecp project <name>` lists repos with GitHub links
- [ ] `pecp project repo add <repo-name> --project <project> --team <team>` → creates additional GitHub repo and links it to the project
- [ ] `pecp team member add <user> <team>` → adds to PECP membership + syncs GitHub team membership (one-way)
- [ ] `pecp team member remove <user> <team>` → removes from PECP membership + removes from GitHub team

### Active (v2 candidates)

**Real Backend Adapters**
- [ ] Real AWS adapter (Lambda, S3, SQS, SNS, DynamoDB, Organizations) replacing mock
- [ ] Real Kubernetes adapter replacing mock
- [ ] Real Salesforce adapter (Connected App + Permission sets) replacing mock
- [ ] Real AEM adapter (site/workspace + author/publish environments) replacing mock
- [ ] Real Datadog, ServiceNow, JFrog adapters replacing mocks

**Authentication & Authorization**
- [ ] JWT/API key authentication enforced at the API layer (stub surfaces already in place)
- [ ] CLI authenticates with API key stored in `~/.pecp/config.yaml`
- [ ] PE approval flow for new teams — `pending → approved` before resources can be created

**Async Infrastructure**
- [ ] ARQ (asyncio) job queue replaces FastAPI BackgroundTasks for distributed worker support
- [ ] `FAILED → PROVISIONING` retry — PE-initiated via API with configurable backoff

**UI Enhancement**
- [ ] Self-service resource submission via UI forms (Humanitec-style)
- [ ] Account status credential display with copy-to-clipboard
- [ ] Mock activity log surfaced in dashboard per resource

### Out of Scope

- Real backend connections in PoC — no real cloud/SaaS credentials; mocks prove the pattern
- Auth enforcement in PoC — significant engineering with zero demo value; stub surfaces in place
- Team-configurable RBAC in PoC — policy engine adds weeks; v2 feature
- GitOps / git-backed state — reconciliation complexity without benefit in mock-adapter world
- Kubernetes operator / CRD runtime — org not versed in K8s; custom API server is the PoC vehicle
- Multi-cluster / multi-region account routing — flat per-team routing sufficient for PoC
- Drift detection / reconciliation loop — mock adapters can't drift; interface hook exists, loop deferred
- Backstage-style software catalog — PECP is a provisioner; scope creep risk

## Context

- Org is not versed in Kubernetes; custom Python API server chosen over K8s operator to maximize team contribution surface
- K8s operator is an acknowledged future migration path — adapter interfaces designed with this in mind
- AWS account creation is slow and semi-manual (PE team sometimes opens tickets manually) — async status with PE-editable notes hides this complexity from users
- Salesforce and AEM resource specs shipped as stubs with placeholder mocks — real specs need product/PE team input before v2
- The `apiVersion: pecp/v1` / `kind` YAML convention is deliberately Kubernetes-flavored to align mental model and make future K8s migration easier
- PoC achieved stakeholder buy-in goal — all 5 success criteria demonstrable in a single live session

## Constraints

- **Tech stack**: Python — org standard for backend services, maximizes team contribution surface
- **Scope**: All backends mocked — no real cloud access available during PoC development
- **Interface**: `pecp` CLI + UI dashboard + REST API (CLI wraps the API)
- **Auth**: None for PoC — must be designed out so it can be added without breaking CLI/API contracts
- **Resource spec format**: `apiVersion: pecp/v1`, `kind: PECP<Type>` — Kubernetes-flavored YAML, not negotiable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Custom API server over K8s operator | Org not versed in K8s; Python API server lowers contribution barrier | ✓ Good — team engagement high, PoC shipped in 4 weeks |
| Mock adapter layer with pluggable interface | All backends mocked for PoC but must be swappable; real adapters come later | ✓ Good — AdapterBase ABC locked in Phase 1, all 7 mocks registered in Phase 2 |
| Team-first resource ownership | All resources, accounts, and deployments belong to a team; no individual-owned resources | ✓ Good — clean scoping, team context enforced at API layer |
| Async account provisioning with PE notes | AWS account creation is slow and manually assisted; status polling + notes field hides this from users | ✓ Good — `--watch` polling and notes model validated in stakeholder demo |
| YAML spec convention mirrors Kubernetes | Aligns mental model, eases future K8s migration path | ✓ Good — `apiVersion: pecp/v1` convention adopted without friction |
| Owner/contributor roles (hardcoded for PoC) | Team-configurable RBAC is valid but out of scope; flat roles keep PoC simple | ✓ Good — sufficient for demo; PE approval flow deferred to v2 |
| SQLite + SQLAlchemy async for PoC | Zero infra dependencies; async patterns in place for production DB swap | ✓ Good — schema managed via Alembic, migration path to Postgres clear |
| FastAPI BackgroundTasks (not ARQ) for PoC | Requires no broker/worker process; pure overhead with mock adapters | ✓ Good — deferred to v2 when real adapters need distributed workers |
| React 19 SPA over Streamlit/Dash | Component flexibility; separates UI process from API process | ✓ Good — Vite + TanStack Query shipped; no coupling to API process |
| Vite proxy to FastAPI in dev | Eliminates CORS complexity during development; same-origin in prod | ✓ Good — `/api/` rewrite pattern works cleanly with dev server |

## Evolution

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-24 — v1.1 milestone started: GitHub onboarding integration*

# Research Summary — PECP

**Synthesized:** 2026-05-27

---

## Executive Summary

PECP is a lightweight internal developer platform control plane: it accepts Kubernetes-flavored YAML specs (`apiVersion: pecp/v1`, `kind: PECPLambda` etc.), routes them through a typed adapter layer to multiple backing systems, and exposes resource status via REST API + CLI + read-only dashboard. The deliberate design constraint — K8s mental model without requiring K8s — makes this a meaningful differentiator for enterprises not yet operating K8s clusters. All backing system calls are mocked for the PoC; the demo centerpiece is `PECPAccount` (AWS account creation), which demonstrates the hardest real-world problem: slow, semi-manual, async provisioning with PE-team communication built in.

The recommended implementation is a fully async Python stack: FastAPI + SQLAlchemy 2.x async + SQLite (swappable to Postgres) + Pydantic v2 discriminated unions for spec validation, Typer + Rich for CLI, React + TanStack Query for the dashboard. Every technology choice reinforces the async-first requirement — provisioning workflows are non-blocking end-to-end.

The critical risk is not technical: it is demonstrating business value rather than CRUD feasibility (pitfall PR-3). The demo script should be written before a line of code is written. The critical technical risk is the adapter interface (pitfall CP-3) — it must be locked from the perspective of the most complex real backend (AWS), not the simplest mock, before mock work begins.

---

## Recommended Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| API server | FastAPI ~0.111 + Uvicorn ~0.30 | Native async/await; auto-generates OpenAPI docs; co-evolves with Pydantic v2 |
| YAML parsing | PyYAML 6.x `safe_load` | Safe parse only — `yaml.load` is an RCE risk |
| Schema validation | Pydantic v2 ~2.7+ | Discriminated unions on `kind`; 5-50x faster than v1; required by FastAPI 0.100+ |
| Async tasks (PoC) | FastAPI `BackgroundTasks` | Zero infrastructure; mock adapters have no real I/O to justify a broker |
| Async tasks (post-PoC) | ARQ ~0.25 | Natively asyncio; avoids Celery's retrofitted async issues |
| Database (PoC) | SQLite + SQLAlchemy 2.x async | Zero infrastructure; one-line connection string swap to Postgres |
| Migrations | Alembic ~1.13 | Prevents schema collapse across demo iterations |
| CLI | Typer ~0.12 + Rich ~13 | Same annotation-driven DX as FastAPI; Rich spinners/tables for status polling |
| CLI HTTP client | httpx ~0.27 | Async-capable; doubles as FastAPI test client |
| UI framework | React 19 + Vite 6 | Widest component ecosystem; SPA served as static files from FastAPI |
| UI components | shadcn/ui + Radix UI | Copy-paste collection; no dependency lock-in; Table/Badge/Card cover the dashboard surface |
| UI data fetching | TanStack Query v5 | `refetchInterval` is the correct primitive for a status-polling dashboard |
| Adapter interface | Python ABC + `typing.Protocol` | Stateful per-adapter config; survives K8s migration unchanged |
| Type checking | mypy ~1.10 | Enforces adapter interface contracts across all mock implementations |
| Linting/formatting | ruff ~0.4 | Replaces flake8 + black + isort in one tool |

**Do not use:** Flask/Django (sync-first), Celery in PoC (requires broker), SQLModel (Pydantic v2 + SA 2.x async rough edges), `yaml.load` (RCE), Next.js (SSR overhead for read-only SPA), Streamlit/Dash (wrong component model for resource inventory).

**Version note:** Verify all versions against PyPI/npm before pinning.

---

## Table Stakes Features

What must exist for the PoC to feel complete and trustworthy to stakeholders.

| Feature | Notes |
|---------|-------|
| Declarative YAML spec (`pecp apply -f`) with `apiVersion/kind/metadata` | Primary interaction model; everything else is built on this |
| Resource status lifecycle: `pending → provisioning → ready → failed` | Users must observe what their request is doing without asking a human |
| Async provisioning with CLI status polling (`pecp status [--watch]`) | Sync wait is broken UX; fire-and-poll is the expected model |
| Team/ownership model — every resource belongs to a team | Foundation of all resource scoping and isolation |
| Team-scoped isolation at the API layer (not just CLI) | Stakeholders will ask; "the CLI enforces it" is a red flag |
| PE-editable notes as append-only log on resources | Encodes the AWS account creation reality; high demo value when PE adds notes live |
| Project grouping within teams | Named container representing a coherent workload |
| Multi-environment support (dev / staging / prod) | Teams expect the same spec to resolve to different configs per env |
| Pluggable adapter interface covering all 7 backing systems | Without this, a second backend requires a rewrite |
| Idempotent apply — `pecp apply` twice is a no-op or update | Fundamental contract of declarative systems |
| 202 Accepted + resource ID for async operations | Correct HTTP semantics for slow provisioning |
| Read-only UI dashboard (inventory + status + deployments) | Operators need a visual inventory view |
| Demo seed script (teams, projects, resources in all states) | One typo in a live demo breaks it; seed data prevents this |
| `RequestContext` auth stub in every route handler | Makes "how would you add auth?" answerable with code evidence |

---

## Architecture in One Page

### Six Components, One Direction of Control

```
CLI (Typer)
  └─ HTTP + X-Team-ID header
     └─ API Layer (FastAPI)
           ├─ TeamContextMiddleware → request.state.team
           ├─ Pydantic discriminated union validation on kind (422 if invalid)
           ├─ Writes PENDING record → Resource Store (SQLite/SA 2.x)
           └─ Dispatches BackgroundTask → Dispatcher
                  └─ State machine (PENDING → PROVISIONING → READY/FAILED)
                  └─ Adapter Registry (kind → AdapterBase subclass)
                        └─ Mock Adapters x 7 (AWS, K8s, Salesforce, AEM,
                                              Datadog, ServiceNow, JFrog)
                              └─ Logs intent, simulates latency,
                                 returns AdapterResult + provider_metadata
```

### Resource State Machine

```
PENDING → PROVISIONING → READY → DELETING → DELETED
                     └→ FAILED → PROVISIONING (retry)
```

The Dispatcher owns all transitions. The API Layer writes PENDING on create and never touches status again.

### Key Invariants

- Team context flows through all 5 layers: CLI header → middleware → route dependency → DB filter → AdapterContext.
- `spec` is immutable after admission. `status` is written only by the Dispatcher. `notes` is append-only, written only via the PE update endpoint.
- Every resource query includes `filter(Resource.team_id == team.id)`. No unscoped queries exist.
- Adapter interface (`provision`, `deprovision`, `get_status`) is locked before any mock is written. Designed for AWS complexity, not mock simplicity.

### K8s Migration Path

The adapter interface is the migration-stable surface. Pydantic ResourceSpec maps to CRD schema; Resource Store to etcd; Dispatcher to operator reconciler loop; AdapterBase subclasses are unchanged. When the org is K8s-ready, app teams rewrite nothing.

---

## Top Pitfalls to Avoid

| # | Pitfall | Prevention |
|---|---------|-----------|
| CP-1 | Schema validation in the adapter, not at API boundary | Validate against Pydantic discriminated union before touching DB; 422 with field-level errors |
| CP-2 | `status` and `notes` written by any code path | Dispatcher exclusively owns status transitions; notes endpoint is append-only |
| CP-3 | Adapter interface designed for mocks, not real backends | Lock full interface before writing any mock — designed from AWS perspective |
| CP-4 | Async jobs lost on process restart | Persist every job in `provisioning_jobs`; scan on startup and mark stale jobs `failed` |
| CP-5 | Team isolation only in CLI | `team_id` non-nullable FK on every resource; every endpoint requires team context |
| PR-3 | PoC proves CRUD on YAML, not business value | Write the demo script before writing any code |

**Zero-effort, high-leverage:** `yaml.safe_load` everywhere; `RequestContext` auth stub in Phase 1; configurable CLI API URL; exponential backoff on `--watch`; `UNIQUE(team_id, kind, name)` for idempotent apply.

---

## Build Order

### Phase 1: Foundation + Contracts
- Project scaffold (Python package, ruff, mypy, pytest, Alembic)
- SQLAlchemy 2.x async models: `Team`, `Resource`, `Project`, `Deployment`, `ProvisioningJob`, `Note`
- Pydantic ResourceSpec discriminated union — all 7 kinds defined
- `AdapterBase` + `AdapterContext` + `AdapterResult` interface — **LOCKED**
- `RequestContext` auth stub in route middleware
- Write demo script (narrative, not code)

### Phase 2: Core Engine
- Dispatcher: state machine + adapter dispatch + status writes
- Adapter Registry: kind → AdapterBase mapping, lifespan registration
- All 7 mock adapters: realistic latency, structured activity log, synthetic metadata
- `PECPAccount` mock: long dwell in PROVISIONING, PE notes simulation

### Phase 3: API Layer
- FastAPI app + lifespan + `TeamContextMiddleware`
- Routers: `/resources`, `/teams`, `/projects`, `/deployments`
- `GET /resources/{id}/status`, `POST /resources/{id}/notes`
- 202 Accepted pattern with BackgroundTask dispatch
- Idempotent apply (upsert + unique constraint)

### Phase 4: CLI
- `pecp apply`, `pecp get`, `pecp delete`, `pecp status [--watch]`
- `pecp team`, `pecp project`, `pecp deployments`, `pecp create awsaccount`
- Configurable API URL; exponential backoff on `--watch`; Rich tables + spinners

### Phase 5: UI Dashboard
- React + Vite + TanStack Query + Tailwind + shadcn/ui scaffold
- Team resource inventory, deployment view, account status with notes log
- TanStack Query `refetchInterval` for live status updates
- **Less than 20% of total PoC effort. No pagination, search, or complex state management.**

### Phase 6: Demo Polish
- Seed script: 2 teams, 3 projects, resources in all states
- `PECPAccount` slow-path walkthrough with live PE notes → READY
- Verify all pitfall preventions in place before stakeholder session

---

## Open Questions

| Question | Impact | Who answers |
|----------|--------|-------------|
| What does a `PECPSalesforce` resource spec look like? | Blocks `PECPSalesforceSpec` Pydantic model | Product / PE team |
| What does a `PECPAem` resource spec look like? | Blocks `PECPAemSpec` | Product / PE team |
| Does the org have a ServiceNow ITSM pattern influencing the approval flow? | Determines ServiceNow mock design | Platform Engineering |
| What triggers `FAILED → PROVISIONING` retry — automatic, PE-initiated, or CLI? | State machine completeness | Product decision |
| Long-term UI strategy — Backstage plugin, standalone, or other? | Determines whether PoC UI is throwaway or foundation | Architecture / leadership |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|-----------|-------|
| Stack | HIGH | Core technologies stable, widely adopted, mutually reinforcing. UI versions warrant verification before pinning. |
| Features | MEDIUM-HIGH | Reference products well-documented. Salesforce and AEM specs are stubs until product provides domain knowledge. |
| Architecture | HIGH | Standard control plane patterns. SQLite concurrency edge case is low-risk at PoC scale. |
| Pitfalls | HIGH (technical) / MEDIUM (strategic) | Grounded in async Python and control plane design patterns. |

**Overall: HIGH confidence in the technical direction. The adapter interface design and the demo narrative are the two highest-leverage investments before coding begins.**

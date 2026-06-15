# Roadmap: PECP — Platform Engineering Control Plane

## Overview

The PECP PoC delivers a Kubernetes-flavored control plane in five vertical slices. Phase 1 locks the contracts (adapter interface, auth stub, demo script) before any implementation begins. Phase 2 builds the async engine and all mock adapters. Phase 3 exposes the full REST API and core CLI so a developer can `pecp apply` and poll status against a running server. Phase 4 adds teams, projects, and deployment context so the platform becomes a multi-team tool. Phase 5 closes the loop with the AWS account provisioning demo, the read-only UI dashboard, and the seed data that makes the stakeholder walkthrough reproducible.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation + Contracts** - Lock adapter interface, auth stub, and demo script before any code is written (completed 2026-05-28)
- [x] **Phase 2: Core Engine** - Dispatcher, state machine, all 7 mock adapters, all 6 resource kinds (completed 2026-05-28)
- [x] **Phase 3: REST API + Core CLI** - Running FastAPI server, idempotent apply, `pecp apply/get/delete/status` (completed 2026-06-14)
- [x] **Phase 4: Teams, Projects, Deployments** - Team model, project grouping, environment-scoped deployment queries, team CLI commands (completed 2026-06-15)
- [ ] **Phase 5: Account Flow + UI + Demo Readiness** - PECPAccount async demo, CLI account commands, React dashboard, seed data

## Phase Details

### Phase 1: Foundation + Contracts

**Goal:** A team member can run `pecp apply -f resource.yaml --team payments` against a running PECP control plane and see the YAML persisted and listed via `GET /resources?team=payments` — proving the full stack (FastAPI + SQLAlchemy async + Typer CLI) end-to-end before any provisioning logic exists.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** ARCH-01, ARCH-02, ARCH-04, ADPT-01
**Success Criteria** (what must be TRUE):

  1. Running `mypy` and `ruff` against the codebase passes with zero errors — the typed skeleton is complete
  2. `AdapterBase` ABC exposes `provision`, `deprovision`, and `get_status` — any attempt to import a mock before implementing all three raises a `TypeError` at import time
  3. Every FastAPI route handler accepts a `RequestContext` dependency with `user_id`, `team_memberships`, and `is_pe_admin` — the stub is hardcoded but structured for JWT drop-in
  4. A `GET /resources` call without a team context parameter returns `400 Bad Request` — team scoping is enforced at the server, not the CLI
  5. The demo script (narrative walkthrough, not code) exists as a readable document and matches the final stakeholder session flow

**Plans:** 3/3 plans complete
**Wave 1**

- [x] 01-01-PLAN.md — Project scaffold + contracts (enums, ProvisionResult, ResourceSpec discriminated union, AdapterBase ABC, RequestContext) + Wave 0 test scaffolds [Wave 1]
- [x] 01-02-PLAN.md — Demo script narrative walkthrough (docs/DEMO-SCRIPT.md) per ARCH-04 + human checkpoint [Wave 1, parallel with 01-01]

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-03-PLAN.md — Walking Skeleton wiring: SQLite + FastAPI app + /resources GET/POST + Typer `pecp apply` + dev run + end-to-end round trip [Wave 2]

### Phase 2: Core Engine

**Goal:** A developer can instantiate any of the 7 mock adapters, call `provision()`, wait for the simulated latency, and inspect a structured activity log and synthetic provider metadata — all without a running HTTP server.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** ADPT-02, ADPT-03, KINDS-01, KINDS-02, KINDS-03, KINDS-04, KINDS-05, KINDS-06
**Success Criteria** (what must be TRUE):

  1. Calling `provision()` on any of the 7 mock adapters (AWS Lambda/Container/Data/Account, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog) completes without error and returns an `AdapterResult` containing synthetic provider metadata
  2. The `PECPAccount` mock adapter dwells in `PROVISIONING` for at least 3 seconds before transitioning to `READY`, simulating the real slow-path AWS account creation
  3. Pydantic rejects an invalid resource spec (e.g., a `PECPLambda` missing `source-code`) with field-level validation errors before any adapter is invoked
  4. The Dispatcher drives a resource from `PENDING` through `PROVISIONING` to `READY` (or `FAILED`) and all state transitions are written exclusively by the Dispatcher — no other code path can write `status`
  5. Each mock adapter's activity log records what it would call in production (e.g., `"Would call: aws lambda create-function ..."`) — structured and inspectable without parsing free text

**Plans:** 4/4 plans complete

**Wave 1**

- [x] 02-01-PLAN.md — Alembic init + ResourceSpec extension (4 new kinds) + db_session conftest fixture + Wave 0 test scaffolds [Wave 1]

**Wave 2** *(blocked on Wave 1)*

- [x] 02-02-PLAN.md — Real AwsLambdaMockAdapter + 9 placeholder adapters + Dispatcher with 10-entry ADAPTER_REGISTRY + end-to-end Lambda integration test [Wave 2]

**Wave 3** *(blocked on Wave 2; Plans 03 + 04 run in parallel)*

- [x] 02-03-PLAN.md — Real AwsContainerMockAdapter + AwsDataMockAdapter (5 subtype branches) + AwsAccountMockAdapter (3s slow-path) + slow-path Dispatcher test [Wave 3]
- [x] 02-04-PLAN.md — Real KubernetesMockAdapter + SalesforceMockAdapter + AemMockAdapter + DatadogMockAdapter + ServiceNowMockAdapter + JFrogMockAdapter + extended-kinds Dispatcher tests [Wave 3, parallel with 02-03]

### Phase 3: REST API + Core CLI

**Goal:** A developer can run `pecp apply -f lambda.yaml`, watch the server accept `202 Accepted`, then run `pecp status PECPLambda my-fn --team platform` and see the resource transition from `pending` to `ready` — entirely from the terminal against a live server.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** CTRL-01, CTRL-02, CTRL-03, CTRL-04, CLI-01, CLI-02, CLI-03, CLI-04, CLI-11
**Success Criteria** (what must be TRUE):

  1. `pecp apply -f resource.yaml` returns a resource ID immediately; a second identical `apply` is a no-op (same ID returned, no duplicate created); applying a changed spec triggers an update
  2. `pecp status <kind> <name> --team <team>` prints current provisioning status and notes; `--watch` polling deferred to Phase 5
  3. `pecp get PECPLambda --team platform` outputs a Rich table with name, status badge, and environment for every Lambda in that team
  4. A PE team member can append a note to any resource via `POST /resources/{id}/notes`, and that note appears in `pecp status` output in append-only order
  5. `pecp` respects `--api-url` flag and `PECP_API_URL` env var for API base URL; `~/.pecp/config.yaml` config file deferred to Phase 5

**Plans:** 3/3 plans complete

**Wave 1**

- [x] 03-01-PLAN.md — Schema migration (env, notes columns + UniqueConstraint), ResourceMetadata.env field, alembic render_as_batch, Wave 0 test scaffolds [Wave 1]

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — POST /resources idempotency + BackgroundTasks dispatch (fresh session), GET /resources/{id}, DELETE /resources/{id} with team verify, POST /resources/{id}/notes [Wave 2]

**Wave 3** *(blocked on Wave 2)*

- [x] 03-03-PLAN.md — CLI vertical slice: pecp get/status/delete with Rich tables, status badges, D-06 notes block; human end-to-end checkpoint [Wave 3]

### Phase 4: Teams, Projects, Deployments

**Goal:** A developer can create a team, add members with roles, group resources into named projects scoped to environments, and query deployment status per environment — entirely via `pecp` CLI commands against the running server.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** TEAM-01, TEAM-02, TEAM-03, CLI-05, CLI-06, CLI-07, CLI-08
**Success Criteria** (what must be TRUE):

  1. `pecp team create payments` creates a team and `pecp team payments` displays its members, their roles (owner/contributor), and metadata
  2. `pecp projects --team payments` lists all projects for the team, each showing its name, target environments, and resource count
  3. `pecp deployments --team payments --environment prod` shows only resources deployed to `prod`, with per-resource status — resources in other environments are excluded from the response
  4. A resource created without a team context (`POST /resources` with no team header) is rejected with `400` — team ownership is enforced at the API layer, not just the CLI

**Plans:** 3/3 plans complete

### Phase 5: Account Flow + UI + Demo Readiness

**Goal:** A stakeholder can watch a complete live demo: `pecp create awsaccount`, poll with `pecp status awsaccount --watch`, see PE add notes mid-provisioning, watch it reach `ready`, then open the UI dashboard and see the full team inventory and deployment view — all from pre-seeded data.
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** CLI-09, CLI-10, UI-01, UI-02, ARCH-03
**Success Criteria** (what must be TRUE):

  1. `pecp create awsaccount --team payments` returns immediately with a resource ID; `pecp status awsaccount --team payments --watch` polls and shows `provisioning` with PE notes updating live, then exits when the account reaches `ready`
  2. `pecp status awsaccount --team payments` displays credential output (account ID, access keys — synthetic) once status is `ready`
  3. The React dashboard loads the team resource inventory as a table with name, kind, status badge, and environment — data refreshes automatically without a page reload
  4. The deployment view filters the resource table by environment (dev / staging / prod) and shows per-resource status for the selected environment
  5. Running the seed script populates 2 teams, 3 projects, and resources spanning all lifecycle states (`pending`, `provisioning`, `ready`, `failed`) — a stakeholder session can start from a clean database with one command

**UI hint:** yes
**Plans:** TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + Contracts | 3/3 | Complete    | 2026-05-28 |
| 2. Core Engine | 4/4 | Complete    | 2026-05-28 |
| 3. REST API + Core CLI | 3/3 | Complete    | 2026-06-14 |
| 4. Teams, Projects, Deployments | 3/3 | Complete   | 2026-06-15 |
| 5. Account Flow + UI + Demo Readiness | 0/TBD | Not started | - |

# PECP — Platform Engineering Control Plane

## What This Is

A Kubernetes-inspired control plane that lets engineering teams declare infrastructure needs via YAML and have the platform provision those resources in the appropriate backing systems — AWS, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog. Teams submit typed resource specs (`kind: PECPLambda`, `kind: PECPDataService`, etc.) via the `pecp` CLI, and the platform handles routing, account management, and provisioning based on team context. For this PoC, all backing systems are mocked — the goal is to prove the control plane pattern and make it demo-able to stakeholders.

## Core Value

A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

## Requirements

### Validated

**Mock Adapter Layer** *(Validated in Phase 2: core-engine)*
- [x] Pluggable adapter interface (`AdapterBase` ABC) — swappable without changing control plane
- [x] Mock adapters for all 10 kinds: Lambda, Container, DataService (5 subtypes), Account (3s async dwell), Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog
- [x] Mock adapters log synthetic "Would call:" entries and return structured provider_metadata
- [x] Dispatcher routes PENDING → PROVISIONING → READY through ADAPTER_REGISTRY (10 entries)

### Validated

**REST API & CLI** *(Validated in Phase 3: rest-api-core-cli)*
- [x] REST API that accepts YAML resource specs, stores them, and dispatches to the appropriate mock adapter
- [x] Resource CRUD: create (idempotent), read, delete with status lifecycle (pending → provisioning → ready)
- [x] Query endpoint: list all resources for a team, filter by kind
- [x] Status endpoint: returns current state including `notes` list (PE-appendable via POST /resources/{id}/notes)
- [x] `pecp apply -f resource.yaml` — submit a resource spec (idempotent)
- [x] `pecp get <kind> --team <team>` — Rich table with color-coded status badges and env column
- [x] `pecp status <kind> <name> --team <team>` — table + notes block
- [x] `pecp delete <kind> <name> --team <team>` — team-scoped, cross-team delete rejected

### Validated

**Teams, Projects & Deployments** *(Validated in Phase 4: teams-projects-deployments)*
- [x] Teams are the primary organizational unit — all resources and accounts belong to a team
- [x] Team creation via `POST /teams` (409 on duplicate, auto-seeds owner member)
- [x] Team has members with roles: `owner` and `contributor`
- [x] A project is a named grouping of resources with resource_count aggregation
- [x] Projects map to environments; deployments are trackable per team and per environment
- [x] Soft-delete on resources: `deleted_at` timestamp, filtered from list/get queries
- [x] `DeploymentRecord` audit rows written atomically on every resource mutation
- [x] `pecp team create <name>` / `pecp team <name>` — Rich panel with members and roles
- [x] `pecp projects --team <team>` — list projects with resource counts
- [x] `pecp deployments --team <team>` — show deployment history by environment
- [x] `pecp apply ... --project <project>` — resource scoped to a project

### Active

**Control Plane API**

**Resource Types (all dispatched to mock adapters for PoC)**
- [ ] `PECPLambda` — function with `exposure` (public/private), `api-gateway` path, `source-code` reference
- [ ] `PECPContainer` — container workload with exposure and deployment context
- [ ] `PECPDataService` — subtypes: S3, SQS, SNS, RDS, DynamoDB
- [ ] `PECPAccount` — provision an AWS account for a team (async, with status polling and PE-editable notes)
- [ ] `PECPSalesforce` — Salesforce resource (spec TBD via research)
- [ ] `PECPAem` — AEM resource (spec TBD via research)

**`pecp` CLI**
- [ ] `pecp create awsaccount --team <team>` — request an AWS account (async provisioning)
- [ ] `pecp status awsaccount --team <team>` — check account readiness, access credentials, PE notes

**UI Dashboard**
- [ ] Team resource inventory view (what's provisioned, what state it's in)
- [ ] Deployment view per environment
- [ ] Account status view
- [ ] Read-only for PoC (no submit from UI — CLI is the submission path)

**Mock Adapter Layer**
- [ ] Pluggable adapter interface so real adapters can be swapped in without changing the control plane
- [ ] Mock adapters for: AWS (Lambda, ECS, S3, SQS, SNS, RDS, DynamoDB, Organizations), Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog
- [ ] Mock adapters log what they would provision and return synthetic status/metadata

### Out of Scope

- Real backend connections — no real AWS, K8s, or SaaS API calls in PoC; mocked to prove the pattern
- Auth/authz — no authentication for PoC; stub surfaces for future integration
- Team-configurable RBAC policies (e.g. "contributors on this team can also create accounts") — valid future feature, adds significant complexity for a PoC
- Kubernetes operator pattern — future direction once org is ready; custom API server is the PoC vehicle
- Multi-cluster or multi-region routing logic — account routing is flat for PoC

## Context

- Org is not versed in Kubernetes; custom Python API server chosen over K8s operator to maximize team contribution surface
- K8s operator is an acknowledged future migration path — adapter interfaces should be designed with this in mind
- AWS account creation is slow and semi-manual (external API is flaky, PE team sometimes opens tickets manually) — async status with PE-editable notes hides this complexity from users
- Salesforce and AEM resource specs are undefined; need research before those kinds can be designed
- The `apiVersion: pecp/v1` / `kind` YAML convention is deliberately Kubernetes-flavored to align mental model and make future K8s migration easier
- All resource kinds should accept `metadata.team` and optionally `spec.account` to support cross-account routing
- This is a PoC to get stakeholder buy-in — it needs to be demo-able, not production-hardened

## Constraints

- **Tech stack**: Python — org standard for backend services, maximizes team contribution surface
- **Scope**: All backends mocked — no real cloud access available during PoC development
- **Interface**: `pecp` CLI + UI dashboard + REST API (CLI wraps the API)
- **Auth**: None for PoC — must be designed out so it can be added without breaking CLI/API contracts
- **Resource spec format**: `apiVersion: pecp/v1`, `kind: PECP<Type>` — Kubernetes-flavored YAML, not negotiable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Custom API server over K8s operator | Org not versed in K8s; Python API server lowers contribution barrier | — Pending |
| Mock adapter layer with pluggable interface | All backends mocked for PoC but must be swappable; real adapters come later | — Pending |
| Team-first resource ownership | All resources, accounts, and deployments belong to a team; no individual-owned resources | — Pending |
| Async account provisioning with PE notes | AWS account creation is slow and manually assisted; status polling + notes field hides this from users | — Pending |
| YAML spec convention mirrors Kubernetes | Aligns mental model, eases future K8s migration path | — Pending |
| Owner/contributor roles (hardcoded for PoC) | Team-configurable RBAC is valid but out of scope; flat roles keep PoC simple | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

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
*Last updated: 2026-06-15 — Phase 4 complete: Teams, Projects, Deployments, Soft-delete — multi-team control plane with audit trail, 146 tests passing*

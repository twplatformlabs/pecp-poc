# PECP — Platform Engineering Control Plane

## What This Is

A Kubernetes-inspired control plane that lets engineering teams declare infrastructure needs via YAML and have the platform provision those resources in the appropriate backing systems — AWS, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog. Teams submit typed resource specs (`kind: PECPLambda`, `kind: PECPDataService`, etc.) via the `pecp` CLI, and the platform handles routing, account management, and provisioning based on team context. For this PoC, all backing systems are mocked — the goal is to prove the control plane pattern and make it demo-able to stakeholders.

## Core Value

A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Control Plane API**
- [ ] REST API that accepts YAML resource specs, stores them, and dispatches to the appropriate mock adapter
- [ ] Resource CRUD: create, read, update, delete with status lifecycle (pending → provisioning → ready → failed)
- [ ] Query endpoint: list all resources for a team, filter by type and environment
- [ ] Status endpoint: returns current state of any resource including a free-text `notes` field (updatable by PE team)

**Resource Types (all dispatched to mock adapters for PoC)**
- [ ] `PECPLambda` — function with `exposure` (public/private), `api-gateway` path, `source-code` reference
- [ ] `PECPContainer` — container workload with exposure and deployment context
- [ ] `PECPDataService` — subtypes: S3, SQS, SNS, RDS, DynamoDB
- [ ] `PECPAccount` — provision an AWS account for a team (async, with status polling and PE-editable notes)
- [ ] `PECPSalesforce` — Salesforce resource (spec TBD via research)
- [ ] `PECPAem` — AEM resource (spec TBD via research)

**Team & Onboarding**
- [ ] Teams are the primary organizational unit — all resources and accounts belong to a team
- [ ] Team creation requires PE approval (initial flow); subsequent teams can be self-service
- [ ] Team has members with roles: `owner` and `contributor`
- [ ] Owners control membership, infrastructure-level resources (AWS accounts), and team settings

**Projects & Environments**
- [ ] A project is a named grouping of resources with a deployment context
- [ ] Projects map to environments (dev, staging, prod)
- [ ] Deployments are trackable per team and per environment

**`pecp` CLI**
- [ ] `pecp apply -f resource.yaml` — submit a resource spec
- [ ] `pecp get <kind> --team <team>` — list resources of a type for a team
- [ ] `pecp delete <kind> <name> --team <team>` — delete a resource
- [ ] `pecp status <kind> <name> --team <team>` — show provisioning status and notes
- [ ] `pecp team <name>` — show team members, roles, and metadata
- [ ] `pecp team create <name>` — request team creation (triggers PE approval flow)
- [ ] `pecp projects --team <team>` — list projects with deployment context and change management metadata
- [ ] `pecp deployments --team <team> --environment <env>` — show deployment status for an environment
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
*Last updated: 2026-05-28 — Phase 1 complete: project scaffold, all contracts locked, walking skeleton live (25 tests passing)*

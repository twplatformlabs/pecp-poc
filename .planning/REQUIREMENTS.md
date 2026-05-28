# Requirements: PECP — Platform Engineering Control Plane

**Defined:** 2026-05-27
**Core Value:** A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

## v1 Requirements

### Control Plane API

- [ ] **CTRL-01**: Platform accepts a YAML resource spec via `POST /resources`, validates against the correct kind schema, and returns `202 Accepted` with a resource ID
- [ ] **CTRL-02**: Platform enforces a resource status lifecycle — `pending → provisioning → ready → failed` — with all transitions owned by the Dispatcher
- [ ] **CTRL-03**: `pecp apply -f resource.yaml` submitted twice is a no-op (spec unchanged) or triggers an update (spec changed) — no duplicate resources created
- [ ] **CTRL-04**: Any resource can have an append-only notes log that PE team members can write to, visible on status queries

### Teams & Onboarding

- [ ] **TEAM-01**: Team can be created and queried — members, roles (owner/contributor), and metadata are visible via `pecp team <name>`
- [ ] **TEAM-02**: Resources can be grouped into named projects — a project has a name and a deployment context (target environments)
- [ ] **TEAM-03**: Deployment status for a team's resources is queryable per environment (`pecp deployments --team <team> --environment dev`)

### Resource Kinds

- [ ] **KINDS-01**: `PECPLambda` — serverless function with `exposure` (public/private), `api-gateway` path, and `source-code` reference (e.g. `github://myorg/repo`)
- [ ] **KINDS-02**: `PECPContainer` — container workload with `exposure` (public/private), `image`, and deployment context
- [ ] **KINDS-03**: `PECPDataService` — managed data resource with `subtype` field (s3, sqs, sns, rds, dynamodb) and relevant config
- [ ] **KINDS-04**: `PECPAccount` — async AWS account provisioning with PE-editable notes, status polling, and credential output when ready
- [ ] **KINDS-05**: `PECPSalesforce` — provisions a Connected App and Permission sets/profiles for a team in Salesforce
- [ ] **KINDS-06**: `PECPAem` — provisions an AEM site/workspace and author + publish environments for a team

### Mock Adapters

- [x] **ADPT-01**: Pluggable adapter interface (`AdapterBase` ABC) with `provision`, `deprovision`, and `get_status` — locked before any mock is written, designed for AWS-complexity real backends
- [ ] **ADPT-02**: Mock adapters exist for all 7 backing systems: AWS (Lambda/Container/Data/Account), Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog
- [ ] **ADPT-03**: Mock adapters simulate realistic latency (3–10 seconds), produce structured activity logs (what they would call in production), and return synthetic provider metadata

### CLI

- [ ] **CLI-01**: `pecp apply -f resource.yaml` — submits a YAML spec to the control plane
- [ ] **CLI-02**: `pecp get <kind> --team <team>` — lists resources of a type for a team with status badges
- [ ] **CLI-03**: `pecp delete <kind> <name> --team <team>` — deletes a resource and triggers deprovisioning
- [ ] **CLI-04**: `pecp status <kind> <name> --team <team> [--watch]` — shows provisioning status and notes log; `--watch` polls with exponential backoff
- [ ] **CLI-05**: `pecp team <name>` — shows team members, roles, and metadata
- [ ] **CLI-06**: `pecp team create <name>` — creates a new team
- [ ] **CLI-07**: `pecp projects --team <team>` — lists projects for a team with environment and metadata
- [ ] **CLI-08**: `pecp deployments --team <team> --environment <env>` — shows deployment status filtered by environment
- [ ] **CLI-09**: `pecp create awsaccount --team <team>` — requests async AWS account provisioning (returns immediately with resource ID)
- [ ] **CLI-10**: `pecp status awsaccount --team <team>` — shows account readiness, access credentials (when ready), and PE notes history
- [ ] **CLI-11**: CLI API base URL is configurable via `--api-url` flag, `PECP_API_URL` env var, or `~/.pecp/config.yaml` (default: `http://localhost:8000`)

### UI Dashboard

- [ ] **UI-01**: Team resource inventory — table view showing all resources for a team with name, kind, status badge, and environment
- [ ] **UI-02**: Deployment view — resources filterable by environment (dev / staging / prod) with per-resource status

### Architecture & Cross-Cutting

- [x] **ARCH-01**: All resource API endpoints enforce team scope at the server — `GET /resources` without team context returns `400`, not all resources
- [x] **ARCH-02**: A `RequestContext` auth stub flows through every route handler with `user_id`, `team_memberships`, `is_pe_admin` — today hardcoded, structured for future JWT replacement
- [ ] **ARCH-03**: Demo seed script populates 2 teams, 3 projects, and resources in all lifecycle states before any stakeholder session
- [x] **ARCH-04**: Demo script (narrative walkthrough) is written before any implementation begins

## v2 Requirements

### Teams

- **TEAM-V2-01**: PE approval flow for new teams — team creation request goes through `pending → approved` before resources can be created
- **TEAM-V2-02**: Team-configurable RBAC — teams can define which actions require owner approval vs. are open to contributors

### Integrations

- **INTG-V2-01**: Real AWS adapter (Lambda, S3, SQS, SNS, DynamoDB, Organizations) replacing the mock
- **INTG-V2-02**: Real Kubernetes adapter replacing the mock
- **INTG-V2-03**: Real Salesforce adapter replacing the mock
- **INTG-V2-04**: Real AEM adapter replacing the mock
- **INTG-V2-05**: Real Datadog adapter (monitors, dashboards, API keys)
- **INTG-V2-06**: Real ServiceNow adapter (change management ticket creation)
- **INTG-V2-07**: Real JFrog adapter (artifact repository provisioning)

### Auth

- **AUTH-V2-01**: JWT/API key authentication enforced at the API layer
- **AUTH-V2-02**: CLI authenticates with an API key stored in `~/.pecp/config.yaml`

### Async

- **ASYNC-V2-01**: ARQ (asyncio) job queue replaces FastAPI BackgroundTasks for distributed worker support
- **ASYNC-V2-02**: `FAILED → PROVISIONING` retry — PE-initiated via API, with configurable backoff

### UI

- **UI-V2-01**: Self-service resource submission via UI forms (Humanitec-style)
- **UI-V2-02**: Account status credential display with copy-to-clipboard
- **UI-V2-03**: Mock activity log surfaced in dashboard per resource

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real backend connections in PoC | No real cloud/SaaS credentials available; mocks prove the pattern |
| Auth enforcement in PoC | Significant engineering with zero demo value; stubbed instead |
| Team-configurable RBAC in PoC | Policy engine (OPA/Cedar) adds 3–4 weeks; v2 feature |
| GitOps / git-backed state | Reconciliation complexity with no benefit in mock-adapter world |
| Kubernetes operator / CRD runtime | Org not versed in K8s; custom API server is the PoC vehicle |
| Multi-cluster / multi-region account routing | Architecturally complex; flat account routing per team is sufficient for PoC |
| Cost management / chargeback | Zero PoC value |
| Backstage-style software catalog | PECP is a provisioner; conflating it with a general catalog creates scope creep |
| Self-service UI for resource submission | CLI proves the submission contract; read-only dashboard is sufficient for demo |
| Drift detection / reconciliation loop | Mock adapters can't drift; build the interface hook but not the loop |
| ServiceNow live integration in PoC | External system dependency adds risk to demo environment; mocked |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01 | Phase 1 | Complete |
| ARCH-02 | Phase 1 | Complete |
| ARCH-04 | Phase 1 | Complete |
| ADPT-01 | Phase 1 | Complete |
| ADPT-02 | Phase 2 | Pending |
| ADPT-03 | Phase 2 | Pending |
| KINDS-01 | Phase 2 | Pending |
| KINDS-02 | Phase 2 | Pending |
| KINDS-03 | Phase 2 | Pending |
| KINDS-04 | Phase 2 | Pending |
| KINDS-05 | Phase 2 | Pending |
| KINDS-06 | Phase 2 | Pending |
| CTRL-01 | Phase 3 | Pending |
| CTRL-02 | Phase 3 | Pending |
| CTRL-03 | Phase 3 | Pending |
| CTRL-04 | Phase 3 | Pending |
| CLI-01 | Phase 3 | Pending |
| CLI-02 | Phase 3 | Pending |
| CLI-03 | Phase 3 | Pending |
| CLI-04 | Phase 3 | Pending |
| CLI-11 | Phase 3 | Pending |
| TEAM-01 | Phase 4 | Pending |
| TEAM-02 | Phase 4 | Pending |
| TEAM-03 | Phase 4 | Pending |
| CLI-05 | Phase 4 | Pending |
| CLI-06 | Phase 4 | Pending |
| CLI-07 | Phase 4 | Pending |
| CLI-08 | Phase 4 | Pending |
| CLI-09 | Phase 5 | Pending |
| CLI-10 | Phase 5 | Pending |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| ARCH-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-27*
*Last updated: 2026-05-27 after roadmap creation — all 33 requirements mapped*

# PECP Demo Scenarios

Each folder contains a `README.md` with step-by-step instructions and the YAML
fixture files needed to run it. Scenarios are self-contained — run them in any order
unless a prerequisite is noted.

## Prerequisites (all scenarios)

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- `pecp` CLI installed: `pip install -e .`

## Scenario Index

| # | Scenario | Phase | What it shows |
|---|----------|-------|---------------|
| [01](01-apply-idempotency/) | Apply & Idempotency | 3 | Same spec twice → same UUID, no duplicate created |
| [02](02-list-and-filter/) | List & Filter | 3 | Multi-kind list per team, cross-team isolation |
| [03](03-notes-and-status/) | Notes & Status | 3 | PE appends notes via API, surfaced in `pecp status` |
| [04](04-cross-team-protection/) | Cross-Team Delete Protection | 3 | Wrong `--team` → 404, owning team → success |
| [05](05-schema-validation/) | Schema Validation | 1 | Missing required field → 422 before adapter is invoked |
| [06](06-team-scope-enforcement/) | Team Scope Enforcement | 1 | No `?team` param → 400 even when bypassing the CLI |
| [07](07-account-async-slowpath/) | PECPAccount Async Slow Path | 2 | Account adapter dwells 3s in `PROVISIONING` before `READY` |
| [08](08-multi-adapter-kinds/) | Multi-Adapter Routing | 2 | Container + DataService (s3/dynamodb) + Kubernetes — each kind routes to its own adapter |
| [09](09-team-lifecycle/) | Team Lifecycle | 4 | `pecp team create` → show panel → 409 on duplicate |
| [10](10-project-grouping/) | Project Grouping | 4 | `project create` → `apply --project` → `pecp projects` with live resource count |
| [11](11-deployments-audit-trail/) | Deployments Audit Trail | 4 | apply → re-apply → delete → full history in `pecp deployments`; soft-delete invisible in `pecp get` |
| [12](12-json-output/) | JSON Output | 4 | `--json` flag on all data commands — pipeable to `jq` |

## Phase Coverage

| Phase | Feature Area | Scenarios |
|-------|-------------|-----------|
| 1 — Foundation & Contracts | Schema validation, team scope enforcement | 05, 06 |
| 2 — Core Engine | Mock adapters, async dispatch, activity logs | 07, 08 |
| 3 — REST API & Core CLI | Apply, get, status, delete, notes | 01, 02, 03, 04 |
| 4 — Teams, Projects, Deployments | Team lifecycle, project grouping, audit trail, JSON output | 09, 10, 11, 12 |

## Running the Full Demo Narrative

For a guided end-to-end walkthrough covering the stakeholder story — team onboarding,
Lambda deployment, async account provisioning, and inventory views — see
[docs/DEMO-SCRIPT.md](../docs/DEMO-SCRIPT.md).

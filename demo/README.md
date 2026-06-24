# PECP Demo Scenarios

Each folder contains a `README.md` with step-by-step instructions and the YAML
fixture files needed to run it. Scenarios are self-contained — run them in any order
unless a prerequisite is noted.

## Prerequisites (all scenarios)

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- `pecp` CLI installed: `pip install -e .`
- Seed data loaded (recommended for a richer display): `python scripts/seed.py`

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
| [13](13-account-async-provisioning/) | Account Async Provisioning | 5 | `pecp create awsaccount` → `--watch` polling → `pecp login` for credentials |
| [14](14-ui-dashboard/) | UI Dashboard | 5 | React browser dashboard — team dropdown, resource inventory, status badges, env filter |
| [15](15-github-automation/) | GitHub Automation | 8 | Team/project creation triggers GitHub teams, repos, and memberships via integration hooks |

## Phase Coverage

| Phase | Feature Area | Scenarios |
|-------|-------------|-----------|
| 1 — Foundation & Contracts | Schema validation, team scope enforcement | 05, 06 |
| 2 — Core Engine | Mock adapters, async dispatch, activity logs | 07, 08 |
| 3 — REST API & Core CLI | Apply, get, status, delete, notes | 01, 02, 03, 04 |
| 4 — Teams, Projects, Deployments | Team lifecycle, project grouping, audit trail, JSON output | 09, 10, 11, 12 |
| 5 — Account Flow & UI | Async account creation, `--watch`, credential retrieval, browser dashboard | 13, 14 |
| 6 — Data Model & Migration | `github_team_slug`, `ProjectRepoRecord`, Alembic migration | (infrastructure — no scenario needed) |
| 7 — Integration Hook Framework | `IntegrationBase` ABC, `INTEGRATION_REGISTRY`, BackgroundTasks dispatch | (infrastructure — no scenario needed) |
| 8 — GitHub Automation | GitHub team/repo provisioning via lifecycle hooks | 15 |

## Notes

- **Phases 6 and 7** are infrastructure-only: phase 6 added data columns and
  migrations, phase 7 built the hook dispatch framework. Neither has a standalone
  scenario because their impact is visible only through other scenarios.
- **Phase 8** (GitHub) requires `GITHUB_PAT` and `GITHUB_ORG` environment variables
  on the server process. Without them, the integration logs a warning and skips
  registration. See [Scenario 15](15-github-automation/) for setup details.
- **Phase 14** (UI Dashboard) requires the Vite dev server running alongside the
  API server: `npm run dev` from the `ui/` directory.

## Running the Full Demo Narrative

For a guided end-to-end walkthrough covering the stakeholder story — team onboarding,
Lambda deployment, async account provisioning, GitHub automation, and inventory views —
see [docs/DEMO-SCRIPT.md](../docs/DEMO-SCRIPT.md).

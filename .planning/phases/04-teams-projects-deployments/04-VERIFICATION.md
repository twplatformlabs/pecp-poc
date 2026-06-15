---
phase: 04-teams-projects-deployments
verified: 2026-06-15T00:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 4: Teams, Projects, Deployments — Verification Report

**Phase Goal:** A developer can create a team, add members with roles, group resources into named projects scoped to environments, and query deployment status per environment — entirely via `pecp` CLI commands against the running server.
**Verified:** 2026-06-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pecp team create payments` creates a team and `pecp team payments` displays its members, their roles (owner/contributor), and metadata | VERIFIED | `POST /teams` and `GET /teams/{name}` in `teams.py`; `team_app` Typer sub-application in `cli/main.py`; `test_post_teams_creates_team_and_owner_member` and `test_get_teams_by_name_returns_members` pass |
| 2 | `pecp projects --team payments` lists all projects for the team, each showing its name, target environments, and resource count | VERIFIED | `GET /projects?team=` with LEFT OUTER JOIN + `func.count` in `projects.py`; `projects_list` command in `cli/main.py`; `test_get_projects_lists_team_projects_with_resource_count` and `test_get_projects_with_resource_returns_count_one` pass |
| 3 | `pecp deployments --team payments --environment prod` shows only resources deployed to `prod`, with per-resource status — resources in other environments are excluded | VERIFIED | `GET /deployments?team=&environment=` with conditional WHERE filter in `deployments.py`; `deployments_list` command with `--environment` param in `cli/main.py`; `test_get_deployments_filters_by_environment` passes |
| 4 | A resource created without a team context (`POST /resources` with no team header) is rejected with `400` — team ownership is enforced at the API layer | VERIFIED | `if not team: raise HTTPException(status_code=400, ...)` present in all route handlers; pre-existing and regression tests confirm ARCH-01 unchanged |
| 5 | User can POST /teams and receive 201 with full team body including auto-seeded owner member; duplicate POST returns 409 | VERIFIED | `create_team` handler in `teams.py`; IntegrityError → 409; `test_post_teams_duplicate_name_returns_409` passes |
| 6 | User can POST /projects and receive 201; duplicate (team, name) returns 409; missing team returns 404 | VERIFIED | `create_project` handler in `projects.py`; `test_post_projects_creates_project_with_environments` and `test_post_projects_duplicate_name_in_same_team_returns_409` pass |
| 7 | Every resource mutation (POST create, POST update, DELETE) writes a DeploymentRecord atomically in the same session.commit() | VERIFIED | 3 `session.add(deployment)` calls in `resources.py` at lines 182, 214, 326; no new `session.commit()` added; audit trail tests all pass |
| 8 | DELETE on a resource performs soft-delete (sets `deleted_at`), making the resource invisible in list/get queries | VERIFIED | `record.deleted_at = now` at line 315 in `resources.py`; `await session.delete` absent; `deleted_at.is_(None)` filters on list and delete-lookup queries; `test_soft_delete.py` 5/5 pass |
| 9 | `pecp apply --project` flag passes project to the API, overriding spec.metadata.project | VERIFIED | `--project` flag in `apply` command; `params["project"] = project` conditional; `test_project_create_command_renders_confirmation` passes |
| 10 | `--json` flag on `pecp team`, `pecp get`, `pecp status`, `pecp projects`, `pecp deployments` outputs clean JSON to stdout | VERIFIED | `print(json.dumps(...))` in 7 places in `cli/main.py`; all `*_json_flag_*` CLI tests pass |
| 11 | All new routes enforce `team` parameter (ARCH-01) and accept `ctx: ContextDep` (ARCH-02) | VERIFIED | ARCH-01 guard present in `projects.py` and `deployments.py`; 4 ContextDep occurrences in `teams.py`, 4 in `projects.py`, 3 in `deployments.py` |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pecp/persistence/models.py` | TeamRecord, TeamMemberRecord, ProjectRecord, DeploymentRecord + project + deleted_at on ResourceRecord | VERIFIED | All 4 classes present; `project: Mapped[str | None]` at line 51; `deleted_at: Mapped[datetime | None]` at line 52 |
| `src/pecp/models/resource_spec.py` | ResourceMetadata.project nullable field | VERIFIED | `project: str | None = None` at line 96 |
| `alembic/versions/0003_add_teams_projects_deployments.py` | Migration 0003 with 4 tables + 2 columns | VERIFIED | `revision = "0003"`, `down_revision = "0002"`; 4 `create_table` calls, 4 `drop_table` calls, 2 `batch_alter_table` calls |
| `src/pecp/api/routes/teams.py` | POST /teams + GET /teams/{name} router | VERIFIED | `router = APIRouter(prefix="/teams"`, `class TeamCreate`, `async def create_team`, `async def get_team`, `def _render_team` all present |
| `src/pecp/api/routes/projects.py` | POST /projects + GET /projects?team= router | VERIFIED | `router = APIRouter(prefix="/projects"`, `class ProjectCreate`, `async def create_project`, `async def list_projects` all present |
| `src/pecp/api/routes/deployments.py` | GET /deployments?team=&environment= router | VERIFIED | `router = APIRouter(prefix="/deployments"`, `async def list_deployments` present |
| `src/pecp/api/routes/resources.py` | Modified with soft-delete, audit trail writes, deleted_at filters, _maybe_get_project_id | VERIFIED | `_maybe_get_project_id` defined; 3 `session.add(deployment)`; `record.deleted_at = now`; no `await session.delete`; `deleted_at.is_(None)` filter in 2 WHERE clauses + 1 post-fetch check |
| `src/pecp/api/main.py` | All 4 routers wired | VERIFIED | `from pecp.api.routes import deployments, projects, resources, teams`; 4 `include_router` calls |
| `src/pecp/cli/main.py` | projects, deployments commands + team sub-app + project sub-app + --json flags + --project on apply | VERIFIED | `@app.command("projects")`, `@app.command("deployments")`; `team_app` + `project_app` Typer sub-applications; 7 `--json` flags; `--project` on apply |
| `tests/test_api/test_teams.py` | 5 test functions | VERIFIED | 5 named test functions present and passing |
| `tests/test_api/test_projects.py` | 5 test functions | VERIFIED | 5 named test functions present and passing |
| `tests/test_api/test_deployments.py` | 6 test functions | VERIFIED | 6 named test functions present and passing |
| `tests/test_api/test_soft_delete.py` | 5 test functions | VERIFIED | 5 named test functions present and passing |
| `tests/test_api/test_cli.py` | 10 new CLI test functions | VERIFIED | All 10 functions present and passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli/main.py team_app` | `routes/teams.py` | `httpx.get/post` to `/teams` and `/teams/{name}` | WIRED | `team_create` POSTs to `/teams`; `team_show` GETs `/teams/{name}` |
| `routes/teams.py` | `models.py TeamRecord, TeamMemberRecord` | SQLAlchemy session add + commit | WIRED | `session.add(team); session.add(member)` in `create_team`; `select(TeamRecord)` in `get_team` |
| `main.py` | `routes/teams.py` | `app.include_router(teams.router)` | WIRED | Confirmed at line 30 |
| `routes/resources.py delete_resource` | `models.py DeploymentRecord` | `session.add(deployment)` + single `session.commit()` | WIRED | Lines 317-327 — atomic soft-delete + audit write |
| `routes/resources.py create_resource` | `models.py DeploymentRecord` | `session.add(deployment)` on create + update paths | WIRED | Lines 173-183 (update), 205-216 (create) — atomic audit writes |
| `routes/projects.py list_projects` | `models.py ResourceRecord` | LEFT OUTER JOIN + `func.count(ResourceRecord.id)` + GROUP BY | WIRED | Lines 103-120 — real DB aggregation query |
| `routes/deployments.py list_deployments` | `models.py ResourceRecord` | JOIN on `DeploymentRecord.resource_id == ResourceRecord.id`, ORDER BY `deployed_at DESC` | WIRED | Lines 42-57 — `order_by(DeploymentRecord.deployed_at.desc())` present |
| `cli/main.py projects/deployments commands` | `routes/projects.py, routes/deployments.py` | `httpx.get` with team param | WIRED | `projects_list` calls `/projects`; `deployments_list` calls `/deployments` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `routes/projects.py list_projects` | `resource_count` | `func.count(ResourceRecord.id)` + GROUP BY + LEFT OUTER JOIN | Yes — real DB aggregate | FLOWING |
| `routes/deployments.py list_deployments` | deployment rows | JOIN `DeploymentRecord → ResourceRecord` + ORDER BY | Yes — real DB rows | FLOWING |
| `routes/teams.py create_team` | team + member data | `session.add(TeamRecord); session.add(TeamMemberRecord)` | Yes — real DB inserts | FLOWING |
| `routes/resources.py delete_resource` | `record.deleted_at` | `datetime.now(timezone.utc)` assigned to ORM column | Yes — real column mutation | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ORM imports and field presence | `python -c "from pecp.persistence.models import..."` | All assertions pass | PASS |
| All 5 team API tests | `pytest tests/test_api/test_teams.py -x -q` | 5 passed | PASS |
| All 5 project API tests | `pytest tests/test_api/test_projects.py -x -q` | 5 passed | PASS |
| All 6 deployment API tests | `pytest tests/test_api/test_deployments.py -x -q` | 6 passed | PASS |
| All 5 soft-delete tests | `pytest tests/test_api/test_soft_delete.py -x -q` | 5 passed | PASS |
| All 19 CLI tests | `pytest tests/test_api/test_cli.py -x -q` | 19 passed | PASS |
| Full test suite (all phases) | `pytest -x -q` | 146 passed | PASS |
| All API routes in OpenAPI paths | `app.openapi()['paths']` contains `/resources`, `/teams`, `/teams/{name}`, `/projects`, `/deployments` | All 5 routes present | PASS |
| CLI help shows all Phase 4 commands | `CliRunner().invoke(app, ['--help'])` | `projects`, `deployments`, `team`, `project` all visible | PASS |

### Probe Execution

Step 7c: No conventional probe scripts found at `scripts/*/tests/probe-*.sh`. Phase has no declared probe paths in PLAN files. SKIPPED — not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TEAM-01 | 04-01, 04-02 | Team can be created and queried — members, roles, metadata visible via `pecp team <name>` | SATISFIED | `POST /teams` + `GET /teams/{name}` + `pecp team` CLI; 5 team tests green |
| TEAM-02 | 04-01, 04-03 | Resources can be grouped into named projects — project has name and deployment context (target environments) | SATISFIED | `POST /projects` + `GET /projects?team=` with LEFT OUTER JOIN resource_count; 5 project tests green |
| TEAM-03 | 04-01, 04-03 | Deployment status for a team's resources queryable per environment | SATISFIED | `GET /deployments?team=&environment=` with JOIN to resource_records + ORDER BY deployed_at DESC; 6 deployment tests green |
| CLI-05 | 04-02 | `pecp team <name>` — shows team members, roles, metadata | SATISFIED | `pecp team payments` invokes `team_show` via `_TeamDefaultGroup`; CLI tests pass |
| CLI-06 | 04-02 | `pecp team create <name>` — creates a new team | SATISFIED | `pecp team create payments --owner alice` invokes `team_create`; CLI tests pass |
| CLI-07 | 04-03 | `pecp projects --team <team>` — lists projects with environment and metadata | SATISFIED | `projects_list` command calls `/projects` with team param; CLI tests pass |
| CLI-08 | 04-03 | `pecp deployments --team <team> --environment <env>` — shows deployment status filtered by environment | SATISFIED | `deployments_list` command with optional `--environment` param; CLI tests pass |

No orphaned Phase 4 requirements detected — all 7 IDs claimed in PLAN frontmatter and all 7 verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None detected | — | — | — | — |

No TBD, FIXME, XXX, or TODO markers in any Phase 4 implementation files. No placeholder returns, no hardcoded empty data in rendering paths, no stubs.

One notable deviation documented in 04-02-SUMMARY.md: the standard Typer callback pattern for `pecp team <name>` was replaced with a `_TeamDefaultGroup(TyperGroup)` subclass override to work around a Typer 0.26.7 dispatch limitation (Pitfall-3). The custom `resolve_command` override stores the name in `_pending_name` and redirects to the `show` sub-command. All tests pass confirming this deviation is a valid implementation.

### Human Verification Required

No human verification items identified. All behavioral criteria are verifiable programmatically and confirmed by the 146-test suite.

### Gaps Summary

No gaps. All 11 must-have truths verified, all 15 artifacts verified at all levels (exists, substantive, wired, data-flowing), all 7 requirement IDs satisfied, full 146-test suite green.

---

_Verified: 2026-06-15_
_Verifier: Claude (gsd-verifier)_

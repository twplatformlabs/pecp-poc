---
phase: "04"
plan: "03"
subsystem: projects-deployments-soft-delete-cli
tags:
  - api
  - cli
  - projects
  - deployments
  - soft-delete
  - audit-trail
  - vertical-slice
dependency_graph:
  requires:
    - "04-01: schema foundation (ProjectRecord, DeploymentRecord, ResourceRecord.project, ResourceRecord.deleted_at)"
    - "04-02: teams vertical slice (POST /teams, GET /teams/{name}, pecp team commands)"
  provides:
    - "POST /projects and GET /projects?team= FastAPI route handlers"
    - "GET /deployments?team=&environment= FastAPI route handler"
    - "Modified POST /resources: DeploymentRecord(create/update) written atomically"
    - "Modified DELETE /resources/{id}: soft-delete (deleted_at=now) + DeploymentRecord(delete) written atomically"
    - "list_resources and delete_resource lookup filter deleted_at IS NULL"
    - "get_resource returns 404 when record.deleted_at is not None"
    - "_maybe_get_project_id helper in resources.py"
    - "pecp projects --team --json CLI command"
    - "pecp deployments --team --environment --json CLI command"
    - "pecp apply --project flag"
    - "pecp project create sub-command"
  affects:
    - "Phase 5: UI dashboard (projects and deployments data available via API)"
tech_stack:
  added: []
  patterns:
    - "LEFT OUTER JOIN + func.count + GROUP BY for resource_count aggregation (Pattern 3)"
    - "Multi-table JOIN DeploymentRecord → ResourceRecord with ORDER BY deployed_at DESC (Pattern 2)"
    - "Soft-delete via deleted_at column + IS NULL filter on all list/lookup queries (D-11)"
    - "Atomic audit trail: DeploymentRecord added to session BEFORE existing session.commit() (Pitfall 2)"
    - "_maybe_get_project_id helper: graceful None return on unknown project (Pitfall 6)"
    - "JSON Text column round-trip: json.dumps on write, json.loads on read (Pitfall 4)"
key_files:
  created:
    - src/pecp/api/routes/projects.py
    - src/pecp/api/routes/deployments.py
  modified:
    - src/pecp/api/routes/resources.py
    - src/pecp/api/main.py
    - src/pecp/cli/main.py
decisions:
  - "Soft-delete via deleted_at IS NULL filter on list_resources and delete_resource lookup; get_resource checks record.deleted_at is not None post-fetch (Pitfall 5)"
  - "Deployment audit trail writes share existing session.commit() calls for atomicity (Pitfall 2) — no new commit sites added"
  - "Race-loser IntegrityError branch explicitly skips deployment write — winner already wrote one (audit integrity)"
  - "No-op POST (same spec) branch skips deployment write — no mutation, no audit row"
  - "GET /deployments JOIN does NOT filter on ResourceRecord.deleted_at — audit trail must remain visible after soft-delete (D-11)"
  - "Worktree required merge from main to get Plan 01/02 foundation before executing Plan 03 (fast-forward merge)"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_modified: 5
---

# Phase 04 Plan 03: Projects + Deployments + Soft-Delete Vertical Slice Summary

**One-liner:** FastAPI /projects and /deployments routes with LEFT OUTER JOIN aggregation and audit-trail writes, surgical soft-delete modifications to resources.py with three atomic DeploymentRecord writes, and pecp projects/deployments/project CLI commands completing Phase 4.

## What Was Built

### New Route Module: `src/pecp/api/routes/projects.py`

- `router = APIRouter(prefix="/projects", tags=["projects"])`
- `class ProjectCreate(BaseModel)` with `name: str`, `team: str`, `environments: list[str]`
- `async def create_project(...)` — POST "" (status_code=201): lookup team by name to get team_id FK (404 if missing), create ProjectRecord with json.dumps(environments), catch IntegrityError → 409 for duplicate (team, name) per D-04. Returns id/team_id/name/environments(list)/created_at.
- `async def list_projects(...)` — GET "": ARCH-01 guard, LEFT OUTER JOIN ProjectRecord → TeamRecord → ResourceRecord with func.count(ResourceRecord.id) + GROUP BY ProjectRecord.id to compute resource_count per project. Returns environments as deserialized list (Pitfall 4).

### New Route Module: `src/pecp/api/routes/deployments.py`

- `router = APIRouter(prefix="/deployments", tags=["deployments"])`
- `async def list_deployments(...)` — GET "": ARCH-01 guard, JOIN DeploymentRecord → ResourceRecord on resource_id, WHERE team filter on ResourceRecord.team, optional WHERE DeploymentRecord.environment filter, ORDER BY deployed_at DESC (D-16). Returns resource_name/kind/change_type/status/deployed_at/environment per row. Soft-deleted resources are NOT filtered — audit trail must remain visible (D-11).

### Modified `src/pecp/api/main.py`

- Import changed to `from pecp.api.routes import deployments, projects, resources, teams` (alphabetical)
- Added `app.include_router(projects.router)` and `app.include_router(deployments.router)` after teams.router

### Modified `src/pecp/api/routes/resources.py`

All changes are surgical — no functions renamed, no public signatures changed, ~80 lines added and ~6 modified.

**New helper `_maybe_get_project_id(project_name, team, session)`:** Resolves project name to ID via JOIN to TeamRecord. Returns None gracefully when project not found (Pitfall 6 — no error raised).

**`list_resources`:** Added `ResourceRecord.deleted_at.is_(None)` to WHERE clause (Pitfall 1 / D-11).

**`get_resource`:** Changed `if record is None:` to `if record is None or record.deleted_at is not None:` (Pitfall 5).

**`delete_resource`:** 
- Initial lookup adds `ResourceRecord.deleted_at.is_(None)` filter (second DELETE returns 404)
- `await session.delete(record)` replaced with `record.deleted_at = now` (soft-delete)
- `DeploymentRecord(change_type="delete", ...)` added to session before existing `session.commit()` (atomic)

**`create_resource` update branch:** Added `existing.project = spec.metadata.project` (D-07) and `DeploymentRecord(change_type="update", ...)` before existing `session.commit()` (atomic).

**`create_resource` new-create branch:** Added `project=spec.metadata.project` to `ResourceRecord(...)` kwargs (D-08) and `DeploymentRecord(change_type="create", ...)` before existing `session.commit()` (atomic, Pitfall 2).

**`create_resource` race-loser branch:** Intentionally no deployment write — winner already wrote one in its create path.

**`create_resource` no-op branch:** Intentionally no deployment write — no mutation occurred.

### Modified `src/pecp/cli/main.py`

**`apply` command:** Added `--project` flag (`str | None`). When provided, adds `project=<name>` to params dict before httpx.post; when absent, params dict contains only `team` (D-07).

**`pecp projects` command (`projects_list`):** GET /projects with `--team` (required), `--environment` (optional), `--json`, `--api-url`. Rich table with ID/Name/Environments/Resources columns. `--json` outputs `print(json.dumps(data))`.

**`pecp deployments` command (`deployments_list`):** GET /deployments with `--team` (required), `--environment` (optional), `--json`, `--api-url`. Rich table with Resource/Kind/Change/Status/Deployed columns. CLI does not re-sort — API delivers rows in deployed_at DESC order (D-16).

**`pecp project create` sub-command:** `project_app = typer.Typer(...)` registered via `app.add_typer(project_app, name="project")`. `@project_app.command("create")` accepts `name` (Argument), `--team`, `--env` (comma-separated), `--json`, `--api-url`. Splits env on commas, POSTs to /projects, prints `Project {name} created (id: {id})` on success (D-06).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement /projects and /deployments route modules; wire into FastAPI app | c6ae686 | projects.py, deployments.py, main.py |
| 2 | Modify resources.py for soft-delete, audit trail, deleted_at filters, project population | 2a24b4f | resources.py |
| 3 | Add pecp projects, pecp deployments CLI; --project on apply; pecp project create | 2e568c0 | cli/main.py |

## Routes Added

| Method | Path | Status Code | Description |
|--------|------|-------------|-------------|
| POST | /projects | 201 | Create project for a team (404 if team missing, 409 on duplicate) |
| GET | /projects | 200 | List projects with resource_count via LEFT OUTER JOIN |
| GET | /deployments | 200 | Audit trail with JOIN to resource_records, sorted newest-first |

## Routes Modified

| Method | Path | Change |
|--------|------|--------|
| GET | /resources | Added deleted_at IS NULL filter |
| GET | /resources/{id} | Returns 404 when deleted_at is not None |
| POST | /resources | DeploymentRecord(create/update) written atomically; project field populated |
| DELETE | /resources/{id} | Soft-delete (sets deleted_at) + DeploymentRecord(delete) atomically |

## CLI Commands Added

| Command | HTTP | Description |
|---------|------|-------------|
| `pecp projects --team X` | GET /projects | Show projects table with resource counts |
| `pecp projects --team X --json` | GET /projects | Clean JSON array |
| `pecp deployments --team X` | GET /deployments | Show deployment audit table |
| `pecp deployments --team X --environment prod` | GET /deployments | Filtered by environment |
| `pecp deployments --team X --json` | GET /deployments | Clean JSON array |
| `pecp project create <name> --team X --env dev,staging,prod` | POST /projects | Create project explicitly (D-06) |
| `pecp apply -f x.yaml --team X --project payments-backend` | POST /resources | Override spec.metadata.project (D-07) |

## Test Results — Wave 0 Tests Turned GREEN

| Test File | Tests | Result | Requirement |
|-----------|-------|--------|-------------|
| `tests/test_api/test_projects.py` | 5 | 5 PASSED | TEAM-02 |
| `tests/test_api/test_deployments.py` | 6 | 6 PASSED | TEAM-03 |
| `tests/test_api/test_soft_delete.py` | 5 | 5 PASSED | D-11/D-12 |
| `tests/test_api/test_cli.py` (new Wave 0 tests) | 7 | 7 PASSED | CLI-07/08 + D-17 |
| Full pytest suite | 146 | 146 PASSED | Phase 4 complete |

## Audit Trail Integrity Confirmation

- Deployment writes for create, update, and delete are committed atomically with the resource mutation in ONE `session.commit()` call per mutation site (Pitfall 2)
- The IntegrityError race-loser branch in `create_resource` does NOT write a deployment row — the winner already committed one in its create path
- The no-op POST branch (same spec) does NOT write a deployment row — no mutation occurred, no audit event
- The `deleted_at` IS NULL filter on the delete_resource lookup ensures second DELETE returns 404 (double-delete protection)
- The deployment audit trail query does NOT filter on `ResourceRecord.deleted_at` — soft-deleted resources remain visible in the audit log per D-11

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree missing Plan 01/02 foundation**
- **Found during:** Task 1 start
- **Issue:** The worktree branch `worktree-agent-a21392417a3f61699` was created from commit 3b1411b (before Plan 01 and Plan 02 commits landed on main). The worktree was missing: teams.py route module, test_projects.py, test_deployments.py, test_soft_delete.py, test_teams.py, alembic migration 0003, ResourceRecord.project/deleted_at columns, DeploymentRecord/TeamRecord/ProjectRecord ORM classes, and the cli/main.py team commands.
- **Fix:** `git merge main --no-edit` (fast-forward) from inside the worktree pulled in all 15 missing files from the wave 1 and wave 2 commits.
- **Files modified:** 15 files merged from main
- **Commit:** Fast-forward merge (no additional commit)

**2. [Rule 1 - Bug] Ruff I001 import sort on resources.py**
- **Found during:** Task 2 ruff check
- **Issue:** Adding `DeploymentRecord, ProjectRecord, TeamRecord` imports and `from sqlalchemy.ext.asyncio import AsyncSession` in separate lines caused I001 (unsorted import block)
- **Fix:** `ruff check --fix` auto-sorted the imports into correct block order
- **Files modified:** `src/pecp/api/routes/resources.py`
- **Commit:** Included in Task 2 commit 2a24b4f

**3. [Rule 1 - Bug] Unused type: ignore[return-value] on _maybe_get_project_id**
- **Found during:** Task 2 mypy check
- **Issue:** `result.scalar_one_or_none()` in `_maybe_get_project_id` returned `str | None` correctly; the `# type: ignore[return-value]` was unnecessary and mypy reported it as "Unused 'type: ignore' comment"
- **Fix:** Removed the `# type: ignore[return-value]` comment
- **Files modified:** `src/pecp/api/routes/resources.py`
- **Commit:** Included in Task 2 commit 2a24b4f

## Known Stubs

None. All routes return real data from the database. All CLI commands call real API endpoints (or mocked ones in tests). No placeholder or hardcoded values exist in rendering logic.

## Threat Flags

All threats documented in the plan's threat model have been mitigated in implementation:

- **T-04-03-01/02:** ARCH-01 enforced on GET /deployments and GET /projects — both return 400 without team param
- **T-04-03-03:** Atomicity enforced — both ResourceRecord mutation and DeploymentRecord insert committed in single session.commit() call
- **T-04-03-04:** Soft-deleted resource inaccessible via GET /resources/{id} (record.deleted_at is not None → 404)
- **T-04-03-05:** GET /deployments JOIN includes WHERE ResourceRecord.team == team filter (no cross-team leakage)
- **T-04-03-06:** Race-loser branch has no deployment write (audit double-count prevented)

No new security-relevant surface beyond what the threat model covers.

## Self-Check: PASSED

- `src/pecp/api/routes/projects.py` — EXISTS with `router = APIRouter(prefix="/projects"`, `class ProjectCreate`, `async def create_project`, `async def list_projects`
- `src/pecp/api/routes/deployments.py` — EXISTS with `router = APIRouter(prefix="/deployments"`, `async def list_deployments`
- `src/pecp/api/main.py` — EXISTS with `from pecp.api.routes import deployments, projects, resources, teams` and all four `app.include_router(...)` calls
- `src/pecp/api/routes/resources.py` — EXISTS with `_maybe_get_project_id`, `record.deleted_at = now`, `change_type="create"`, `change_type="update"`, `change_type="delete"`, `project=spec.metadata.project` (×2), `session.add(deployment)` (×3), `ResourceRecord.deleted_at.is_(None)` (×2)
- `src/pecp/cli/main.py` — EXISTS with `@app.command("projects")`, `@app.command("deployments")`, `--project` flag on apply, `project_create`, `project_app`, `app.add_typer(project_app, name="project")`
- Commits c6ae686, 2a24b4f, 2e568c0 — all in git log
- `pytest -x -q` — 146 PASSED (Phase 4 complete)

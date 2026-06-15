---
phase: 04-teams-projects-deployments
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - alembic/versions/0003_add_teams_projects_deployments.py
  - src/pecp/api/main.py
  - src/pecp/api/routes/deployments.py
  - src/pecp/api/routes/projects.py
  - src/pecp/api/routes/resources.py
  - src/pecp/api/routes/teams.py
  - src/pecp/cli/main.py
  - src/pecp/models/resource_spec.py
  - src/pecp/persistence/models.py
  - tests/test_api/test_cli.py
  - tests/test_api/test_deployments.py
  - tests/test_api/test_projects.py
  - tests/test_api/test_soft_delete.py
  - tests/test_api/test_teams.py
findings:
  critical: 3
  warning: 4
  info: 3
  total: 10
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 04 introduces teams, projects, deployments, and soft-delete. The overall structure is solid: migration is reversible, ORM models align with the migration, route handlers follow the established ARCH-01/02 conventions, and the idempotency logic in `create_resource` is carefully handled. However, three blockers were found: a broken CLI feature (the `--project` flag is silently swallowed because the API has no corresponding query parameter), a data-integrity hole (soft-deleted resources can receive new notes), and a race condition in the CLI's `pecp delete` flow that can act on the wrong resource. Four warnings cover a bare `except Exception` in the `_TeamDefaultGroup` router, a missing team-scoping check on the `/notes` endpoint, project-name storage that is cross-team ambiguous in the JOIN, and a missing `team` check on `add_note`. Three info items cover minor quality issues.

---

## Critical Issues

### CR-01: CLI `--project` flag is silently ignored — feature is broken end-to-end

**File:** `src/pecp/cli/main.py:88-91`

**Issue:** The `apply` command sends `--project` as a query parameter (`params["project"] = project`). The `create_resource` handler signature is:

```python
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ...
```

There is no `project` query parameter declared on the endpoint. FastAPI silently ignores unknown query parameters when they are not declared on the handler. The project override value is therefore dropped on the floor — it never reaches `spec.metadata.project`, so `project=None` is stored on the `ResourceRecord` and `DeploymentRecord` regardless of what the CLI user supplied. The documented D-07 behaviour ("CLI --project overrides spec.metadata.project") does not work at all.

**Fix:** Add `project: str | None = None` to the `create_resource` signature and use it to override `spec.metadata.project` before the idempotency lookup:

```python
@router.post("", status_code=202)
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    project: str | None = None,          # D-07: CLI --project override
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, str]:
    ...
    # After spec is validated:
    effective_project = project if project is not None else spec.metadata.project
    # Use effective_project wherever spec.metadata.project was used
```

---

### CR-02: `add_note` endpoint allows notes on soft-deleted resources

**File:** `src/pecp/api/routes/resources.py:346-351`

**Issue:** The `add_note` handler fetches the resource without checking `deleted_at`:

```python
result = await session.execute(
    select(ResourceRecord).where(ResourceRecord.id == resource_id)
)
record = result.scalar_one_or_none()
if record is None:
    raise HTTPException(status_code=404, detail="Resource not found")
```

A resource that has been soft-deleted is invisible via `GET /resources/{id}` (which correctly checks `deleted_at`) and via `GET /resources` list, but `POST /resources/{id}/notes` will still find and mutate it. This means a caller can add notes to a deleted resource, leaving data in a state the system claims is inaccessible. It also reveals deleted resource IDs to any caller who already knows them.

**Fix:** Add the `deleted_at` check to the lookup:

```python
result = await session.execute(
    select(ResourceRecord).where(
        ResourceRecord.id == resource_id,
        ResourceRecord.deleted_at.is_(None),
    )
)
```

---

### CR-03: CLI `delete` and `status` commands have a TOCTOU race — wrong resource can be acted on

**File:** `src/pecp/cli/main.py:257-296` (delete), `src/pecp/cli/main.py:182-212` (status)

**Issue:** Both the `delete` and `status` commands resolve a resource to its ID with a first `GET /resources?team=…&kind=…` call, then use that `id` in a second `DELETE /resources/{id}` or `GET /resources/{id}` call. Between the two calls another process can create or soft-delete a resource with the same `(kind, name)`, and the CLI will act on a stale `id`. More concretely for `delete`: the list call returns id `A`; the resource is deleted externally; a new resource with the same name is created and gets id `B`; the CLI then tries to delete `A`, which already returns 404, but if the timing is different it could delete the new `B`. This is a TOCTOU window that makes the delete unsafe for concurrent workflows.

The deeper design problem is that the API does not expose a direct `DELETE /resources?team=T&kind=K&name=N` endpoint, forcing the CLI into this two-step pattern.

**Fix (minimal):** Add a `name` filter to `GET /resources` and expose a name-scoped delete endpoint so the API can perform the lookup and delete atomically:

```
DELETE /resources?team=T&kind=K&name=N
```

As a short-term mitigation, the CLI should re-confirm the name field from the delete response to detect the mismatch, and document the race window.

---

## Warnings

### WR-01: `_TeamDefaultGroup.resolve_command` swallows all exceptions, masking real errors

**File:** `src/pecp/cli/main.py:469-480`

**Issue:** The `resolve_command` override catches the bare `except Exception:` to intercept unrecognised command tokens. Any real error thrown by `super().resolve_command()` — such as an `AttributeError` or `ImportError` from a broken plugin — will be silently swallowed and misinterpreted as "this token is a team name", redirecting to the `show` sub-command with a nonsensical name. The `raise` at the end of the `except` block only re-raises if `show_cmd is None or team_name is None`, so for the vast majority of real errors the exception is dropped.

**Fix:** Narrow the catch to the specific Click exception that signals an unrecognised command (typically `click.UsageError` or `click.exceptions.UsageError`):

```python
import click

try:
    return super().resolve_command(ctx, args)
except click.UsageError:
    # First token is not a known command — treat as team name
    team_name = args[0] if args else None
    show_cmd = self.commands.get("show")
    if show_cmd is not None and team_name is not None:
        _TeamDefaultGroup._pending_name = team_name
        return (team_name, show_cmd, args[1:])
    raise
```

---

### WR-02: `add_note` endpoint has no team-scope guard — any caller can mutate any resource

**File:** `src/pecp/api/routes/resources.py:331-363`

**Issue:** `GET /resources/{id}` and `DELETE /resources/{id}` both accept a `team` query parameter and return 404 if the resource's team does not match (correctly collapsing the 403 to avoid information leakage per A5). `POST /resources/{id}/notes` accepts no `team` parameter and performs no ownership check. Any caller who knows a `resource_id` (or can enumerate IDs) can append notes to resources belonging to other teams. This contradicts the ARCH-01 team-scoping convention applied everywhere else.

**Fix:** Add `team: str | None = None` to `add_note`, require it, and verify `record.team == team` before proceeding:

```python
@router.post("/{resource_id}/notes", status_code=201)
async def add_note(
    resource_id: str,
    body: NoteCreate,
    team: str | None = None,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, list[dict[str, str]]]:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    ...
    if record.team != team:
        raise HTTPException(status_code=404, detail="Resource not found")
```

---

### WR-03: Project `resource_count` JOIN is ambiguous when two teams have a project with the same name

**File:** `src/pecp/api/routes/projects.py:101-119`

**Issue:** The LEFT OUTER JOIN condition linking `ResourceRecord` to `ProjectRecord` is:

```python
(ResourceRecord.project == ProjectRecord.name)
& (ResourceRecord.team == team)
& (ResourceRecord.deleted_at.is_(None))
```

`ResourceRecord.project` stores the **project name string** (not a `project_id` FK). Two different teams can create projects with the same name (e.g., both "platform" and "payments" have a project called "backend"). When `GET /projects?team=payments` runs, the JOIN matches `resource.project == 'backend'` AND `resource.team == 'payments'`, which is correct. However, if a resource in team "payments" was assigned a project name that happens to match a project in team "platform", the join silently puts it in the wrong bucket (or double-counts it). The underlying problem is that `resource_records.project` is a free-text name and not a proper FK to `projects.id`.

**Fix:** Populate `resource_records.project` with the project ID (not the project name) when a project is resolved, and update the JOIN condition to use `ResourceRecord.project == ProjectRecord.id`. This requires a small schema migration and updates to the write path in `resources.py`.

Alternatively, as a short-term fix without a migration, add `ProjectRecord.team_id == TeamRecord.id` as an additional JOIN guard to prevent cross-team collisions, but this does not fully address the ambiguity if the same resource name appears in two same-named projects.

---

### WR-04: `_TeamDefaultGroup._pending_name` is class-level state — will corrupt concurrent CLI invocations

**File:** `src/pecp/cli/main.py:457-509`

**Issue:** `_pending_name` is a class-level attribute shared across all instances. The comment in the source acknowledges this: "Thread-safe for PoC single-process CLI use." However, if the CLI is ever invoked from a context where multiple commands run in the same process (e.g., test suite running CLI commands concurrently, a future async wrapper, or an integration test that parallelises CLI calls), a `team show` call from one coroutine/thread can overwrite the pending name of another. The `team_show` function reads and clears `_pending_name` non-atomically.

**Fix:** Pass the team name as an explicit argument rather than using class-level state. The cleanest fix is to use a Click `pass_context` pattern and store the name in `ctx.obj`:

```python
def resolve_command(self, ctx, args):
    try:
        return super().resolve_command(ctx, args)
    except click.UsageError:
        team_name = args[0] if args else None
        show_cmd = self.commands.get("show")
        if show_cmd is not None and team_name is not None:
            ctx.ensure_object(dict)
            ctx.obj["pending_team_name"] = team_name
            return (team_name, show_cmd, args[1:])
        raise
```

---

## Info

### IN-01: `ResourceSpec` does not validate `apiVersion` — any string accepted

**File:** `src/pecp/models/resource_spec.py:99-103`

**Issue:** `api_version: str` accepts any string. A YAML submitted with `apiVersion: v9999` or `apiVersion: totally-wrong` will pass validation and be persisted. The project constraint is `apiVersion: pecp/v1` — not negotiable. Failing to validate this means stale or misrouted YAML from other tools will silently enter the system.

**Fix:** Change the field type to `Literal["pecp/v1"]`:

```python
api_version: Literal["pecp/v1"] = Field(alias="apiVersion")
```

---

### IN-02: `import unittest.mock as mock` repeated inside every test function

**File:** `tests/test_api/test_cli.py:35, 88, 128, 153, ...` (multiple lines)

**Issue:** Every test function in `test_cli.py` imports `unittest.mock` locally inside the function body. This is a style inconsistency — standard practice is a module-level import. It has no runtime correctness impact but hurts readability and violates the convention used in every other test file in the suite.

**Fix:** Add `from unittest import mock` at the top of `test_cli.py` and remove the per-function import statements.

---

### IN-03: Alembic downgrade removes `deleted_at` before `deployments` table is dropped, breaking FK audit trail intent

**File:** `alembic/versions/0003_add_teams_projects_deployments.py:75-83`

**Issue:** The downgrade does `drop_table("deployments")` first, then uses `batch_alter_table` to drop `deleted_at` from `resource_records`. The order is correct for FK satisfaction (deployments references resource_records, so drop deployments first). However, the migration does not reverse the `project` column added to `resource_records` in the same order it was added: the upgrade adds `project` first then `deleted_at`, and the downgrade drops `deleted_at` first then `project`. This is functionally equivalent for SQLite but is asymmetric. More importantly, there is no error raised if `deleted_at` contains non-null values at downgrade time, which could silently discard soft-delete audit information.

**Fix:** The downgrade ordering is acceptable, but add a comment noting that downgrading while soft-deleted rows exist will lose `deleted_at` audit data. Optionally, raise an error or warning if non-null `deleted_at` rows exist before proceeding.

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

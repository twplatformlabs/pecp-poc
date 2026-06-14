---
phase: 03-rest-api-core-cli
plan: 02
subsystem: api
tags:
  - rest-api
  - fastapi-background-tasks
  - idempotency
  - notes
  - dispatch-wiring
  - vertical-slice
dependency_graph:
  requires:
    - 03-01
  provides:
    - REST API vertical slice: POST /resources with idempotency, GET list with kind filter
    - GET /resources/{id} full detail
    - DELETE /resources/{id} with team verification
    - POST /resources/{id}/notes with NoteCreate model
    - _dispatch_with_session BackgroundTasks wrapper
  affects:
    - tests/conftest.py (client fixture now resets schema per test)
tech_stack:
  added: []
  patterns:
    - Lookup-before-insert idempotency with IntegrityError safety net (CTRL-03)
    - BackgroundTasks wrapper opens fresh AsyncSessionLocal (Pitfall 1 resolution)
    - NoteCreate Pydantic model for 422-on-bad-body (Pitfall 5 resolution)
    - Cross-team DELETE collapses to 404 to avoid resource existence leakage (A5)
key_files:
  created: []
  modified:
    - src/pecp/api/routes/resources.py
    - tests/conftest.py
decisions:
  - "Use module-reference import (`import pecp.persistence.database as _db`) for AsyncSessionLocal in _dispatch_with_session so test fixtures that reload the database module are respected"
  - "conftest.py client fixture drops and recreates schema per test (not just init) to prevent UniqueConstraint collisions in shared StaticPool in-memory SQLite"
metrics:
  duration: 7m
  completed: "2026-06-14"
  tasks_completed: 2
  files_changed: 2
---

# Phase 03 Plan 02: REST API Core Vertical Slice Summary

**One-liner:** Five-route REST vertical slice with idempotency (lookup-before-insert + IntegrityError), BackgroundTasks dispatch using fresh AsyncSessionLocal, kind filter on list, GET/DELETE/notes routes — all Plan 01 Wave 0 RED tests are now GREEN.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | POST /resources idempotency + BackgroundTasks + kind filter | d543357 | src/pecp/api/routes/resources.py, tests/conftest.py |
| 2 | GET /resources/{id}, DELETE, POST /resources/{id}/notes | d543357 | src/pecp/api/routes/resources.py |

> Note: Tasks 1 and 2 were implemented as a single atomic rewrite of `resources.py` since the routes are co-located and interdependent (NoteCreate model used by Task 2 is in the same file rewritten by Task 1). Both tasks share one commit.

## Implementation Details

### _dispatch_with_session signature

```python
async def _dispatch_with_session(resource_id: str) -> None:
```

Body opens `async with _db.AsyncSessionLocal() as session:` and calls `await dispatch(resource_id, session)`. No try/except — Dispatcher writes terminal status on failure. Uses `_db.AsyncSessionLocal` (module reference) rather than a direct import to support test fixtures that reload `pecp.persistence.database`.

### Route handler signatures

```python
async def list_resources(team: str | None = None, kind: str | None = None, ctx: ContextDep, session: SessionDep) -> list[dict[str, str]]
async def create_resource(background_tasks: BackgroundTasks, team: str | None = None, body: bytes = Body(...), ctx: ContextDep, session: SessionDep) -> dict[str, str]
async def get_resource(resource_id: str, ctx: ContextDep, session: SessionDep) -> dict[str, object]
async def delete_resource(resource_id: str, team: str | None = None, ctx: ContextDep, session: SessionDep) -> None
async def add_note(resource_id: str, body: NoteCreate, ctx: ContextDep, session: SessionDep) -> dict[str, list[dict[str, str]]]
```

### IntegrityError handling location

`src/pecp/api/routes/resources.py` lines inside `create_resource`:

```python
try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    race_result = await session.execute(
        select(ResourceRecord).where(...)
    )
    winner = race_result.scalar_one()
    return {"id": winner.id, "status": winner.status, ...}
```

### Timestamp format string (D-06)

```python
datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
```

### Test counts (all GREEN after this plan)

| File | Tests | Status |
|------|-------|--------|
| tests/test_api/test_idempotency.py | 3 | PASS |
| tests/test_api/test_notes.py | 3 | PASS |
| tests/test_api/test_dispatch_wiring.py | 2 | PASS |
| tests/test_api/test_routes.py | 9 | PASS |
| **Total** | **17** | **17 PASS** |

Full suite: 106 passed (excluding test_cli.py Wave 0 RED tests belonging to Plan 03-03).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test isolation failure in client fixture for in-memory StaticPool SQLite**

- **Found during:** Task 1 test run (test_dispatch_transitions_pending_to_ready_with_fresh_session failed when run after test_post_resources_enqueues_background_dispatch)
- **Issue:** The `client` fixture only called `init_schema()` (CREATE TABLE IF NOT EXISTS) which does not reset existing data. With idempotency now active, the second dispatch-wiring test found the same `dispatch-test-lambda` resource already in DB (from the first test with mocked dispatch), received the no-op path (same spec), and no dispatch was re-enqueued — status stayed `pending`.
- **Fix:** Updated `tests/conftest.py` client fixture to drop all tables then recreate before yielding, ensuring each test starts with a clean database.
- **Files modified:** `tests/conftest.py`
- **Commit:** d543357

**2. [Rule 1 - Bug] AsyncSessionLocal module-reference import to support test reload pattern**

- **Found during:** Full suite run — `test_apply_then_list_round_trip` in `test_walking_skeleton.py` failed after my changes
- **Issue:** The `isolated_client` fixture in `test_walking_skeleton.py` reloads `pecp.persistence.database` to get a fresh engine. If `AsyncSessionLocal` is imported by name (`from pecp.persistence.database import AsyncSessionLocal`), the routes module holds a stale reference to the pre-reload factory. Background tasks then connect to the old (empty) in-memory DB and `dispatch` raises `NoResultFound`.
- **Fix:** Changed import to `import pecp.persistence.database as _db` and use `_db.AsyncSessionLocal()` inside `_dispatch_with_session`. The module attribute lookup is resolved at call time, not at import time, so reloads are respected.
- **Files modified:** `src/pecp/api/routes/resources.py`
- **Commit:** d543357

## Known Stubs

None. All routes return real data from the database. Notes, provider_metadata, activity_log, and env fields are wired to the actual ORM columns.

## Threat Flags

No new threat surface introduced. All threats in the plan's threat register are mitigated:
- T-3-02-01: IntegrityError safety net implemented
- T-3-02-02: _dispatch_with_session opens its own AsyncSessionLocal
- T-3-02-03: DELETE team-mismatch collapses to 404
- T-3-02-04: NoteCreate(BaseModel) enforces 422 on bad body
- T-3-02-06: yaml.safe_load preserved (unchanged)

## Self-Check: PASSED

- src/pecp/api/routes/resources.py exists: FOUND
- tests/conftest.py modified: FOUND
- Commit d543357 exists: FOUND
- 17 tests pass in target test files: PASS
- mypy --strict exits 0: PASS
- ruff check exits 0: PASS

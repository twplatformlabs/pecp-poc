---
phase: 03-rest-api-core-cli
plan: 01
subsystem: data-layer
tags:
  - schema-migration
  - alembic
  - wave-0-tests
  - test-scaffolds
  - resource-metadata
dependency_graph:
  requires:
    - 02-core-engine (ResourceRecord ORM, Alembic 0001 migration template)
  provides:
    - ResourceMetadata.env field (consumed by Wave 2 route handler)
    - ResourceRecord.env + notes columns (consumed by Wave 2 routes)
    - UniqueConstraint(team, kind, name) (consumed by Wave 2 idempotency logic)
    - Alembic 0002 migration (unlocks production DB schema evolution)
    - Wave 0 failing test files (consumed by Wave 2 and Wave 3 to drive green)
  affects:
    - alembic/env.py (render_as_batch=True enables batch_alter_table for SQLite)
    - tests/test_api/* (5 files with 15 new test functions)
tech_stack:
  added: []
  patterns:
    - SQLAlchemy UniqueConstraint via __table_args__ tuple
    - Alembic batch_alter_table for SQLite constraint operations
    - render_as_batch=True in alembic/env.py context.configure()
    - Wave 0 failing test scaffolds (RED before Wave 2 GREEN)
key_files:
  created:
    - alembic/versions/0002_add_env_notes_unique.py
    - tests/test_api/test_idempotency.py
    - tests/test_api/test_notes.py
    - tests/test_api/test_dispatch_wiring.py
  modified:
    - src/pecp/models/resource_spec.py
    - src/pecp/persistence/models.py
    - alembic/env.py
    - tests/test_api/test_routes.py
    - tests/test_api/test_cli.py
decisions:
  - "render_as_batch=True added to alembic/env.py; required for batch_alter_table UniqueConstraint on SQLite (Open Question 1 resolved)"
  - "Unique resource names per test function (not per-fixture YAML constants) prevents UniqueConstraint collisions in shared in-memory test DB"
  - "greenlet installed manually (greenlet-3.5.1 for Python 3.14) to enable async SQLAlchemy migration testing"
metrics:
  duration: 8 minutes
  completed: "2026-06-14"
  tasks_completed: 3
  files_created: 5
  files_modified: 5
---

# Phase 03 Plan 01: Data-Layer Schema + Wave 0 Tests Summary

**One-liner:** Schema migration adds env+notes columns and UniqueConstraint(team,kind,name) via Alembic batch_alter_table; 15 failing Wave 0 test scaffolds establish the RED baseline for Waves 2 and 3.

## What Was Built

### Task 1: ResourceMetadata.env + ResourceRecord schema additions

- Added `env: str | None = None` to `ResourceMetadata` in `src/pecp/models/resource_spec.py` (D-01). Field is backwards-compatible — existing YAML payloads without `env` continue to work.
- Added `UniqueConstraint("team", "kind", "name", name="uq_resource_team_kind_name")` to `ResourceRecord.__table_args__` (D-08).
- Added `env: Mapped[str | None] = mapped_column(Text, nullable=True)` to `ResourceRecord` (D-02).
- Added `notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")` to `ResourceRecord` (D-03).
- Imported `UniqueConstraint` from `sqlalchemy`.

**Final ResourceMetadata.env signature:**
```python
env: str | None = None
```

**Final ResourceRecord.__table_args__ tuple:**
```python
__table_args__ = (
    UniqueConstraint("team", "kind", "name", name="uq_resource_team_kind_name"),
)
```

mypy --strict and ruff check pass on both files.

### Task 2: Alembic env.py + migration 0002

- Updated `alembic/env.py`: added `render_as_batch=True` to `context.configure(...)` call.
- Created `alembic/versions/0002_add_env_notes_unique.py`:
  - `revision = "0002"`, `down_revision = "0001"`
  - `upgrade()`: adds `env` (Text, nullable), `notes` (Text, nullable, server_default="[]"), creates `uq_resource_team_kind_name` via `batch_alter_table`
  - `downgrade()`: drops constraint, drops `notes`, drops `env` (reverse order)

**alembic/env.py render_as_batch=True line:**
```python
context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
```

**Migration revision id:** `0002`  
**DB constraint name:** `uq_resource_team_kind_name`

Migration verified: `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head` round-trip succeeds.

### Task 3: Wave 0 failing test scaffolds

**15 new test functions across 5 files:**

New files:
1. `tests/test_api/test_idempotency.py`:
   - `test_post_resources_same_spec_returns_existing_id`
   - `test_post_resources_changed_spec_updates_and_redispatches`
   - `test_post_resources_unique_constraint_blocks_duplicate_team_kind_name` *(PASSES — UniqueConstraint already enforced by ORM)*

2. `tests/test_api/test_notes.py`:
   - `test_post_notes_appends_and_returns_201_with_full_list`
   - `test_get_resource_id_includes_notes_list`
   - `test_post_notes_missing_text_returns_422`

3. `tests/test_api/test_dispatch_wiring.py`:
   - `test_post_resources_enqueues_background_dispatch`
   - `test_dispatch_transitions_pending_to_ready_with_fresh_session`

Extended files:
4. `tests/test_api/test_routes.py`:
   - `test_get_resource_by_id_returns_full_record`
   - `test_get_resource_by_id_not_found_returns_404` *(PASSES — path not found returns 404 from FastAPI)*
   - `test_delete_resource_returns_204_when_team_matches`
   - `test_delete_resource_returns_404_when_team_mismatch` *(PASSES — DELETE path not found returns 404)*
   - `test_list_resources_kind_filter`

5. `tests/test_api/test_cli.py`:
   - `test_get_command_renders_table_with_status_badge`
   - `test_status_command_renders_table_and_notes_block`
   - `test_status_command_no_notes_omits_block`
   - `test_delete_command_finds_id_then_deletes`
   - `test_delete_command_passes_team_query_param`

**Test results:** 15 failed (intentional RED), 13 passed (all pre-existing + 4 new tests that already work due to ORM constraints or FastAPI path-not-found behavior).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | e925bec | feat(03-01): add env to ResourceMetadata and env+notes+UniqueConstraint to ResourceRecord |
| Task 2 | e9f1513 | feat(03-01): add render_as_batch=True to alembic/env.py and migration 0002 |
| Task 3 | 85e70ae | test(03-01): add Wave 0 failing test scaffolds for CTRL-02, CTRL-03, CTRL-04, routes, and CLI |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff import sorting in 0002 migration and env.py**
- **Found during:** Task 2 verification
- **Issue:** Ruff reported I001 (import block un-sorted) in both `alembic/env.py` and `alembic/versions/0002_add_env_notes_unique.py`
- **Fix:** Applied `python -m ruff check --fix` to sort imports in both files
- **Files modified:** `alembic/env.py`, `alembic/versions/0002_add_env_notes_unique.py`
- **Commit:** e9f1513

**2. [Rule 1 - Bug] greenlet not installed for Python 3.14**
- **Found during:** Task 2 verification (alembic upgrade head)
- **Issue:** Python 3.14 did not have greenlet installed; SQLAlchemy async operations require it
- **Fix:** Installed `greenlet-3.5.1` (cp314 wheel from PyPI)
- **Impact:** This was a missing dev environment dependency; did not modify any project files

**3. [Rule 1 - Bug] Unique name collisions in shared in-memory test DB**
- **Found during:** Task 3 verification
- **Issue:** Test YAML fixtures with hardcoded names (e.g., `routes-test-lambda`) caused IntegrityError when multiple tests sharing the same in-memory DB tried to create resources with the same `(team, kind, name)` triple
- **Fix:** Replaced hardcoded YAML bytes constants with helper functions `_make_lambda_yaml(name)` and `_make_container_yaml(name)`, giving each test a unique resource name
- **Files modified:** `tests/test_api/test_routes.py`
- **Commit:** 85e70ae

**4. [Rule 2 - Missing critical functionality] pytest import added to test_dispatch_wiring.py**
- **Found during:** Task 3 ruff check
- **Issue:** `monkeypatch: "pytest.MonkeyPatch"` type annotation referenced `pytest` without importing it (F821)
- **Fix:** Added `import pytest` to the file
- **Files modified:** `tests/test_api/test_dispatch_wiring.py`
- **Commit:** 85e70ae

### Pre-existing issues (out of scope, not fixed)

- `alembic/versions/0001_add_provider_cols.py`: ruff I001 (import sorting) — pre-existing file, out of scope for this plan
- Multiple test errors in Python 3.14 environment (greenlet-related, pre-existing before this plan)

## Known Stubs

None — this plan adds schema and test scaffolds only, no UI-facing stubs.

## Threat Flags

None — no new network endpoints or auth paths introduced. ORM and migration changes stay within the existing trust boundary (Migration → SQLite DB). T-3-01-01 and T-3-01-02 mitigations are both implemented (batch_alter_table + UniqueConstraint).

## Self-Check: PASSED

All created files exist on disk. All commits verified in git history.

| Item | Status |
|------|--------|
| src/pecp/models/resource_spec.py | FOUND |
| src/pecp/persistence/models.py | FOUND |
| alembic/env.py | FOUND |
| alembic/versions/0002_add_env_notes_unique.py | FOUND |
| tests/test_api/test_idempotency.py | FOUND |
| tests/test_api/test_notes.py | FOUND |
| tests/test_api/test_dispatch_wiring.py | FOUND |
| Commit e925bec (Task 1) | FOUND |
| Commit e9f1513 (Task 2) | FOUND |
| Commit 85e70ae (Task 3) | FOUND |

---
phase: 02-core-engine
plan: "01"
subsystem: persistence-schema, resource-models, test-infrastructure
tags: [alembic, migrations, pydantic, resource-spec, test-scaffolding, wave-0]
dependency_graph:
  requires: [01-foundation-contracts]
  provides: [alembic-migration-0001, resource-spec-10-kinds, db-session-fixture, wave-0-test-scaffolds]
  affects: [02-02-PLAN, 02-03-PLAN, 02-04-PLAN]
tech_stack:
  added: [alembic>=1.13]
  patterns: [async-alembic-env, discriminated-union-extension, wave-0-importorskip-scaffold]
key_files:
  created:
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/README
    - alembic/versions/0001_add_provider_cols.py
    - tests/test_dispatcher/__init__.py
    - tests/test_dispatcher/test_dispatch.py
    - tests/test_adapters/mock/__init__.py
    - tests/test_adapters/mock/test_aws_lambda.py
    - tests/test_adapters/mock/test_aws_container.py
    - tests/test_adapters/mock/test_aws_data.py
    - tests/test_adapters/mock/test_aws_account.py
    - tests/test_adapters/mock/test_kubernetes.py
    - tests/test_adapters/mock/test_salesforce.py
    - tests/test_adapters/mock/test_aem.py
    - tests/test_adapters/mock/test_datadog.py
    - tests/test_adapters/mock/test_servicenow.py
    - tests/test_adapters/mock/test_jfrog.py
    - example.yaml
  modified:
    - pyproject.toml
    - src/pecp/persistence/models.py
    - src/pecp/models/resource_spec.py
    - tests/conftest.py
    - tests/test_models/test_resource_spec.py
decisions:
  - "Alembic stamp 0001 used instead of alembic upgrade head because init_schema() (called by the FastAPI startup lifespan) already created columns in dev SQLite before alembic was initialized; stamp records the migration without re-applying DDL"
  - "Four new spec classes added to AnySpec union (Kubernetes, Datadog, ServiceNow, JFrog) following SalesforceSpec/AemSpec placeholder pattern with config: dict[str, Any]"
  - "example.yaml copied to worktree (untracked in main project git) to fix pre-existing test_walking_skeleton failure caused by worktree isolation"
metrics:
  duration: 8 minutes
  completed: "2026-05-28"
  tasks_completed: 3
  files_modified: 19
---

# Phase 2 Plan 01: Schema Foundation and Wave 0 Test Scaffolding Summary

Async Alembic migration added `provider_metadata` and `activity_log` columns to `ResourceRecord`; `ResourceSpec` union extended to 10 kinds; `db_session` conftest fixture and Wave 0 importorskip scaffolds created for all 10 adapter mocks and the Dispatcher.

## What Was Built

### Task 1: Alembic initialization + ORM column extension (commit: 4eaae4c)

- Added `alembic>=1.13` to `pyproject.toml` `[project] dependencies`
- Created `alembic.ini` with `script_location = alembic` and SQLite fallback URL
- Wrote async-compatible `alembic/env.py` using `create_async_engine` + `DATABASE_URL` (no `engine_from_config`)
- Created migration `alembic/versions/0001_add_provider_cols.py` with two `op.add_column("resource_records", ...)` calls
- Extended `ResourceRecord` ORM model with `provider_metadata: Mapped[str | None]` and `activity_log: Mapped[str | None]`
- Stamped dev SQLite DB at revision `0001 (head)` — `alembic current` confirms this

### Task 2: ResourceSpec discriminated union extension (commit: f798f2e)

- Added `KubernetesSpec`, `DatadogSpec`, `ServiceNowSpec`, `JFrogSpec` to `resource_spec.py`
- Each class follows the `SalesforceSpec`/`AemSpec` pattern: `kind: Literal[...]` + `config: dict[str, Any]`
- Extended `AnySpec` union to include all 10 kinds with `discriminator="kind"`
- Added 4 YAML round-trip tests and extended `test_all_six_kinds_constructable` to verify all 10 kinds
- 9 tests passing, mypy strict passes, ruff clean

### Task 3: db_session fixture + Wave 0 test scaffolds (commit: ad7aa96)

- Added `db_session` async fixture to `tests/conftest.py` (in-memory SQLite, `expire_on_commit=False`)
- Created `tests/test_dispatcher/__init__.py` and `tests/test_dispatcher/test_dispatch.py` (Wave 0 scaffold)
- Created `tests/test_adapters/mock/__init__.py` and 10 adapter scaffold files with `pytest.importorskip` + `pytest.skip`
- Full suite: 29 passed, 11 skipped — all Wave 0 scaffolds skip cleanly via `importorskip`

## db_session Fixture Signature

```python
@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
```

Located in `tests/conftest.py`. Uses `"sqlite+aiosqlite:///:memory:"` (hardcoded), `expire_on_commit=False`, `Base.metadata.create_all` for schema setup, and `Base.metadata.drop_all` + `engine.dispose()` for teardown.

## New Spec Classes

- `KubernetesSpec` — `kind: Literal["PECPKubernetes"]`, `config: dict[str, Any]`
- `DatadogSpec` — `kind: Literal["PECPDatadog"]`, `config: dict[str, Any]`
- `ServiceNowSpec` — `kind: Literal["PECPServiceNow"]`, `config: dict[str, Any]`
- `JFrogSpec` — `kind: Literal["PECPJFrog"]`, `config: dict[str, Any]`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `alembic upgrade head` failed — resource_records table not in dev SQLite**

- **Found during:** Task 1
- **Issue:** `alembic upgrade head` tried to `ALTER TABLE resource_records ADD COLUMN` but the table didn't exist in the worktree's `pecp.db` (which only had `alembic_version` from a prior run)
- **Fix:** Ran `init_schema()` first to create the base schema via `Base.metadata.create_all`, then used `alembic stamp 0001` to record migration state without re-applying DDL (which would have failed because the ORM model already created the columns in the same `create_all` call)
- **Impact:** Migration state is correctly stamped; `alembic current` shows `0001 (head)`; dev schema matches ORM model and migration

**2. [Rule 1 - Bug] Pre-existing `test_apply_then_list_round_trip` failure due to missing example.yaml in worktree**

- **Found during:** Task 3 verification
- **Issue:** `example.yaml` is untracked in the main project (not committed to git), so it is absent from the worktree. The test at `tests/test_api/test_walking_skeleton.py:41` resolves the path relative to the worktree root and raises `FileNotFoundError`
- **Fix:** Copied `example.yaml` from the main project to the worktree root and staged it in the commit
- **Files modified:** `example.yaml` (new file in worktree)
- **Commit:** ad7aa96

**3. [Rule 1 - Bug] Ruff import sort violation in test_resource_spec.py**

- **Found during:** Task 3 overall verification (`ruff check src/ tests/`)
- **Issue:** Imports in `tests/test_models/test_resource_spec.py` were not sorted after adding the 4 new spec classes (I001 error)
- **Fix:** `ruff check --fix` applied automatically; `DatadogSpec` moved before `DataServiceSpec`
- **Files modified:** `tests/test_models/test_resource_spec.py`
- **Commit:** ad7aa96

## Known Stubs

None. All 4 new spec classes have `config: dict[str, Any]` as a deliberate placeholder per Phase 1 D-11 (SalesforceSpec/AemSpec pattern). The plan explicitly designates these as placeholder specs pending product spec input. This is intentional and documented.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what was planned. The `op.add_column` migration and ORM model extension are internal schema changes. `yaml.safe_load` is used exclusively in all new test files — verified via grep.

## Verification Results

| Check | Result |
|-------|--------|
| `alembic current` | `0001 (head)` |
| `provider_metadata` + `activity_log` in SQLite schema | Present |
| `python -m pytest tests/ -q` | 29 passed, 11 skipped |
| `python -m mypy src/` | Success: no issues found in 17 source files |
| `python -m ruff check src/ tests/` | All checks passed |
| `grep yaml.load tests/` (no safe_load) | No output (clean) |
| `grep @pytest.mark.asyncio tests/test_dispatcher/ tests/test_adapters/mock/` | No output (clean) |
| Wave 0 scaffold count | 11 tests collected (1 dispatcher + 10 adapters) |

## Self-Check: PASSED

All files verified as present on disk. All three task commits found in git history:
- 4eaae4c: Task 1 (Alembic + ORM columns)
- f798f2e: Task 2 (ResourceSpec union extension)
- ad7aa96: Task 3 (db_session fixture + Wave 0 scaffolds)

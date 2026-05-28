---
phase: 01-foundation-contracts
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - src/pecp/models/enums.py
  - src/pecp/models/provision_result.py
  - src/pecp/models/resource_spec.py
  - src/pecp/adapters/base.py
  - src/pecp/api/dependencies.py
  - src/pecp/api/main.py
  - src/pecp/api/routes/resources.py
  - src/pecp/cli/main.py
  - src/pecp/persistence/database.py
  - src/pecp/persistence/models.py
  - tests/conftest.py
  - tests/test_adapters/test_adapter_base.py
  - tests/test_api/test_routes.py
  - tests/test_api/test_walking_skeleton.py
  - tests/test_api/test_cli.py
  - tests/test_models/test_resource_spec.py
  - tests/test_persistence/test_database.py
findings:
  critical: 2
  warning: 6
  info: 5
  total: 13
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-28
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The foundation contracts layer is well-structured overall. The adapter ABC, Pydantic discriminated union, async SQLAlchemy persistence, and FastAPI wiring all follow the intended design. However, two blockers require attention before any downstream phase builds on this code: the global module-level SQLAlchemy engine is created at import time using whatever `PECP_DATABASE_URL` is set at that moment — making the `isolated_client` fixture's `importlib.reload` workaround both fragile and broken in the test suite — and the `spec.model_dump_json()` serialization of the aliased `LambdaSpec` stores Pydantic's internal field names (`api_gateway`, `source_code`) instead of the wire-format alias names (`api-gateway`, `source-code`), meaning any future deserialization of that JSON back into a `ResourceSpec` will fail.

There are also six warnings covering missing input validation, incomplete `extra="forbid"` coverage on resource models, an async fixture missing the `AsyncGenerator` yield type, and a test isolation mechanism that is unreliable across Python import caching.

---

## Critical Issues

### CR-01: `spec.model_dump_json()` stores internal field names, not alias names — deserialization will break

**File:** `src/pecp/api/routes/resources.py:87`

**Issue:** `spec.model_dump_json()` serializes `LambdaSpec` using Python attribute names (`api_gateway`, `source_code`) rather than the declared aliases (`api-gateway`, `source-code`). `ResourceSpec` is defined with `populate_by_name=True` but without `by_alias=True` as the default for serialization. When any future code path attempts to reconstruct a `ResourceSpec` from `spec_json` (e.g., the dispatcher reading back a persisted record), `model_validate_json()` will succeed only if it happens to use attribute names — but the wire format and example.yaml use aliases. This is a latent data-corruption / deserialization-failure bug waiting to surface.

**Fix:**
```python
# routes/resources.py line 87 — pass by_alias=True so stored JSON matches wire format
spec_json=spec.model_dump_json(by_alias=True),
```

---

### CR-02: SQLAlchemy engine created at module import time — test isolation is broken

**File:** `src/pecp/persistence/database.py:20-28`

**Issue:** `DATABASE_URL`, `engine`, and `AsyncSessionLocal` are module-level globals evaluated once at first import. The `isolated_client` fixture in `test_walking_skeleton.py` (lines 18-24) sets `PECP_DATABASE_URL` and then calls `importlib.reload(db_module)` to force recreation, but this does **not** rebind the `engine` reference already imported by `pecp.api.routes.resources` via `SessionDep`. The route handler's `session` dependency was closed over the original engine at its own import time. The reload only fixes the `db_module` namespace — `resources.py`'s `SessionDep` still points to the old engine. Consequently, the `isolated_client` fixture may silently write to a different database than intended, making isolation guarantees unreliable. In CI environments where the original engine was created against `sqlite+aiosqlite:///:memory:` (set by `conftest.py`), this may happen to pass, masking the bug.

**Fix:** Create the engine lazily inside `get_session()`, or pass the engine/session factory as a parameter, or use FastAPI's dependency override mechanism to inject a test session factory:

```python
# Option A — use FastAPI dependency_overrides in the fixture (cleanest)
# In isolated_client fixture:
from pecp.api.main import app
from pecp.persistence.database import get_session, AsyncSessionLocal

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", ...)

async def override_get_session():
    async with async_sessionmaker(test_engine, ...)() as session:
        yield session

app.dependency_overrides[get_session] = override_get_session
```

---

## Warnings

### WR-01: `apiVersion` value is never validated — any string is accepted

**File:** `src/pecp/models/resource_spec.py:68`

**Issue:** `api_version: str` accepts any string. A request with `apiVersion: pecp/v2` or `apiVersion: garbage` passes validation and is persisted. The project spec mandates `apiVersion: pecp/v1` as the canonical wire format. This will allow future version skew to silently accumulate rather than being caught at the API boundary.

**Fix:**
```python
from typing import Literal
api_version: Literal["pecp/v1"] = Field(alias="apiVersion")
```

---

### WR-02: `DataServiceSpec`, `AccountSpec`, `SalesforceSpec`, and `AemSpec` lack `extra="forbid"`

**File:** `src/pecp/models/resource_spec.py:34-52`

**Issue:** Only `LambdaSpec` and `ContainerSpec` set `model_config = ConfigDict(extra="forbid", ...)`. The remaining four spec models silently accept and discard unknown fields. A typo like `subtypes: s3` (instead of `subtype: s3`) on `DataServiceSpec` would pass validation with the field silently dropped rather than raising a `ValidationError`. This is exactly the class of bug `extra="forbid"` exists to catch.

**Fix:** Add `model_config = ConfigDict(extra="forbid")` to `DataServiceSpec`, `AccountSpec`, `SalesforceSpec`, and `AemSpec`.

---

### WR-03: `ResourceMetadata.team` is optional but routes unconditionally read it as present

**File:** `src/pecp/models/resource_spec.py:62-63` and `src/pecp/api/routes/resources.py:85`

**Issue:** `ResourceMetadata.team` is `str | None = None`. However, `create_resource` writes `team=team` from the query parameter (correct), but `spec.metadata.name` on line 85 is fine — the issue is that nothing prevents a caller from submitting a spec where `metadata.team` is a different team from the `?team=` query parameter. There is no reconciliation or warning. More critically, if any future code reads `spec.metadata.team` (e.g., the dispatcher), it will get `None` rather than the query-param team, creating a silent mismatch.

**Fix:** Either remove `team` from `ResourceMetadata` entirely (since it is sourced from the query param), or validate that when both are present they agree:
```python
if spec.metadata.team and spec.metadata.team != team:
    raise HTTPException(status_code=422, detail="metadata.team conflicts with team query parameter")
```

---

### WR-04: `isolated_client` fixture has incorrect return type annotation — missing `AsyncGenerator`

**File:** `tests/test_api/test_walking_skeleton.py:16`

**Issue:** The fixture is declared as `async def isolated_client() -> AsyncClient` but it uses `yield`, making it a generator. The correct return type is `AsyncGenerator[AsyncClient, None]`. The `# type: ignore[return]` comment suppresses the mypy error rather than fixing it. With `asyncio_mode = "auto"` and `pytest-asyncio >= 0.21`, async fixtures must be properly typed or they may not be recognized as async generators in all configurations.

**Fix:**
```python
from collections.abc import AsyncGenerator

@pytest.fixture
async def isolated_client() -> AsyncGenerator[AsyncClient, None]:
```
And remove the `# type: ignore[return]` comment.

---

### WR-05: `db_session` fixture has the same missing `AsyncGenerator` annotation

**File:** `tests/test_persistence/test_database.py:17`

**Issue:** Same pattern as WR-04. `async def db_session() -> AsyncSession` uses `yield` but is annotated as a bare return type, with `# type: ignore[return]` suppressing the error. Beyond the typing issue, the fixture does not clean up if the test raises an exception before the `yield` — the `drop_all` / `engine.dispose()` teardown on lines 29-31 runs in the same generator frame after the `yield`, but if session creation itself fails the teardown is skipped.

**Fix:**
```python
async def db_session() -> AsyncGenerator[AsyncSession, None]:
```
And use `try/finally` around the `yield` for teardown safety.

---

### WR-06: Empty YAML body is accepted and produces a misleading 422 rather than 400

**File:** `src/pecp/api/routes/resources.py:70-73`

**Issue:** `body: bytes = Body(b"", ...)` defaults to an empty byte string. When the body is empty, `yaml.safe_load(b"")` returns `None`. The subsequent `ResourceSpec.model_validate(None)` then raises a `ValidationError`, which is caught and re-raised as a 422 with a Pydantic error dump. This is technically correct, but the error message ("Input should be a valid dictionary...") is confusing to a caller who simply omitted the body. A dedicated guard before the Pydantic validation step would produce a cleaner response.

**Fix:**
```python
if not body:
    raise HTTPException(status_code=400, detail="Request body is required")
parsed = yaml.safe_load(body)
if not isinstance(parsed, dict):
    raise HTTPException(status_code=422, detail="YAML body must be a mapping")
```

---

## Info

### IN-01: `get_status` on `AdapterBase` returns `ProvisionResult` — mismatches the CLAUDE.md contract

**File:** `src/pecp/adapters/base.py:26`

**Issue:** The project spec in `CLAUDE.md` declares the adapter interface as `async def get_status(resource: ResourceModel) -> ResourceStatus`. The implementation returns `ProvisionResult` instead. This is an intentional deviation that may be fine, but it is not documented anywhere in the ABC, and any future adapter implementor reading the project docs will write the wrong signature.

**Fix:** Either update `CLAUDE.md` to reflect the actual contract (`-> ProvisionResult`), or add a docstring in `AdapterBase.get_status` noting the deviation and rationale.

---

### IN-02: `conftest.py` calls `init_schema()` every time the `client` fixture is created — no isolation between tests

**File:** `tests/conftest.py:27`

**Issue:** The shared `client` fixture in `conftest.py` calls `init_schema()` once but does not drop/recreate tables between tests that share the same in-memory engine. Any test using the `client` fixture that writes records will affect subsequent tests in the same session. Currently this is benign because the only test using `client` that writes is `test_walking_skeleton.py` (which uses its own `isolated_client` fixture), but this is a fragile dependency on test ordering.

**Fix:** Move `init_schema()` into a session-scoped fixture and use a separate per-test transaction rollback, or add `asyncio_fixture` scope annotation.

---

### IN-03: `ResourceRecord.created_at` uses a Python-side `default` lambda instead of a server-side `server_default`

**File:** `src/pecp/persistence/models.py:32-36`

**Issue:** The `default=lambda: datetime.now(timezone.utc)` is evaluated in Python, not at the database level. This is fine for SQLite PoC usage, but means the column has no database-enforced default. If rows are ever inserted via raw SQL or a migration tool, `created_at` will be NULL despite the `nullable=False` constraint.

**Fix:** For a PoC this is acceptable, but note it for migration to a production database: replace with `server_default=func.now()` if SQLite UTC handling is acceptable, or keep the Python default and document the constraint.

---

### IN-04: Magic string `"pending"` used in two places instead of the `ResourceStatus` enum

**File:** `src/pecp/api/routes/resources.py:86,93` and `src/pecp/persistence/models.py:30`

**Issue:** `status="pending"` is hardcoded as a raw string in `routes/resources.py` (lines 86 and 93) and as the column default in `persistence/models.py` (line 30). The `ResourceStatus` enum exists precisely to avoid this. If the enum value is ever renamed or extended, the string literals will silently diverge.

**Fix:**
```python
from pecp.models.enums import ResourceStatus
# ...
status=ResourceStatus.pending.value,  # or just ResourceStatus.pending if ORM handles str enum
```

---

### IN-05: CLI `version` command hardcodes the version string instead of reading from package metadata

**File:** `src/pecp/cli/main.py:77`

**Issue:** `console.print("pecp 0.1.0")` duplicates the version declared in `pyproject.toml`. When the package version is bumped, this string will be stale unless manually updated in both places.

**Fix:**
```python
from importlib.metadata import version
console.print(f"pecp {version('pecp')}")
```

---

_Reviewed: 2026-05-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

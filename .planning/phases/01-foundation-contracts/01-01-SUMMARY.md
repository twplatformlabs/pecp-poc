---
phase: 01-foundation-contracts
plan: "01"
subsystem: contracts
tags:
  - python
  - pydantic
  - fastapi
  - scaffolding
  - contracts
dependency_graph:
  requires: []
  provides:
    - pecp.models.enums.ResourceStatus
    - pecp.models.provision_result.ProvisionResult
    - pecp.models.resource_spec.ResourceSpec
    - pecp.adapters.base.AdapterBase
    - pecp.api.dependencies.RequestContext
    - pecp.api.dependencies.ContextDep
  affects:
    - Plan 02 (demo script uses these types)
    - Plan 03 (FastAPI app builds on RequestContext, ResourceSpec)
    - Phase 2 (mock adapters implement AdapterBase)
tech_stack:
  added:
    - pydantic 2.13.4
    - fastapi 0.136.x
    - pytest 9.0.x
    - pytest-asyncio 1.4.x
    - mypy 2.1.x
    - ruff 0.15.x
  patterns:
    - Pydantic v2 discriminated union on `kind` with model_validator for wire format
    - ABC abstract methods for adapter interface enforcement
    - FastAPI Depends() with Annotated type alias for RequestContext
    - src/ layout with editable install
key_files:
  created:
    - pyproject.toml
    - .gitignore
    - src/pecp/__init__.py
    - src/pecp/models/__init__.py
    - src/pecp/models/enums.py
    - src/pecp/models/provision_result.py
    - src/pecp/models/resource_spec.py
    - src/pecp/adapters/__init__.py
    - src/pecp/adapters/base.py
    - src/pecp/api/__init__.py
    - src/pecp/api/dependencies.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_models/__init__.py
    - tests/test_models/test_enums.py
    - tests/test_models/test_provision_result.py
    - tests/test_models/test_resource_spec.py
    - tests/test_adapters/__init__.py
    - tests/test_adapters/test_adapter_base.py
    - tests/test_api/__init__.py
    - tests/test_api/test_context.py
    - tests/test_api/test_routes.py
  modified: []
decisions:
  - model_validator injects top-level `kind` into spec dict to handle wire format (example.yaml omits kind from spec block)
  - LambdaSpec and ContainerSpec use extra=forbid per T-01-02 security mitigation
  - IncompleteAdapter instantiation uses type: ignore[abstract] to satisfy mypy while testing runtime TypeError
  - Async generator return type AsyncGenerator[AsyncClient, None] required for mypy strict compliance in conftest.py
metrics:
  duration: "6 minutes"
  completed: "2026-05-28"
  tasks_completed: 3
  files_created: 22
  tests_passing: 15
  tests_skipped: 3
---

# Phase 1 Plan 01: Python Project Scaffold + Phase 1 Contracts Summary

**One-liner:** Python src-layout scaffold with Pydantic v2 discriminated union (6 resource kinds), AdapterBase ABC (3 abstract methods), ResourceStatus enum, ProvisionResult model, and FastAPI RequestContext dependency — all mypy-strict clean with 15 passing + 3 Plan-03-deferred tests.

## What Was Built

### Task 1: pyproject.toml + project scaffold

- `pyproject.toml` with all 13 runtime/dev dependencies, `[tool.ruff]`, `[tool.mypy]`, `[tool.pydantic-mypy]`, `[tool.pytest.ini_options]` (D-07)
- `.gitignore` with standard Python entries
- 8 empty `__init__.py` files for `src/pecp/`, `src/pecp/models/`, `src/pecp/adapters/`, `src/pecp/api/`, `tests/`, `tests/test_models/`, `tests/test_adapters/`, `tests/test_api/`
- `pip install -e ".[dev]"` exits 0, `python -c "import pecp"` exits 0

### Task 2: Contract implementations (TDD RED → GREEN)

**RED commit:** 5 test files created, all failing (implementations absent)

**GREEN commit:** 5 contract files implemented:

- `src/pecp/models/enums.py` — `ResourceStatus(str, Enum)` with `pending`, `provisioning`, `ready`, `failed` (D-12)
- `src/pecp/models/provision_result.py` — `ProvisionResult` with `status`, `provider_metadata={}`, `activity_log=[]`, `error=None` (D-01/D-02/D-03)
- `src/pecp/models/resource_spec.py` — discriminated union on `kind` covering all 6 resource types: `LambdaSpec`, `ContainerSpec`, `DataServiceSpec`, `AccountSpec`, `SalesforceSpec`, `AemSpec` (D-09/D-10/D-11); `model_validator` injects top-level `kind` into `spec` dict; `LambdaSpec`/`ContainerSpec` use `extra="forbid"` (T-01-02)
- `src/pecp/adapters/base.py` — `AdapterBase(ABC)` with 3 `@abstractmethod` async methods: `provision`, `deprovision`, `get_status` (ADPT-01, D-04)
- `src/pecp/api/dependencies.py` — `RequestContext` Pydantic model, `get_request_context()` hardcoded stub, `ContextDep = Annotated[RequestContext, Depends(get_request_context)]` (ARCH-02)

### Task 3: Wave 0 test scaffolds

- `tests/conftest.py` — async `client` fixture with `ASGITransport` + `importorskip` guard deferring app import to Plan 03
- `tests/test_api/test_routes.py` — `test_context_dependency_callable` (passing, no app needed) + 3 ARCH-01 skipped placeholders
- Fixed mypy strict issues: `type: ignore[abstract]` on abstract class instantiation test, `AsyncGenerator[AsyncClient, None]` return type on fixture

## Contracts Locked

| Contract | Citation | File | Key Detail |
|----------|----------|------|------------|
| ResourceStatus enum | D-12 | `src/pecp/models/enums.py` | 4 members, str mixin |
| ProvisionResult model | D-01/D-02/D-03 | `src/pecp/models/provision_result.py` | Default factories, error field |
| 6-kind discriminated union | D-09/D-10/D-11 | `src/pecp/models/resource_spec.py` | `kind` discriminator, hyphenated aliases |
| AdapterBase ABC | ADPT-01, D-04 | `src/pecp/adapters/base.py` | 3 abstract async methods |
| RequestContext dependency | ARCH-02 | `src/pecp/api/dependencies.py` | ContextDep Annotated alias |

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Install | `pip install -e ".[dev]"` | Exit 0, pecp-0.1.0 installed |
| Lint | `ruff check src/ tests/` | Exit 0, 0 errors |
| Type check | `mypy src/ tests/` | Exit 0, 0 errors (20 files) |
| Tests | `pytest tests/ -x -q` | 15 passed, 3 skipped |
| Round-trip | `ResourceSpec.model_validate(yaml.safe_load(...))` | LambdaSpec, source_code correct |
| Security gate | `grep -rn "yaml.load(" src/ tests/` | CLEAN — no unsafe yaml.load |

## Test Coverage

**18 tests collected:**
- 15 passing: enums (3), provision_result (3), resource_spec (5), adapter_base (2), context (2)
- 3 skipped: `test_get_resources_without_team_returns_400`, `test_get_resources_with_team_returns_200`, `test_post_resource_without_team_returns_400` — all marked `pytest.skip(reason="Pending Plan 03: ...")`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wire format: example.yaml omits `kind` from spec block**
- **Found during:** Task 2 GREEN phase (test_lambda_spec_parses_from_example_yaml failed)
- **Issue:** The discriminated union expects `kind` in the `spec` dict, but `example.yaml` only has `kind` at the top level of the resource. `pydantic_core.ValidationError: Unable to extract tag using discriminator 'kind'`
- **Fix:** Added `@model_validator(mode="before")` to `ResourceSpec` that injects the top-level `kind` into the `spec` dict when absent
- **Files modified:** `src/pecp/models/resource_spec.py`
- **Commit:** d7f12f3

**2. [Rule 1 - Bug] mypy strict: `type: ignore[override]` wrong for non-abstract stub methods**
- **Found during:** Task 3 mypy run
- **Issue:** `IncompleteAdapter` stub methods used `...` as body with `type: ignore[override]` — mypy 2.1 reports `empty-body` not covered by that ignore comment
- **Fix:** Changed stub methods to return `ProvisionResult(status=ResourceStatus.ready)`, used `type: ignore[abstract]` on the instantiation line
- **Files modified:** `tests/test_adapters/test_adapter_base.py`
- **Commit:** 9e8cf22

**3. [Rule 1 - Bug] mypy strict: async generator return type in conftest**
- **Found during:** Task 3 mypy run
- **Issue:** `async def client()` with `yield` inside is an async generator — mypy requires return type `AsyncGenerator[AsyncClient, None]` not `AsyncClient`
- **Fix:** Added `from collections.abc import AsyncGenerator` and typed fixture correctly
- **Files modified:** `tests/conftest.py`
- **Commit:** 9e8cf22

**4. [Rule 1 - Bug] ruff: unused imports and unsorted imports in test_resource_spec.py**
- **Found during:** Task 3 ruff run
- **Issue:** `AnySpec` and `ResourceMetadata` imported but unused; import block unsorted
- **Fix:** `ruff check --fix` auto-removed unused imports and sorted the block
- **Files modified:** `tests/test_models/test_resource_spec.py`
- **Commit:** 9e8cf22

## Deferred to Plan 03

- FastAPI app instance (`src/pecp/api/main.py`) — not created; `tests/conftest.py` guards against its absence
- `/resources` route handlers — 3 skipped tests cover ARCH-01 enforcement
- SQLAlchemy persistence wiring — Plan 03 scope
- `src/pecp/cli/main.py` — CLI entrypoint registered in `pyproject.toml` but module not yet created (Plan 03)

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `SalesforceSpec.config: dict[str, Any]` | `src/pecp/models/resource_spec.py` | D-11: intentional; real spec undefined pending PE team input |
| `AemSpec.config: dict[str, Any]` | `src/pecp/models/resource_spec.py` | D-11: intentional; real spec undefined pending PE team input |
| `get_request_context()` returns hardcoded values | `src/pecp/api/dependencies.py` | ARCH-02: intentional PoC stub; JWT replacement swaps function body only |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond the plan's `<threat_model>`. T-01-01 (yaml.safe_load), T-01-02 (extra=forbid), T-01-04 (auth stub) all applied as specified.

## Self-Check: PASSED

- pyproject.toml: FOUND
- src/pecp/models/enums.py: FOUND
- src/pecp/models/provision_result.py: FOUND
- src/pecp/models/resource_spec.py: FOUND
- src/pecp/adapters/base.py: FOUND
- src/pecp/api/dependencies.py: FOUND
- tests/conftest.py: FOUND
- tests/test_adapters/test_adapter_base.py: FOUND
- tests/test_models/test_resource_spec.py: FOUND
- tests/test_api/test_routes.py: FOUND
- Commit ce6e5c8 (Task 1): FOUND
- Commit 3527c2d (RED tests): FOUND
- Commit d7f12f3 (GREEN contracts): FOUND
- Commit 9e8cf22 (Wave 0 scaffolds): FOUND

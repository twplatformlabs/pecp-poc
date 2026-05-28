---
phase: 02-core-engine
plan: "02"
subsystem: mock-adapters, dispatcher, integration-tests
tags: [mock-adapters, dispatcher, tdd, adapter-registry, state-machine]
dependency_graph:
  requires: [02-01]
  provides: [aws-lambda-adapter, placeholder-adapters-9, dispatcher, adapter-registry-10, dispatcher-integration-tests]
  affects: [02-03-PLAN, 02-04-PLAN]
tech_stack:
  added: []
  patterns: [adapter-registry-dict, dispatch-state-machine, isinstance-narrowing, asyncio-sleep-patching, probe-adapter-test-pattern]
key_files:
  created:
    - src/pecp/adapters/mock/__init__.py
    - src/pecp/adapters/mock/aws_lambda.py
    - src/pecp/adapters/mock/aws_container.py
    - src/pecp/adapters/mock/aws_data.py
    - src/pecp/adapters/mock/aws_account.py
    - src/pecp/adapters/mock/kubernetes.py
    - src/pecp/adapters/mock/salesforce.py
    - src/pecp/adapters/mock/aem.py
    - src/pecp/adapters/mock/datadog.py
    - src/pecp/adapters/mock/servicenow.py
    - src/pecp/adapters/mock/jfrog.py
    - src/pecp/dispatcher.py
  modified:
    - tests/test_adapters/mock/test_aws_lambda.py
    - tests/test_dispatcher/test_dispatch.py
decisions:
  - "isinstance narrowing used instead of assert for mypy strict compatibility (Pitfall 6) — returns ProvisionResult(status=failed) not AssertionError"
  - "Dispatcher does NOT wrap adapter.provision() in try/except — adapters return ProvisionResult(status=failed) per D-04; dispatcher reads result"
  - "Placeholder adapters have no asyncio.sleep — sleep arrives with real implementations in Plans 03/04"
  - "monkeypatch.setitem used for ProbeAdapter test to avoid permanent registry mutation"
metrics:
  duration: 6 minutes
  completed: "2026-05-28"
  tasks_completed: 3
  files_modified: 14
---

# Phase 2 Plan 02: Mock Adapters and Dispatcher Summary

AwsLambdaMockAdapter with full provision/deprovision/get_status, 9 placeholder adapters wiring all 10 registry slots, and Dispatcher driving PENDING→PROVISIONING→READY state machine — full vertical slice testable without HTTP server.

## What Was Built

### Task 1: AwsLambdaMockAdapter and 9 placeholder adapters (commits: d416e79, 61ddee2)

- **AwsLambdaMockAdapter** (`src/pecp/adapters/mock/aws_lambda.py`):
  - `provision()`: `await asyncio.sleep(2)`, isinstance narrowing for mypy, returns `ProvisionResult` with `function_arn/region/runtime` metadata and two `"Would call: aws lambda ..."` log entries
  - `deprovision()`: `await asyncio.sleep(1)`, returns delete-function log entry
  - `get_status()`: minimal `ProvisionResult(status=ready)` per Phase 1 D-03 — no sleep, no metadata
  - Defensive fallback: non-LambdaSpec returns `ProvisionResult(status=failed, error="Unexpected spec type: ...")`

- **9 placeholder adapters**: `AwsContainerMockAdapter`, `AwsDataMockAdapter`, `AwsAccountMockAdapter`, `KubernetesMockAdapter`, `SalesforceMockAdapter`, `AemMockAdapter`, `DatadogMockAdapter`, `ServiceNowMockAdapter`, `JFrogMockAdapter`
  - Each is an instantiable `AdapterBase` subclass
  - `provision`/`deprovision` return `activity_log=["Would call: (placeholder -- implemented in plan 03 or 04)"]`
  - `get_status` returns minimal `ProvisionResult(status=ready)` per D-03
  - **Grep marker for Plans 03/04**: `(placeholder -- implemented in plan 03 or 04)`

- **`src/pecp/adapters/mock/__init__.py`**: explicit named imports and `__all__` for all 10 adapter classes

- **5 tests in `tests/test_adapters/mock/test_aws_lambda.py`**: provision happy path, sleep patching, deprovision delete log, get_status no metadata, non-lambda spec returns failed

### Task 2: Dispatcher module (commits: 9c5ff45, 48c7917)

- **`src/pecp/dispatcher.py`** at top-level (not inside `api/` — D-05):
  - `AdapterNotFoundError(KeyError)` with `.kind` attribute
  - `ADAPTER_REGISTRY: dict[str, AdapterBase]` with all 10 entries in canonical kind order
  - `async def dispatch(resource_id: str, session: AsyncSession) -> None` — locked signature for Phase 3 BackgroundTasks
  - State machine: PENDING → PROVISIONING (committed) → adapter.provision() → READY|FAILED (committed)
  - Missing kind: writes `status=failed` + `activity_log=["No adapter registered for kind: ..."]` + commits + returns (no uncaught KeyError)
  - No `from fastapi` or `from pecp.api` imports

### Task 3: Dispatcher integration tests (commit: 510c88d, d176aa9)

- **3 tests in `tests/test_dispatcher/test_dispatch.py`**:
  - `test_dispatch_drives_pending_to_ready`: inserts PECPLambda record, calls dispatch, asserts `status=ready`, `activity_log` has `"Would call:"` prefix, `provider_metadata` contains `function_arn`
  - `test_dispatch_writes_provisioning_before_adapter_returns`: ProbeAdapter class captures DB status during `provision()` via same session — asserts `"provisioning"` was visible before adapter returned
  - `test_dispatch_unknown_kind_writes_failed`: monkeypatches `ADAPTER_REGISTRY={}`, asserts `status=failed` and kind name in activity_log

## dispatch() Function Signature

```python
async def dispatch(resource_id: str, session: AsyncSession) -> None
```

Locked per D-03 — Phase 3 will call this from `BackgroundTasks` with no changes.

## ADAPTER_REGISTRY Kind List

| Kind | Adapter Class |
|------|--------------|
| `PECPLambda` | `AwsLambdaMockAdapter` (real implementation) |
| `PECPContainer` | `AwsContainerMockAdapter` (placeholder — Plan 03) |
| `PECPDataService` | `AwsDataMockAdapter` (placeholder — Plan 03) |
| `PECPAccount` | `AwsAccountMockAdapter` (placeholder — Plan 03) |
| `PECPKubernetes` | `KubernetesMockAdapter` (placeholder — Plan 04) |
| `PECPSalesforce` | `SalesforceMockAdapter` (placeholder — Plan 04) |
| `PECPAem` | `AemMockAdapter` (placeholder — Plan 04) |
| `PECPDatadog` | `DatadogMockAdapter` (placeholder — Plan 04) |
| `PECPServiceNow` | `ServiceNowMockAdapter` (placeholder — Plan 04) |
| `PECPJFrog` | `JFrogMockAdapter` (placeholder — Plan 04) |

## AwsLambdaMockAdapter Activity Log Shape

```python
activity_log=[
    "Would call: aws lambda create-function --function-name {fn_name} --runtime python3.12 --code S3Bucket=pecp-deploys,S3Key={spec.source_code}",
    "Would call: aws lambda add-permission --function-name {fn_name} --statement-id AllowAPIGateway --action lambda:InvokeFunction",
]
```

## Placeholder Adapters for Plans 03 and 04

All 9 placeholder adapters contain the grep marker: `(placeholder -- implemented in plan 03 or 04)`

**Plans 03 and 04** can locate placeholder bodies via:
```bash
grep -r "placeholder -- implemented in plan" src/pecp/adapters/mock/
```

Plan 03 owns: `AwsContainerMockAdapter`, `AwsDataMockAdapter`, `AwsAccountMockAdapter`
Plan 04 owns: `KubernetesMockAdapter`, `SalesforceMockAdapter`, `AemMockAdapter`, `DatadogMockAdapter`, `ServiceNowMockAdapter`, `JFrogMockAdapter`

## Deviations from Plan

None — plan executed exactly as written. Import sort order in test files was auto-fixed by ruff (Rule 1 - style).

### Auto-fixed Issues

**1. [Rule 1 - Style] Ruff import sort violation in test files**
- **Found during:** Task 3 overall verification (ruff check src/ tests/)
- **Issue:** `import pytest` appeared before `from unittest.mock import patch` in test_aws_lambda.py (I001); imports were un-sorted in test_dispatch.py (I001); unused `pytest` import in test_aws_lambda.py (F401)
- **Fix:** `ruff check --fix` applied automatically
- **Files modified:** `tests/test_adapters/mock/test_aws_lambda.py`, `tests/test_dispatcher/test_dispatch.py`
- **Commit:** d176aa9

## Known Stubs

The 9 placeholder adapters are intentional stubs per the plan design — they return `activity_log=["Would call: (placeholder -- implemented in plan 03 or 04)"]`. These are not rendering stubs that block plan goals; they enable the registry to be fully wired while Plans 03/04 replace the bodies. Documented explicitly in each file's docstring and class docstring.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what was planned.

T-02-02-S01 (Spoofing via unknown kind) — mitigated: `if spec.kind not in ADAPTER_REGISTRY` branch writes `status=failed` + structured log + commits + returns. Verified by `test_dispatch_unknown_kind_writes_failed`.

T-02-02-V01/V02 (Input validation) — mitigated: Pydantic discriminator + isinstance narrowing in AwsLambdaMockAdapter. Verified by `test_aws_lambda_rejects_non_lambda_spec_returns_failed`.

## Verification Results

| Check | Result |
|-------|--------|
| `python -m pytest tests/test_dispatcher/test_dispatch.py -x -q` | 3 passed in 0.06s |
| `python -m pytest tests/test_adapters/mock/test_aws_lambda.py -x -q` | 5 passed in 0.03s |
| `python -m pytest tests/ -q` | 37 passed, 9 skipped in 0.30s |
| `python -m mypy src/` | Success: no issues found in 29 source files |
| `python -m ruff check src/ tests/` | All checks passed |
| ADAPTER_REGISTRY has 10 entries | Verified |
| All 10 adapter classes importable from pecp.adapters.mock | Verified |
| No `@pytest.mark.asyncio` in new tests | Verified |
| No `yaml.load` (unsafe) | Verified |
| No `from fastapi` or `from pecp.api` in dispatcher.py | Verified |

## TDD Gate Compliance

**Task 1:** RED commit d416e79 (failing test), GREEN commit 61ddee2 (implementation) — gates satisfied.
**Task 2:** RED commit 9c5ff45 (failing import test), GREEN commit 48c7917 (dispatcher implementation) — gates satisfied.
**Task 3:** Integration test promotion in commit 510c88d — tests passed on first run since dispatcher was already implemented.

## Self-Check: PASSED

---
phase: 02-core-engine
plan: "03"
subsystem: mock-adapters-aws-family
tags: [mock-adapters, aws-container, aws-data, aws-account, tdd, kinds-02, kinds-03, kinds-04, slow-path, subtype-branching]
dependency_graph:
  requires: [02-02]
  provides: [aws-container-adapter, aws-data-adapter-5-subtypes, aws-account-adapter-slow-path, dispatcher-account-integration-test]
  affects: [02-04-PLAN, 03-api-server]
tech_stack:
  added: []
  patterns: [isinstance-narrowing, asyncio-sleep-patching, subtype-branching, slow-path-dwell, tdd-red-green]
key_files:
  created: []
  modified:
    - src/pecp/adapters/mock/aws_container.py
    - src/pecp/adapters/mock/aws_data.py
    - src/pecp/adapters/mock/aws_account.py
    - tests/test_adapters/mock/test_aws_container.py
    - tests/test_adapters/mock/test_aws_data.py
    - tests/test_adapters/mock/test_aws_account.py
    - tests/test_dispatcher/test_dispatch.py
decisions:
  - "asyncio.sleep(3) placed inline in AwsAccountMockAdapter.provision() — Dispatcher does NOT poll; sleep is the dwell simulation per KINDS-04"
  - "if/elif chain used for DataServiceSubtype branching (over match statement) for Python 3.10+ compatibility and simplicity"
  - "deprovision() on AwsAccountMockAdapter has no sleep — deprovision is fast; only provision simulates the AWS Organizations latency"
metrics:
  duration: 30 minutes
  completed: "2026-05-28"
  tasks_completed: 3
  files_modified: 7
---

# Phase 2 Plan 03: AWS Family Adapter Implementations Summary

Three AWS placeholder adapters replaced with real implementations — AwsContainerMockAdapter (ECS), AwsDataMockAdapter (5-subtype branching), and AwsAccountMockAdapter (3s slow-path dwell); all accompanied by promoted test files and one new Dispatcher integration test proving the slow-path routes end-to-end.

## What Was Built

### Task 1: AwsContainerMockAdapter (KINDS-02) — commits: f8e5da3 (RED), 86a81fb (GREEN)

**`src/pecp/adapters/mock/aws_container.py`** — real ECS simulation:
- `provision()`: `await asyncio.sleep(2)`; isinstance narrowing for ContainerSpec; returns `ProvisionResult` with:
  - `provider_metadata`: `task_definition_arn` (synthetic ARN), `cluster` (`pecp-{name}-cluster`), `image` (echoed from spec.image), `exposure` (echoed from spec.exposure)
  - `activity_log` [2 entries]:
    - `"Would call: aws ecs register-task-definition --family pecp-{name} --container-definitions name={name},image={image}"`
    - `"Would call: aws ecs create-service --cluster pecp-{name}-cluster --service-name {name} --desired-count 1"`
- `deprovision()`: `await asyncio.sleep(1)`; returns `"Would call: aws ecs delete-service --cluster pecp-{name}-cluster --service {name} --force"`
- `get_status()`: minimal `ProvisionResult(status=ready)` per D-03

**`tests/test_adapters/mock/test_aws_container.py`** — 5 tests covering:
1. `test_aws_container_provision_returns_ready_with_image_in_log` — status=ready, 2+ log entries, nginx:1.27 in log, image in metadata
2. `test_aws_container_provision_patches_sleep` — sleep call count >= 1
3. `test_aws_container_deprovision_returns_delete_log` — "Would call: aws ecs delete-service" prefix
4. `test_aws_container_get_status_returns_ready_no_metadata` — status=ready, empty metadata
5. `test_aws_container_rejects_non_container_spec_returns_failed` — status=failed, "Unexpected spec type" in error

### Task 2: AwsDataMockAdapter (KINDS-03) — commits: 358c09e (RED), 6b770eb (GREEN), 696f858 (ruff fix)

**`src/pecp/adapters/mock/aws_data.py`** — 5-subtype branching:

| Subtype | Activity Log Entry | Metadata Key |
|---------|-------------------|--------------|
| s3 | `"Would call: aws s3api create-bucket --bucket pecp-{name}"` | `bucket_arn`: `arn:aws:s3:::pecp-{name}` |
| sqs | `"Would call: aws sqs create-queue --queue-name pecp-{name}"` | `queue_url`: `https://sqs.us-east-1.amazonaws.com/123456789012/pecp-{name}` |
| sns | `"Would call: aws sns create-topic --name pecp-{name}"` | `topic_arn`: `arn:aws:sns:us-east-1:123456789012:pecp-{name}` |
| rds | `"Would call: aws rds create-db-instance --db-instance-identifier pecp-{name}"` | `db_instance_arn`: `arn:aws:rds:us-east-1:123456789012:db:pecp-{name}` |
| dynamodb | `"Would call: aws dynamodb create-table --table-name pecp-{name}"` | `table_arn`: `arn:aws:dynamodb:us-east-1:123456789012:table/pecp-{name}` |

All branches also include `name` and `subtype` keys in `provider_metadata`. `deprovision()` emits `"Would call: aws {subtype} delete-resource --name pecp-{name}"`.

**`tests/test_adapters/mock/test_aws_data.py`** — 9 tests:
- 5 parametrized `test_aws_data_provision_branches_per_subtype` (one per subtype), verifying log prefix and metadata key
- 4 standalone: sleep patching, deprovision delete-resource log, get_status no metadata, non-data spec rejection

### Task 3: AwsAccountMockAdapter slow-path + Dispatcher integration (KINDS-04) — commits: 8327847 (RED adapter), 0ca9d99 (RED dispatcher), db754bc (GREEN)

**`src/pecp/adapters/mock/aws_account.py`** — 3s slow-path:
- `provision()`: isinstance check → `team = resource.metadata.team or "unknown"` → **`await asyncio.sleep(3)`** (literal 3, single call, KINDS-04 dwell) → returns:
  - `provider_metadata`: `{"account_id": "123456789012", "account_email": "aws+{team}@example.com", "account_name": "pecp-{team}", "management_console_url": "https://console.aws.amazon.com/switch-role?account=123456789012"}`
  - `activity_log` [3 entries]: `aws organizations create-account`, `aws organizations describe-create-account-status`, `aws sts assume-role`
- `deprovision()`: no sleep; returns `"Would call: aws organizations close-account (manual PE action required)"`
- `get_status()`: minimal `ProvisionResult(status=ready)` per D-03

**`tests/test_adapters/mock/test_aws_account.py`** — 7 tests:
1. `test_aws_account_provision_calls_sleep_3_seconds` — `mock_sleep.call_args == call(3)` verifies the literal 3 dwell value (KINDS-04 key verification)
2. `test_aws_account_provision_returns_ready_with_synthetic_metadata` — account_id, account_email, account_name, management_console_url present
3. `test_aws_account_provision_activity_log_has_organizations_create_account` — `aws organizations create-account` in log
4. `test_aws_account_provision_team_unknown_when_metadata_team_none` — `aws+unknown@example.com` when team=None
5. `test_aws_account_deprovision_returns_close_account_log` — "close-account" in log
6. `test_aws_account_get_status_returns_ready_no_metadata` — status=ready, empty metadata
7. `test_aws_account_rejects_non_account_spec_returns_failed` — status=failed, "Unexpected spec type" in error

**New test in `tests/test_dispatcher/test_dispatch.py`**:
- `test_dispatch_drives_account_pending_to_ready` — inserts PECPAccount record, calls `dispatch()` with `asyncio.sleep` patched, asserts `status=ready`, `account_id == "123456789012"` in metadata, `"aws organizations create-account"` in log. Proves the KINDS-04 slow-path routes through the Dispatcher state machine identically to Lambda's fast path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] DataServiceSpec `name` field missing from `_build_spec` helper**
- **Found during:** Task 2 RED test run
- **Issue:** `_build_spec()` initially only passed `"subtype"` in the spec dict, but `DataServiceSpec.name` is a required field. Pydantic raised `ValidationError` before any adapter logic ran.
- **Fix:** Added `"name": name` to the spec dict inside `_build_spec()`. One-line fix.
- **Files modified:** `tests/test_adapters/mock/test_aws_data.py`
- **Commit:** 358c09e (corrected before RED commit)

**2. [Rule 1 - Style] Unused `DataServiceSubtype` import in test_aws_data.py**
- **Found during:** Final `ruff check` verification
- **Issue:** `DataServiceSubtype` was imported for anticipated use in `_build_spec` but the parametrized test uses string values directly (Pydantic coerces them to enum members). Ruff F401 caught the unused import.
- **Fix:** Removed `DataServiceSubtype` from the import line.
- **Files modified:** `tests/test_adapters/mock/test_aws_data.py`
- **Commit:** 696f858

## Known Stubs

None. All three adapters are fully implemented with real mock logic. The 6 adapters owned by Plan 04 (`KubernetesMockAdapter`, `SalesforceMockAdapter`, `AemMockAdapter`, `DatadogMockAdapter`, `ServiceNowMockAdapter`, `JFrogMockAdapter`) remain as deliberate Plan 02 placeholders — out of scope for this plan.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All threats in the plan's threat model are addressed:

- **T-02-03-V01** (wrong spec subtype): Mitigated — each adapter's first action is `isinstance` check; `test_aws_*_rejects_non_*_spec_returns_failed` tests verify this.
- **T-02-03-T01** (unknown DataServiceSubtype): Non-issue — `DataServiceSubtype` is a Python Enum; Pydantic rejects unknown values at validation time; the `else` branch covers `dynamodb` (the final enum value after all `elif` branches).
- **T-02-03-T02** (hostile `metadata.team` string): Accepted — PoC scope; `json.dumps` escapes control characters in activity_log; no real AWS API call made.
- **T-02-03-D01** (3s sleep blocks dispatch): Accepted + mitigated in tests — `asyncio.sleep` patched to zero in all tests; wall time 0.10s for all 25 tests.
- **T-02-03-I01** (synthetic ARNs): Accepted — all values are constants with no real account IDs.

## Verification Results

| Check | Result |
|-------|--------|
| `python -m pytest tests/test_adapters/mock/test_aws_container.py -q` | 5 passed in 0.03s |
| `python -m pytest tests/test_adapters/mock/test_aws_data.py -q` | 9 passed in 0.02s |
| `python -m pytest tests/test_adapters/mock/test_aws_account.py -q` | 7 passed in 0.03s |
| `python -m pytest tests/test_dispatcher/test_dispatch.py -q` | 4 passed in 0.07s |
| `python -m pytest tests/ -q` | 59 passed, 6 skipped in 0.31s |
| `python -m mypy src/` | Success: no issues found in 29 source files |
| `python -m ruff check src/ tests/` | All checks passed |
| `grep "(placeholder" src/pecp/adapters/mock/aws_*.py` | No output — all 3 placeholders replaced |
| `grep -c "Would call: aws" src/pecp/adapters/mock/aws_data.py` | 6 (5 provision branches + 1 deprovision) |
| Total wall time (25 new tests) | 0.10s — under 2s requirement |

## TDD Gate Compliance

- **Task 1:** RED commit f8e5da3 (failing tests), GREEN commit 86a81fb (implementation) — gates satisfied
- **Task 2:** RED commit 358c09e (failing tests), GREEN commit 6b770eb (implementation) — gates satisfied
- **Task 3:** RED commits 8327847 (account adapter tests), 0ca9d99 (dispatcher integration test), GREEN commit db754bc (implementation) — gates satisfied

## Self-Check: PASSED

All files verified as present on disk. All task commits found in git history:
- f8e5da3: Task 1 RED (container tests)
- 86a81fb: Task 1 GREEN (container adapter)
- 358c09e: Task 2 RED (data tests)
- 6b770eb: Task 2 GREEN (data adapter)
- 696f858: Task 2 ruff fix
- 8327847: Task 3 RED (account adapter tests)
- 0ca9d99: Task 3 RED (dispatcher integration test)
- db754bc: Task 3 GREEN (account adapter)

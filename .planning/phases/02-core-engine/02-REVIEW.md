---
phase: 02-core-engine
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - alembic/env.py
  - alembic/script.py.mako
  - alembic/versions/0001_add_provider_cols.py
  - src/pecp/adapters/mock/__init__.py
  - src/pecp/adapters/mock/aem.py
  - src/pecp/adapters/mock/aws_account.py
  - src/pecp/adapters/mock/aws_container.py
  - src/pecp/adapters/mock/aws_data.py
  - src/pecp/adapters/mock/aws_lambda.py
  - src/pecp/adapters/mock/datadog.py
  - src/pecp/adapters/mock/jfrog.py
  - src/pecp/adapters/mock/kubernetes.py
  - src/pecp/adapters/mock/salesforce.py
  - src/pecp/adapters/mock/servicenow.py
  - src/pecp/dispatcher.py
  - src/pecp/models/resource_spec.py
  - src/pecp/persistence/models.py
  - tests/conftest.py
  - tests/test_adapters/mock/test_aem.py
  - tests/test_adapters/mock/test_aws_account.py
  - tests/test_adapters/mock/test_aws_container.py
  - tests/test_adapters/mock/test_aws_data.py
  - tests/test_adapters/mock/test_aws_lambda.py
  - tests/test_adapters/mock/test_datadog.py
  - tests/test_adapters/mock/test_jfrog.py
  - tests/test_adapters/mock/test_kubernetes.py
  - tests/test_adapters/mock/test_salesforce.py
  - tests/test_adapters/mock/test_servicenow.py
  - tests/test_dispatcher/test_dispatch_extended_kinds.py
  - tests/test_dispatcher/test_dispatch.py
  - tests/test_models/test_resource_spec.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the Phase 02 core engine implementation: Alembic migrations, all 10 mock adapters, the Dispatcher state machine, resource spec models, persistence models, and the full test suite. The adapters are internally consistent and well-tested in isolation. However, three blockers prevent the system from functioning end-to-end as a control plane.

The most critical gap is that the `dispatch()` function — which drives the state machine — is never wired into the API route that creates resources. Every `POST /resources` call leaves the record permanently in `pending` state. The dispatcher also has two unguarded failure modes that corrupt state. On the model side, 8 of 10 spec types silently accept unknown fields, weakening the validation contract the platform is built on.

## Critical Issues

### CR-01: `dispatch()` is never called from the API route — resources are never provisioned

**File:** `src/pecp/api/routes/resources.py:54-97`
**Issue:** `create_resource()` persists the `ResourceRecord` with `status="pending"` but never triggers the dispatcher. The `dispatch()` function exists and works (proven by tests), but there is no `BackgroundTasks` wiring in the route handler. Every resource submitted via `POST /resources` stays in `pending` forever, making the entire provisioning flow unreachable through the API.

**Fix:**
```python
from fastapi import BackgroundTasks
from pecp.dispatcher import dispatch
from pecp.persistence.database import AsyncSessionLocal

@router.post("", status_code=202)
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, str]:
    ...
    session.add(record)
    await session.commit()

    async def _dispatch_with_own_session(rid: str) -> None:
        async with AsyncSessionLocal() as bg_session:
            await dispatch(rid, bg_session)

    background_tasks.add_task(_dispatch_with_own_session, resource_id)
    return {"id": resource_id, "status": "pending", "kind": spec.kind, "name": spec.metadata.name}
```

Note: the background task must open its own session; using the request-scoped session from the route's `SessionDep` after the response is sent causes a `MissingGreenlet` / closed-session error with async SQLAlchemy.

---

### CR-02: Unhandled exception in `dispatch()` leaves records permanently stuck in `provisioning`

**File:** `src/pecp/dispatcher.py:66-73`
**Issue:** The dispatcher commits `status=provisioning` before calling `adapter.provision()` (line 57), but there is no `try/except` around the adapter call (line 67). The `AdapterBase` contract says adapters should not raise, but that is a convention, not an enforcement. Any unexpected exception (a bug in an adapter, an unhandled edge case, a future real-adapter network error) propagates out of `dispatch()`, the final `session.commit()` on line 73 is skipped, and the record is permanently frozen in `provisioning`. There is no recovery path.

**Fix:**
```python
try:
    provision_result = await adapter.provision(spec)
except Exception as exc:  # noqa: BLE001
    record.status = ResourceStatus.failed.value
    record.activity_log = json.dumps([f"Adapter raised unexpected exception: {exc}"])
    await session.commit()
    return

record.status = provision_result.status.value
record.provider_metadata = json.dumps(provision_result.provider_metadata)
record.activity_log = json.dumps(provision_result.activity_log)
await session.commit()
```

---

### CR-03: `dispatch()` uses `scalar_one()` with no guard — `NoResultFound` propagates on unknown ID

**File:** `src/pecp/dispatcher.py:48-51`
**Issue:** `result.scalar_one()` raises `sqlalchemy.exc.NoResultFound` if the `resource_id` does not match any row. This path is reachable when `dispatch()` is called from a `BackgroundTask` after the record is created, if — for any reason — the ID is wrong or the commit was rolled back. The exception propagates silently out of `BackgroundTasks` (FastAPI logs it but does not surface it to the caller). There is no structured failure record written to the database.

**Fix:**
```python
record = result.scalar_one_or_none()
if record is None:
    # Nothing to update — log and return; caller will see no state change
    return
```

---

## Warnings

### WR-01: Engine connection pool leaked when `do_run_migrations()` raises in `alembic/env.py`

**File:** `alembic/env.py:31-35`
**Issue:** `connectable.dispose()` is called unconditionally after the `async with` block, but if `connection.run_sync(do_run_migrations)` raises an exception, the exception propagates out of the `async with` block (which correctly releases the connection) but then skips `await connectable.dispose()`. The engine's connection pool is not shut down, leaving it open until the process exits. For a one-shot migration script this is low-impact, but it is still a resource management defect.

**Fix:**
```python
async def run_async_migrations() -> None:
    connectable = create_async_engine(DATABASE_URL)
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()
```

---

### WR-02: 8 of 10 resource spec models lack `extra="forbid"` — unknown fields are silently dropped

**File:** `src/pecp/models/resource_spec.py:34-72`
**Issue:** `LambdaSpec` and `ContainerSpec` correctly use `ConfigDict(extra="forbid")`, but `DataServiceSpec`, `AccountSpec`, `SalesforceSpec`, `AemSpec`, `KubernetesSpec`, `DatadogSpec`, `ServiceNowSpec`, and `JFrogSpec` do not. A user submitting `kind: PECPAccount` with a typo in a field name (e.g., `regoin: us-east-1`) will receive a 202 with no error. The field is silently ignored. This defeats the validation contract that Pydantic is supposed to enforce at the API boundary.

**Fix:** Add `model_config = ConfigDict(extra="forbid")` to every spec class that lacks it. The `config: dict[str, Any]` field on the generic specs means any valid key-value pairs are still accepted — `extra="forbid"` only blocks fields that are not declared on the model itself, which for those models is just `kind` and `config`.

```python
class DataServiceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["PECPDataService"]
    name: str
    subtype: DataServiceSubtype
```

Apply the same pattern to `AccountSpec`, `SalesforceSpec`, `AemSpec`, `KubernetesSpec`, `DatadogSpec`, `ServiceNowSpec`, and `JFrogSpec`.

---

### WR-03: Whitespace-only `team` parameter bypasses the required-field check in both route handlers

**File:** `src/pecp/api/routes/resources.py:35-36, 67-68`
**Issue:** Both `list_resources` and `create_resource` check `if not team:` to enforce the required `team` parameter. A string of whitespace (e.g., `team=   `) is truthy in Python, so it passes this check. The record is then persisted with `team="   "` (or queried with a whitespace key), which will never match any real team and silently returns wrong results.

**Fix:**
```python
if not team or not team.strip():
    raise HTTPException(status_code=400, detail="team parameter is required")
```

Or strip at assignment: `team = (team or "").strip()` followed by `if not team:`.

---

### WR-04: `spec.metadata.team` in YAML is never validated against the `?team=` query parameter

**File:** `src/pecp/api/routes/resources.py:80-90`
**Issue:** The route accepts a `?team=` query parameter and stores it in `ResourceRecord.team`. The submitted YAML spec can contain a different `metadata.team` value (or omit it entirely). There is no cross-validation. A submitter can pass `?team=platform-team` with `metadata.team: other-team` in the YAML body. The record is stored under `platform-team`, but the adapter receives the `ResourceSpec` with `metadata.team = "other-team"`, and all provisioned resources (namespaces, emails, etc.) are scoped to `other-team`. This is a team-attribution mismatch and a correctness defect.

**Fix:** After parsing the spec, assert or enforce consistency:
```python
if spec.metadata.team is not None and spec.metadata.team != team:
    raise HTTPException(
        status_code=422,
        detail=f"YAML metadata.team ({spec.metadata.team!r}) does not match ?team= ({team!r})",
    )
# Optionally, backfill metadata.team if absent:
# spec = spec.model_copy(update={"metadata": spec.metadata.model_copy(update={"team": team})})
```

---

## Info

### IN-01: `test_all_six_kinds_constructable` is misnamed and omits `LambdaSpec`

**File:** `tests/test_models/test_resource_spec.py:62-74`
**Issue:** The test is named `test_all_six_kinds_constructable` with a docstring claiming "All 10 resource kinds", but it constructs only 9 kinds. `LambdaSpec` is the missing one. The test name also still says "six" — a stale carry-over from before the 4 new kinds were added. If `LambdaSpec` has a constructor regression, this test will not catch it.

**Fix:** Rename the test to `test_all_ten_kinds_constructable` and add the missing `LambdaSpec` construction:
```python
LambdaSpec(
    kind="PECPLambda",
    name="fn",
    exposure="private",
    **{"api-gateway": "/fn", "source-code": "github://org/repo"},
)
```
Or use `model_validate` with the alias keys since `LambdaSpec` uses `Field(alias=...)`.

---

### IN-02: `AdapterNotFoundError` is defined but never raised

**File:** `src/pecp/dispatcher.py:24-29`
**Issue:** `AdapterNotFoundError(KeyError)` is defined at module level with a helpful message, but the dispatcher's unknown-kind path (lines 60-64) does not raise it — it manually writes a failed record and returns. Nothing in the codebase raises or catches `AdapterNotFoundError`. This is dead code that adds confusion.

**Fix:** Either remove `AdapterNotFoundError` since the dispatcher handles unknown kinds inline, or use it as an internal signal within the dispatcher and catch it there. Do not leave it defined but unused.

---

_Reviewed: 2026-05-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

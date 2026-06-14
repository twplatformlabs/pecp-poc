---
phase: 03-rest-api-core-cli
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - alembic/env.py
  - alembic/versions/0002_add_env_notes_unique.py
  - src/pecp/api/routes/resources.py
  - src/pecp/cli/main.py
  - src/pecp/models/resource_spec.py
  - src/pecp/persistence/models.py
  - tests/conftest.py
  - tests/test_api/test_cli.py
  - tests/test_api/test_dispatch_wiring.py
  - tests/test_api/test_idempotency.py
  - tests/test_api/test_notes.py
  - tests/test_api/test_routes.py
findings:
  critical: 3
  warning: 3
  info: 3
  total: 9
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

This phase delivers the REST API routes (list, create, get, delete, add-note), the Typer CLI, Pydantic resource models, SQLAlchemy ORM models, Alembic migration 0002, and a full test suite. The architecture is sound and the idempotency and team-scoping logic is correct for the happy paths. Three bugs require fixes before this code ships: a CLI error swallowing path that renders garbage output on server errors, a logic inconsistency in spec-kind resolution that silently misroutes resources, and an unhandled exception that surfaces as a 500 when a concurrent-creation race is extremely unlucky. Three warnings cover a notes read-modify-write race, an unguarded exception propagation path in the dispatcher, and a weak test assertion that always passes.

---

## Critical Issues

### CR-01: CLI `status` command does not check HTTP status code on detail fetch — crashes or silently renders error body as resource fields

**File:** `src/pecp/cli/main.py:197`

**Issue:** After successfully finding the resource ID via the list endpoint, the `status` command fetches `GET /resources/{id}` but never checks `detail_response.status_code` before calling `detail_response.json()`. If the server returns a non-200 response (404, 500, network timeout that completes with an HTTP response, etc.), `detail = detail_response.json()` parses the FastAPI error envelope `{"detail": "..."}`. The subsequent loop at line 203 then calls `detail["status"]` (a hard key access, not `.get()`), which raises an uncaught `KeyError` — crashing the CLI with a traceback. Even if the key happened to exist in an error body, the rendered table would display error-envelope fields as resource data.

**Fix:**
```python
    detail_response = httpx.get(f"{base}/resources/{record_id}", timeout=10.0)

    if detail_response.status_code != 200:
        console.print(
            f"[red]Error[/red] {detail_response.status_code}: {detail_response.text}"
        )
        raise typer.Exit(code=1)

    detail = detail_response.json()
```

---

### CR-02: `spec.spec` type and `ResourceRecord.kind` become inconsistent when user supplies `kind` inside the `spec` block

**File:** `src/pecp/models/resource_spec.py:116`

**Issue:** `inject_kind_into_spec` guards with `"kind" not in spec` before injecting the top-level `kind` into the spec dict. If a caller deliberately (or accidentally) includes `kind` in the spec block with a different value — e.g., top-level `kind: PECPLambda` but `spec.kind: PECPContainer` — the discriminated union resolves to `ContainerSpec` (correct for the spec body), while `ResourceSpec.kind` remains `"PECPLambda"`. The dispatcher then stores `kind="PECPLambda"` in the DB and routes to `AwsLambdaMockAdapter` with a `ContainerSpec` payload. Confirmed with the project venv:

```
spec.kind: PECPLambda    spec.spec type: ContainerSpec
```

The adapter receives the wrong model type. After storing, `spec_json` contains `ContainerSpec` fields under a `PECPLambda` record, silently corrupting the stored spec. The fix is to validate consistency after resolution:

**Fix:** Add a `model_validator(mode="after")` to `ResourceSpec`:
```python
@model_validator(mode="after")
def check_kind_consistency(self) -> "ResourceSpec":
    if self.spec.kind != self.kind:
        raise ValueError(
            f"Top-level kind {self.kind!r} does not match spec kind {self.spec.kind!r}"
        )
    return self
```

---

### CR-03: Unhandled `NoResultFound` exception in IntegrityError recovery path returns HTTP 500

**File:** `src/pecp/api/routes/resources.py:177`

**Issue:** When two concurrent `POST /resources` requests race for the same `(team, kind, name)` triple, the loser catches `IntegrityError`, rolls back, then re-fetches the winner's record using `scalar_one()`. If the winning record is deleted between the `IntegrityError` and the re-fetch (possible under concurrent load or when a DELETE runs immediately after a POST), `scalar_one()` raises `sqlalchemy.exc.NoResultFound`, which is not caught anywhere in the handler. FastAPI converts this to an unhandled 500 response. The caller sent a valid request and receives a server error.

**Fix:** Replace `scalar_one()` with `scalar_one_or_none()` and handle the missing case:
```python
        winner = race_result.scalar_one_or_none()
        if winner is None:
            raise HTTPException(
                status_code=409,
                detail="Resource was concurrently created and deleted; retry the request.",
            )
        return {
            "id": winner.id,
            "status": winner.status,
            "kind": winner.kind,
            "name": winner.name,
        }
```

---

## Warnings

### WR-01: Notes endpoint has a read-modify-write race — concurrent requests silently drop notes

**File:** `src/pecp/api/routes/resources.py:282-291`

**Issue:** `add_note` reads the current JSON blob from the DB, appends a new note in Python, then writes the whole list back. Two concurrent `POST /resources/{id}/notes` requests both read the same initial state (e.g., `[]`), both append their note locally, and both write a list with a single entry. The second `session.commit()` wins and the first note is permanently lost — no error, no retry, no warning to the caller. This is a textbook read-modify-write race on a JSON blob stored in a non-atomic column.

**Fix:** For PoC scope, acquire a row-level lock before reading:
```python
    result = await session.execute(
        select(ResourceRecord)
        .where(ResourceRecord.id == resource_id)
        .with_for_update()
    )
```
For a production path, migrate the notes to a child table with an append-only `INSERT`.

---

### WR-02: Dispatcher has no `try/except` guard around `adapter.provision()` — unhandled adapter exceptions strand resources in `provisioning` state

**File:** `src/pecp/dispatcher.py:67`

**Issue:** The docstring in `AdapterBase` says adapters must not raise, but this is a convention that cannot be enforced at compile time. If any adapter raises an unexpected exception (a bug in a future real adapter, an unhandled edge case, an external library exception), the exception propagates out of the `BackgroundTask`. FastAPI logs the exception and silently suppresses it at the background task level. The `ResourceRecord` remains in `status="provisioning"` indefinitely — a permanently stuck resource with no error message and no way to detect it short of polling. The record in `ADAPTER_REGISTRY` miss path already sets `status=failed`; unhandled exceptions bypass that path entirely.

**Fix:**
```python
    try:
        provision_result = await adapter.provision(spec)
    except Exception as exc:
        record.status = ResourceStatus.failed.value
        record.activity_log = json.dumps([f"Unhandled adapter exception: {exc}"])
        await session.commit()
        return

    record.status = provision_result.status.value
```

---

### WR-03: Test assertion in `test_apply_command_success_output` always passes regardless of whether team is in the URL

**File:** `tests/test_api/test_cli.py:122`

**Issue:** The assertion `assert "toxins-research" in str(url_arg) or "toxins-research" in str(call_kwargs)` has a tautological OR branch. `call_kwargs` is the entire `call_args` object which always contains `params={"team": "toxins-research"}`, so `"toxins-research" in str(call_kwargs)` is always `True`. This means the test passes even if the left branch (`url_arg`) contained an entirely wrong URL. The test intended to verify that the team value is present in the request, but because the OR always fires, it provides no coverage of the URL correctness.

**Fix:** Remove the OR fallback and assert specifically what matters — that the team is passed as a query param:
```python
    call_kwargs = mock_post.call_args
    params = call_kwargs[1].get("params", {}) if call_kwargs[1] else {}
    assert params.get("team") == "toxins-research"
```

---

## Info

### IN-01: `ResourceSpec.api_version` field accepts any string — no version validation

**File:** `src/pecp/models/resource_spec.py:100`

**Issue:** `api_version: str = Field(alias="apiVersion")` accepts `pecp/v99`, `wrongversion`, or an empty string without error. Kubernetes-flavored YAML convention expects this to be validated against the supported versions. If future versions introduce breaking spec changes, there is no version-gate to reject stale clients.

**Fix:** Use `Literal["pecp/v1"]` for now, widening to a union when v2 ships:
```python
api_version: Literal["pecp/v1"] = Field(alias="apiVersion")
```

---

### IN-02: ORM model and Alembic migration 0002 disagree on `notes` default storage

**File:** `src/pecp/persistence/models.py:43` / `alembic/versions/0002_add_env_notes_unique.py:23`

**Issue:** The Alembic migration adds `notes` with `server_default="[]"` (a DB-level default), but the ORM `mapped_column` sets only a Python-level `default="[]"` with no `server_default`. The migration's `server_default` applies to rows inserted via raw SQL or other ORMs, but the ORM `default` fires during SQLAlchemy `INSERT`. These are effectively equivalent for the ORM path but differ in schema intent. If the schema is inspected or a raw `INSERT` is done without the ORM, the behavior depends on which layer is consulted. Neither is wrong, but the inconsistency is a maintenance hazard — a future developer may remove the Python-level default assuming `server_default` covers it (it does not for in-memory SQLite tests that bypass migrations).

**Fix:** Align both by adding `server_default` to the ORM column definition:
```python
notes: Mapped[str | None] = mapped_column(
    Text, nullable=True, default="[]", server_default="[]"
)
```

---

### IN-03: `add_note` return type annotation is narrower than what `json.loads` actually returns

**File:** `src/pecp/api/routes/resources.py:266`

**Issue:** The return type annotation is `dict[str, list[dict[str, str]]]`, implying all note field values are `str`. At runtime `json.loads` returns `list[Any]` and Pydantic/mypy cannot enforce the inner dict shape. The type annotation is asserted rather than verified. With `mypy --strict`, this will produce a type error on the `json.loads` call assignment. Additionally, because `NoteCreate.text` is `str` and `ctx.user_id` / `datetime.strftime()` both return `str`, the annotation is correct in practice — but should use `Any` or a proper dataclass to make the intent clear.

**Fix:** Either introduce a typed `Note` dataclass or relax the return annotation:
```python
class Note(TypedDict):
    author: str
    timestamp: str
    text: str

async def add_note(...) -> dict[str, list[Note]]:
    ...
    current_notes: list[Note] = json.loads(record.notes or "[]")
```

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

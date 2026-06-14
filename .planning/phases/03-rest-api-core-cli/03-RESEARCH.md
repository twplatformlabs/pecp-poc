# Phase 3: REST API + Core CLI - Research

**Researched:** 2026-06-14
**Domain:** FastAPI REST endpoints, SQLAlchemy 2.x async ORM, Alembic migrations, Typer/Rich CLI, BackgroundTasks dispatch wiring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Add optional `env` field to `ResourceMetadata` in `src/pecp/models/resource_spec.py`. Users may include it in their YAML spec under `metadata.env`. All 6 existing kind models already share `ResourceMetadata` — no per-kind changes needed.

**D-02:** Store `env` as a top-level nullable `Text` column on `ResourceRecord`. Set it from `spec.metadata.env` at creation time. Do NOT parse it from `spec_json` at query time — direct column is faster and simpler for filtering.

**D-03:** `notes` stored as a nullable `Text` column on `ResourceRecord` containing a JSON-serialized list of `{"author": str, "timestamp": str, "text": str}` dicts. No separate table — matches the existing `activity_log` pattern on the same record.

**D-04:** `POST /resources/{id}/notes` accepts a JSON body `{"text": "..."}`. Author is inferred server-side from `ctx.user_id` (RequestContext stub). Timestamp is set server-side at append time.

**D-05:** `POST /resources/{id}/notes` returns `201 Created` with `{"notes": [...]}` — the full updated notes list. Caller sees the appended result immediately; CLI can confirm what was added without a second request.

**D-06:** Notes rendered in `pecp status` output as a timestamped block below the main status table. Format: `[YYYY-MM-DD HH:MM] author: text` — one line per note. Clearly separated from the adapter `activity_log`.

**D-07:** No separate `GET /resources/{id}/notes` endpoint. Notes are only visible via `GET /resources/{id}` (the status endpoint). Fewer routes, single call for `pecp status`.

**D-08:** Uniqueness key is `(team, kind, name)`. Mirrors Kubernetes: `metadata.name` is unique per kind within a team (namespace). `POST /resources` queries by this triple before deciding to create or update.

**D-09:** No-op (spec unchanged after lookup): return `202 Accepted` with the existing resource `id` and current `status`. Same response shape as a create — CLI output is identical.

**D-10:** Changed spec (same `team + kind + name`, different content): update `spec_json` in place, reset `status` to `pending`, re-dispatch via BackgroundTasks. The resource `id` is preserved.

**D-11:** Spec change detection: serialize the incoming spec via `model_dump_json()` and compare the string to the stored `spec_json`. Deterministic with Pydantic's stable serialization. No extra columns or hashing.

**D-12:** `POST /resources` (both create and update paths) enqueues `dispatch(resource_id, session)` via FastAPI `BackgroundTasks`. Dispatcher signature at `src/pecp/dispatcher.py` remains unchanged (D-03 from Phase 2 CONTEXT).

### Claude's Discretion

- `pecp status` output format: Rich table for resource fields (id, kind, name, status, env, created_at), followed by notes block if notes exist. No interactive refresh (--watch is deferred).
- `pecp get` Rich table columns: name, kind, status badge (colored by status), env (or `—` if absent).
- `pecp delete` calls `DELETE /resources/{id}` (route to be added) and prints confirmation. No soft-delete in PoC — hard delete from DB.
- Alembic migration for the two new columns (`env`, `notes`) — follows the Phase 2 pattern (`provider_metadata`, `activity_log`).
- DB-level unique constraint on `(team, kind, name)` for defense-in-depth against race conditions.

### Deferred Ideas (OUT OF SCOPE)

- `pecp status --watch` polling with exponential backoff.
- `~/.pecp/config.yaml` config file (CLI-11 — `--api-url` + `PECP_API_URL` env var are sufficient for Phase 3).
- `pecp team` commands, projects/deployments endpoints — Phase 4+.
- Real-time status updates in CLI (Rich Live refresh).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTRL-01 | Platform accepts a YAML resource spec via `POST /resources`, validates against the correct kind schema, and returns `202 Accepted` with a resource ID | Existing route extended with idempotency logic; BackgroundTasks dispatch added |
| CTRL-02 | Platform enforces `pending → provisioning → ready → failed` lifecycle owned by Dispatcher | Dispatcher already implements lifecycle; Phase 3 wires BackgroundTasks to trigger it |
| CTRL-03 | `pecp apply -f resource.yaml` submitted twice is a no-op (spec unchanged) or triggers an update (spec changed) — no duplicate resources | Uniqueness lookup on `(team, kind, name)` before insert; Alembic unique constraint; `model_dump_json()` comparison |
| CTRL-04 | Any resource can have an append-only notes log that PE team members can write to, visible on status queries | `POST /resources/{id}/notes` appending to JSON text column; `GET /resources/{id}` returning notes list |
| CLI-01 | `pecp apply -f resource.yaml` — submits a YAML spec to the control plane | Existing `apply` command extended to display idempotency-aware output |
| CLI-02 | `pecp get <kind> --team <team>` — lists resources of a type for a team with status badges | New `get` command with Rich Table, colored status badges |
| CLI-03 | `pecp delete <kind> <name> --team <team>` — deletes a resource and triggers deprovisioning | New `delete` command calling `DELETE /resources/{id}` |
| CLI-04 | `pecp status <kind> <name> --team <team>` — shows provisioning status and notes log | New `status` command with Rich table + notes block below |
| CLI-11 | CLI API base URL configurable via `--api-url` flag, `PECP_API_URL` env var, or `~/.pecp/config.yaml` | URL resolution pattern already established; `--api-url` + env var are the Phase 3 scope |
</phase_requirements>

---

## Summary

Phase 3 wires the existing engine (Dispatcher, adapters, ORM) to the world via REST endpoints and a Typer CLI. The Phase 2 codebase is already mature — the Dispatcher, all adapters, the async session factory, and the walking skeleton route all exist. Phase 3 is primarily additive: extend the `POST /resources` route with idempotency, add three new routes (`GET /resources/{id}`, `POST /resources/{id}/notes`, `DELETE /resources/{id}`), wire `BackgroundTasks`, add two ORM columns and an Alembic migration, and implement three new CLI commands (`get`, `status`, `delete`).

The single most important implementation pitfall in this phase is the **BackgroundTasks session lifetime problem**: the FastAPI `SessionDep` yields a session that closes when the request handler returns. If `dispatch(resource_id, session)` is passed the request-scoped session via `BackgroundTasks`, that session is closed before the background task begins. The fix is to create a fresh `AsyncSession` inside the background task using `AsyncSessionLocal` directly — not to pass the request session.

The second critical item is the **`UniqueConstraint` on `(team, kind, name)`**: the Alembic migration must add this constraint alongside the `env` and `notes` columns, and the route handler must catch `IntegrityError` to handle the race condition window that exists between the lookup and the insert.

**Primary recommendation:** Implement in a single wave — migration first, then API routes (idempotency + new routes), then CLI commands — because the CLI tests depend on the API shape being stable.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Resource submission (YAML → DB) | API / Backend | — | Validation, persistence, dispatch wiring all belong server-side |
| Idempotency logic | API / Backend | — | Server enforces uniqueness; client is unaware of duplicate detection |
| BackgroundTasks dispatch | API / Backend | — | Dispatcher is decoupled from HTTP but called by the API layer |
| Status lifecycle | API / Backend (Dispatcher) | — | Dispatcher exclusively writes status transitions |
| Notes append | API / Backend | — | Server sets author and timestamp; client provides text only |
| CLI commands | CLI Client | — | Thin HTTP wrappers; all logic lives server-side |
| Rich table rendering | CLI Client | — | Presentation only; data comes from API responses |
| URL resolution | CLI Client | — | `--api-url` → `PECP_API_URL` → default already established |
| DB migrations | Database / Storage | — | Alembic manages schema evolution |

---

## Standard Stack

### Core (all already in pyproject.toml — no new installs)

| Library | Version (PyPI current) | Purpose | Why Standard |
|---------|----------------------|---------|--------------|
| `fastapi` | 0.128.8 | REST API framework | Already in use; BackgroundTasks is a first-class FastAPI feature |
| `sqlalchemy` | 2.0.50 | Async ORM | Already in use; `UniqueConstraint` added via `__table_args__` |
| `alembic` | 1.16.5 | DB migrations | Already configured; Phase 2 migration (`0001`) is the template |
| `typer` | 0.23.2 | CLI framework | Already in use; `get`/`status`/`delete` commands follow `apply` pattern |
| `rich` | 15.0.0 | Terminal tables, badges | `console = Console()` already in `cli/main.py`; `Table`, colored `Text` |
| `httpx` | 0.28.1 | CLI HTTP client | Already a dependency; `httpx.get`, `httpx.delete` join `httpx.post` |
| `pydantic` | 2.x (in use) | Schema validation | `model_dump_json()` for spec comparison (D-11) |
| `aiosqlite` | 0.20+ | Async SQLite driver | Already in use; no change |

[VERIFIED: PyPI registry] — versions confirmed via `pip3 index versions` on 2026-06-14.

### No New Packages Required

Phase 3 installs zero new dependencies. All required libraries are already declared in `pyproject.toml`. This is significant — no package legitimacy audit is needed.

---

## Package Legitimacy Audit

**No new packages** are introduced in Phase 3. All libraries used (fastapi, sqlalchemy, alembic, typer, rich, httpx, pydantic, aiosqlite) were vetted in prior phases and are already installed. This section is intentionally empty.

| Package | Action |
|---------|--------|
| (none new) | — |

---

## Architecture Patterns

### System Architecture Diagram

```
CLI (pecp apply/get/status/delete)
        │
        │  HTTP (httpx)
        ▼
FastAPI Route Handlers  (/resources, /resources/{id}, /resources/{id}/notes)
        │                       │
        │  Session (SessionDep) │  BackgroundTasks.add_task(dispatch, id, fresh_session)
        ▼                       ▼
SQLAlchemy AsyncSession      Dispatcher (dispatch.py)
        │                       │
        ▼                       ▼
SQLite (resource_records)   ADAPTER_REGISTRY → MockAdapter.provision()
                                │
                                ▼
                         resource_records (status, provider_metadata, activity_log)
```

**Data flow for `pecp apply`:**
1. CLI reads YAML, POSTs to `/resources?team=X`
2. Route handler validates YAML → Pydantic `ResourceSpec`
3. Uniqueness check: `SELECT WHERE team=? AND kind=? AND name=?`
4. If new: INSERT record with `status=pending`, enqueue `dispatch` via BackgroundTasks
5. If same spec: return existing `id` + current `status` (202, no-op)
6. If changed spec: UPDATE `spec_json`, reset `status=pending`, enqueue `dispatch`
7. Response: `{"id": "...", "status": "pending", "kind": "...", "name": "..."}`
8. BackgroundTask creates a **new** `AsyncSession`, calls `dispatch(resource_id, session)`
9. Dispatcher drives record `pending → provisioning → ready/failed`

### Recommended Project Structure (additions only)

```
src/pecp/
├── api/
│   └── routes/
│       └── resources.py      # MODIFIED: idempotency + 3 new routes
├── cli/
│   └── main.py               # MODIFIED: add get, status, delete commands
├── models/
│   └── resource_spec.py      # MODIFIED: add env to ResourceMetadata
└── persistence/
    └── models.py             # MODIFIED: add env + notes columns + UniqueConstraint

alembic/versions/
└── 0002_add_env_notes_unique.py   # NEW: migration
```

### Pattern 1: BackgroundTasks with Fresh Session

**What:** FastAPI's `BackgroundTasks` runs after the response is sent. The request-scoped session (from `SessionDep`) is closed at that point. The dispatcher must receive a **new** session it owns.

**When to use:** Every time `dispatch()` is enqueued via `BackgroundTasks`.

**Example:**
```python
# Source: FastAPI BackgroundTasks docs + SQLAlchemy async session lifecycle
from fastapi import BackgroundTasks
from pecp.persistence.database import AsyncSessionLocal
from pecp.dispatcher import dispatch

async def _dispatch_with_session(resource_id: str) -> None:
    """Background task wrapper that owns its own session lifetime."""
    async with AsyncSessionLocal() as session:
        await dispatch(resource_id, session)

@router.post("", status_code=202)
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, str]:
    # ... validate, persist ...
    background_tasks.add_task(_dispatch_with_session, resource_id)
    return {"id": resource_id, "status": "pending", ...}
```

[ASSUMED] — BackgroundTasks session lifetime behavior is well-documented in FastAPI community knowledge; the pattern of creating a fresh session inside the task is the canonical solution.

### Pattern 2: Idempotency Query Before Insert

**What:** Check existence by `(team, kind, name)` before deciding to create, skip, or update.

**When to use:** `POST /resources` handler.

**Example:**
```python
# Source: SQLAlchemy 2.x async select pattern (already used in dispatcher.py)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Lookup
result = await session.execute(
    select(ResourceRecord).where(
        ResourceRecord.team == team,
        ResourceRecord.kind == spec.kind,
        ResourceRecord.name == spec.metadata.name,
    )
)
existing = result.scalar_one_or_none()

if existing is None:
    # Create path
    record = ResourceRecord(...)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        # Race condition: concurrent create — re-fetch and return existing
        await session.rollback()
        result = await session.execute(...)
        existing = result.scalar_one()
        return {"id": existing.id, "status": existing.status, ...}
    background_tasks.add_task(_dispatch_with_session, resource_id)

elif existing.spec_json == spec.model_dump_json():
    # No-op path
    return {"id": existing.id, "status": existing.status, ...}

else:
    # Update path
    existing.spec_json = spec.model_dump_json()
    existing.status = "pending"
    if existing.env is not None or spec.metadata.env is not None:
        existing.env = spec.metadata.env
    await session.commit()
    background_tasks.add_task(_dispatch_with_session, existing.id)
    return {"id": existing.id, "status": "pending", ...}
```

[ASSUMED] — Pattern derived from existing dispatcher.py `scalar_one()` usage and SQLAlchemy 2.x async API already in use.

### Pattern 3: Alembic Migration for New Columns + UniqueConstraint

**What:** Add `env` (Text nullable), `notes` (Text nullable, default `"[]"`), and a `UniqueConstraint` on `(team, kind, name)`.

**When to use:** Single migration `0002_add_env_notes_unique.py` following the `0001` template.

**Example:**
```python
# Source: alembic/versions/0001_add_provider_cols.py (existing template)
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"

def upgrade() -> None:
    op.add_column("resource_records", sa.Column("env", sa.Text(), nullable=True))
    op.add_column(
        "resource_records",
        sa.Column("notes", sa.Text(), nullable=True, server_default='[]'),
    )
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.create_unique_constraint(
            "uq_resource_team_kind_name", ["team", "kind", "name"]
        )

def downgrade() -> None:
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.drop_constraint("uq_resource_team_kind_name", type_="unique")
    op.drop_column("resource_records", "notes")
    op.drop_column("resource_records", "env")
```

**Critical:** SQLite requires `batch_alter_table` for adding constraints to existing tables. This is already handled by aiosqlite + alembic if `render_as_batch=True` is set in `env.py`. Check `alembic/env.py` — if `render_as_batch` is not set, add it to `context.configure()`.

[ASSUMED] — batch_alter_table requirement for SQLite is standard Alembic knowledge; confirmed by existing migration pattern.

### Pattern 4: ORM Model Update for UniqueConstraint

**What:** Add `__table_args__` to `ResourceRecord` so mypy and the ORM are aware of the constraint alongside Alembic adding it at the DB level.

**Example:**
```python
# Source: SQLAlchemy 2.x mapped_column docs (existing codebase pattern)
from sqlalchemy import UniqueConstraint

class ResourceRecord(Base):
    __tablename__ = "resource_records"
    __table_args__ = (
        UniqueConstraint("team", "kind", "name", name="uq_resource_team_kind_name"),
    )
    # ... existing columns ...
    env: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
```

[ASSUMED] — SQLAlchemy 2.x `__table_args__` with `UniqueConstraint` is the standard ORM pattern.

### Pattern 5: Notes Append Operation

**What:** Load record, deserialize JSON list, append new note dict, serialize back, commit.

**Example:**
```python
# Source: Existing activity_log pattern in dispatcher.py
import json
from datetime import datetime, timezone

@router.post("/{resource_id}/notes", status_code=201)
async def add_note(
    resource_id: str,
    body: dict[str, str],  # {"text": "..."}
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, list[dict[str, str]]]:
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    current_notes: list[dict[str, str]] = json.loads(record.notes or "[]")
    current_notes.append({
        "author": ctx.user_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "text": body["text"],
    })
    record.notes = json.dumps(current_notes)
    await session.commit()
    return {"notes": current_notes}
```

[ASSUMED] — Pattern mirrors existing `activity_log` JSON text column usage in dispatcher.py.

### Pattern 6: Rich Table with Status Badges

**What:** Colored status badges in `pecp get` and `pecp status` output.

**Example:**
```python
# Source: Existing console = Console() in src/pecp/cli/main.py
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()

STATUS_COLORS = {
    "pending": "yellow",
    "provisioning": "blue",
    "ready": "green",
    "failed": "red",
}

def status_badge(status: str) -> Text:
    color = STATUS_COLORS.get(status, "white")
    return Text(status, style=f"bold {color}")

# pecp get usage:
table = Table(title=f"Resources ({kind}) — team: {team}")
table.add_column("Name")
table.add_column("Kind")
table.add_column("Status")
table.add_column("Env")

for r in resources:
    table.add_row(
        r["name"],
        r["kind"],
        status_badge(r["status"]),
        r.get("env") or "—",
    )
console.print(table)
```

[ASSUMED] — Rich Table and Text API is stable; pattern derived from Rich docs and existing `console.print` usage in cli/main.py.

### Pattern 7: CLI `get`, `status`, `delete` Commands

**What:** Three new Typer commands following the existing `apply` pattern (URL resolution, httpx call, Rich output).

**URL resolution (already established, must be consistent):**
```python
base = api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"
base = base.rstrip("/")
```

**`pecp get <kind> --team <team>`:**
- GET `/resources?team={team}&kind={kind}` — the existing list endpoint already accepts `team`; add optional `kind` filter server-side, OR filter client-side from the full list.
- Decision: filter server-side (add `kind` query param to `GET /resources`) — keeps CLI thin.

**`pecp delete <kind> <name> --team <team>`:**
1. GET `/resources?team={team}` to find resource `id` by `kind + name`
2. DELETE `/resources/{id}`
3. Print `Deleted {kind} {name}` or error

**`pecp status <kind> <name> --team <team>`:**
1. GET `/resources?team={team}` to find resource `id`
2. GET `/resources/{id}` for full detail including notes
3. Print Rich table (id, kind, name, status, env, created_at)
4. If notes: print timestamped block below table

[ASSUMED] — Typer and httpx patterns derived from existing cli/main.py; no new API behavior.

### Anti-Patterns to Avoid

- **Passing `session` from `SessionDep` into `BackgroundTasks`:** The session closes when the request handler returns. The background task receives a closed session and all DB operations silently fail or raise `MissingGreenlet`. Always create a fresh `async with AsyncSessionLocal() as session:` inside the wrapper function.
- **Using `yaml.load()` instead of `yaml.safe_load()`:** Already enforced (T-01-01); `yaml.load` allows arbitrary Python object instantiation. Never introduce it.
- **Placing idempotency logic after `session.add()` but before `session.commit()`:** The uniqueness check must happen with a SELECT before the insert. Checking after the add but before commit does not protect against concurrent requests.
- **Mutating `ResourceRecord.status` outside the Dispatcher:** Only the Dispatcher writes status after initial creation. The exception: the route handler sets `status="pending"` on create and on spec-changed-update — this is the correct initial state that the Dispatcher then advances.
- **Filtering by `kind` in `GET /resources` client-side only:** If a team has many resources, returning all and filtering in the CLI leaks unnecessary data. Add `kind` as an optional query param to the list route.
- **Storing notes as a separate table:** D-03 locks notes as a JSON text column on `ResourceRecord`. A separate table adds complexity with no benefit at PoC scale.
- **`batch_alter_table` omission for SQLite constraints:** SQLite does not support `ALTER TABLE ADD CONSTRAINT` natively. Without `batch_alter_table`, the Alembic migration will raise an `OperationalError` when run against SQLite.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Spec comparison / content hashing | Custom hash function or field diff | `model_dump_json()` string compare | Pydantic's serialization is deterministic for the same input; no custom logic needed |
| JSON append for notes | Custom parser or update-in-place SQL | Load with `json.loads`, append in Python, write back with `json.dumps` | Matches existing `activity_log` pattern; SQLite has no native JSON append |
| Rich table coloring | Custom ANSI escape strings | `rich.text.Text(status, style=f"bold {color}")` | Rich handles terminal capability detection and style application |
| HTTP session management in CLI | Connection pooling or session reuse | `httpx.get()` / `httpx.post()` / `httpx.delete()` per call | PoC with low request frequency; per-call httpx is sufficient |
| Unique ID generation | UUID v1, timestamp-based | `uuid.uuid4().hex` | Already established in existing `create_resource`; consistent |
| Background job queue | asyncio.Queue, threading | FastAPI `BackgroundTasks` | All adapters are mock; no durability needed; BackgroundTasks is sufficient for PoC |

**Key insight:** The hard problems (idempotency, background dispatch, schema evolution) all have zero-surprise solutions in the existing stack. The implementation risk is in session lifetime management, not algorithmic complexity.

---

## Common Pitfalls

### Pitfall 1: BackgroundTasks Session Lifetime (CRITICAL)

**What goes wrong:** `dispatch()` is enqueued with the request-scoped session. The session closes when `create_resource()` returns (before the background task runs). The dispatcher executes against a closed connection and raises `MissingGreenlet` or `sqlalchemy.exc.InvalidRequestError`.

**Why it happens:** FastAPI's `SessionDep` uses `async with AsyncSessionLocal() as session: yield session` — the context manager closes the session on generator cleanup, which happens at end-of-request, not end-of-background-task.

**How to avoid:** Create a `_dispatch_with_session(resource_id: str)` wrapper function that opens its own `async with AsyncSessionLocal() as session:` block. Pass this wrapper (not `dispatch`) to `background_tasks.add_task()`. Never pass the request session to BackgroundTasks.

**Warning signs:** `MissingGreenlet`, `sqlalchemy.exc.InvalidRequestError: This session is provisioning...`, or background tasks that silently never update resource status.

### Pitfall 2: SQLite UniqueConstraint Requires batch_alter_table

**What goes wrong:** `op.create_unique_constraint()` without `batch_alter_table` raises `OperationalError: Cannot add a UNIQUE constraint to a table that has existing data` or simply `OperationalError: near "CONSTRAINT": syntax error` on SQLite.

**Why it happens:** SQLite's ALTER TABLE does not support adding constraints. Alembic's batch mode works around this by creating a new table, copying data, and dropping the old one.

**How to avoid:** In the migration, always use `with op.batch_alter_table("resource_records") as batch_op: batch_op.create_unique_constraint(...)`. Also ensure `alembic/env.py` passes `render_as_batch=True` to `context.configure()` — check this before writing the migration.

**Warning signs:** `OperationalError` during `alembic upgrade head` on SQLite. Works on PostgreSQL but fails locally.

### Pitfall 3: `model_dump_json()` Ordering Non-Determinism

**What goes wrong:** Two identical specs compare as different because `model_dump_json()` produces keys in different orders between Pydantic versions or Python dict insertion orders change.

**Why it happens:** Pydantic v2 `model_dump_json()` is documented as deterministic for the same model instance, but dict fields in `config: dict[str, Any]` (used by Salesforce, AEM, Kubernetes kinds) are order-dependent.

**How to avoid:** For Phase 3, the only kinds with freeform `config` dicts are the non-Lambda/Container/DataService kinds. For those, `model_dump_json()` comparison will work correctly as long as users don't reorder keys in their YAML between applies. This is acceptable for PoC. Document the limitation in a comment.

**Warning signs:** Re-apply of an identical Salesforce/AEM/Kubernetes spec triggers an update instead of a no-op.

### Pitfall 4: `pecp delete` Requires ID Lookup

**What goes wrong:** CLI passes `(kind, name, team)` but `DELETE /resources/{id}` requires an ID. If the CLI calls DELETE with a made-up path, it gets 404 or 422.

**Why it happens:** The CLI exposes human-friendly `(kind, name, team)` but the API uses opaque IDs.

**How to avoid:** The `delete` command must first call `GET /resources?team={team}` (optionally filtered by `kind`), find the record matching `name + kind`, extract the `id`, then call `DELETE /resources/{id}`. Consider adding `kind` as a filter param to the list endpoint to avoid scanning all resources.

**Warning signs:** `pecp delete` getting 404 because it constructs a wrong ID, or deleting the wrong resource if name matching is too loose.

### Pitfall 5: Notes Body Schema Validation

**What goes wrong:** `POST /resources/{id}/notes` receives a body that is not `{"text": "..."}`. FastAPI's default `dict[str, str]` type hint accepts anything with string values; missing `text` key raises a `KeyError` at runtime rather than a clean 422.

**How to avoid:** Define a `NoteCreate(BaseModel)` Pydantic model with `text: str` and use it as the request body type. FastAPI will then return 422 with field-level errors for missing or wrong-typed fields.

**Warning signs:** `KeyError: 'text'` in route handler logs; 500 instead of 422 on bad note body.

### Pitfall 6: `alembic upgrade head` Not Run Before Tests

**What goes wrong:** Tests that use `init_schema()` (which calls `Base.metadata.create_all`) will pick up the new ORM columns because they create tables from the current model state. But integration tests against `pecp.db` (the local dev database) may fail if Alembic migration hasn't been applied — the `env` and `notes` columns won't exist.

**How to avoid:** Add a Wave 0 task that runs `alembic upgrade head` before any implementation. The test suite already uses `create_all` which bypasses Alembic (as established in `conftest.py`); this is correct and intentional for tests. The dev database needs the migration applied separately.

---

## Runtime State Inventory

Phase 3 is not a rename/refactor phase. This section is omitted.

---

## Code Examples

### GET /resources/{id} Route

```python
# Source: Existing GET /resources pattern in src/pecp/api/routes/resources.py
import json

@router.get("/{resource_id}")
async def get_resource(
    resource_id: str,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict:
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {
        "id": record.id,
        "team": record.team,
        "kind": record.kind,
        "name": record.name,
        "status": record.status,
        "env": record.env,
        "created_at": record.created_at.isoformat(),
        "provider_metadata": json.loads(record.provider_metadata or "{}"),
        "activity_log": json.loads(record.activity_log or "[]"),
        "notes": json.loads(record.notes or "[]"),
    }
```

### DELETE /resources/{id} Route

```python
@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> None:
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    await session.delete(record)
    await session.commit()
```

### `pecp status` CLI Command

```python
@app.command("status")
def status(
    kind: str = typer.Argument(help="Resource kind (e.g. PECPLambda)"),
    name: str = typer.Argument(help="Resource name"),
    team: str = typer.Option(..., "--team", help="Team that owns the resource"),
    api_url: str | None = typer.Option(None, "--api-url"),
) -> None:
    base = api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"
    base = base.rstrip("/")

    # Step 1: find the resource id
    try:
        list_resp = httpx.get(f"{base}/resources", params={"team": team, "kind": kind})
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    resources = [r for r in list_resp.json() if r["name"] == name and r["kind"] == kind]
    if not resources:
        console.print(f"[red]Not found[/red]: {kind} {name} in team {team}")
        raise typer.Exit(code=1)

    resource_id = resources[0]["id"]

    # Step 2: get full detail
    detail_resp = httpx.get(f"{base}/resources/{resource_id}")
    data = detail_resp.json()

    # Step 3: render status table
    table = Table(title=f"{kind}: {name}")
    table.add_column("Field")
    table.add_column("Value")
    for field in ["id", "kind", "name", "status", "env", "created_at"]:
        value = str(data.get(field) or "—")
        if field == "status":
            value = status_badge(value)
        table.add_row(field, value)
    console.print(table)

    # Step 4: render notes block if present
    notes = data.get("notes", [])
    if notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in notes:
            console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery for background jobs | FastAPI BackgroundTasks (PoC) → ARQ (post-PoC) | PECP design decision | Simpler PoC; no broker needed |
| Sync Flask routes | Async FastAPI handlers | Project inception | Enables `await` throughout; no event loop conflicts |
| `yaml.load()` | `yaml.safe_load()` | Standard security practice | Eliminates arbitrary code execution vector |
| SQLAlchemy 1.x `Session.query()` | SQLAlchemy 2.x `select()` + `session.execute()` | SQLAlchemy 2.0 (2023) | Already in use in this codebase |

**Deprecated/outdated in this project's context:**
- `SQLModel`: excluded in CLAUDE.md — Pydantic v2 + SQLAlchemy 2.x async has documented rough edges.
- `Marshmallow`/`Cerberus`: pre-Pydantic; excluded.
- `Flask`/`Quart`: sync-first; excluded.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ with pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` — `asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_api/ -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CTRL-01 | `POST /resources` returns 202 with resource ID | integration | `pytest tests/test_api/test_routes.py -x -q` | ✅ (extend existing) |
| CTRL-03 | Same-spec re-apply returns existing ID, no duplicate | integration | `pytest tests/test_api/test_idempotency.py -x -q` | ❌ Wave 0 |
| CTRL-03 | Changed-spec re-apply updates spec_json, re-dispatches | integration | `pytest tests/test_api/test_idempotency.py -x -q` | ❌ Wave 0 |
| CTRL-04 | `POST /resources/{id}/notes` appends note, returns 201 with full list | integration | `pytest tests/test_api/test_notes.py -x -q` | ❌ Wave 0 |
| CTRL-04 | Notes appear in `GET /resources/{id}` response | integration | `pytest tests/test_api/test_routes.py -x -q` | ❌ Wave 0 (extend) |
| CLI-01 | `pecp apply` displays correct output for create vs no-op | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ✅ (extend existing) |
| CLI-02 | `pecp get PECPLambda --team X` outputs Rich table | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 |
| CLI-03 | `pecp delete` calls DELETE on correct resource ID | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 |
| CLI-04 | `pecp status` renders table + notes block | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 |
| CLI-11 | URL resolution: flag → env var → default | unit | `pytest tests/test_api/test_cli.py -x -q` | ✅ (already tested for apply) |
| CTRL-02 | BackgroundTasks dispatch transitions status | integration | `pytest tests/test_api/test_dispatch_wiring.py -x -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_api/ -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_api/test_idempotency.py` — covers CTRL-03 (no-op and update paths)
- [ ] `tests/test_api/test_notes.py` — covers CTRL-04 (append note, return 201)
- [ ] `tests/test_api/test_dispatch_wiring.py` — covers CTRL-02 (BackgroundTasks triggers dispatch, status transitions)
- [ ] Extend `tests/test_api/test_routes.py` — add `GET /resources/{id}` and `DELETE /resources/{id}` test cases
- [ ] Extend `tests/test_api/test_cli.py` — add `get`, `status`, `delete` command test cases

---

## Security Domain

`security_enforcement` is enabled (absent = enabled), `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Auth is stubbed for PoC; `RequestContext` is the hook |
| V3 Session Management | No | No user sessions in PoC; stateless API |
| V4 Access Control | Partial | Team scoping enforced at route level (ARCH-01 already passing); `ctx.is_pe_admin` not enforced for notes in PoC |
| V5 Input Validation | Yes | Pydantic v2 validates all YAML specs; `NoteCreate` model validates notes body; `yaml.safe_load` exclusively |
| V6 Cryptography | No | No secrets, tokens, or sensitive data in PoC |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML injection via `yaml.load()` | Tampering | `yaml.safe_load()` — already enforced (T-01-01) |
| Missing `team` param → data leak across teams | Information Disclosure | 400 check already in GET/POST; extend to new routes |
| Notes body without `text` key → 500 | Denial of Service | `NoteCreate(BaseModel)` with `text: str` required |
| Arbitrary resource_id in DELETE → delete other team's resource | Tampering | In PoC: no cross-team check since team is not embedded in the ID. Mitigation: after fetching by ID, verify `record.team == team` (add `team` as a query param to DELETE route) |
| SQL injection via ORM | Tampering | SQLAlchemy parameterized queries — already in use |

**ASVS Level 1 note:** The team-ownership check on `DELETE /resources/{id}` is the one new security control this phase must add. Without it, a caller who knows a resource ID can delete resources they don't own. For PoC, the fix is cheap: add `team` query param to DELETE route and verify `record.team == team` before deleting.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 (system) | Project runtime | ✓ | 3.9.6 (system) | Project may use a virtualenv |
| pip3 | Package management | ✓ | Available | — |
| SQLite | Database | ✓ | Built into Python | — |
| FastAPI (installed) | API server | Confirmed in pyproject.toml | ≥0.136 declared | — |
| All declared deps | All features | Confirmed in pyproject.toml | — | — |

**Note:** System Python is 3.9.6 but `pyproject.toml` requires `python>=3.12`. The project must be run in a virtualenv with Python 3.12+. This is pre-existing — not a Phase 3 concern.

**Missing dependencies with no fallback:** None.

---

## Open Questions (RESOLVED)

1. **`render_as_batch` in alembic/env.py**
   - What we know: The existing `env.py` uses `context.configure(connection=connection, target_metadata=target_metadata)` without `render_as_batch=True`.
   - What's unclear: Whether the existing `0001` migration ran successfully without it (it only added columns, not constraints). Adding a `UniqueConstraint` in `0002` without `render_as_batch=True` will fail on SQLite.
   - Recommendation: The migration plan must add `render_as_batch=True` to `context.configure()` in `alembic/env.py` as a Wave 0 task, before writing the `0002` migration. This is a one-line change.
   - **RESOLVED:** Plan 03-01 Task 2 adds `render_as_batch=True` to `alembic/env.py` `context.configure()` before the `0002` migration is written.

2. **`kind` filter on `GET /resources`**
   - What we know: Existing `GET /resources` only filters by `team`. The `pecp delete` and `pecp status` commands need to find a resource by `(kind, name, team)`.
   - What's unclear: Whether to add `kind` as a query param to the existing list route or do client-side filtering.
   - Recommendation: Add optional `kind: str | None = None` query param to `list_resources`. Filter with `ResourceRecord.kind == kind` when provided. This is the server-side approach (D-02 precedent for direct column filtering).
   - **RESOLVED:** Plan 03-02 Task 1 adds `kind: str | None = Query(None)` to `list_resources` with server-side filtering.

3. **`GET /resources/{id}` response shape for CLI**
   - What we know: `pecp status` needs `env`, `created_at`, `notes`, and optionally `provider_metadata` / `activity_log`.
   - What's unclear: Whether the status endpoint should include `provider_metadata` and `activity_log` in the response — these are useful for debugging but noisy in normal output.
   - Recommendation: Include all fields in `GET /resources/{id}` response. The CLI can selectively render only the fields it needs. API consumers always have full information.
   - **RESOLVED:** Plan 03-02 Task 2 returns all fields (`id`, `team`, `kind`, `name`, `status`, `env`, `created_at`, `provider_metadata`, `activity_log`, `notes`); CLI renders a subset.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BackgroundTasks session must be a fresh session, not the request session | Pitfall 1, Pattern 1 | Critical: dispatching with a closed session silently fails or crashes |
| A2 | SQLite requires `batch_alter_table` for `UniqueConstraint` on existing table | Pitfall 2, Pattern 3 | High: migration fails at `alembic upgrade head` |
| A3 | `model_dump_json()` is deterministic for same-input Pydantic v2 models | Pattern 2 | Medium: freeform `config` dict specs may trigger false updates |
| A4 | `render_as_batch=True` is required in `alembic/env.py` for the constraint migration | Open Questions | High: `0002` migration will fail without it |
| A5 | `pecp delete` should verify `record.team == team` for security | Security Domain | Medium: cross-team delete possible in PoC without this check |

---

## Sources

### Primary (HIGH confidence)
- Existing codebase — read directly: `src/pecp/api/routes/resources.py`, `src/pecp/cli/main.py`, `src/pecp/persistence/models.py`, `src/pecp/dispatcher.py`, `alembic/versions/0001_add_provider_cols.py`, `tests/conftest.py`
- `pip3 index versions` — confirmed FastAPI 0.128.8, SQLAlchemy 2.0.50, Alembic 1.16.5, Typer 0.23.2, Rich 15.0.0, httpx 0.28.1 on 2026-06-14

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions D-01 through D-12 — locked user decisions consumed verbatim
- Phase 2 CONTEXT.md — confirmed Dispatcher signature stability requirement (D-03)

### Tertiary (LOW confidence / ASSUMED)
- BackgroundTasks session lifetime pattern (A1) — standard FastAPI community knowledge
- SQLite `batch_alter_table` requirement (A2, A4) — standard Alembic knowledge for SQLite
- Pydantic `model_dump_json()` determinism (A3) — documented in Pydantic v2 release notes

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed and in use; versions confirmed from PyPI
- Architecture: HIGH — existing codebase provides all patterns; Phase 3 is additive
- Pitfalls: MEDIUM — session lifetime and SQLite constraint issues are well-known; exact behavior in this project's Alembic configuration needs verification at implementation time
- Security: HIGH — ASVS Level 1 requirements are minimal and straightforward for this PoC

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable stack; no fast-moving dependencies)

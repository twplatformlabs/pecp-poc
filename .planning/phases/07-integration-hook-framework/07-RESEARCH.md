# Phase 7: Integration Hook Framework - Research

**Researched:** 2026-06-24
**Domain:** Python ABC, FastAPI BackgroundTasks, pydantic-settings env validation
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTG-01 | `IntegrationBase` ABC defines lifecycle hooks: `on_team_create(team)`, `on_project_create(project, team)`, `on_member_add(user, team)`, `on_member_remove(user, team)` — all async, all optional (default no-op) | Section: Standard Stack, Architecture Patterns, Code Examples |
| INTG-02 | `INTEGRATION_REGISTRY` (list of `IntegrationBase` instances) is consulted by team/project/member service layer after successful DB writes — integrations are fired in registration order, errors logged but non-fatal to the primary operation | Section: Architecture Patterns, Don't Hand-Roll, Common Pitfalls |
| INTG-03 | Integration configuration is loaded from environment variables at startup — missing config disables the integration with a logged warning, does not crash the server | Section: Standard Stack (pydantic-settings), Code Examples |
</phase_requirements>

---

## Summary

Phase 7 introduces the integration hook framework — a `IntegrationBase` ABC and `INTEGRATION_REGISTRY` dispatcher that mirrors the existing `AdapterBase` / `ADAPTER_REGISTRY` pattern already established in `src/pecp/adapters/`. The pattern is straightforward: define an ABC with async lifecycle hooks that default to no-ops, register instances in a list, and fire them sequentially inside a `BackgroundTasks` function that runs after `session.commit()`.

The critical invariant is **commit-before-hook**: hooks must fire after the DB row is durably written. This is enforced by wiring the `BackgroundTasks` function to the route handler only after `await session.commit()` completes. The hook runner must receive a **data snapshot** (plain dataclass or dict) rather than the ORM object itself — the request-scoped `AsyncSession` will be closed by the time the background task executes, causing `DetachedInstanceError` if code tries to access lazy-loaded attributes on the ORM object.

Phase 7 deliberately introduces no GitHub API code. It produces: (1) `src/pecp/integrations/base.py` (ABC), (2) `src/pecp/integrations/__init__.py` (INTEGRATION_REGISTRY, dispatch helper), (3) a `NoOpIntegration` for test use, and (4) a startup warning when `GITHUB_PAT`/`GITHUB_ORG` are absent. All existing 166 tests must continue to pass; new tests must verify the four success criteria in the ROADMAP.

**Primary recommendation:** Mirror `AdapterBase`/`ADAPTER_REGISTRY`/`dispatcher.py` exactly. Use `logging.getLogger(__name__)` for hook failure logging. Use `pydantic-settings` `BaseSettings` for env-var config with `model_config = SettingsConfigDict(env_prefix="", extra="ignore")`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| IntegrationBase ABC definition | API / Backend | — | Pure Python contract; no HTTP or DB involvement |
| INTEGRATION_REGISTRY dispatch | API / Backend | — | Lives in `pecp/integrations/__init__.py`; consulted by route handlers |
| Hook invocation timing (after commit) | API / Backend | — | BackgroundTasks added to route handlers after `session.commit()` |
| Env-var config (PAT/ORG) | API / Backend | — | pydantic-settings loaded at startup in lifespan or module init |
| Hook isolation (error non-fatal) | API / Backend | — | try/except wrapping each integration call in the dispatcher |
| Data snapshot passing | API / Backend | — | Snapshot built before session closes; prevents DetachedInstanceError |

---

## Standard Stack

### Core (all already installed — zero new packages)

| Library | Version in pyproject.toml | Purpose | Why Standard |
|---------|--------------------------|---------|--------------|
| `fastapi` | `>=0.136` | BackgroundTasks mechanism for post-commit hook invocation | Already used in resources.py for dispatch |
| `sqlalchemy` | `>=2.0` | Async session whose `commit()` is the trigger point | Already used everywhere |
| `pydantic` | `>=2.13` | BaseModel for typed data snapshots passed to hooks | Already used everywhere |
| `python` `abc` stdlib | N/A (stdlib) | ABC + abstractmethod decorators for IntegrationBase | Zero overhead; matches AdapterBase pattern exactly |
| `logging` stdlib | N/A (stdlib) | `logging.getLogger(__name__)` for hook failure warning | Project has no custom logging infra; stdlib sufficient |

### New Package Required: pydantic-settings

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic-settings` | `~2.14` (locked in STATE.md decisions) | Env-var validation at startup — `BaseSettings` class reads GITHUB_PAT/GITHUB_ORG, logs warning on absence | Official Pydantic project; standard FastAPI pattern; prevents silent misconfiguration |

`pydantic-settings` is NOT yet in `pyproject.toml` and must be added in this phase. [ASSUMED — version ~2.14 is from STATE.md, confirmed reasonable based on pydantic v2 compatibility requirements]

### New Package Required: pytest-httpx (dev)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest-httpx` | `~0.36` (locked in STATE.md decisions) | Mock httpx HTTP calls in Phase 8 GitHub integration tests | Needed from Phase 8; can be added now per STATE.md decision |

STATE.md explicitly names both `pydantic-settings ~2.14` and `pytest-httpx ~0.36` as additions locked in the v1.1 roadmap planning. [ASSUMED — version pinning from STATE.md, not independently verified against PyPI this session]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pydantic-settings BaseSettings` | `os.getenv()` + manual validation | pydantic-settings gives typed validation and a clear startup error log vs. scattered `os.getenv` calls; aligns with PROJECT.md tech stack |
| `BackgroundTasks` (post-commit) | `asyncio.create_task` inside route handler | BackgroundTasks is FastAPI-managed; lifecycle is tied to the response, not a floating coroutine; matches existing pattern in resources.py |
| List-based INTEGRATION_REGISTRY | Dict-based (like ADAPTER_REGISTRY) | Integrations fire on every event regardless of kind (not dispatched by resource kind), so a plain list ordered by registration is semantically correct and simpler |

**Installation:**
```bash
pip install "pydantic-settings~=2.14"
pip install "pytest-httpx~=0.36"
```

Add to `pyproject.toml`:
```toml
# In [project] dependencies:
"pydantic-settings>=2.14",

# In [project.optional-dependencies] dev:
"pytest-httpx>=0.36",
```

---

## Package Legitimacy Audit

> Both packages are referenced by name in official Pydantic/FastAPI documentation and are well-established in the Python ecosystem.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `pydantic-settings` | PyPI | ~3 yrs (since Pydantic v2 split) | 10M+/wk [ASSUMED] | github.com/pydantic/pydantic-settings | OK | Approved |
| `pytest-httpx` | PyPI | ~5 yrs | 500K+/wk [ASSUMED] | github.com/Colin-b/pytest-httpx | OK | Approved |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Both packages are official sub-projects or widely-adopted companions to libraries already in use (`pydantic`, `httpx`). Version numbers from STATE.md are [ASSUMED]; executor must run `pip index versions pydantic-settings` and `pip index versions pytest-httpx` before pinning.*

---

## Architecture Patterns

### System Architecture Diagram

```
POST /teams (route handler)
    │
    ├── session.add(TeamRecord)
    ├── await session.commit()          ← DB row exists HERE
    │
    ├── snapshot = TeamSnapshot(id=team.id, name=team.name, ...)
    │
    └── background_tasks.add_task(
            fire_integrations,          ← BackgroundTask added AFTER commit
            "on_team_create",
            snapshot
        )
            │
            └── for integration in INTEGRATION_REGISTRY:
                    try:
                        await integration.on_team_create(snapshot)
                    except Exception:
                        logger.warning("Integration hook failed: ...")
                        # primary operation already succeeded — error is non-fatal
```

### Recommended Project Structure

```
src/pecp/
├── integrations/
│   ├── __init__.py      # INTEGRATION_REGISTRY list + fire_integrations() dispatcher
│   ├── base.py          # IntegrationBase ABC + snapshot dataclasses
│   └── noop.py          # NoOpIntegration (for tests and as a reference impl)
```

Phase 8 will add `github.py` to this directory. No other changes needed to the directory structure.

### Pattern 1: IntegrationBase ABC (mirrors AdapterBase)

**What:** Abstract base class with async lifecycle hooks, all optional (default no-op).
**When to use:** Every integration class inherits from this. The default `pass` implementation means partial implementations are safe.

```python
# Source: mirrors src/pecp/adapters/base.py (VERIFIED: codebase)
from abc import ABC
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TeamSnapshot:
    """Data snapshot passed to on_team_create hooks (avoids DetachedInstanceError)."""
    id: str
    name: str
    owner_id: str
    created_at: datetime
    github_team_slug: str | None = None


@dataclass
class ProjectSnapshot:
    id: str
    name: str
    team_id: str
    environments: list[str]
    created_at: datetime


@dataclass
class MemberSnapshot:
    user_id: str
    role: str


class IntegrationBase(ABC):
    """Contract for all PECP lifecycle integrations (INTG-01).

    All hooks are optional — default implementations are no-ops.
    Errors MUST NOT propagate to callers; the dispatcher wraps each call.
    """

    async def on_team_create(self, team: TeamSnapshot) -> None:
        pass

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass
```

### Pattern 2: INTEGRATION_REGISTRY and fire_integrations dispatcher

**What:** Module-level list; `fire_integrations` fires all registered hooks in order, catching and logging errors per integration.
**When to use:** Called from BackgroundTasks functions added to route handlers after `session.commit()`.

```python
# Source: mirrors src/pecp/dispatcher.py ADAPTER_REGISTRY pattern (VERIFIED: codebase)
import logging
from typing import Any

logger = logging.getLogger(__name__)

INTEGRATION_REGISTRY: list[IntegrationBase] = []


async def fire_integrations(hook_name: str, *args: Any) -> None:
    """Fire all registered integrations for the named lifecycle hook.

    Errors in individual integrations are caught and logged — they never
    propagate to the caller (INTG-02). Fired in INTEGRATION_REGISTRY order.
    """
    for integration in INTEGRATION_REGISTRY:
        hook = getattr(integration, hook_name, None)
        if hook is not None:
            try:
                await hook(*args)
            except Exception:
                logger.warning(
                    "Integration hook %s.%s failed",
                    type(integration).__name__,
                    hook_name,
                    exc_info=True,
                )
```

### Pattern 3: Commit-before-hook wiring in route handler

**What:** BackgroundTasks is added after `await session.commit()` — never before.
**When to use:** Every route handler that creates a team, project, or member.

```python
# Source: mirrors resources.py BackgroundTasks pattern (VERIFIED: codebase)
# In POST /teams route handler:
session.add(team)
session.add(member)
try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise HTTPException(status_code=409, ...)

# snapshot built AFTER commit — ORM object is safe to read here (still in session scope)
snapshot = TeamSnapshot(
    id=team.id,
    name=team.name,
    owner_id=team.owner_id,
    created_at=team.created_at,
    github_team_slug=team.github_team_slug,
)
# BackgroundTask added AFTER commit — this is the critical invariant
background_tasks.add_task(fire_integrations, "on_team_create", snapshot)
```

### Pattern 4: pydantic-settings env config with startup warning

**What:** `BaseSettings` subclass reads env vars; missing required vars trigger a logged warning, not a crash. The integration self-disables when config is absent.
**When to use:** `IntegrationConfig` is loaded once at module import time (or in lifespan).

```python
# Source: pydantic-settings docs pattern [ASSUMED — standard BaseSettings usage]
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    GITHUB_PAT: str = ""
    GITHUB_ORG: str = ""


def load_and_register_integrations() -> None:
    """Load integration config and populate INTEGRATION_REGISTRY.

    Called from FastAPI lifespan. Missing config logs a warning and
    skips registration — server starts normally (INTG-03).
    """
    import logging
    logger = logging.getLogger(__name__)
    cfg = IntegrationConfig()
    if not cfg.GITHUB_PAT or not cfg.GITHUB_ORG:
        logger.warning(
            "GITHUB_PAT or GITHUB_ORG not set — GitHub integration disabled"
        )
        # Do not register GitHubIntegration — INTEGRATION_REGISTRY stays empty
        return
    # Phase 8 will add: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

### Anti-Patterns to Avoid

- **Passing ORM objects to background tasks:** The request-scoped `AsyncSession` is closed before the background task runs. Access `team.id`, `team.name`, etc. inside the route handler (while the session is still open) and pass a dataclass snapshot. Never pass `TeamRecord` directly. [VERIFIED: codebase — same pattern used in resources.py `_dispatch_with_session`]
- **Raising exceptions from hook failures:** Hook errors must be caught inside `fire_integrations`. If they propagate, a failing GitHub integration would roll back a successful team creation — catastrophic UX regression.
- **Using `ABC` + `@abstractmethod` on lifecycle hooks:** Hooks must NOT be abstract. Making them abstract forces every integration to implement all hooks, breaking the "optional" contract (INTG-01). Use `ABC` for the class but plain `async def hook(...) -> None: pass` for each method.
- **Running hooks before commit:** If hooks fire before `session.commit()`, a hook failure could prevent the DB write from being reached, and a hook success (e.g., GitHub team created) leaves a ghost resource with no PECP record. Commit always happens first.
- **Registering GitHubIntegration when PAT is missing:** Registering it but having it fail silently on every call is worse than not registering it — it generates log noise. The startup check should conditionally register only when both PAT and ORG are present.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var validation at startup | Custom `os.getenv()` chains + manual `if not val: raise` | `pydantic-settings BaseSettings` | Type coercion, `.env` file support, missing-var detection in one class |
| Hook error isolation | Manual try/except in every route handler | Centralized `fire_integrations()` dispatcher | Keeps route handlers clean; all error logging in one place |
| Data snapshot passing | Custom dict serialization | `@dataclass` with typed fields | Dataclasses are zero-overhead, self-documenting, and support type checking via mypy |
| Background task session management | Accessing ORM objects in background task | Build snapshot before background task is added | Matches the established pattern in `_dispatch_with_session` in resources.py |

**Key insight:** This phase is almost entirely structural — it defines contracts and wiring, not algorithms. The primary complexity is ensuring the commit-before-hook invariant holds in all code paths (including the IntegrityError rollback path, where no hook must fire).

---

## Common Pitfalls

### Pitfall 1: DetachedInstanceError in background task
**What goes wrong:** Background task tries to access `team.github_team_slug` after request session is closed — SQLAlchemy raises `DetachedInstanceError`.
**Why it happens:** FastAPI's `get_session` dependency closes `AsyncSession` when the request completes. Background tasks run after response is sent.
**How to avoid:** Build the `TeamSnapshot` dataclass inside the route handler, after `session.commit()` but before the function returns. Pass the snapshot (not the ORM object) to `background_tasks.add_task`.
**Warning signs:** `MissingGreenlet` or `DetachedInstanceError` in test output; hooks that appear to do nothing silently.

### Pitfall 2: Hook fires when IntegrityError triggers rollback
**What goes wrong:** Route handler catches IntegrityError (duplicate team name), rolls back — but the `background_tasks.add_task(fire_integrations, ...)` call was already made.
**Why it happens:** If `add_task` is called before the `try/except IntegrityError` block, FastAPI still executes the background task even though the commit failed.
**How to avoid:** Structure the route handler so `background_tasks.add_task` is only called in the success path (after the `try` block, not inside it). In the existing `create_team` route, the `raise HTTPException(409)` exits the function immediately, so any `add_task` call after the `try` block is never reached on error. Keep this structure.
**Warning signs:** Ghost GitHub teams created for team names that return 409.

### Pitfall 3: Missing GITHUB_PAT crashes server
**What goes wrong:** `IntegrationConfig()` raises `ValidationError` at import time because `GITHUB_PAT` is declared as a required `str` field with no default.
**Why it happens:** pydantic-settings raises on missing required fields, just like Pydantic BaseModel.
**How to avoid:** Declare `GITHUB_PAT: str = ""` and `GITHUB_ORG: str = ""` with empty-string defaults. Check `if not cfg.GITHUB_PAT` in `load_and_register_integrations()`. This allows the server to start, logs a warning, and leaves INTEGRATION_REGISTRY empty.
**Warning signs:** `ValidationError: 1 validation error for IntegrationConfig` on server startup.

### Pitfall 4: AsyncSession module reference pattern
**What goes wrong:** Tests that reload `pecp.persistence.database` do not see the updated `AsyncSessionLocal` if the background task function captured it at import time via `from pecp.persistence.database import AsyncSessionLocal`.
**Why it happens:** Python's import system caches the reference at import time; reloading the module does not update already-bound names.
**How to avoid:** Access `AsyncSessionLocal` via the module reference (`import pecp.persistence.database as _db; _db.AsyncSessionLocal()`). This pattern is already established in `resources.py` (`import pecp.persistence.database as _db`). The integration dispatcher does not open sessions itself (it receives snapshots, not session objects) so this pitfall is limited to Phase 9 wiring when hooks need DB access.
**Warning signs:** `fire_integrations` background task opens the wrong in-memory test DB.

### Pitfall 5: Snapshot built before session.commit()
**What goes wrong:** `TeamSnapshot` captures `team.id` before commit; commit fails; snapshot is passed to hook with an ID that was never persisted.
**Why it happens:** ORM object attributes are available before commit, but the row isn't durable.
**How to avoid:** Build snapshot only after the `try: await session.commit()` block completes successfully (i.e., in the code path that does not raise HTTPException). The ROADMAP explicitly states "hooks fire after session.commit() — commit-before-hook is the critical invariant".

---

## Code Examples

### NoOpIntegration (test/reference implementation)

```python
# src/pecp/integrations/noop.py
from pecp.integrations.base import IntegrationBase, TeamSnapshot, ProjectSnapshot, MemberSnapshot


class NoOpIntegration(IntegrationBase):
    """No-op integration for tests and as a reference implementation.

    Records calls for assertion in tests via self.calls list.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def on_team_create(self, team: TeamSnapshot) -> None:
        self.calls.append(("on_team_create", team))

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_project_create", project))

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_member_add", user))

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_member_remove", user))
```

### Failing integration test pattern (INTG-02 success criterion 2)

```python
# In tests/test_integrations/test_registry.py
async def test_failing_integration_does_not_block_primary_operation() -> None:
    class BoomIntegration(IntegrationBase):
        async def on_team_create(self, team: TeamSnapshot) -> None:
            raise RuntimeError("Simulated integration failure")

    from pecp.integrations import INTEGRATION_REGISTRY, fire_integrations
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.append(BoomIntegration())
    try:
        # fire_integrations must complete without raising
        await fire_integrations("on_team_create", TeamSnapshot(id="x", name="x", owner_id="x", created_at=...))
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)
```

### Commit-before-hook assertion pattern (INTG success criterion 4)

```python
# Test proves DB row exists when hook fires
async def test_hook_fires_after_commit(client: AsyncClient, db_session) -> None:
    """Verify on_team_create fires after session.commit() — DB row exists when hook runs."""
    from pecp.integrations import INTEGRATION_REGISTRY
    from pecp.integrations.noop import NoOpIntegration

    noop = NoOpIntegration()
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.append(noop)

    response = await client.post("/teams", json={"name": "test-team", "owner": "alice"})
    assert response.status_code == 201

    # Background task has run by now (TestClient runs background tasks synchronously)
    assert len(noop.calls) == 1
    hook_name, snapshot = noop.calls[0]
    assert hook_name == "on_team_create"
    # Verify the DB row exists — it must have been committed before the hook ran
    from sqlalchemy.future import select
    from pecp.persistence.models import TeamRecord
    result = await db_session.execute(select(TeamRecord).where(TeamRecord.name == "test-team"))
    row = result.scalar_one_or_none()
    assert row is not None, "TeamRecord must exist in DB when on_team_create fires"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Signal libraries (blinker/django signals) | Direct ABC + list dispatch | — | Zero extra dependencies; explicit call order; no magic |
| Celery/async task queue for hooks | FastAPI BackgroundTasks | v1.1 roadmap decision | No broker required for mock/PoC; hooks run in same process |
| Global module-level side effects on import | `load_and_register_integrations()` called from lifespan | — | Testable; registry can be cleared/replaced in tests |

**Deprecated/outdated:**
- `blinker` signals: Pre-dates async Python; signal receivers can't be `async def` without workarounds. Not appropriate here.
- Celery: Explicitly rejected in CLAUDE.md for PoC due to broker + worker overhead.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pydantic-settings ~2.14` is the version locked by v1.1 roadmap planning | Standard Stack | Wrong version may conflict with pydantic >=2.13 already installed; executor must verify with `pip index versions pydantic-settings` |
| A2 | `pytest-httpx ~0.36` is the version locked by v1.1 roadmap planning | Standard Stack | Wrong version may not support current `httpx >=0.28`; executor must verify with `pip index versions pytest-httpx` |
| A3 | `pydantic-settings` and `pytest-httpx` are OK on PyPI with no SLOP signals | Package Legitimacy | Both are official Pydantic ecosystem / well-known packages; risk is LOW |
| A4 | `httpx.AsyncClient` in the test suite (TestClient via ASGITransport) runs background tasks before yield completes | Code Examples | If background tasks are truly async and don't complete before the response is returned, the `test_hook_fires_after_commit` pattern needs `asyncio.sleep(0)` or similar; verify with Phase 7 TDD cycle |

---

## Open Questions

1. **Background task completion timing in tests**
   - What we know: `resources.py` tests work with the existing `BackgroundTasks` + `AsyncClient` pattern, so background tasks do complete before test assertions.
   - What's unclear: Whether `httpx.AsyncClient` with `ASGITransport` guarantees background task completion before `await client.post(...)` returns.
   - Recommendation: Add a small `asyncio.sleep(0)` after the POST if hooks are not observed in tests; or use `BackgroundTasks` starlette test utilities. The Phase 7 TDD cycle will resolve this.

2. **pydantic-settings version compatibility**
   - What we know: `pydantic >= 2.13` is already installed. `pydantic-settings` 2.x is the companion package for pydantic v2.
   - What's unclear: Exact minimum `pydantic-settings` version that supports `SettingsConfigDict` API used in the pattern.
   - Recommendation: Use `pip index versions pydantic-settings` to confirm latest 2.x stable before pinning. `~=2.14` from STATE.md should be compatible.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pydantic-settings` | INTG-03 env config | ✗ (not in pyproject.toml yet) | — | No fallback — must install |
| `pytest-httpx` | Phase 8 GitHub tests | ✗ (not in pyproject.toml yet) | — | Defer to Phase 8 if not adding now |
| `pytest` | Test suite | ✓ | >=9.0 | — |
| `pytest-asyncio` | Async tests | ✓ | >=1.4 | — |
| Python stdlib `abc`, `logging`, `dataclasses` | IntegrationBase, dispatcher | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
- `pydantic-settings` — required to satisfy INTG-03; must be added to pyproject.toml and installed before writing IntegrationConfig.

**Missing dependencies with fallback:**
- `pytest-httpx` — needed in Phase 8 but not Phase 7 itself; can be added now per STATE.md decision or deferred.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio 1.4.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `python -m pytest tests/test_integrations/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTG-01 | `IntegrationBase` ABC can be subclassed with no-op hooks that receive typed snapshot args | unit | `python -m pytest tests/test_integrations/test_base.py -x -q` | ❌ Wave 0 |
| INTG-01 | `NoOpIntegration` implements all 4 hooks and records calls | unit | `python -m pytest tests/test_integrations/test_noop.py -x -q` | ❌ Wave 0 |
| INTG-02 | Registered integration receives `on_team_create` after team creation via `POST /teams` | integration | `python -m pytest tests/test_integrations/test_registry.py::test_noop_receives_on_team_create -x -q` | ❌ Wave 0 |
| INTG-02 | Registered integration receives `on_project_create` after project creation | integration | `python -m pytest tests/test_integrations/test_registry.py::test_noop_receives_on_project_create -x -q` | ❌ Wave 0 |
| INTG-02 | Failing integration does not prevent `POST /teams` from returning 201 | integration | `python -m pytest tests/test_integrations/test_registry.py::test_failing_integration_does_not_block_team_create -x -q` | ❌ Wave 0 |
| INTG-02 | Integrations fire in registration order | unit | `python -m pytest tests/test_integrations/test_registry.py::test_integrations_fire_in_order -x -q` | ❌ Wave 0 |
| INTG-03 | Server starts without GITHUB_PAT/GITHUB_ORG set — logs warning, does not crash | unit | `python -m pytest tests/test_integrations/test_config.py::test_missing_env_logs_warning_not_crash -x -q` | ❌ Wave 0 |
| INTG-03 | INTEGRATION_REGISTRY is empty when config is missing | unit | `python -m pytest tests/test_integrations/test_config.py::test_empty_registry_when_env_missing -x -q` | ❌ Wave 0 |
| SC-4 | Hooks fire after `session.commit()` — DB row exists when hook runs | integration | `python -m pytest tests/test_integrations/test_commit_ordering.py::test_hook_fires_after_commit -x -q` | ❌ Wave 0 |
| Regression | All 166 prior tests still pass | regression | `python -m pytest tests/ -x -q` | ✓ (existing suite) |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_integrations/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green (>= 166 + new tests) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_integrations/__init__.py` — package marker
- [ ] `tests/test_integrations/test_base.py` — INTG-01 ABC contract tests
- [ ] `tests/test_integrations/test_noop.py` — NoOpIntegration behavior
- [ ] `tests/test_integrations/test_registry.py` — INTEGRATION_REGISTRY dispatch + error isolation
- [ ] `tests/test_integrations/test_config.py` — INTG-03 missing-env startup behavior
- [ ] `tests/test_integrations/test_commit_ordering.py` — commit-before-hook invariant

---

## Security Domain

> `security_enforcement` is `true` and `security_asvs_level` is `1` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in PoC |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No access control in PoC |
| V5 Input Validation | no | Snapshots are built from already-validated ORM objects; no external input enters hook layer |
| V6 Cryptography | no | No secrets stored; GITHUB_PAT is only loaded by Phase 8 |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hook error leaking exception details to response | Information Disclosure | Hook errors caught in `fire_integrations`; only logged server-side via `logger.warning` — never surfaced in API response body |
| Ghost resources if hook fires before commit | Tampering | Structural: `background_tasks.add_task` placed strictly after `await session.commit()` in success path; IntegrityError rollback path does not reach `add_task` |
| INTEGRATION_REGISTRY mutation in tests polluting other tests | Tampering (test integrity) | Tests that modify INTEGRATION_REGISTRY must save/restore it in try/finally; or use a test fixture that resets it |
| `GITHUB_PAT` logged accidentally | Information Disclosure | `IntegrationConfig` must NOT log the PAT value; only log "GITHUB_PAT not set" (absence). Phase 8 concern but the design must support it from Phase 7 |

**Phase 7 ASVS L1 applicability:** No new network endpoints, no auth paths, no user input enters the hook layer. The only security-relevant concern is log hygiene (don't log secret values) — mitigated by design in `load_and_register_integrations()`.

---

## Sources

### Primary (HIGH confidence)
- `src/pecp/adapters/base.py` — AdapterBase ABC pattern to mirror [VERIFIED: codebase read]
- `src/pecp/dispatcher.py` — ADAPTER_REGISTRY + `dispatch()` pattern to mirror [VERIFIED: codebase read]
- `src/pecp/api/routes/resources.py` — BackgroundTasks commit-before-hook pattern [VERIFIED: codebase read]
- `.planning/STATE.md` — Locked decisions: IntegrationBase mirrors AdapterBase; commit-before-hook invariant; snapshot not ORM object; pydantic-settings ~2.14; pytest-httpx ~0.36 [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` — INTG-01, INTG-02, INTG-03 requirement text [VERIFIED: file read]
- `.planning/ROADMAP.md` — Phase 7 success criteria [VERIFIED: file read]
- `pyproject.toml` — Current dependency versions and test configuration [VERIFIED: file read]
- `tests/conftest.py` — Test fixture patterns for INTEGRATION_REGISTRY isolation [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- CLAUDE.md tech stack constraints (no Celery for PoC, Python ABC for interfaces) [VERIFIED: file read]

### Tertiary (LOW confidence)
- pydantic-settings version ~2.14 from STATE.md roadmap planning [ASSUMED — not verified against PyPI]
- pytest-httpx version ~0.36 from STATE.md roadmap planning [ASSUMED — not verified against PyPI]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core packages already installed; only `pydantic-settings` and `pytest-httpx` are new; both are official companion packages
- Architecture: HIGH — mirrors existing AdapterBase/ADAPTER_REGISTRY/BackgroundTasks pattern exactly; codebase verified
- Pitfalls: HIGH — DetachedInstanceError and commit-before-hook pitfalls are directly evidenced in existing codebase patterns (resources.py `_dispatch_with_session`, STATE.md decisions)
- Package versions: MEDIUM — version pins come from STATE.md planning session, not live PyPI verification this session

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable stdlib + pydantic ecosystem; 30-day window)

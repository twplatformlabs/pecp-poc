# Phase 7: Integration Hook Framework - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 8 (3 new source, 1 new package dir, 2 modified routes, 1 modified config, 6 new test files)
**Analogs found:** 7 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pecp/integrations/base.py` | ABC / contract | event-driven | `src/pecp/adapters/base.py` | role-match (ABC pattern, different hook signatures) |
| `src/pecp/integrations/__init__.py` | registry + dispatcher | event-driven | `src/pecp/dispatcher.py` | role-match (registry + dispatch, different dispatch model: list vs dict) |
| `src/pecp/integrations/noop.py` | reference implementation | event-driven | `src/pecp/adapters/mock/aws_lambda.py` | partial (concrete impl of ABC) |
| `src/pecp/api/routes/teams.py` (modify) | controller | request-response | `src/pecp/api/routes/resources.py` | exact (BackgroundTasks after session.commit()) |
| `src/pecp/api/routes/projects.py` (modify) | controller | request-response | `src/pecp/api/routes/resources.py` | exact (BackgroundTasks after session.commit()) |
| `pyproject.toml` (modify) | config | — | existing `pyproject.toml` | exact (append to existing dependency lists) |
| `tests/test_integrations/` (6 files) | test | — | `tests/test_adapters/test_adapter_base.py`, `tests/test_api/test_dispatch_wiring.py` | role-match |

---

## Pattern Assignments

### `src/pecp/integrations/base.py` (ABC, event-driven)

**Analog:** `src/pecp/adapters/base.py`

**Imports pattern** (lines 1-6 of analog):
```python
from abc import ABC, abstractmethod

from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec
```

For `base.py`, replace the adapter imports with stdlib dataclasses:
```python
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
```

**Key divergence from analog — no `@abstractmethod`:**
`AdapterBase` (analog, lines 19-26) uses `@abstractmethod` on all methods, making them required. `IntegrationBase` must NOT use `@abstractmethod` — all lifecycle hooks default to `pass` to allow partial implementations. Use `ABC` on the class only.

**Analog class structure** (`src/pecp/adapters/base.py` lines 9-26):
```python
class AdapterBase(ABC):
    """
    Contract for all PECP backing-system adapters.
    ...
    """

    @abstractmethod
    async def provision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def get_status(self, resource: ResourceSpec) -> ProvisionResult: ...
```

**Target structure for `IntegrationBase`** (hooks are optional, not abstract):
```python
class IntegrationBase(ABC):
    async def on_team_create(self, team: TeamSnapshot) -> None:
        pass

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass
```

**Snapshot dataclasses** (no analog exists — use `@dataclass` stdlib pattern):
```python
@dataclass
class TeamSnapshot:
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
```

---

### `src/pecp/integrations/__init__.py` (registry + dispatcher, event-driven)

**Analog:** `src/pecp/dispatcher.py`

**Registry pattern** (`src/pecp/dispatcher.py` lines 32-43):
```python
ADAPTER_REGISTRY: dict[str, AdapterBase] = {
    "PECPLambda": AwsLambdaMockAdapter(),
    ...
}
```

**Key divergence:** `ADAPTER_REGISTRY` is a `dict` keyed by resource kind. `INTEGRATION_REGISTRY` is a `list` — integrations fire on every event, not routed by kind. Use `list[IntegrationBase] = []`.

**Dispatch pattern** (`src/pecp/dispatcher.py` lines 46-73 show the session-based dispatch). For integration dispatch, no session is needed — hooks receive snapshots. The pattern simplifies to:
```python
import logging
from typing import Any

from pecp.integrations.base import IntegrationBase

logger = logging.getLogger(__name__)

INTEGRATION_REGISTRY: list[IntegrationBase] = []


async def fire_integrations(hook_name: str, *args: Any) -> None:
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

**Module docstring pattern** (copy from `src/pecp/dispatcher.py` line 1):
```python
"""PECP Dispatcher — drives ResourceRecord through PENDING → PROVISIONING → READY|FAILED (D-03 through D-06)."""
```
Adapt to: `"""PECP integration hook registry and dispatcher (INTG-01, INTG-02)."""`

---

### `src/pecp/integrations/noop.py` (reference implementation, event-driven)

**Analog:** `src/pecp/adapters/mock/aws_lambda.py` (concrete subclass of ABC that records calls)

The noop pattern is self-contained per RESEARCH.md. It inherits from `IntegrationBase` and appends to `self.calls` for test assertions. No analog in the codebase does this exact "spy" pattern, but the subclassing convention follows all mock adapters.

**Import pattern** (mirrors mock adapter import style):
```python
from pecp.integrations.base import IntegrationBase, MemberSnapshot, ProjectSnapshot, TeamSnapshot
```

**Class structure:**
```python
class NoOpIntegration(IntegrationBase):
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

---

### `src/pecp/api/routes/teams.py` (modify — add BackgroundTasks wiring)

**Analog:** `src/pecp/api/routes/resources.py`

**BackgroundTasks parameter injection** (`src/pecp/api/routes/resources.py` lines 113-119):
```python
@router.post("", status_code=202)
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, str]:
```

Add `background_tasks: BackgroundTasks` to `create_team`'s signature. FastAPI injects it automatically — no other registration needed.

**Commit-before-hook pattern** (`src/pecp/api/routes/resources.py` lines 215-237):
```python
    try:
        await session.commit()  # atomic: resource + deployment insert in one transaction (Pitfall 2)
    except IntegrityError:
        await session.rollback()
        ...
        return { ... }  # exits function — add_task never reached on error

    background_tasks.add_task(_dispatch_with_session, resource_id)  # after commit, after except block
    return { ... }
```

Apply same structure to `create_team` in `teams.py` (lines 86-92). Currently:
```python
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")
    return _render_team(team, [member])
```

After modification, add snapshot build + `add_task` between `return _render_team` and the function end — after the `try/except` block exits cleanly:
```python
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")

    # Snapshot built after commit — ORM object still in session scope here
    snapshot = TeamSnapshot(
        id=team.id,
        name=team.name,
        owner_id=team.owner_id,
        created_at=team.created_at,
    )
    background_tasks.add_task(fire_integrations, "on_team_create", snapshot)
    return _render_team(team, [member])
```

**Import additions needed for `teams.py`:**
```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pecp.integrations import fire_integrations
from pecp.integrations.base import TeamSnapshot
```

---

### `src/pecp/api/routes/projects.py` (modify — add BackgroundTasks wiring)

**Analog:** `src/pecp/api/routes/resources.py` (same BackgroundTasks pattern as teams.py)

Current `create_project` commit block (`src/pecp/api/routes/projects.py` lines 65-73):
```python
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Project '{body.name}' already exists in team '{body.team}'",
        )
```

After modification, add snapshot and `add_task` between the `try/except` and the `return`:
```python
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(...)

    snapshot = ProjectSnapshot(
        id=project.id,
        name=project.name,
        team_id=project.team_id,
        environments=body.environments,
        created_at=project.created_at,
    )
    background_tasks.add_task(fire_integrations, "on_project_create", snapshot, team_snapshot)
    return { ... }
```

Note: `on_project_create` takes both `project` and `team` snapshots. Build a `TeamSnapshot` from the already-fetched `team` ORM object (line 51 of `projects.py`) before the commit.

**Import additions needed for `projects.py`:**
```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pecp.integrations import fire_integrations
from pecp.integrations.base import ProjectSnapshot, TeamSnapshot
```

---

### `pyproject.toml` (modify)

**Analog:** existing `pyproject.toml`

**New dependency in `[project] dependencies`** (after line 22, before closing bracket):
```toml
"pydantic-settings>=2.14",
```

**New dev dependency in `[project.optional-dependencies] dev`** (after line 30):
```toml
"pytest-httpx>=0.36",
```

Current `[project.optional-dependencies]` section (`pyproject.toml` lines 26-31):
```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-asyncio>=1.4",
    "mypy>=2.1",
    "ruff>=0.15",
]
```

---

### `tests/test_integrations/` (6 new test files)

**Analogs:**
- `tests/test_adapters/test_adapter_base.py` — ABC contract test pattern (unit)
- `tests/test_api/test_dispatch_wiring.py` — BackgroundTasks integration test pattern (monkeypatch + AsyncClient)
- `tests/conftest.py` — fixtures to reuse (`client`, `db_session`)

**Test file imports pattern** (`tests/test_adapters/test_adapter_base.py` lines 1-8):
```python
"""Tests for AdapterBase ABC (ADPT-01)."""

import pytest

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec
```

Adapt to integration tests:
```python
"""Tests for IntegrationBase ABC (INTG-01)."""

import pytest

from pecp.integrations.base import IntegrationBase, TeamSnapshot, ProjectSnapshot, MemberSnapshot
```

**Async test pattern** (`tests/test_api/test_dispatch_wiring.py` lines 27-48):
```python
async def test_post_resources_enqueues_background_dispatch(
    client: AsyncClient,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    dispatch_mock = mock.AsyncMock()
    monkeypatch.setattr(
        "pecp.api.routes.resources._dispatch_with_session",
        dispatch_mock,
    )
    ...
    dispatch_mock.assert_called_once_with(resource_id)
```

For INTEGRATION_REGISTRY isolation pattern from RESEARCH.md:
```python
async def test_failing_integration_does_not_block_primary_operation() -> None:
    from pecp.integrations import INTEGRATION_REGISTRY, fire_integrations
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.append(BoomIntegration())
    try:
        await fire_integrations("on_team_create", ...)
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)
```

**conftest.py fixtures** (`tests/conftest.py` lines 18-57) — reuse `client` and `db_session` fixtures as-is. No new fixtures required for Phase 7.

**pytest.ini_options** (`pyproject.toml` lines 64-67):
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]
```

`asyncio_mode = "auto"` means all `async def test_*` functions run as coroutines automatically — no `@pytest.mark.asyncio` decorator needed. All 6 new test files follow this convention (consistent with existing test suite).

---

## Shared Patterns

### Module-level logger
**Source:** `src/pecp/dispatcher.py` (pattern) — `logging.getLogger(__name__)`
**Apply to:** `src/pecp/integrations/__init__.py`
```python
import logging

logger = logging.getLogger(__name__)
```

### BackgroundTasks injection (FastAPI)
**Source:** `src/pecp/api/routes/resources.py` lines 113-119
**Apply to:** `src/pecp/api/routes/teams.py` `create_team`, `src/pecp/api/routes/projects.py` `create_project`

Add `background_tasks: BackgroundTasks` as the first parameter after `self` (or as first positional parameter for free functions). FastAPI injects it from the request context automatically.

### `IntegrityError` rollback exits before `add_task`
**Source:** `src/pecp/api/routes/resources.py` lines 215-237
**Apply to:** Both route modifications

The `raise HTTPException(...)` inside the `except IntegrityError` block exits the function. Any `background_tasks.add_task(...)` placed after the `try/except` block is never reached on error. This is the critical structural invariant — do not place `add_task` inside the `try` block.

### Test INTEGRATION_REGISTRY isolation
**Source:** RESEARCH.md code example (no existing codebase analog)
**Apply to:** All 6 test files in `tests/test_integrations/`

Pattern: save `original = list(INTEGRATION_REGISTRY)` before test, use `try/finally` to restore. Alternatively, tests that use `client` fixture (which drops/recreates schema) can rely on the fact that `INTEGRATION_REGISTRY` is a module-level list — reset it in a `pytest.fixture` with `autouse=True` per test module if needed.

### Snapshot built in session scope, passed to background task
**Source:** `src/pecp/api/routes/resources.py` line 237 (add_task after commit)
**Apply to:** Both route modifications

The ORM object (`TeamRecord`, `ProjectRecord`) is safe to access inside the route handler — the request `AsyncSession` is still open. Build the dataclass snapshot from ORM attributes immediately after `session.commit()` returns, before the `return` statement. Never pass the ORM object itself to `add_task`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/pecp/integrations/noop.py` (spy pattern) | reference impl | event-driven | No existing "call recorder" spy pattern in codebase — mock adapters don't track calls |

---

## Metadata

**Analog search scope:** `src/pecp/adapters/`, `src/pecp/api/routes/`, `src/pecp/dispatcher.py`, `tests/`
**Files scanned:** 9 source files, 3 test files, `pyproject.toml`, `tests/conftest.py`
**Pattern extraction date:** 2026-06-24

# Phase 8: GitHub Integration - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 5 (2 new source, 3 modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pecp/integrations/github.py` | integration (event-driven) | event-driven | `src/pecp/integrations/noop.py` | exact (same ABC, same hook methods, same data flow) |
| `tests/test_integrations/test_github.py` | test | event-driven | `tests/test_integrations/test_noop.py`, `tests/test_integrations/test_registry.py`, `tests/test_integrations/test_commit_ordering.py` | role-match (snapshot construction, INTEGRATION_REGISTRY isolation, DB writeback from background task) |
| `src/pecp/integrations/__init__.py` | registry (modify) | config | `src/pecp/integrations/__init__.py` (lines 48-61) | exact (modifying the existing stub) |
| `src/pecp/integrations/base.py` | ABC (modify) | contract | `src/pecp/integrations/base.py` (lines 38-55) | exact (adding a method to the ABC) |
| `src/pecp/api/main.py` | FastAPI app (modify) | request-response | `src/pecp/api/main.py` (lines 18-24) | exact (modifying lifespan shutdown block) |

---

## Pattern Assignments

### `src/pecp/integrations/github.py` (integration, event-driven — NEW)

**Analog:** `src/pecp/integrations/noop.py`

**Import pattern** (`src/pecp/integrations/noop.py` lines 1-8):
```python
"""NoOpIntegration — call-recording spy for tests and reference implementation (INTG-01)."""

from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)
```

**Target import pattern for `github.py`:**
```python
"""GitHubIntegration — provisions GitHub teams, repos, and memberships (GH-01 through GH-05)."""

import logging
import httpx
from sqlalchemy.future import select

from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)
from pecp.integrations import IntegrationConfig

logger = logging.getLogger(__name__)
```

**Module-level constants:**
```python
GITHUB_API = "https://api.github.com"
```

Note: `IntegrationConfig` is imported from `pecp.integrations` (the parent package), creating an import that could cause circular dependencies. The `GitHubIntegration` class itself is **deferred-imported** inside `load_and_register_integrations()` in `__init__.py` to avoid this.

**Class structure pattern — follow `NoOpIntegration`** (`src/pecp/integrations/noop.py` lines 11-30):

`NoOpIntegration` uses `IntegrationBase` subclass with no `super().__init__()`. `GitHubIntegration` follows the same pattern but stores an `httpx.AsyncClient` and the org name:

```python
class GitHubIntegration(IntegrationBase):
    def __init__(self, config: IntegrationConfig) -> None:
        self._org = config.GITHUB_ORG
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {config.GITHUB_PAT}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
```

**Hook error handling pattern** — each hook wraps its body in try/except, catches all exceptions, logs with context via `logger.exception()`, and re-raises. `fire_integrations` in `__init__.py` already catches and swallows integration errors (Phase 7 pattern), but each hook should defensively log GitHub-specific context before re-raising so the log message is meaningful.

Follow this structure (analog: `src/pecp/integrations/__init__.py` lines 15-32 for the fire-and-catch pattern):

```python
async def on_team_create(self, team: TeamSnapshot) -> None:
    try:
        resp = await self._client.post(
            f"/orgs/{self._org}/teams",
            json={"name": team.name, "privacy": "closed"},
        )
        resp.raise_for_status()
        slug: str = resp.json()["slug"]
        await _write_team_slug(team.id, slug)
    except Exception:
        logger.exception("GitHubIntegration.on_team_create failed for team %s", team.name)
        raise  # fire_integrations swallows this — non-fatal
```

**Member hook re-fetch pattern** — `on_member_add` and `on_member_remove` re-fetch `github_team_slug` from DB rather than relying on `TeamSnapshot.github_team_slug` (D-05, D-06):

```python
async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
    slug = await _fetch_team_slug(team.id)
    if slug is None:
        logger.warning("on_member_add: team %s has no github_team_slug — skipping", team.name)
        return
    try:
        resp = await self._client.put(
            f"/orgs/{self._org}/teams/{slug}/memberships/{user.user_id}",
            json={"role": "member"},
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("GitHubIntegration.on_member_add failed for user %s", user.user_id)
        raise
```

**DELETE 404-as-success pattern** (D-02 — `on_member_remove` treats 404 as success):

```python
async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
    slug = await _fetch_team_slug(team.id)
    if slug is None:
        logger.warning("on_member_remove: team %s has no github_team_slug — skipping", team.name)
        return
    try:
        resp = await self._client.delete(
            f"/orgs/{self._org}/teams/{slug}/memberships/{user.user_id}",
        )
        if resp.status_code not in (204, 404):
            resp.raise_for_status()
    except Exception:
        logger.exception("GitHubIntegration.on_member_remove failed for user %s", user.user_id)
        raise
```

**DB writeback helpers pattern** — background task DB writeback with module-reference import and fresh `AsyncSession`:

**Analog:** `tests/test_integrations/test_commit_ordering.py` lines 28-35 (opens a fresh `AsyncSession` inside a hook):

```python
import pecp.persistence.database as _db  # module reference, NOT 'from ... import AsyncSessionLocal'

async def _write_team_slug(team_id: str, slug: str) -> None:
    """Open a fresh AsyncSession to write github_team_slug back to TeamRecord."""
    from pecp.persistence.models import TeamRecord

    async with _db.AsyncSessionLocal() as session:
        result = await session.execute(
            select(TeamRecord).where(TeamRecord.id == team_id)
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.github_team_slug = slug
            await session.commit()
        else:
            logger.warning("_write_team_slug: TeamRecord %s not found", team_id)


async def _write_project_repo(project_id: str, repo_name: str, repo_url: str) -> None:
    """Open a fresh AsyncSession to insert a ProjectRepoRecord."""
    import uuid
    from datetime import datetime, timezone
    from pecp.persistence.models import ProjectRepoRecord

    async with _db.AsyncSessionLocal() as session:
        repo = ProjectRepoRecord(
            id=uuid.uuid4().hex,
            project_id=project_id,
            repo_name=repo_name,
            repo_url=repo_url,
            created_at=datetime.now(timezone.utc),
        )
        session.add(repo)
        await session.commit()
```

**`aclose()` pattern** — no-op default on `IntegrationBase` (base.py), override in `GitHubIntegration`:

```python
async def aclose(self) -> None:
    await self._client.aclose()
```

---

### `tests/test_integrations/test_github.py` (test, event-driven — NEW)

**Analog:** `tests/test_integrations/test_noop.py`, `tests/test_integrations/test_registry.py`, `tests/test_integrations/test_commit_ordering.py`

**Import pattern** — snapshot construction from `test_noop.py` (lines 1-6):
```python
"""Tests for GitHubIntegration (GH-01 through GH-05)."""

from datetime import datetime, timezone

from pecp.integrations.base import MemberSnapshot, ProjectSnapshot, TeamSnapshot
from pecp.integrations.github import GitHubIntegration
from pecp.integrations import IntegrationConfig
```

**Test config pattern** — use a fake PAT/OFF for all tests:
```python
FAKE_CONFIG = IntegrationConfig(GITHUB_PAT="ghp_FAKE", GITHUB_ORG="acme")
```

**pytest-httpx fixture usage** — `httpx_mock` auto-injects as a test parameter. No `@pytest.mark.asyncio` needed (pyproject.toml has `asyncio_mode = "auto"`).

No existing pytest-httpx usage in codebase yet — this is the first. Pattern comes from RESEARCH.md (lines 289-319):

```python
from pytest_httpx import HTTPXMock


async def test_on_team_create_calls_github_and_writes_slug(httpx_mock: HTTPXMock, db_session):
    """GH-02: on_team_create calls POST /orgs/{org}/teams and writes slug to DB."""
    # Arrange: register mock response for the GitHub API call
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        json={"slug": "toxins-research", "name": "toxins-research"},
        status_code=201,
    )

    # Arrange: insert a TeamRecord in the DB so _write_team_slug has something to update
    # (db_session fixture provides an isolated in-memory session)
    from pecp.persistence.models import TeamRecord
    record = TeamRecord(
        id="t1", name="Toxins Research", owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(record)
    await db_session.commit()

    # Act
    integration = GitHubIntegration(FAKE_CONFIG)
    team = TeamSnapshot(id="t1", name="Toxins Research", owner_id="u1", created_at=datetime.now(timezone.utc))
    await integration.on_team_create(team)

    # Assert: DB slug was written
    await db_session.refresh(record)
    assert record.github_team_slug == "toxins-research"
```

**Member hook pattern — no DB writeback, just HTTP call:**
```python
async def test_on_member_add_syncs_to_github(httpx_mock: HTTPXMock, db_session):
    """GH-04: on_member_add calls PUT memberships endpoint."""
    # Arrange: insert a TeamRecord with github_team_slug set
    from pecp.persistence.models import TeamRecord
    record = TeamRecord(
        id="t1", name="Toxins Research", owner_id="u1",
        github_team_slug="toxins-research",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(record)
    await db_session.commit()

    # Register mock for PUT membership
    httpx_mock.add_response(
        method="PUT",
        url="https://api.github.com/orgs/acme/teams/toxins-research/memberships/alice",
        json={"state": "active", "role": "member"},
        status_code=200,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    user = MemberSnapshot(user_id="alice", role="contributor")
    team = TeamSnapshot(id="t1", name="Toxins Research", owner_id="u1",
                         created_at=datetime.now(timezone.utc))

    await integration.on_member_add(user, team)
    # No exception means success — membership sync is fire-and-forget
```

**Error non-fatal pattern (GH-05)** — 422 on team create:

```python
async def test_on_team_create_422_is_non_fatal(httpx_mock: HTTPXMock):
    """GH-05: 422 on team create is caught and logged — does not crash."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        status_code=422,
        json={"message": "Validation Failed"},
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    team = TeamSnapshot(id="t1", name="Toxins Research", owner_id="u1",
                         created_at=datetime.now(timezone.utc))

    # The hook raises httpx.HTTPStatusError; fire_integrations catches it
    with pytest.raises(httpx.HTTPStatusError):
        await integration.on_team_create(team)
```

**DB session from httpx_mock test with db_session fixture** — `db_session` fixture from `tests/conftest.py` (lines 44-60) yields an isolated in-memory SQLite session. Use it alongside `httpx_mock`:

```python
async def test_on_team_create_creates_team_and_writes_slug(
    httpx_mock: HTTPXMock, db_session,
) -> None:
```

Note: `db_session` is from `conftest.py` at the project root — no need to import fixtures.

**INTEGRATION_REGISTRY isolation pattern** — for tests that exercise `fire_integrations` through the `client` fixture, follow `test_registry.py` pattern (lines 26-36):

```python
from pecp.integrations import INTEGRATION_REGISTRY


def _clear_registry() -> list:
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    return original


def _restore_registry(original: list) -> None:
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.extend(original)
```

**Snapshot construction pattern** — from `test_noop.py` (lines 18-23, 31-37, 51-57):

```python
team = TeamSnapshot(
    id="t1",
    name="test-team",
    owner_id="u1",
    created_at=datetime.now(timezone.utc),
)

project = ProjectSnapshot(
    id="p1",
    name="test-project",
    team_id="t1",
    environments=["dev"],
    created_at=datetime.now(timezone.utc),
)

user = MemberSnapshot(user_id="alice", role="contributor")
```

---

### `src/pecp/integrations/__init__.py` (modify — activate stub at line 61)

**Analog:** `src/pecp/integrations/__init__.py` (self-modification)

**Current stub at line 61:**
```python
    # Phase 8: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

**Replace with deferred import + registration** — import `GitHubIntegration` inside the function to avoid circular imports (`GitHubIntegration` imports from `pecp.integrations.base`, which is imported by `pecp.integrations.__init__`):

```python
    from pecp.integrations.github import GitHubIntegration
    INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

The guard pattern (`if not cfg.GITHUB_PAT or not cfg.GITHUB_ORG`) already handles the case where env vars are missing — `IntegrationConfig()` defaults to empty strings (lines 54-59). Keep the existing `return` guard:

```python
def load_and_register_integrations() -> None:
    cfg = IntegrationConfig()
    if not cfg.GITHUB_PAT or not cfg.GITHUB_ORG:
        logger.warning(
            "GITHUB_PAT or GITHUB_ORG not set — GitHub integration disabled"
        )
        return

    from pecp.integrations.github import GitHubIntegration
    INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

---

### `src/pecp/integrations/base.py` (modify — add `aclose()` to ABC)

**Analog:** `src/pecp/integrations/base.py` (self-modification, lines 38-55)

**Current ABC class** (lines 38-55):
```python
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

**Add `aclose()` after `on_member_remove`** — no-op default that concrete subclasses can override:

```python
    async def aclose(self) -> None:
        """Close the integration's resources (e.g. httpx.AsyncClient connection pool).

        Called from FastAPI lifespan shutdown. Default is a no-op —
        integrations that own resources override this method.
        """
        pass
```

---

### `src/pecp/api/main.py` (modify — wire aclose() into lifespan shutdown)

**Analog:** `src/pecp/api/main.py` (self-modification, lines 18-24)

**Current lifespan** (lines 18-24):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database schema and load integrations on startup."""
    await init_schema()
    load_and_register_integrations()
    yield
```

**Modified lifespan with shutdown block** — iterate `INTEGRATION_REGISTRY` and await each integration's `aclose()`:

```python
from pecp.integrations import INTEGRATION_REGISTRY, load_and_register_integrations


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database schema and load integrations on startup.

    On shutdown, close all registered integrations' resources.
    """
    await init_schema()
    load_and_register_integrations()
    yield
    # Shutdown: close all integration resources
    for integration in INTEGRATION_REGISTRY:
        await integration.aclose()
```

Note: `INTEGRATION_REGISTRY` is already imported from line 14? Let me check — currently `src/pecp/api/main.py` line 14 only imports `load_and_register_integrations`, not `INTEGRATION_REGISTRY`. Add `INTEGRATION_REGISTRY` to the import:

```python
from pecp.integrations import INTEGRATION_REGISTRY, load_and_register_integrations
```

---

## Shared Patterns

### Module-level logger
**Source:** `src/pecp/integrations/__init__.py` line 10
**Apply to:** `src/pecp/integrations/github.py`
```python
import logging
logger = logging.getLogger(__name__)
```

### Background task snapshot pass-by-value
**Source:** `src/pecp/integrations/base.py` lines 8-36 (snapshot dataclasses)
**Apply to:** All `on_*` hook method signatures in `github.py`
```python
# Snapshots are plain dataclasses — never pass ORM objects to background tasks
team = TeamSnapshot(id=..., name=..., owner_id=..., created_at=...)
```

### Deferred import to avoid circular dependency
**Source:** RESEARCH.md Section: Architecture Patterns
**Apply to:** `src/pecp/integrations/__init__.py` `load_and_register_integrations()`
```python
# Import inside function, not at module level
from pecp.integrations.github import GitHubIntegration
INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

### Module-reference DB import (avoid import-time session binding)
**Source:** `tests/test_integrations/test_commit_ordering.py` line 11
**Apply to:** `src/pecp/integrations/github.py` DB writeback helpers
```python
import pecp.persistence.database as _db  # module ref, never 'from ... import AsyncSessionLocal'

async with _db.AsyncSessionLocal() as session:
    ...
```

### GitHub team name sanitization
**Source:** RESEARCH.md Section: Name Sanitization (D-07)
**Apply to:** `src/pecp/integrations/github.py` — sanitize team/project names before sending to GitHub API:
```python
def _sanitize(name: str) -> str:
    """Lowercase and replace spaces with hyphens for GitHub API consumption."""
    return name.lower().replace(" ", "-")
```

### pytest-httpx test isolation pattern
**Source:** RESEARCH.md (no existing codebase analog — first usage)
**Apply to:** All tests in `test_github.py`
```python
from pytest_httpx import HTTPXMock

# Each test registers its own mock responses before exercising the integration
httpx_mock.add_response(method="POST", url=..., json=..., status_code=201)
```

### asyncio_mode = "auto" — no `@pytest.mark.asyncio` needed
**Source:** `pyproject.toml` (Phase 7, inherited)
**Apply to:** All async test functions in `test_github.py`
```python
# This works without decorators:
async def test_something(httpx_mock: HTTPXMock) -> None:
    ...
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_integrations/test_github.py` (pytest-httpx portion) | test | event-driven | No existing pytest-httpx usage in the codebase — this is the first test file using it. Use RESEARCH.md patterns as reference. |

## Metadata

**Analog search scope:** `src/pecp/integrations/`, `src/pecp/api/`, `tests/test_integrations/`, `tests/conftest.py`
**Files scanned:** 8 source files, 4 test files, `tests/conftest.py`
**Pattern extraction date:** 2026-06-24

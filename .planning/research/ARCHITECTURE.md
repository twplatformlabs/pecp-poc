# Architecture Patterns — PECP v1.1 GitHub Integration

**Domain:** Integration hook system layered onto existing FastAPI + SQLAlchemy service
**Researched:** 2026-06-24
**Confidence:** HIGH (based on direct codebase analysis of existing v1.0 implementation)

---

## Current System (v1.0 baseline)

The existing control plane uses a flat, route-handler-centric style with no service layer:

```
CLI (httpx) → FastAPI route handler → SQLAlchemy AsyncSession → DB commit
                                     → BackgroundTasks (dispatcher) → AdapterBase
```

Route handlers own DB writes directly — there is no intermediate service module. `teams.py` and `projects.py` each do their own ORM work inline. The dispatcher pattern (`BackgroundTasks.add_task(_dispatch_with_session, resource_id)`) opens a fresh `AsyncSessionLocal` context so the background task is fully decoupled from the request session.

Key invariant already proven: `session.commit()` happens in the route handler before `background_tasks.add_task(...)` is called. FastAPI executes background tasks after the response is sent to the client. This ordering guarantee (commit → respond → background task) is the foundation of the integration hook pattern.

---

## New System Architecture (v1.1)

The integration hook system mirrors the adapter pattern already in place. The key design decisions are:

1. **Hooks fire in the service layer, not the route handler** — a thin `TeamService` / `ProjectService` layer is extracted to own both DB write and hook dispatch, keeping route handlers thin
2. **`INTEGRATION_REGISTRY` is a module-level list** initialized at FastAPI lifespan startup — no dependency injection needed, same pattern as `ADAPTER_REGISTRY` in `dispatcher.py`
3. **Hooks are fire-and-forget via `BackgroundTasks`** — GitHub API calls are async side-effects that must not block the primary DB operation or the HTTP response
4. **Partial failure is non-fatal** — GitHub call failure logs a warning; PECP DB write is already committed

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLI (httpx) — pecp team create / project create / team member add/rm   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Route Handlers  (teams.py, projects.py)                                │
│  • Parse request body, validate                                         │
│  • Delegate to TeamService / ProjectService                             │
│  • Pass background_tasks: BackgroundTasks as argument                   │
│  • Return response from service result                                  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Service Layer  (pecp/services/team_service.py, project_service.py)     │
│  NEW — extracted from route handlers                                    │
│  1. DB write (team/project/member INSERT or DELETE) + await commit()    │
│  2. background_tasks.add_task(_fire_hooks, hook_name, payload)          │
│  3. Return ORM record to caller                                         │
└──────────┬───────────────────────────────┬──────────────────────────────┘
           │                               │
           ▼                               ▼
┌─────────────────────┐       ┌────────────────────────────────────────────┐
│  SQLAlchemy ORM     │       │  _fire_hooks (background coroutine)        │
│  AsyncSession       │       │  Opens fresh httpx.AsyncClient             │
│  teams, projects,   │       │  Iterates INTEGRATION_REGISTRY             │
│  team_members,      │       │  Calls hook.on_team_create(team) etc.      │
│  project_repos      │       │  Catches all exceptions, logs, continues   │
└─────────────────────┘       └────────────┬───────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────────────────────────┐
                              │  INTEGRATION_REGISTRY                       │
                              │  list[IntegrationBase]                      │
                              │  Populated in lifespan() from env vars      │
                              │  Empty list = no-op (no env vars set)       │
                              └────────────────┬────────────────────────────┘
                                               │ implements
                                               ▼
                              ┌─────────────────────────────────────────────┐
                              │  IntegrationBase ABC                        │
                              │  on_team_create(team: TeamRecord)           │
                              │  on_project_create(project, team)           │
                              │  on_member_add(username, team)              │
                              │  on_member_remove(username, team)           │
                              │  All async, all default no-op               │
                              └────────────────┬────────────────────────────┘
                                               │
                                               ▼
                              ┌─────────────────────────────────────────────┐
                              │  GitHubIntegration(IntegrationBase)         │
                              │  httpx.AsyncClient + GITHUB_PAT env var     │
                              │  POST /orgs/{org}/teams                     │
                              │  POST /orgs/{org}/repos                     │
                              │  PUT /orgs/{org}/teams/{slug}/memberships/  │
                              │  DELETE /orgs/{org}/teams/{slug}/members/   │
                              │  Stores slug/URL on TeamRecord (via arg)    │
                              └─────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Route handlers (`teams.py`, `projects.py`) | HTTP contract, request parsing, response shaping | Service layer only; passes `BackgroundTasks` down |
| `TeamService` / `ProjectService` | DB write + hook dispatch sequencing | `AsyncSession`, `BackgroundTasks`, `INTEGRATION_REGISTRY` |
| `_fire_hooks` coroutine | Fire each registered integration's hook; catch errors | `INTEGRATION_REGISTRY` items only |
| `IntegrationBase` ABC | Define lifecycle hook interface; default no-ops | None (pure interface) |
| `GitHubIntegration` | Real GitHub API calls via httpx | GitHub REST API; writes back `github_team_slug` via return value |
| `INTEGRATION_REGISTRY` | Module-level list; populated at lifespan startup | Env vars (`GITHUB_PAT`, `GITHUB_ORG`) |
| `ProjectRepo` ORM model | One-to-many repos per project | `project_repos` table via Alembic migration 0004 |

---

## Integration Points in Existing Code

These are the exact lines where hooks need to wire in. Nothing else in the existing codebase requires modification.

### 1. `src/pecp/api/main.py` — lifespan event

**Current state:** `lifespan()` only calls `await init_schema()`.

**Change:** After `init_schema()`, build and populate `INTEGRATION_REGISTRY`:

```python
from pecp.integrations.registry import build_registry
from pecp.integrations import INTEGRATION_REGISTRY as _registry

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_schema()
    _registry.extend(build_registry())   # reads GITHUB_PAT, GITHUB_ORG from env
    yield
    _registry.clear()
```

`build_registry()` returns `[GitHubIntegration(...)]` if env vars present, `[]` if not — server does not crash on missing config (INTG-03).

### 2. `src/pecp/api/routes/teams.py` — `create_team` handler

**Current state:** Route handler does ORM work inline and returns directly.

**Change:** Extract ORM work into `TeamService.create(...)`, add `BackgroundTasks` dependency, pass to service. Route handler becomes a thin wrapper:

```python
@router.post("", status_code=201)
async def create_team(
    body: TeamCreate,
    background_tasks: BackgroundTasks,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, object]:
    team, member = await TeamService.create(body.name, body.owner, session, background_tasks)
    return _render_team(team, [member])
```

### 3. `src/pecp/api/routes/teams.py` — member add/remove (new endpoints)

**New endpoints needed:** `POST /teams/{name}/members` and `DELETE /teams/{name}/members/{username}` — both call `TeamService.add_member(...)` / `TeamService.remove_member(...)` which do DB write then fire `on_member_add` / `on_member_remove`.

### 4. `src/pecp/api/routes/projects.py` — `create_project` handler

**Current state:** Route handler does ORM work inline.

**Change:** Same extraction as teams — `ProjectService.create(...)` handles DB write and fires `on_project_create`.

### 5. `src/pecp/api/routes/projects.py` — repo add (new endpoint)

**New endpoint:** `POST /projects/{id}/repos` — calls `ProjectService.add_repo(...)` which calls GitHub to create a repo and inserts a `ProjectRepo` row.

---

## Data Flow: Team Create → GitHub Hook

The complete sequence for `pecp team create <name>`:

```
1.  CLI: POST /teams  {name, owner}

2.  Route handler: create_team()
    a. FastAPI injects AsyncSession, BackgroundTasks
    b. Delegates to TeamService.create(name, owner, session, background_tasks)

3.  TeamService.create():
    a. Build TeamRecord + TeamMemberRecord ORM objects
    b. session.add(...); await session.commit()   ← DB write committed, durable
    c. background_tasks.add_task(
           _fire_hooks, "on_team_create", team_id=team.id
       )
    d. Return (team, member) to route handler

4.  Route handler: return _render_team(team, [member])
    ← HTTP 201 sent to client with github_team_slug=None (not yet set)

5.  BackgroundTasks: _fire_hooks() runs AFTER response is sent
    a. Opens fresh AsyncSessionLocal + httpx.AsyncClient
    b. Re-fetches TeamRecord by team_id (fresh session, avoid stale reference)
    c. For each integration in INTEGRATION_REGISTRY:
         result = await integration.on_team_create(team)
         if result.github_team_slug:
             team.github_team_slug = result.github_team_slug
             await session.commit()   ← write slug back to DB
    d. Catches all exceptions; logs with context; continues to next integration

6.  Subsequent GET /teams/{name} returns github_team_slug (populated)
    CLI output: "GitHub team: https://github.com/orgs/{org}/teams/{slug}"
```

**Why the slug write-back happens inside `_fire_hooks` (not the route):** The route returns 201 before GitHub responds. The slug is only available after the async GitHub call. Re-fetching the record inside `_fire_hooks` with a fresh session is required because `expire_on_commit=False` does not guarantee the route handler's session object reflects writes from the background task.

---

## New File Layout

```
src/pecp/
  integrations/
    __init__.py          # INTEGRATION_REGISTRY: list[IntegrationBase] = []
    base.py              # IntegrationBase ABC — on_team_create, on_project_create,
                         #   on_member_add, on_member_remove — all async, default no-op
    github.py            # GitHubIntegration(IntegrationBase)
    registry.py          # build_registry() → reads env, constructs instances
  services/
    __init__.py
    team_service.py      # TeamService.create(), add_member(), remove_member()
    project_service.py   # ProjectService.create(), add_repo()
```

**No changes to:**
- `src/pecp/adapters/` — adapter pattern is separate concern
- `src/pecp/dispatcher.py` — resource provisioning unchanged
- `src/pecp/persistence/database.py` — engine/session factory unchanged
- `src/pecp/api/dependencies.py` — RequestContext unchanged

**Modified files:**
- `src/pecp/api/main.py` — lifespan: call `build_registry()`
- `src/pecp/api/routes/teams.py` — delegate to `TeamService`, add member endpoints
- `src/pecp/api/routes/projects.py` — delegate to `ProjectService`, add repo endpoint
- `src/pecp/persistence/models.py` — add `github_team_slug` on `TeamRecord`, add `ProjectRepo` model
- `alembic/versions/0004_add_github_integration.py` — new migration (batch mode for SQLite)

---

## Async Failure Handling Pattern

### Hook errors must not fail the primary operation

The fundamental contract (INTG-02): a GitHub API error must not roll back the PECP team/project DB write. This is enforced by the sequence order — `session.commit()` happens before `background_tasks.add_task(...)`. By the time the hook fires, the DB write is already durable.

Inside `_fire_hooks`, each integration call is wrapped independently:

```python
async def _fire_hooks(hook_name: str, **payload: object) -> None:
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:
            for integration in INTEGRATION_REGISTRY:
                try:
                    hook = getattr(integration, hook_name)
                    await hook(session=session, client=client, **payload)
                except Exception as exc:
                    logger.warning(
                        "Integration hook failed",
                        extra={
                            "integration": type(integration).__name__,
                            "hook": hook_name,
                            "error": str(exc),
                        },
                    )
                    # continue — do not re-raise; next integration still fires
```

### GitHub-specific partial failures

| Failure scenario | Behaviour | Recovery path |
|------------------|-----------|---------------|
| `GITHUB_PAT` missing | `build_registry()` returns `[]`; no hook fires; warning logged at startup | Set env var and restart server |
| GitHub 422 "already exists" | Treat as soft success — attempt GET to retrieve slug/URL, store it; log info | No action needed; idempotent |
| GitHub 404 user not found (member add) | Log warning with username; skip — PECP membership still written | PE investigates username mismatch |
| GitHub 429 / rate limit | Log warning with `Retry-After` value; do not retry in PoC | Manual re-trigger (v2: retry queue) |
| GitHub 5xx server error | Log warning; hook is abandoned for this call | PECP record is intact; re-run hook via admin endpoint (v2) |
| Network timeout (httpx) | Log warning; hook is abandoned | Same as 5xx |

### The slug/repo-URL write-back is best-effort

`TeamRecord.github_team_slug` and `ProjectRepo.repo_url` are nullable. If the GitHub call fails, the row has a `NULL` slug. `GET /teams/{name}` returns `github_team_slug: null` and `github_team_url: null`. The CLI suppresses the GitHub line if null rather than showing a broken URL.

---

## `IntegrationBase` ABC Design

```python
# src/pecp/integrations/base.py
from abc import ABC
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pecp.persistence.models import ProjectRecord, TeamRecord


@dataclass
class IntegrationResult:
    """Structured return value from a lifecycle hook.

    All fields optional — integrations only populate what they set.
    """
    github_team_slug: str | None = None
    github_team_url: str | None = None
    github_repo_url: str | None = None
    github_repo_name: str | None = None


class IntegrationBase(ABC):
    """Lifecycle hook interface for PECP integrations.

    All methods are async. Default implementations are no-ops that return an
    empty IntegrationResult — concrete subclasses override only what they handle.

    The session and client are provided by the _fire_hooks coroutine so that:
    - The session is fresh (not request-scoped)
    - The httpx client is shared across all hooks in one background run
    """

    async def on_team_create(
        self,
        team: TeamRecord,
        session: AsyncSession,
        client: httpx.AsyncClient,
    ) -> IntegrationResult:
        return IntegrationResult()

    async def on_project_create(
        self,
        project: ProjectRecord,
        team: TeamRecord,
        session: AsyncSession,
        client: httpx.AsyncClient,
    ) -> IntegrationResult:
        return IntegrationResult()

    async def on_member_add(
        self,
        username: str,
        team: TeamRecord,
        session: AsyncSession,
        client: httpx.AsyncClient,
    ) -> IntegrationResult:
        return IntegrationResult()

    async def on_member_remove(
        self,
        username: str,
        team: TeamRecord,
        session: AsyncSession,
        client: httpx.AsyncClient,
    ) -> IntegrationResult:
        return IntegrationResult()
```

**Why `IntegrationResult` instead of side-effects:** The hook returns a structured result so `_fire_hooks` can apply write-backs without each integration needing direct session access for the outer record. Keeps the hook implementation focused on the external API call.

**Why pass `session` and `client` rather than creating them in the hook:** Sharing a single `httpx.AsyncClient` across all integrations in one background run avoids N connection pool setups. Sharing the session allows write-backs to be batched in one commit.

---

## `INTEGRATION_REGISTRY` Initialization

```python
# src/pecp/integrations/__init__.py
from pecp.integrations.base import IntegrationBase

INTEGRATION_REGISTRY: list[IntegrationBase] = []
```

```python
# src/pecp/integrations/registry.py
import logging
import os

from pecp.integrations.base import IntegrationBase
from pecp.integrations.github import GitHubIntegration

logger = logging.getLogger(__name__)


def build_registry() -> list[IntegrationBase]:
    """Read environment variables and return configured integrations.

    Missing env vars disable the integration with a warning — server does not crash.
    Call once from lifespan(); extend INTEGRATION_REGISTRY with the result.
    """
    integrations: list[IntegrationBase] = []

    pat = os.getenv("GITHUB_PAT")
    org = os.getenv("GITHUB_ORG")
    if pat and org:
        integrations.append(GitHubIntegration(pat=pat, org=org))
        logger.info("GitHubIntegration registered for org=%s", org)
    else:
        logger.warning(
            "GitHubIntegration disabled — GITHUB_PAT or GITHUB_ORG not set"
        )

    return integrations
```

**Why module-level list, not `app.state`:** The existing `ADAPTER_REGISTRY` in `dispatcher.py` is a module-level dict — same pattern here. No dependency injection needed; service functions import `INTEGRATION_REGISTRY` directly. This avoids threading `Request` into service functions just to read `app.state`.

**Why `build_registry()` returns a list instead of mutating in place:** Lifespan can do `_registry.extend(build_registry())` and `_registry.clear()` on shutdown — clean, testable, no circular import.

---

## Data Model Changes

### `TeamRecord` (modified)

Add one nullable column:

```python
github_team_slug: Mapped[str | None] = mapped_column(String, nullable=True)
```

`github_team_url` is derived (`f"https://github.com/orgs/{org}/teams/{slug}"`), not stored — avoids stale URL if org name changes.

### `ProjectRepo` (new table)

```python
class ProjectRepo(Base):
    __tablename__ = "project_repos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

No `UniqueConstraint` on `(project_id, repo_name)` in the initial migration — requirements allow adding multiple repos per project and `pecp project repo add` explicitly creates additional repos. If idempotency is needed later, the constraint can be added in a follow-on migration.

### Alembic migration `0004_add_github_integration.py`

Two operations in one migration (DATA-03):

1. `batch_alter_table("teams")` → add `github_team_slug VARCHAR NULL`
2. `create_table("project_repos", ...)` with FK to `projects.id`

SQLite requires `batch_alter_table` for column additions (existing pattern in `0003`).

---

## Build Order

Dependencies between components determine sequence:

```
Step 1: Data model + migration (0004_add_github_integration.py)
  └─ TeamRecord.github_team_slug, ProjectRepo table
  └─ No code depends on this — safe to ship first
  └─ Run: alembic upgrade head

Step 2: IntegrationBase ABC + IntegrationResult dataclass
  └─ src/pecp/integrations/base.py
  └─ No imports of application code — pure Python ABC
  └─ GitHubIntegration depends on this; services depend on this

Step 3: GitHubIntegration
  └─ src/pecp/integrations/github.py
  └─ Depends on: IntegrationBase, httpx (already in stack)
  └─ Tests: respx (httpx mock library) to mock GitHub endpoints

Step 4: INTEGRATION_REGISTRY + build_registry()
  └─ src/pecp/integrations/__init__.py + registry.py
  └─ Depends on: GitHubIntegration
  └─ Wire into main.py lifespan

Step 5: _fire_hooks coroutine + TeamService / ProjectService
  └─ src/pecp/services/team_service.py, project_service.py
  └─ Depends on: INTEGRATION_REGISTRY, SQLAlchemy models (Step 1)
  └─ This is where DB write + hook dispatch is sequenced

Step 6: Route handler updates + new endpoints
  └─ teams.py: delegate to TeamService, add member add/remove endpoints
  └─ projects.py: delegate to ProjectService, add repo endpoint
  └─ Depends on: services layer (Step 5)
  └─ API contract changes: add github_team_slug/url to team responses

Step 7: CLI updates
  └─ pecp team create → display GitHub team line
  └─ pecp team show → display GitHub row in panel
  └─ pecp project create → display GitHub repo line
  └─ pecp project show → list repos
  └─ pecp team member add/remove → call new API endpoints
  └─ Depends on: API contract (Step 6)
```

---

## Patterns to Follow

### Pattern 1: Commit-before-hook ordering

The existing dispatcher pattern (`dispatch_with_session` in `resources.py`) already demonstrates the correct pattern: commit the primary write before the background task runs. Services must follow this strictly:

```python
# CORRECT
await session.commit()                           # durable first
background_tasks.add_task(_fire_hooks, ...)     # side-effect after

# WRONG — hook could see uncommitted state if commit fails
background_tasks.add_task(_fire_hooks, ...)
await session.commit()
```

### Pattern 2: Fresh session in background task

Identical to `_dispatch_with_session` in `resources.py` — background task opens its own `AsyncSessionLocal` context. Never reuse the request-scoped session (it closes when the request ends; using it after causes `MissingGreenlet` errors).

### Pattern 3: GitHub 422 "already exists" as soft success

GitHub returns `422 Unprocessable Entity` when a team or repo with the same name already exists. Treat this as a recoverable success — attempt a `GET` to retrieve the existing resource's slug/URL and store it. Do not surface a 4xx to the PECP caller.

```python
try:
    r = await client.post(f"https://api.github.com/orgs/{org}/teams", ...)
    r.raise_for_status()
    return IntegrationResult(github_team_slug=r.json()["slug"], ...)
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 422:
        # Team may already exist — try GET to recover slug
        get_r = await client.get(f"https://api.github.com/orgs/{org}/teams/{name_slug}")
        if get_r.status_code == 200:
            return IntegrationResult(github_team_slug=get_r.json()["slug"], ...)
    logger.warning("GitHub API error: %s %s", exc.response.status_code, exc.response.text)
    return IntegrationResult()   # empty result — slug remains NULL
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hook fires before DB commit

**What:** Calling `_fire_hooks` before `session.commit()`.

**Why bad:** If the DB commit fails after the GitHub team was already created, PECP has no record of the team but GitHub does. The next `pecp team create` will fail with 409 from PECP but will also fail on GitHub with 422 "already exists" — creating a stuck state.

**Instead:** Always `await session.commit()` before enqueuing hooks. The "already exists" idempotency recovery (Pattern 3) handles the rare case where the commit succeeds but the hook fails, then the user retries.

### Anti-Pattern 2: Injecting `app.state` into service functions

**What:** Passing `request: Request` into service functions to access `request.app.state.integration_registry`.

**Why bad:** Service functions become HTTP-aware. Breaks testability — tests must construct a mock `Request` to call services. Existing `ADAPTER_REGISTRY` pattern proves module-level dict works cleanly.

**Instead:** Import `INTEGRATION_REGISTRY` directly in service functions. Tests can manipulate the list directly in fixtures.

### Anti-Pattern 3: Synchronous GitHub calls in route handlers

**What:** Calling GitHub API synchronously in the route handler, blocking the response.

**Why bad:** GitHub API P50 latency is ~200–500ms; worst-case with rate limits could be seconds. PECP's `POST /teams` would hang for the duration. Breaks the `pecp team create` UX.

**Instead:** All external API calls go in background tasks. Route returns 201 immediately; GitHub slug appears on subsequent GET.

### Anti-Pattern 4: One `httpx.AsyncClient` instance per hook call

**What:** Each hook method does `async with httpx.AsyncClient() as client: ...` independently.

**Why bad:** Each `AsyncClient` context manager creates and destroys a connection pool. If multiple integrations fire in sequence, each opens a new pool, saturates file descriptors on slow GitHub responses.

**Instead:** `_fire_hooks` creates one `AsyncClient` and passes it to all integration hooks. Client is scoped to the background task lifetime.

### Anti-Pattern 5: Storing `github_team_url` as a DB column

**What:** Adding a `github_team_url TEXT` column to `TeamRecord`.

**Why bad:** The URL is fully derived from `github_team_slug` and the configured `GITHUB_ORG`. Storing derived data creates a consistency risk if the org name changes.

**Instead:** Derive the URL at read time: `f"https://github.com/orgs/{org}/teams/{slug}"`. The `GITHUB_ORG` env var is available to the API response serializer.

---

## Scalability Considerations

| Concern | At current PoC scale | At org-wide adoption |
|---------|----------------------|----------------------|
| GitHub rate limit | No issue — low call volume | Add retry queue (ARQ) with exponential backoff; primary operations are unaffected |
| Integration registry size | 1 integration, constant time | O(n) across integrations but n is always small (5–10); not a bottleneck |
| DB contention on write-back | None — single SQLite writer | Move to Postgres; async write-backs are isolated per background task |
| Hook failure visibility | Logs only | Add `IntegrationEvent` audit table (v2) to surface hook outcomes in UI |
| Multiple integrations ordering | Sequential in registration order | No ordering guarantee needed; hooks are independent |

---

## Sources

- Codebase analysis: `src/pecp/api/main.py`, `src/pecp/api/routes/teams.py`, `src/pecp/api/routes/projects.py`, `src/pecp/dispatcher.py`, `src/pecp/persistence/models.py`, `src/pecp/adapters/base.py` — confidence HIGH (direct inspection)
- FastAPI BackgroundTasks execution model: fires after HTTP response is delivered — confidence MEDIUM (training knowledge, consistent with observed behavior in codebase)
- GitHub API 422 "already exists" behavior: confidence LOW (training knowledge; verify against GitHub docs before implementation)
- SQLAlchemy async session lifetime and `MissingGreenlet` risk in background tasks: confidence MEDIUM (training knowledge; demonstrated by existing `_dispatch_with_session` pattern in `resources.py`)

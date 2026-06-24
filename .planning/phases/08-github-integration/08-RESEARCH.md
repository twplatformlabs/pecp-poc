# Phase 8: GitHub Integration - Research

**Researched:** 2026-06-24
**Domain:** GitHub REST API v3, httpx AsyncClient, pytest-httpx, SQLAlchemy async writeback from BackgroundTasks
**Confidence:** MEDIUM

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GH-01 | `GitHubIntegration` class implements `IntegrationBase` using real httpx calls to GitHub API, authenticated via `GITHUB_PAT`, scoped to `GITHUB_ORG` | Section: Standard Stack, Architecture Patterns, Code Examples |
| GH-02 | `on_team_create` creates a GitHub team; resulting slug stored on `TeamRecord.github_team_slug` via a new DB session in the background task | Section: Architecture Patterns (DB writeback pattern), Common Pitfalls |
| GH-03 | `on_project_create` creates an empty GitHub repo `{team-name}-{project-name}`; URL stored in `ProjectRepoRecord` | Section: Architecture Patterns, Code Examples |
| GH-04 | `on_member_add`/`on_member_remove` one-way sync to GitHub team membership; PECP operation succeeds regardless of GitHub username validity | Section: GitHub API endpoints, Common Pitfalls |
| GH-05 | GitHub API errors (rate limit, 422, user not found) caught, logged with context, non-fatal | Section: Common Pitfalls, Architecture Patterns |
</phase_requirements>

---

## Summary

Phase 8 implements `GitHubIntegration(IntegrationBase)` — a concrete subclass of the ABC established in Phase 7 that makes real GitHub API calls using the `httpx.AsyncClient` already present in the project. The class is instantiated with an `IntegrationConfig` (GITHUB_PAT, GITHUB_ORG) and registered in `INTEGRATION_REGISTRY` via the stub comment left in Phase 7's `load_and_register_integrations()`.

The single most important architectural challenge is the **DB writeback from a background task**: `on_team_create` receives a `TeamSnapshot` (not an ORM object) but must write the GitHub slug back to `TeamRecord.github_team_slug`. Since the request session is closed by the time the background task runs, the background task must open its own `AsyncSession` via the module-level `AsyncSessionLocal` factory. This is a well-understood SQLAlchemy async pattern — one session per async task.

All GitHub HTTP calls are intercepted in tests by `pytest-httpx` (the `httpx_mock` fixture), which was already pinned in Phase 7's `pyproject.toml` update. No new packages are needed for this phase. Tests must register mock responses for all four GitHub endpoints before exercising the integration, and must use `@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)` on tests where optional/partial GitHub calls occur.

**Primary recommendation:** Implement `GitHubIntegration` as a single module `src/pecp/integrations/github.py`. Use a persistent `httpx.AsyncClient` constructed in `__init__` with default `Authorization: Bearer {PAT}` and `Accept: application/vnd.github+json` headers. Open a new `AsyncSession` inside each hook that needs to write back to the DB (specifically `on_team_create` and `on_project_create`). All exceptions caught with `logger.exception(...)` — fire_integrations in Phase 7 already prevents propagation, but each hook should defensively catch and log GitHub-specific errors before re-raising so the log context is meaningful.

---

## Project Constraints (from CLAUDE.md)

- **Python only** — org standard; no non-Python tooling in the integration layer
- **httpx ~0.28** — already installed; AsyncClient for GitHub API calls (`>= 0.28.1` installed)
- **pydantic-settings ~2.14** — already pinned in Phase 7 pyproject.toml update; use for config
- **pytest-httpx ~0.36** — already pinned as dev dep in Phase 7; use for all GitHub HTTP mocking
- **Never use `yaml.load` (unsafe)** — not relevant to this phase but standing constraint
- **No auth enforcement in PoC** — GitHub PAT is config, not user auth
- **GSD workflow** — all file changes through execute-phase

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| GitHub team creation | API / Backend | — | Fires from background task after POST /teams commit |
| GitHub repo creation | API / Backend | — | Fires from background task after POST /projects commit |
| GitHub member sync (add/remove) | API / Backend | — | Fires from background task after member add/remove |
| DB writeback (github_team_slug) | API / Backend | Database / Storage | Background task opens new AsyncSession to UPDATE teams SET github_team_slug |
| DB writeback (project_repos row) | API / Backend | Database / Storage | Background task inserts ProjectRepoRecord via new AsyncSession |
| GitHub error handling | API / Backend | — | Caught inside each hook; logged; never propagated to HTTP response |
| PAT config validation | API / Backend | — | IntegrationConfig already handles this in Phase 7; GitHub integration reuses it |
| Test HTTP interception | Test tier | — | pytest-httpx httpx_mock fixture intercepts all httpx calls |

---

## Standard Stack

### Core (zero new packages — all installed by Phase 7)

| Library | Version Installed | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| `httpx` | 0.28.1 [VERIFIED: pip show] | AsyncClient for GitHub API calls — all four endpoints | Already project HTTP client; supports default headers on client init |
| `pytest-httpx` | 0.36.2 [VERIFIED: pip index versions pytest-httpx] | Intercept all httpx calls in tests via `httpx_mock` fixture | Pinned in Phase 7; purpose-built for httpx mocking |
| `pydantic-settings` | 2.14.2 [VERIFIED: pip index versions pydantic-settings] | `IntegrationConfig` already exists from Phase 7; GitHub integration reuses it | No new config class needed |
| `sqlalchemy` | 2.0.50 [VERIFIED: pip show sqlalchemy] | `AsyncSessionLocal()` for DB writeback session inside background task | Already project ORM; session factory at `pecp.persistence.database.AsyncSessionLocal` |

### No New Packages

This phase installs zero new packages. All dependencies were established in Phases 1-7. [VERIFIED: pip show on all four packages above]

**Installation:**
```bash
# Nothing to install — all deps already present
pip install -e ".[dev]"   # ensures pydantic-settings and pytest-httpx are available in venv
```

---

## Package Legitimacy Audit

> Phase 8 installs no new packages. The packages below were audited as part of Phase 7 and are carried forward.

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| `pytest-httpx` | PyPI | published 2026-04-09 (0.36.2) | github.com/Colin-b/pytest_httpx | OK [ASSUMED — well-established, official PyPI maintainer Colin Bounouar; seam returns SUS due to missing weekly-downloads data only] | Approved — used in Phase 7 plan already |
| `httpx` | PyPI | active since 2019 | github.com/encode/httpx | OK [VERIFIED: pip show] | Approved |
| `pydantic-settings` | PyPI | published 2026-06-19 (2.14.2) | github.com/pydantic/pydantic-settings | OK [ASSUMED — official Pydantic org package; seam flags too-new on latest release but package itself is 5+ years old] | Approved |
| `sqlalchemy` | PyPI | active since 2006 | sqlalchemy.org | OK [VERIFIED: pip show] | Approved |

**Packages removed due to [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none with genuine risk. PyPI legitimacy seam returned SUS for pytest-httpx and pydantic-settings due to missing weekly-download data (a tooling gap, not a legitimacy signal). Both packages are from known authoritative maintainers (Colin-b/pytest_httpx and pydantic/pydantic-settings on GitHub). [ASSUMED]

---

## Architecture Patterns

### System Architecture Diagram

```
POST /teams or POST /projects (HTTP request)
         |
         v
[Route Handler] ──── session.commit() ────> [SQLite DB: TeamRecord / ProjectRecord written]
         |
         | background_tasks.add_task(fire_integrations, "on_team_create", snapshot)
         v
[HTTP Response 201 sent to client]
         |
         | (FastAPI BackgroundTasks run after response)
         v
[fire_integrations("on_team_create", team_snapshot)]
         |
         v
[GitHubIntegration.on_team_create(team_snapshot)]
         |
         |──── POST https://api.github.com/orgs/{org}/teams ──> [GitHub API]
         |            returns {"slug": "toxins-research", ...}
         |
         v
[_write_team_slug_to_db(team_id, slug)]  <─── new AsyncSession from AsyncSessionLocal()
         |
         v
[SQLite DB: UPDATE teams SET github_team_slug='toxins-research' WHERE id=...]
```

### Recommended Project Structure

```
src/pecp/
└── integrations/
    ├── __init__.py          # INTEGRATION_REGISTRY, fire_integrations (Phase 7)
    ├── base.py              # IntegrationBase ABC + snapshots (Phase 7)
    ├── noop.py              # NoOpIntegration spy (Phase 7)
    └── github.py            # GitHubIntegration (Phase 8, NEW)

tests/test_integrations/
    ├── __init__.py
    ├── test_base.py         # Phase 7
    ├── test_noop.py         # Phase 7
    ├── test_registry.py     # Phase 7
    ├── test_config.py       # Phase 7
    └── test_github.py       # Phase 8, NEW — all httpx_mock tests for GH-01 through GH-05
```

### Pattern 1: GitHubIntegration Class Structure

**What:** `GitHubIntegration(IntegrationBase)` with an `httpx.AsyncClient` initialized with default headers. Each hook calls the appropriate GitHub endpoint and writes back to DB when needed.

**When to use:** Registered in `load_and_register_integrations()` when both GITHUB_PAT and GITHUB_ORG are set (the stub comment in Phase 7's `__init__.py`).

```python
# Source: httpx official docs (python-httpx.org) + Phase 7 PATTERNS.md IntegrationBase contract
import logging
import httpx
from sqlalchemy.future import select
from pecp.integrations.base import IntegrationBase, MemberSnapshot, ProjectSnapshot, TeamSnapshot
from pecp.integrations import IntegrationConfig

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


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

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        repo_name = f"{team.name}-{project.name}"
        try:
            resp = await self._client.post(
                f"/orgs/{self._org}/repos",
                json={"name": repo_name, "private": False, "auto_init": False},
            )
            resp.raise_for_status()
            repo_url: str = resp.json()["clone_url"]
            await _write_project_repo(project.id, repo_name, repo_url)
        except Exception:
            logger.exception("GitHubIntegration.on_project_create failed for project %s", project.name)
            raise

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        if team.github_team_slug is None:
            logger.warning("on_member_add: team %s has no github_team_slug — skipping", team.name)
            return
        try:
            resp = await self._client.put(
                f"/orgs/{self._org}/teams/{team.github_team_slug}/memberships/{user.user_id}",
                json={"role": "member"},
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("GitHubIntegration.on_member_add failed for user %s", user.user_id)
            raise

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        if team.github_team_slug is None:
            logger.warning("on_member_remove: team %s has no github_team_slug — skipping", team.name)
            return
        try:
            resp = await self._client.delete(
                f"/orgs/{self._org}/teams/{team.github_team_slug}/memberships/{user.user_id}",
            )
            if resp.status_code not in (204, 404):
                resp.raise_for_status()
        except Exception:
            logger.exception("GitHubIntegration.on_member_remove failed for user %s", user.user_id)
            raise
```

### Pattern 2: DB Writeback from Background Task (the Key Design Challenge)

**What:** The `on_team_create` hook receives a `TeamSnapshot` (not an ORM object). It must write the GitHub slug back to `TeamRecord.github_team_slug`. The request-scoped session is closed by the time this runs. The solution is a standalone async helper that opens its own `AsyncSession`.

**When to use:** Any hook that needs to persist data discovered from the GitHub API response (slug, repo URL).

**Critical invariant:** Import `AsyncSessionLocal` as a **module reference**, not as a direct import binding at definition time. This matches the established Phase 3 reload pattern. [ASSUMED — based on Phase 3 decision documented in STATE.md]

```python
# Source: SQLAlchemy 2.x async docs + STATE.md Phase 3 reload pattern
import pecp.persistence.database as _db  # module reference, NOT 'from ... import AsyncSessionLocal'

async def _write_team_slug(team_id: str, slug: str) -> None:
    """Open a fresh AsyncSession to write github_team_slug back to TeamRecord."""
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

### Pattern 3: pytest-httpx Test Pattern for GitHub Calls

**What:** `httpx_mock` fixture auto-injects; `add_response(url=, method=, json=, status_code=)` registers mock responses. Tests with `asyncio_mode="auto"` (already set in pyproject.toml) use plain `async def test_*`.

**When to use:** Every test in `test_github.py` — no real network calls ever in pytest.

```python
# Source: colin-b.github.io/pytest_httpx/ + pyproject.toml asyncio_mode="auto"
from pytest_httpx import HTTPXMock
from pecp.integrations.github import GitHubIntegration
from pecp.integrations import IntegrationConfig

FAKE_CONFIG = IntegrationConfig(GITHUB_PAT="ghp_FAKE", GITHUB_ORG="acme")


async def test_on_team_create_calls_github_and_writes_slug(httpx_mock: HTTPXMock, db_session):
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        json={"slug": "toxins-research", "name": "toxins-research"},
        status_code=201,
    )
    integration = GitHubIntegration(FAKE_CONFIG)
    # ... call on_team_create with a TeamSnapshot whose id matches a real DB row ...


async def test_on_team_create_422_is_non_fatal(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        status_code=422,
        json={"message": "Validation Failed"},
    )
    # fire_integrations wraps in try/except — GH-05: error must not propagate
    # Test: GitHubIntegration.on_team_create raises (fire_integrations catches it)
    # Verify: calling fire_integrations does not raise
```

### Pattern 4: Registering GitHubIntegration in load_and_register_integrations

**What:** Phase 7 left a stub comment `# Phase 8: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))` in `src/pecp/integrations/__init__.py`. Phase 8 replaces this comment with the actual call.

```python
# In src/pecp/integrations/__init__.py load_and_register_integrations():
# Replace the Phase 7 stub comment:
from pecp.integrations.github import GitHubIntegration
INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
```

**Import must be deferred** (inside the function) to avoid circular imports — `GitHubIntegration` imports from `pecp.integrations.base`, which is imported by `pecp.integrations.__init__`. [ASSUMED — deferred import is the standard pattern here]

### Anti-Patterns to Avoid

- **Sharing the request-scoped AsyncSession in the background task**: FastAPI's `SessionDep` session is closed when the route handler returns. Never pass it to a background task function — always open a new session via `AsyncSessionLocal()`.
- **Storing `httpx.AsyncClient` as a module-level singleton**: Client holds the PAT in its Authorization header. Creating it per-request is wasteful. Creating it in `__init__` (per-integration-instance) is correct — the integration instance is created once at startup.
- **Using fine-grained PAT for org-level operations**: Fine-grained PATs return 403 or empty arrays for organization team management endpoints [CITED: docs.github.com/en/rest/teams/members]. Use classic PAT with `write:org` + `repo` scopes for the PoC.
- **Setting `private: True` on repos without verifying org plan**: GitHub requires a paid org plan for private org repos. Default to `private: False` for the PoC demo org [ASSUMED — STATE.md open question, resolved here as: default to public].
- **Calling `resp.raise_for_status()` inside `on_member_add`/`on_member_remove` without handling 404**: A 404 on DELETE memberships (user was already not a member) is safe to ignore. Handle `status_code in (204, 404)` as success for DELETE.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking in tests | Custom mock server / monkeypatching `httpx.AsyncClient` | `pytest-httpx` `httpx_mock` fixture | Purpose-built for httpx; handles async/sync, URL matching, request assertion on teardown |
| GitHub API client | Custom requests wrapper | `httpx.AsyncClient` with default headers | Already in the project; handles async natively; pytest-httpx intercepts it transparently |
| Env config reading | `os.getenv` chains | `pydantic-settings IntegrationConfig` | Already established in Phase 7; validates at startup |
| DB writeback | Passing ORM object to background task | New `AsyncSessionLocal()` session per background task | ORM objects from the request session are detached after session close — accessing them in background task raises `DetachedInstanceError` |
| GitHub slug derivation | Deriving slug from team name with string transforms | Use the `slug` field from the API response | GitHub's slug generation handles Unicode, special chars, length limits — replicating it is error-prone |

**Key insight:** `pytest-httpx` is designed specifically to intercept `httpx` calls at the transport layer — it requires zero changes to production code and zero monkey-patching. The `httpx_mock` fixture automatically activates for any test that declares it as a parameter.

---

## GitHub REST API Reference

### Endpoints Required by This Phase

| Requirement | Method | Path | Request Body | Key Response Fields | Success Status | Error Statuses |
|-------------|--------|------|-------------|---------------------|----------------|----------------|
| GH-02 | POST | `/orgs/{org}/teams` | `{name, privacy}` | `slug` | 201 | 422 (already exists), 403 (forbidden) |
| GH-03 | POST | `/orgs/{org}/repos` | `{name, private, auto_init}` | `clone_url`, `html_url` | 201 | 422 (already exists), 403 |
| GH-04 add | PUT | `/orgs/{org}/teams/{team_slug}/memberships/{username}` | `{role: "member"}` | `state`, `role` | 200 | 422 (org as member), 403 (team sync) |
| GH-04 remove | DELETE | `/orgs/{org}/teams/{team_slug}/memberships/{username}` | none | (empty) | 204 | 403 (team sync) |

[CITED: docs.github.com/en/rest/teams/teams, docs.github.com/en/rest/teams/members]

### Authentication

Classic PAT with scopes: `write:org`, `repo` [CITED: docs.github.com/en/rest/teams/teams]
Header format: `Authorization: Bearer ghp_xxx`
GitHub API version header (recommended): `X-GitHub-Api-Version: 2022-11-28`

Fine-grained PATs **cannot** manage organization teams — they return 403 or empty data for team endpoints [CITED: docs.github.com — fine-grained PAT limitations]. **Use classic PAT for PoC.** [STATE.md open question resolved.]

### Repo Privacy for PoC

`POST /orgs/{org}/repos` with `private: false` (default). Paid org plan required for private org repos. Demo org on free tier must use public repos. [ASSUMED — STATE.md open question, research conclusion: default to public for PoC safety]

---

## Common Pitfalls

### Pitfall 1: DetachedInstanceError from Passing ORM Object to Background Task

**What goes wrong:** Route handler builds a `TeamRecord` ORM object, passes it to the background task, and the background task accesses `team_record.github_team_slug` — which requires the session to lazy-load. But the request-scoped session was closed when the handler returned.

**Why it happens:** SQLAlchemy async sessions don't lazy-load after session close. `expire_on_commit=False` prevents expiry but doesn't keep the session alive across task boundaries.

**How to avoid:** Always pass `TeamSnapshot` (plain dataclass) to hooks, not ORM objects. Phase 7 established this invariant. `on_team_create` receives a `TeamSnapshot` — the hook then opens its own session to write the slug back.

**Warning signs:** `sqlalchemy.orm.exc.DetachedInstanceError` in background task logs.

### Pitfall 2: httpx_mock Fails on Unexpected Requests

**What goes wrong:** A test registers mock responses for `on_team_create` but the GitHubIntegration also makes an unexpected call (e.g., retrying on 422). pytest-httpx raises `httpx.TimeoutException` by default for unregistered requests.

**Why it happens:** `httpx_mock` intercepts ALL httpx requests. Any call not registered with `add_response` causes the test to fail.

**How to avoid:** Register all expected GitHub API calls before calling the integration. For tests that exercise error paths, use `httpx_mock.add_exception(httpx.HTTPStatusError(...))` or `add_response(status_code=422, ...)`.

**Warning signs:** `httpx.TimeoutException` during test execution — means a request was made that wasn't registered.

### Pitfall 3: 422 "Team Already Exists" Must Be Non-Fatal

**What goes wrong:** If `on_team_create` calls `resp.raise_for_status()` on a 422 response, it raises `httpx.HTTPStatusError`. This propagates up through `fire_integrations` (which catches and logs it), so the PECP team creation itself succeeds. BUT: `github_team_slug` is never written to the DB, leaving it NULL.

**Why it happens:** A 422 "already exists" case happens on demo resets or name collisions. The team was already created in GitHub.

**How to avoid:** For 422 responses on POST /teams, attempt a GET to retrieve the existing team slug and write it back. This makes `on_team_create` idempotent. [ASSUMED — defensive design choice, not required by GH-05 spec but prevents permanent null slug]

**Warning signs:** `github_team_slug` remains NULL in DB after a successful GitHub team creation (visible when querying the teams table).

### Pitfall 4: Member Sync with github_team_slug Not Yet Populated

**What goes wrong:** `on_member_add` is called shortly after team creation. If `on_team_create`'s DB writeback hasn't completed (race condition between background tasks), the `TeamSnapshot` passed to `on_member_add` still has `github_team_slug=None`.

**Why it happens:** Phase 7 builds the snapshot before the hook runs. The snapshot's `github_team_slug` reflects the DB value at route-handler time (before the GitHub team was created).

**How to avoid:** In `on_member_add` and `on_member_remove`, re-fetch the `github_team_slug` from the DB inside the background task using a fresh session before calling the GitHub API. Do NOT rely on the snapshot's `github_team_slug` field for member hooks.

**Warning signs:** `on_member_add: team X has no github_team_slug — skipping` warning in logs immediately after team creation.

### Pitfall 5: httpx.AsyncClient Not Closed on Server Shutdown

**What goes wrong:** `httpx.AsyncClient` holds an open connection pool. If `on_team_create` constructs a new client per call, connection pools accumulate. If the server shuts down abruptly, unclosed clients cause `ResourceWarning` in tests.

**Why it happens:** `AsyncClient` must be properly closed via `await client.aclose()` or used as an `async with` context manager.

**How to avoid:** Construct the client once in `GitHubIntegration.__init__` and close it in an `aclose()` method called from the FastAPI lifespan shutdown event. For tests, `httpx_mock` manages the transport — client teardown warnings are suppressed automatically. [ASSUMED — best practice based on httpx documentation]

---

## Runtime State Inventory

> This is a greenfield integration (new file `github.py`, no rename). No runtime state inventory required.

**None — verified:** No stored data, live service config, OS-registered state, secrets, or build artifacts reference `github.py` or `GitHubIntegration` before this phase.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | GitHub API calls | ✓ | 0.28.1 | — |
| `pytest-httpx` | Test mocking | ✓ | 0.36.2 | — |
| `pydantic-settings` | IntegrationConfig | ✓ | 2.14.2 | — |
| `sqlalchemy` (async) | DB writeback | ✓ | 2.0.50 | — |
| GITHUB_PAT (env) | Production/demo use | ✗ (dev env) | — | Integration disabled; pytest uses fake PAT via monkeypatch |
| GITHUB_ORG (env) | Production/demo use | ✗ (dev env) | — | Integration disabled; pytest uses monkeypatch |

**Missing dependencies with no fallback:** None — all code-level dependencies are installed.

**Missing dependencies with fallback:** GITHUB_PAT/GITHUB_ORG not set in dev env — integration disabled via existing Phase 7 `load_and_register_integrations()` guard. Tests inject via monkeypatch.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio 1.4 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `python -m pytest tests/test_integrations/test_github.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GH-01 | `GitHubIntegration` instantiates with config; inherits `IntegrationBase` | unit | `pytest tests/test_integrations/test_github.py::test_github_integration_is_integration_base -x -q` | ❌ Wave 0 |
| GH-02 | `on_team_create` calls `POST /orgs/{org}/teams` and writes slug to DB | unit + integration | `pytest tests/test_integrations/test_github.py::test_on_team_create_creates_team_and_writes_slug -x -q` | ❌ Wave 0 |
| GH-03 | `on_project_create` calls `POST /orgs/{org}/repos` and inserts ProjectRepoRecord | unit + integration | `pytest tests/test_integrations/test_github.py::test_on_project_create_creates_repo_and_writes_url -x -q` | ❌ Wave 0 |
| GH-04 add | `on_member_add` calls PUT memberships endpoint; PECP succeeds even if user not found | unit | `pytest tests/test_integrations/test_github.py::test_on_member_add_syncs_to_github -x -q` | ❌ Wave 0 |
| GH-04 remove | `on_member_remove` calls DELETE memberships endpoint | unit | `pytest tests/test_integrations/test_github.py::test_on_member_remove_syncs_to_github -x -q` | ❌ Wave 0 |
| GH-05 | 422 "already exists" caught and logged; PECP operation unaffected | unit | `pytest tests/test_integrations/test_github.py::test_github_errors_are_non_fatal -x -q` | ❌ Wave 0 |
| GH-05 | Rate limit (429) caught and logged; does not propagate | unit | `pytest tests/test_integrations/test_github.py::test_rate_limit_is_non_fatal -x -q` | ❌ Wave 0 |
| GH-05 | User not found (404) on member add; PECP team membership still exists | unit | `pytest tests/test_integrations/test_github.py::test_member_not_found_is_non_fatal -x -q` | ❌ Wave 0 |
| All | No real GitHub API calls during pytest (httpx intercepted) | infra | `python -m pytest tests/ -x -q` (httpx_mock auto-active for any test declaring it) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_integrations/test_github.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work` — must be 166 + N new tests passing

### Wave 0 Gaps

- [ ] `tests/test_integrations/test_github.py` — covers GH-01 through GH-05
- [ ] `src/pecp/integrations/github.py` — `GitHubIntegration` class + `_write_team_slug` + `_write_project_repo` helpers
- [ ] Phase 7 stub activated: `src/pecp/integrations/__init__.py` — replace stub comment with `INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))`

*(All other infrastructure exists from Phases 1-7)*

---

## Security Domain

> `security_enforcement: true` in config.json. ASVS Level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in PoC |
| V3 Session Management | No | No user sessions |
| V4 Access Control | No | No user roles in PoC |
| V5 Input Validation | Yes | Team/project names are validated by Pydantic before reaching integration hooks |
| V6 Cryptography | No | PAT is a secret in env; not stored in DB; not encrypted at rest (PoC scope) |
| V7 Error Handling | Yes | GitHub errors caught and logged; stack traces not surfaced in HTTP responses |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PAT value logged accidentally | Information Disclosure | Phase 7 test `test_warning_message_does_not_contain_pat_value` asserts PAT never appears in logs; `logger.exception(...)` must not interpolate config values |
| Unhandled 422 leaks GitHub error details to HTTP response | Information Disclosure | All GitHub exceptions caught inside hooks; `fire_integrations` in Phase 7 prevents propagation; HTTP response body never contains GitHub error messages |
| httpx.AsyncClient PAT leaks via redirect | Information Disclosure | httpx strips Authorization header on cross-domain redirects automatically [CITED: python-httpx.org/advanced/authentication]; GitHub API redirects are same-domain |
| repo_name constructed from user-supplied team/project names | Tampering/Injection | Names validated by Pydantic TeamCreate/ProjectCreate models at the route layer; GitHub rejects invalid repo names with 422 (non-fatal per GH-05) |
| Fake PAT in test logs | Information Disclosure | Tests must use placeholder values like "ghp_FAKE" not real PAT values; consistent with Phase 7 `test_config.py` pattern |

### Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-08-01 | Information Disclosure | `logger.exception` in hooks | mitigate | Ensure format strings reference variable NAMES only (team.name, user.user_id) — never interpolate PAT, org, or API token values into log messages |
| T-08-02 | Tampering | repo name from team+project names | accept | Names are Pydantic-validated at route layer; GitHub 422 is non-fatal per GH-05 |
| T-08-03 | Availability | GitHub API rate limit | mitigate | Rate limit errors caught and logged; fire_integrations marks as warning; PoC demo volume is far below GitHub's 5000 req/hr limit |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` (sync) | `httpx.AsyncClient` (async) | ~2021 | Async-first; required for FastAPI async route handlers and BackgroundTasks |
| `responses` library for mocking requests | `pytest-httpx` for mocking httpx | ~2021 | Purpose-built; zero production code changes needed |
| Classic PAT (only option) | Fine-grained PAT (preferred for production) | 2023 | Fine-grained PATs are org-approved but **cannot** manage teams yet; classic PAT required for PoC org team ops |

**Deprecated/outdated:**

- Fine-grained PATs for org team management: Not yet supported for `POST /orgs/{org}/teams` at org level — returns 403 [CITED: docs.github.com fine-grained PAT permissions page]. Classic PAT with `write:org` + `repo` scopes is the working approach for this phase.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Classic PAT with `write:org` + `repo` scopes is required; fine-grained PAT cannot manage org teams | Anti-Patterns, GitHub API Reference | Low — GitHub docs confirm this; worst case is org policy requiring fine-grained PAT approval flow |
| A2 | Default to `private: False` for repo creation (PoC demo uses free org plan) | Anti-Patterns | Low — GitHub returns 422 if private repo attempted on free plan; non-fatal per GH-05 anyway |
| A3 | Deferred import of GitHubIntegration inside `load_and_register_integrations()` avoids circular import | Architecture Patterns | Medium — if Phase 7 impl used a different import structure, this may differ; verify against Phase 7 actual code |
| A4 | `on_member_add`/`on_member_remove` should re-fetch `github_team_slug` from DB rather than rely on snapshot | Common Pitfalls | Medium — if slug is always populated before member add (enforced by Phase 9 service layer order), snapshot value may be sufficient; confirm with Phase 9 planner |
| A5 | `httpx.AsyncClient` constructed in `__init__` (not per-call) is safe for concurrent background tasks | Architecture Patterns | Low — httpx AsyncClient is designed for reuse; explicit aclose() needed at shutdown |
| A6 | pytest-httpx and pydantic-settings are legitimate packages despite `SUS` signal from legitimacy seam | Package Legitimacy Audit | Very Low — both have known public maintainers and GitHub repos |

---

## Open Questions

1. **Classic PAT requirement vs org policy**
   - What we know: Classic PAT with `write:org` + `repo` is the only working approach for org team management today
   - What's unclear: Whether the demo org enforces a "no classic PATs" policy
   - Recommendation: Document `.env.example` with classic PAT requirement; let the Phase 8 executor confirm during demo setup

2. **on_member_add snapshot vs DB re-fetch for github_team_slug**
   - What we know: `TeamSnapshot.github_team_slug` is populated from the DB value at route-handler time, which may be NULL if `on_team_create` hasn't completed its writeback yet
   - What's unclear: Whether Phase 9 service layer will serialize team creation before member add (making this a non-issue)
   - Recommendation: Phase 8 implement defensive DB re-fetch pattern in member hooks; Phase 9 can simplify if service layer ordering is guaranteed

3. **GitHubIntegration.aclose() in lifespan**
   - What we know: httpx.AsyncClient holds a connection pool that should be closed on shutdown
   - What's unclear: Whether the FastAPI lifespan shutdown block in `main.py` should call `integration.aclose()` for registered integrations, or whether this can be deferred
   - Recommendation: Add a no-op `async def aclose(self) -> None` to `IntegrationBase` and implement it in `GitHubIntegration`; wire to lifespan shutdown — this is a Phase 8 addition to the Phase 7 ABC

---

## Sources

### Primary (HIGH confidence)
- Installed package versions: `pip show httpx sqlalchemy` — confirmed 0.28.1 and 2.0.50 respectively
- Phase 7 `07-01-PLAN.md` and `07-PATTERNS.md` — `IntegrationBase` ABC contract, snapshot dataclass definitions, `load_and_register_integrations` stub
- `src/pecp/persistence/models.py` — `TeamRecord.github_team_slug` (nullable), `ProjectRepoRecord` schema

### Secondary (MEDIUM confidence)
- GitHub REST API docs: [docs.github.com/en/rest/teams/teams](https://docs.github.com/en/rest/teams/teams) — POST /orgs/{org}/teams endpoint, 422 behavior, slug field
- GitHub REST API docs: [docs.github.com/en/rest/teams/members](https://docs.github.com/en/rest/teams/members) — PUT/DELETE membership endpoints
- pytest-httpx docs: [colin-b.github.io/pytest_httpx](https://colin-b.github.io/pytest_httpx/) — httpx_mock fixture usage, add_response parameters

### Tertiary (LOW confidence)
- SQLAlchemy async background task pattern — derived from project's existing `database.py` + SQLAlchemy 2.x async docs pattern
- Fine-grained PAT limitations — from GitHub blog and community discussions confirming org team management limitations

---

## Metadata

**Confidence breakdown:**
- GitHub API endpoints: MEDIUM — verified against official GitHub docs
- pytest-httpx usage: MEDIUM — verified against official project docs
- DB writeback pattern: MEDIUM — derived from existing project patterns and SQLAlchemy docs
- PAT scope requirements: LOW — from GitHub docs and community discussions; org policy may vary

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (30 days — GitHub API is stable; pytest-httpx 0.36.x is current)

# Stack Research — PECP

**Project:** Platform Engineering Control Plane (PECP)
**Researched:** 2026-05-27 (v1.0) / 2026-06-24 (v1.1 additions)
**Constraint:** Python backend, org-standard
**Scope:** PoC — demo-able to stakeholders, all backends mocked, no auth

> **Version note (v1.1 additions):** Versions verified against PyPI on 2026-06-24 via `pip index versions`.

---

## v1.1 Addition: GitHub API Integration

This section covers the new libraries and patterns needed **only** for v1.1. The existing stack (FastAPI, SQLAlchemy, httpx, Typer, React) is unchanged and validated.

### GitHub HTTP Client

**Recommendation: raw `httpx.AsyncClient` — no new library required.**

The project already depends on `httpx >=0.28`. A shared `AsyncClient` instance with `default_headers` set for the GitHub Bearer token and `Accept: application/vnd.github+json` is sufficient for all four PECP GitHub operations (create team, create repo, add member, remove member).

**Why not PyGithub 2.9.1:** PyGithub is synchronous — it wraps `requests` under the hood. Using it inside FastAPI async route handlers requires `asyncio.run_in_executor`, which negates the async model and adds thread-pool complexity with no benefit.

**Why not gidgethub 5.4.0:** gidgethub has an httpx backend (`gidgethub.httpx.GitHubAPI`) and is async-native. It adds built-in rate limit tracking and etag caching. However, for PECP's 3–4 write operations (all of which are fire-and-forget, no pagination), these features are overhead not value. gidgethub returns `dict` responses — no typing advantage over raw httpx. It is a good choice if PECP later needs webhook handling or paginated queries.

**Implementation pattern:**

```python
# pecp/integrations/github/client.py
import httpx

GITHUB_API = "https://api.github.com"

def make_github_client(pat: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=GITHUB_API,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0),
    )
```

The client is created at integration startup and closed in a shutdown lifecycle hook, consistent with how the FastAPI app manages the SQLAlchemy engine.

---

### GitHub API Endpoints

All four operations needed for v1.1 requirements:

| Operation | Method | Endpoint | Success Code |
|-----------|--------|----------|--------------|
| Create org team | `POST` | `/orgs/{org}/teams` | 201 |
| Create repo | `POST` | `/orgs/{org}/repos` | 201 |
| Add member to team | `PUT` | `/orgs/{org}/teams/{slug}/memberships/{username}` | 200 |
| Remove member from team | `DELETE` | `/orgs/{org}/teams/{slug}/memberships/{username}` | 204 |

**Required PAT scopes:** `repo` (repository creation) + `admin:org` (team management and member sync). Document this in `.env.example` — a scope-insufficient PAT produces a `403` that can be mistaken for a network error.

**Known error cases to handle (requirement GH-05):**

- `422` on team create: GitHub returns `{"message": "Validation Failed", "errors": [{"message": "Name has already been taken"}]}` — detect and log as idempotent, not as failure.
- `404` on member add/remove: user does not exist in GitHub org — log and return structured error, do not fail the PECP operation.
- `403`: PAT lacks required scope — log the scope error explicitly.
- `429`: Rate limit hit — `x-ratelimit-remaining: 0` in response headers; log with reset time from `x-ratelimit-reset` header.

---

### Environment Variable Configuration

**Recommendation: `pydantic-settings ~2.14` — add to `pyproject.toml` dependencies.**

Current version: **2.14.2**

The project currently uses `os.getenv()` directly (see `persistence/database.py`). For GitHub credentials, `pydantic-settings` is the correct choice because:

1. **Fail-fast validation**: Missing `GITHUB_PAT` or `GITHUB_ORG` raises `ValidationError` at server startup, not at first API call. Silent misconfiguration (empty string, wrong var name) is caught immediately.
2. **Consistent with existing Pydantic v2 stack**: `BaseSettings` is a Pydantic `BaseModel` — the same typing and validation infrastructure already in use.
3. **No additional transitive dependencies**: `python-dotenv` is already in `pyproject.toml`; `pydantic-settings` uses it for `.env` file loading when present.

**Pattern:**

```python
# pecp/integrations/github/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    github_pat: str = ""          # GITHUB_PAT env var
    github_org: str = ""          # GITHUB_ORG env var

    @property
    def is_configured(self) -> bool:
        return bool(self.github_pat and self.github_org)
```

`is_configured` enables the INTG-03 requirement: missing config disables the integration with a logged warning rather than crashing the server. The integration registry checks `is_configured` before registering `GitHubIntegration`.

**`.env.example` additions:**

```
# GitHub Integration (v1.1)
# PAT requires scopes: repo, admin:org
GITHUB_PAT=ghp_...
GITHUB_ORG=your-org-name
```

---

### Testing: Mocking GitHub API Calls

**Recommendation: `pytest-httpx ~0.36` — add to `pyproject.toml` dev dependencies.**

Current version: **0.36.2** — compatible with `httpx >=0.28`.

**Why pytest-httpx over respx:**

Both libraries intercept httpx at the transport level and work with `pytest-asyncio`. pytest-httpx wins on three grounds for this project:

1. **Fixture-based cleanup**: The `httpx_mock` fixture resets state between tests automatically. No decorator plumbing on every test function.
2. **Simpler API for PECP's use case**: `httpx_mock.add_response(method="POST", url="https://api.github.com/orgs/.../teams", json={...}, status_code=201)` is direct. PECP tests are asserting that specific endpoints are called with correct payloads — not building a mock API server.
3. **Exception injection**: `httpx_mock.add_exception(httpx.ConnectError(...))` tests the GH-05 error-handling paths cleanly.

respx (0.23.1) is a solid alternative with a more expressive routing DSL, but the fixture cleanup advantage is decisive for this test suite's existing style (see `tests/conftest.py` — all fixtures, no decorators).

**Pattern for GitHub API tests:**

```python
# tests/test_integrations/test_github.py
import httpx
import pytest
from pytest_httpx import HTTPXMock

from pecp.integrations.github.client import GitHubIntegration

async def test_on_team_create_posts_to_github(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/test-org/teams",
        json={"id": 1, "slug": "payments", "html_url": "https://github.com/orgs/test-org/teams/payments"},
        status_code=201,
    )
    integration = GitHubIntegration(pat="test-pat", org="test-org")
    result = await integration.on_team_create(team_name="payments")
    assert result.github_team_slug == "payments"

async def test_on_team_create_handles_already_exists(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/test-org/teams",
        json={"message": "Validation Failed", "errors": [{"message": "Name has already been taken"}]},
        status_code=422,
    )
    integration = GitHubIntegration(pat="test-pat", org="test-org")
    result = await integration.on_team_create(team_name="payments")
    # Should not raise — GH-05: errors logged, PECP operation succeeds
    assert result is not None
```

**Important**: `pytest-httpx` intercepts **all** httpx calls in a test, including calls the FastAPI `AsyncClient` makes in `conftest.py`. When testing GitHub integration via the API routes (integration tests), use `httpx_mock` to intercept the outbound GitHub calls while `ASGITransport` handles the inbound PECP API calls. These two transports do not conflict.

---

## Updated Supporting Libraries (v1.1 additions only)

| Library | Version | Purpose | Why Added |
|---------|---------|---------|-----------|
| `pydantic-settings` | ~2.14 | Typed env var config for `GITHUB_PAT` / `GITHUB_ORG` | Fail-fast startup validation; fits existing Pydantic v2 stack |
| `pytest-httpx` | ~0.36 (dev) | Mock httpx requests in GitHub integration tests | Fixture-based cleanup; compatible with httpx 0.28 and pytest-asyncio |

**No changes to existing dependencies** — `httpx >=0.28` already in `pyproject.toml` covers all GitHub API HTTP calls.

---

## What NOT to Add (v1.1)

| Technology | Version Available | Reason to Skip |
|------------|-------------------|----------------|
| `PyGithub` | 2.9.1 | Synchronous (`requests`-backed) — blocks FastAPI async handlers |
| `gidgethub` | 5.4.0 | Async-native but unnecessary abstraction for 3–4 write operations; better for webhook/pagination workloads |
| `ghapi` | — | Auto-generated from GitHub OpenAPI spec; verbose API surface for simple use case |
| `respx` | 0.23.1 | Valid alternative to pytest-httpx but decorator-based approach conflicts with project's fixture-only test style |

---

## Existing Stack (validated v1.0 — unchanged)

| Component | Recommendation | Confidence |
|-----------|---------------|------------|
| API Server | FastAPI + Uvicorn | HIGH |
| YAML Parsing | PyYAML `safe_load` | HIGH |
| Validation | Pydantic v2 | HIGH |
| CLI Framework | Typer + Rich | HIGH |
| HTTP Client (CLI + GitHub) | httpx >=0.28 | HIGH |
| Async Tasks (PoC) | FastAPI BackgroundTasks | HIGH |
| Database (PoC) | SQLite + SQLAlchemy 2.x async | HIGH |
| ORM | SQLAlchemy 2.x async | HIGH |
| Migrations | Alembic | HIGH |
| UI Framework | React 19 + Vite 6 | MEDIUM |
| UI Components | shadcn/ui + Radix UI | MEDIUM |
| UI Data Fetching | TanStack Query v5 | HIGH |
| UI Styling | Tailwind CSS v4 | MEDIUM |

## v1.1 Additions Confidence

| Component | Recommendation | Confidence | Notes |
|-----------|---------------|------------|-------|
| GitHub HTTP Client | raw httpx | HIGH | No new dep; existing httpx already in project |
| Env Var Config | pydantic-settings 2.14.2 | MEDIUM | Versions verified on PyPI; integration with existing Pydantic v2 stack is well-established |
| GitHub API Mocking | pytest-httpx 0.36.2 | MEDIUM | Versions verified on PyPI; compatibility with httpx 0.28 confirmed by version coupling |

---

## pyproject.toml Changes Required

```toml
[project]
dependencies = [
    # ... existing deps ...
    "pydantic-settings>=2.14",   # ADD: GitHub integration env var config
]

[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "pytest-httpx>=0.36",        # ADD: GitHub API mock in tests
]
```

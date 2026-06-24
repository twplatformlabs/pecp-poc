# Project Research Summary — PECP v1.1

**Project:** PECP — Platform Engineering Control Plane
**Domain:** GitHub API integration / internal developer platform
**Researched:** 2026-06-24
**Confidence:** MEDIUM-HIGH

## Executive Summary

PECP v1.1 adds a GitHub integration layer on top of the fully-built v1.0 control plane. The work is well-scoped: four GitHub API operations (create org team, create org repo, add team member, remove team member) wired into a new `IntegrationBase` ABC + `INTEGRATION_REGISTRY` dispatcher that mirrors the existing `AdapterBase` / `ADAPTER_REGISTRY` pattern. The existing stack requires no new runtime dependencies beyond `pydantic-settings ~2.14` for env var validation at startup; `pytest-httpx ~0.36` is the only new dev dependency. Raw `httpx.AsyncClient` covers all GitHub operations — no GitHub client library is needed.

The recommended architecture extracts a thin service layer (`TeamService`, `ProjectService`) from route handlers, with hooks firing via `FastAPI.BackgroundTasks` **after** `session.commit()`. This commit-before-hook ordering is the single most critical invariant: hooks fired before commit create ghost GitHub resources whenever the PECP DB write fails. Two schema changes land in one Alembic migration: a nullable `github_team_slug VARCHAR` on `TeamRecord` and a new `ProjectRepo` table (`id`, `project_id`, `repo_name`, `repo_url`, `created_at`).

The primary risks are: (1) hook timing — integration code fired before `commit()` creates ghost GitHub resources with no PECP record; (2) session scope — passing the request-scoped yield-dependency session to a background task causes silent `DetachedInstanceError` since FastAPI closes the session before running background tasks; (3) test isolation — real GitHub API calls in tests cause flaky CI and rate limit exposure. All three have clear preventions that must be enforced during the integration framework phase **before** any `GitHubIntegration` code is written.

---

## Stack Additions (v1.1 only)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Env var config | `pydantic-settings ~2.14` | Fail-fast at startup if `GITHUB_PAT`/`GITHUB_ORG` missing; fits existing Pydantic v2 stack |
| GitHub HTTP client | `httpx.AsyncClient` (existing) | No new dep; PyGithub is sync-only; gidgethub overhead not worth it for 4 operations |
| Test mocking | `pytest-httpx ~0.36` | Fixture-based (`httpx_mock`) intercepts outbound GitHub calls; compatible with existing `ASGITransport` test setup |

**Do not add:** PyGithub (sync), gidgethub (pagination/webhook library, wrong tool), requests.

**GitHub PAT scopes required:** `admin:org` (covers team creation, org repo creation, team membership). Token owner must be an org owner. Document in `.env.example`.

---

## GitHub API Behavior (Table Stakes)

| Operation | Endpoint | Idempotent? | Key Behavior |
|-----------|----------|-------------|--------------|
| Create org team | `POST /orgs/{org}/teams` | **No** — 422 if name taken | Catch 422, GET to retrieve existing slug |
| Create org repo | `POST /orgs/{org}/repos` | **No** — 422 if name taken | Catch 422, GET to retrieve existing URL |
| Add team member | `PUT /orgs/{org}/teams/{slug}/memberships/{username}` | **Yes** | Returns `state: pending` for non-org members (not an error) |
| Remove team member | `DELETE /orgs/{org}/teams/{slug}/memberships/{username}` | **Yes** | Safe to re-run |

**GitHub returns 422 (not 409) for "already exists."** Any idempotency guard checking `status_code == 409` silently fails.

**Membership `state: pending` is success.** When a GitHub username is not yet an org member, GitHub sends an org invitation and returns `state: pending`. PECP treats this as success. True failures are 422 (username does not exist on GitHub) — log warning, skip.

---

## Architecture in One Page

### New Components

```
Route Handler (thin)
  └─ TeamService / ProjectService (new)
        ├─ await session.commit()          ← DB write first
        └─ background_tasks.add_task(      ← hooks after response
             _fire_hooks,
             registry=INTEGRATION_REGISTRY,
             event="on_team_create",
             team=team_snapshot            ← pass snapshot, not ORM object
           )

INTEGRATION_REGISTRY (module-level list, like ADAPTER_REGISTRY)
  └─ [GitHubIntegration(), ...]
        └─ IntegrationBase ABC
              on_team_create(team) → IntegrationResult
              on_project_create(project, team) → IntegrationResult
              on_member_add(user, team) → IntegrationResult
              on_member_remove(user, team) → IntegrationResult
```

### Critical Invariants

- **Hooks always fire after `session.commit()`** — DB write is durable before any external call
- **Background tasks use a fresh session**, not the route's yield-dependency session (closed before BG tasks run)
- **`github_team_url` is derived at read time** (`f"https://github.com/orgs/{org}/teams/{slug}"`), not stored — avoids org-rename consistency risk
- **Integration failures are non-fatal** — logged with context, PECP operation succeeds regardless

### Suggested Build Order

1. Alembic migration `0004` — unblocks everything; no code dependencies
2. `IntegrationBase` ABC + `INTEGRATION_REGISTRY` — pure Python; lock the contract first
3. `GitHubIntegration` — highest-risk; build with `pytest-httpx` mocking from the first commit
4. Service layer + route handler updates — commit→hook dispatch ordering; new member/repo endpoints
5. CLI updates — additive only; depends on stable API contract

---

## Top Pitfalls to Avoid

| # | Pitfall | Phase | Prevention |
|---|---------|-------|-----------|
| GH-1 | Hook fires before `session.commit()` — ghost GitHub resources | 2 | Enforce `commit()` → hook ordering in service layer; test for it |
| GH-2 | Route session passed to background task → `DetachedInstanceError` | 2 | Pass data snapshot (dict/dataclass), not ORM object; open fresh session in hook |
| GH-3 | GitHub 422 treated as unexpected error (not "already exists") | 3 | Check `status_code == 422` and `errors[0]["message"]` contains "already taken"; GET to recover |
| GH-4 | Real GitHub API calls in tests — flaky CI, rate limit exposure | 3 | `pytest-httpx` mocks all outbound calls; no `GITHUB_PAT` in test environment |
| GH-9 | `NOT NULL` on `github_team_slug` Alembic migration breaks existing rows | 1 | Column must be `nullable=True`; SQLite rejects `ADD COLUMN NOT NULL` without DEFAULT |

---

## Open Questions

| Question | Impact | Phase |
|----------|--------|-------|
| GitHub 422 "already exists" error body (`errors[0].message` exact text) | Idempotency handler correctness | Before Phase 3 |
| BackgroundTasks vs yield-dependency teardown order in current FastAPI — write minimal test to confirm | Core architectural invariant | Before Phase 4 |
| Classic PAT vs fine-grained PAT if org policy prohibits classic | Setup instructions for demo | Before Phase 3 |
| `private: true` on org repos — requires paid org plan? | Repo creation `403` on free org | Before Phase 3 |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|-----------|-------|
| Stack additions | HIGH | Raw httpx confirmed; pydantic-settings fit is clear; pytest-httpx fixture pattern matches existing tests |
| GitHub API behavior | MEDIUM | Stable REST API; trained through Aug 2025; live doc verification recommended for 422 error body |
| Architecture pattern | HIGH | Direct codebase analysis; mirrors existing ADAPTER_REGISTRY pattern; BackgroundTasks timing confirmed from FastAPI docs |
| Pitfalls | MEDIUM | FastAPI session/BG task timing confirmed from official docs; GitHub error codes from domain knowledge |

**Overall: MEDIUM-HIGH. The integration is well-scoped and self-contained. Three critical pitfalls (GH-1, GH-2, GH-4) must be addressed architecturally before any GitHub-specific code is written.**

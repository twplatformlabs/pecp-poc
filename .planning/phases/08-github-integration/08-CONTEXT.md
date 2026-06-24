# Phase 08: GitHub Integration - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 delivers `GitHubIntegration(IntegrationBase)` — a concrete subclass of the Phase 7 ABC that makes real httpx calls to the GitHub REST API for team creation (GH-02), repo creation (GH-03), and member sync (GH-04), with structured error handling (GH-05). All GitHub HTTP calls are intercepted in tests via pytest-httpx — no real API calls during pytest.

**What's in:** GH-01, GH-02, GH-03, GH-04, GH-05. `GitHubIntegration` class, DB writeback helpers, pytest-httpx test suite, modification to `IntegrationBase` to add `aclose()`, wiring in lifespan shutdown, activation of the Phase 7 stub in `load_and_register_integrations()`.

**What's not in:** API endpoint changes for member endpoints (Phase 9), CLI command changes (Phase 10), service layer extraction (Phase 9), two-way member sync (v2), repo templates (v2), any real GitHub API calls during pytest.

</domain>

<decisions>
## Implementation Decisions

### 422 Idempotency Strategy
- **D-01:** 422 "already exists" on `POST /orgs/{org}/teams` or `POST /orgs/{org}/repos` is logged and skipped — no GET-fallback to recover the existing slug/repo_url. GH-05 catches the error and the primary PECP operation succeeds. The slug/repo_url stays NULL on 422.
- **D-02:** `DELETE /orgs/{org}/teams/{slug}/memberships/{username}` returning 404 (user already removed) is treated as success — idempotent remove.

### aclose() on IntegrationBase
- **D-03:** Add `async def aclose(self) -> None: pass` to `IntegrationBase` ABC (modifies Phase 7 base class) and implement it in `GitHubIntegration` to close the `httpx.AsyncClient` connection pool.
- **D-04:** Wire `aclose()` into FastAPI lifespan shutdown via a helper that iterates `INTEGRATION_REGISTRY` and awaits each integration's `aclose()`. Called from `src/pecp/api/main.py` lifespan shutdown block.

### Member Hook GitHub Team Slug Resolution
- **D-05:** `on_member_add` and `on_member_remove` re-fetch `github_team_slug` from the DB (via a new `AsyncSession`) rather than relying on the `TeamSnapshot` value. This handles the race condition where `on_team_create`'s DB writeback may not have completed before the member hook fires.
- **D-06:** If `github_team_slug` is still NULL after the DB re-fetch, log a warning and return silently. No retry — PECP membership operation already succeeded.

### Name Sanitization
- **D-07:** Team and project names are sanitized before sending to GitHub API: lowercase + replace spaces with hyphens. This covers the most common naming mismatch without aggressive character stripping.

### Carried Forward from Prior Phases
- **D-03 (Phase 7):** All hook exceptions are caught by `fire_integrations`, logged via `logger.warning(..., exc_info=True)`, and NEVER re-raised. Primary PECP operation succeeds regardless of integration failures.
- **D-04 (Phase 7):** `on_member_add` and `on_member_remove` are implemented on `GitHubIntegration` but are NOT wired into any route in Phase 8. API wiring happens in Phase 9.
- **D-05 (Phase 7):** Commit-before-hook invariant: `background_tasks.add_task(fire_integrations, ...)` is placed strictly AFTER `await session.commit()`.
- **D-06 (Phase 7):** `IntegrationConfig` uses pydantic-settings with empty-string defaults. PAT value is never included in log messages — only the variable name.
- **D-01 (Phase 6):** Unique constraint on `(project_id, repo_name)` prevents duplicate repo creation.

### the agent's Discretion
- Test file organization follows existing `tests/test_integrations/` patterns.
- Exact `httpx.AsyncClient` configuration details (timeouts, retries) are at the agent's discretion.
- Sanitization helper implementation scope (standalone function vs inline) is at the agent's discretion.
- Test mock registration order and specific pytest-httpx fixture usage is at the agent's discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — GH-01 through GH-05 requirement texts
- `.planning/ROADMAP.md` — Phase 8 success criteria (5 items)
- `.planning/PROJECT.md` — constraints and project context

### Phase 7 Contracts (Phase 8 depends on these)
- `.planning/phases/07-integration-hook-framework/07-CONTEXT.md` — Phase 7 decisions (D-01 through D-06)
- `src/pecp/integrations/base.py` — `IntegrationBase` ABC + `TeamSnapshot`, `ProjectSnapshot`, `MemberSnapshot` dataclasses. **Phase 8 adds `aclose()` to the ABC.**
- `src/pecp/integrations/__init__.py` — `INTEGRATION_REGISTRY`, `fire_integrations()`, `IntegrationConfig`, `load_and_register_integrations()` (stub comment at line 61 ready for Phase 8 activation)
- `.planning/phases/07-integration-hook-framework/07-RESEARCH.md` — comprehensive research with code patterns, GitHub API endpoints, test patterns
- `.planning/phases/07-integration-hook-framework/07-PATTERNS.md` — code patterns reference

### Phase 6 Schema (Phase 8 writes to these)
- `src/pecp/persistence/models.py` — `TeamRecord.github_team_slug` (nullable Text column), `ProjectRepoRecord` table
- `.planning/phases/06-data-model-migration/06-CONTEXT.md` — D-01 through D-06 schema decisions

### Research
- `.planning/phases/08-github-integration/08-RESEARCH.md` — comprehensive technical research with code patterns, GitHub API endpoint reference, DB writeback pattern, test patterns, common pitfalls

### Lifespan Integration Point
- `src/pecp/api/main.py` — FastAPI app lifespan. Phase 8 wires `aclose()` into the shutdown block.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IntegrationBase` at `src/pecp/integrations/base.py` — ABC to extend with `aclose()` and implement in `GitHubIntegration`
- `IntegrationConfig` at `src/pecp/integrations/__init__.py:35` — pydantic-settings class for GITHUB_PAT/GITHUB_ORG (reused as-is)
- `fire_integrations()` at `src/pecp/integrations/__init__.py:15` — error-isolated dispatch (catches all hook exceptions)
- `load_and_register_integrations()` at `src/pecp/integrations/__init__.py:48` — stub comment at line 61 ready for Phase 8 activation
- `AsyncSessionLocal` at `src/pecp/persistence/database.py` — session factory for DB writeback in background tasks

### Established Patterns
- **Module-reference import:** `import pecp.persistence.database as _db` — avoids `DetachedInstanceError` from import-time session binding. Use for `_write_team_slug` helper.
- **Background task snapshot pattern:** Pass dataclass snapshots (never ORM objects) to background tasks. Phase 7 established this — Phase 8's `on_team_create` receives `TeamSnapshot`.
- **Deferred import:** Import `GitHubIntegration` inside `load_and_register_integrations()` to avoid circular imports (`GitHubIntegration` imports from `pecp.integrations.base`, which is imported by `pecp.integrations.__init__`).
- **Module-level logger:** `logger = logging.getLogger(__name__)` at module level.

### Integration Points
- `src/pecp/integrations/__init__.py:61` — replace `# Phase 8: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))` stub with actual call
- `src/pecp/integrations/base.py` — add `async def aclose(self) -> None: pass` to `IntegrationBase`
- `src/pecp/api/main.py` — lifespan shutdown block: iterate `INTEGRATION_REGISTRY` and `await integration.aclose()`
- `src/pecp/api/routes/teams.py` — `create_team` route (BackgroundTasks dispatch already wired in Phase 7)
- `src/pecp/api/routes/projects.py` — `create_project` route (BackgroundTasks dispatch already wired in Phase 7)

</code_context>

<specifics>
## Specific Ideas

- `GitHubIntegration` module at `src/pecp/integrations/github.py`
- Test file at `tests/test_integrations/test_github.py`
- Name sanitization: lowercase + spaces→hyphens (`"Toxins Research"` → `"toxins-research"`)
- `on_member_add`: if `github_team_slug` is NULL after DB re-fetch, log warning and return
- `on_member_remove`: treat 404 (user already not a member) as success
- `aclose()` on `IntegrationBase` with no-op default; `GitHubIntegration` overrides to `await self._client.aclose()`
- Lifespan shutdown helper that awaits each registered integration's `aclose()`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-github-integration*
*Context gathered: 2026-06-24*

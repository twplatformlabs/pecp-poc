# Phase 07: Integration Hook Framework - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 delivers the integration hook framework: `IntegrationBase` ABC with optional async lifecycle hooks, snapshot dataclasses, `INTEGRATION_REGISTRY` dispatcher, `fire_integrations()` with per-hook error isolation, `IntegrationConfig` via pydantic-settings, and wiring into FastAPI lifespan + `POST /teams` and `POST /projects` routes via `BackgroundTasks` with the commit-before-hook invariant.

The framework mirrors the existing `AdapterBase`/`ADAPTER_REGISTRY` pattern but diverges in key ways: `INTEGRATION_REGISTRY` is a `list[IntegrationBase]` (not a dict), hooks are optional (no `@abstractmethod`), and errors are caught and logged without propagating.

**What's in:** INTG-01, INTG-02, INTG-03. Two waves: (1) ABC + registry + config + NoOp + unit tests, (2) lifespan wiring + route-level BackgroundTasks dispatch + integration tests.

**What's not in:** Any GitHub API code, CLI changes, or member endpoints — those are Phases 8–10.
</domain>

<decisions>
## Implementation Decisions

### Overall Approach
- **D-01:** Existing 07-01-PLAN.md and 07-02-PLAN.md are approved as-is. Research (07-RESEARCH.md), patterns (07-PATTERNS.md), and validation (07-VALIDATION.md) are all adopted without changes.
- **D-02:** The framework must be contract-locked before any GitHub API code (Phase 8) or route wiring beyond teams/projects is introduced.

### Hook Error Handling
- **D-03:** All hook exceptions are caught by `fire_integrations`, logged via `logger.warning(..., exc_info=True)`, and NEVER re-raised. The primary operation (team/project creation) succeeds regardless of integration failures.

### Member Hooks
- **D-04:** `on_member_add` and `on_member_remove` are defined on `IntegrationBase` as no-op defaults but are NOT wired into any route in this phase. They will be wired in Phase 9 when member endpoints are created.

### Commit-Before-Hook Invariant
- **D-05:** The structural invariant is: `background_tasks.add_task(fire_integrations, ...)` is placed strictly AFTER `await session.commit()` in every route handler. 409 (IntegrityError) and 404 (missing team) paths exit via `raise HTTPException` BEFORE the add_task call, preventing ghost integration calls.

### Integration Configuration
- **D-06:** `IntegrationConfig` uses pydantic-settings with empty-string defaults (`GITHUB_PAT: str = ""`, `GITHUB_ORG: str = ""`) so missing env vars log a warning but never crash the server. PAT value is never included in log messages — only the variable name.

### the agent's Discretion
- Snapshot fields are already defined in RESEARCH.md/PATTERNS.md — no changes requested.
- Test organization (`tests/test_integrations/`) follows existing patterns — no changes requested.
- `pydantic-settings>=2.14` and `pytest-httpx>=0.36` dep pins as specified in plans.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — INTG-01, INTG-02, INTG-03 requirement texts
- `.planning/ROADMAP.md` — Phase 7 success criteria (4 items)

### Existing Plans and Research (approved)
- `.planning/phases/07-integration-hook-framework/07-RESEARCH.md` — comprehensive research with code patterns
- `.planning/phases/07-integration-hook-framework/07-01-PLAN.md` — Wave 1: ABC + registry + config
- `.planning/phases/07-integration-hook-framework/07-02-PLAN.md` — Wave 2: lifespan + route wiring
- `.planning/phases/07-integration-hook-framework/07-PATTERNS.md` — code patterns reference
- `.planning/phases/07-integration-hook-framework/07-VALIDATION.md` — test strategy

### Existing Code (patterns to mirror)
- `src/pecp/adapters/base.py` — AdapterBase ABC pattern (note: IntegrationBase uses NO @abstractmethod)
- `src/pecp/dispatcher.py` — ADAPTER_REGISTRY + dispatch (note: INTEGRATION_REGISTRY is list, not dict)
- `src/pecp/api/routes/resources.py` — BackgroundTasks + commit-before-hook pattern (lines 215-237)
- `src/pecp/persistence/models.py` — TeamRecord, ProjectRecord (snapshot data sources)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pecp/adapters/base.py` — ABC pattern to mirror (but hooks are optional, not @abstractmethod)
- `src/pecp/dispatcher.py` — Module-level registry pattern with iteration + error isolation
- `src/pecp/api/routes/resources.py` — Proven BackgroundTasks + commit-before-hook wiring pattern

### Established Patterns
- **BackgroundTasks after commit:** `session.commit()` → `background_tasks.add_task(...)` — invariant in all route handlers
- **Snapshot pattern:** Data-only dataclasses passed to background tasks (never ORM objects) to avoid DetachedInstanceError
- **Module-level logger:** `logger = logging.getLogger(__name__)` at module level in __init__.py (mirrors dispatcher.py)

### Integration Points
- `src/pecp/api/main.py` — lifespan must call `load_and_register_integrations()` after `init_schema()`
- `src/pecp/api/routes/teams.py` — `create_team` gains BackgroundTasks + snapshot dispatch
- `src/pecp/api/routes/projects.py` — `create_project` gains BackgroundTasks + snapshot dispatch
- Phase 8 will append `GitHubIntegration(cfg)` to INTEGRATION_REGISTRY

</code_context>

<specifics>
No specific requirements beyond what's documented in the approved plans and research.

</specifics>

<deferred>
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-integration-hook-framework*
*Context gathered: 2026-06-24*

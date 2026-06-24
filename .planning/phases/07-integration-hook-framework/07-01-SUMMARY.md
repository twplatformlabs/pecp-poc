---
phase: 07-integration-hook-framework
plan: 01
subsystem: api
tags:
  - integration-framework
  - python-abc
  - pydantic-settings
  - lifecycle-hooks
requires:
  - phase: 01-foundation-contracts
    provides: AdapterBase ABC pattern (mirrored for IntegrationBase)
  - phase: 03-rest-api-core-cli
    provides: FastAPI BackgroundTasks pattern, dispatcher.py module-level registry
  - phase: 06-data-model-migration
    provides: TeamRecord/ProjectRecord models with github_team_slug
provides:
  - IntegrationBase ABC with 4 optional async hooks (on_team_create, on_project_create, on_member_add, on_member_remove)
  - TeamSnapshot, ProjectSnapshot, MemberSnapshot dataclasses for safe data passing to background tasks
  - NoOpIntegration spy for test call recording
  - INTEGRATION_REGISTRY list with fire_integrations dispatcher (per-hook error isolation, logged warnings)
  - IntegrationConfig with pydantic-settings for GITHUB_PAT/GITHUB_ORG env vars (empty-string defaults)
  - load_and_register_integrations startup function (logs warning, leaves registry empty when env unset)
affects:
  - Phase 8 (GitHub integration — INTEGRATION_REGISTRY.append insertion point)
  - Plan 02 (Route wiring — fire_integrations called from team/project/member routes via BackgroundTasks)

tech-stack:
  added:
    - pydantic-settings>=2.14
    - pytest-httpx>=0.36 (dev)
  patterns:
    - IntegrationBase ABC mirrors AdapterBase but with optional (non-@abstractmethod) hooks
    - INTEGRATION_REGISTRY is a list (not dict) — integrations fire on every event, not routed by kind
    - Module-level logger from stdlib (mirrors dispatcher.py)
    - pydantic-settings BaseSettings with empty-string defaults for env vars (server doesn't crash on missing PAT)
    - Test registry isolation via save/restore in try/finally
    - TDD execution: test files committed before implementation (RED→GREEN cycle)

key-files:
  created:
    - src/pecp/integrations/__init__.py
    - src/pecp/integrations/base.py
    - src/pecp/integrations/noop.py
    - tests/test_integrations/__init__.py
    - tests/test_integrations/test_base.py
    - tests/test_integrations/test_noop.py
    - tests/test_integrations/test_registry.py
    - tests/test_integrations/test_config.py
  modified:
    - pyproject.toml

key-decisions:
  - "INTEGRATION_REGISTRY is a list[IntegrationBase], not a dict — integrations fire on every event, no kind-routing needed"
  - "IntegrationBase hooks are NOT @abstractmethod — partial implementations are valid (anti-pattern from RESEARCH.md)"
  - "GITHUB_PAT and GITHUB_ORG have empty-string defaults in IntegrationConfig — prevents server crash on missing env vars"
  - "load_and_register_integrations logs a warning referencing the variable NAME only, never the PAT value (T-07-03)"
  - "pydantic-settings >=2.14 and pytest-httpx >=0.36 pinned (verified available on PyPI at 2.14.2 / 0.36.2)"

patterns-established:
  - "Integration ABC pattern: ABC for type hierarchy, no @abstractmethod on lifecycle hooks, all default to pass"
  - "Registry isolation in tests: save original list, clear, try/finally restore"
  - "TDD per task: RED (create test files) → GREEN (implement source) → optionally REFACTOR (ruff)"

requirements-completed:
  - INTG-01
  - INTG-02
  - INTG-03

duration: 5 min
completed: 2026-06-24
status: complete
---

# Phase 7 Plan 1: Integration Hook Framework — Foundation

**IntegrationBase ABC with optional async lifecycle hooks, NoOpIntegration spy, INTEGRATION_REGISTRY dispatcher with per-hook error isolation, and pydantic-settings IntegrationConfig with missing-env startup warning**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-24T17:47:11Z
- **Completed:** 2026-06-24T17:51:25Z
- **Tasks:** 2 (4 commits: RED→GREEN per task + 1 refactor)
- **Files modified:** 9 (8 created, 1 modified)

## Accomplishments

- **INTG-01:** `IntegrationBase` ABC with 4 optional async hooks (`on_team_create`, `on_project_create`, `on_member_add`, `on_member_remove`) — all default to `pass`, none decorated with `@abstractmethod`
- **INTG-01:** `TeamSnapshot`, `ProjectSnapshot`, `MemberSnapshot` dataclasses with typed fields for safe snapshot passing to background tasks
- **INTG-01:** `NoOpIntegration` spy implementing all 4 hooks, recording `(hook_name, first_arg)` tuples in `self.calls` for test assertions
- **INTG-02:** `INTEGRATION_REGISTRY: list[IntegrationBase]` with `fire_integrations()` dispatcher — iterates in registration order, wraps each hook in try/except, logs WARNING with `exc_info=True` on failure, never re-raises
- **INTG-03:** `IntegrationConfig(BaseSettings)` with `GITHUB_PAT: str = ""` and `GITHUB_ORG: str = ""` — empty-string defaults prevent server crash on missing env
- **INTG-03:** `load_and_register_integrations()` logs WARNING referencing variable names only (no PAT value leak per T-07-03), leaves INTEGRATION_REGISTRY empty when env is unset
- **Dependencies:** `pydantic-settings>=2.14` and `pytest-httpx>=0.36` added to pyproject.toml and installed
- **Tests:** 20 new tests (6 base + 4 noop + 5 registry + 5 config), all passing alongside 166 existing tests (186 total)

## Task Commits

Each task was committed atomically via TDD RED→GREEN cycle:

1. **Task 1, RED:** `test(07-01): add failing tests for IntegrationBase ABC and NoOpIntegration` — `a54ab47`
2. **Task 1, GREEN:** `feat(07-01): implement IntegrationBase ABC, snapshot dataclasses, and NoOpIntegration` — `829141e`
3. **Task 2, RED:** `test(07-01): add failing tests for INTEGRATION_REGISTRY, dispatcher, and config` — `1334dbf`
4. **Task 2, GREEN:** `feat(07-01): implement INTEGRATION_REGISTRY, fire_integrations dispatcher, IntegrationConfig` — `7da1c5a`
5. **Refactor:** `refactor(07-01): organize imports per ruff (I001)` — `a53bf02`

## Files Created/Modified

- `pyproject.toml` — Added `pydantic-settings>=2.14` + `pytest-httpx>=0.36`
- `src/pecp/integrations/__init__.py` — INTEGRATION_REGISTRY, fire_integrations, IntegrationConfig, load_and_register_integrations, module logger
- `src/pecp/integrations/base.py` — IntegrationBase ABC + TeamSnapshot, ProjectSnapshot, MemberSnapshot dataclasses
- `src/pecp/integrations/noop.py` — NoOpIntegration call-recording spy
- `tests/test_integrations/__init__.py` — Package marker
- `tests/test_integrations/test_base.py` — 6 tests for IntegrationBase ABC contract (INTG-01)
- `tests/test_integrations/test_noop.py` — 4 tests for NoOpIntegration spy (INTG-01)
- `tests/test_integrations/test_registry.py` — 5 tests for registry dispatch, isolation, error handling (INTG-02)
- `tests/test_integrations/test_config.py` — 5 tests for IntegrationConfig, env vars, startup warning (INTG-03)

## Decisions Made

- **INTEGRATION_REGISTRY is a list, not dict** — integrations fire on every event (no kind-routing), so a plain list ordered by registration is semantically correct and simpler than the ADAPTER_REGISTRY dict pattern
- **No `@abstractmethod` on hooks** — partial implementations are valid; an integration that only cares about `on_team_create` should not be forced to implement `on_project_create`
- **Empty-string defaults for GITHUB_PAT/GITHUB_ORG** — prevents `ValidationError` crash on server startup when env vars are absent (Pitfall 3 from RESEARCH.md)
- **PAT value never appears in log output** — `load_and_register_integrations` logs the variable name `"GITHUB_PAT"` only, never the value (T-07-03 security mitigation)
- **pydantic-settings for env config** — official Pydantic companion package, now at 2.14.2; not hand-rolling `os.getenv()` chains (per RESEARCH.md "Don't Hand-Roll")

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- **ruff I001 import sorting** — `ruff check` flagged 2 import-ordering issues in test files (stdlib imports before third-party). Auto-fixed with `ruff check --fix` in a separate refactor commit. The ruff lint configuration (`select = ["E4", "E7", "E9", "F", "I"]`) enforces the I rule set including import sorting.

## Known Stubs

- `src/pecp/integrations/__init__.py` line 56: `# Phase 8: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))` — intentional stub marker for the next plan in the phase
- `src/pecp/integrations/__init__.py` `load_and_register_integrations()` — currently only handles the missing-env case; the `if cfg.GITHUB_PAT and cfg.GITHUB_ORG` branch has a comment stub awaiting Phase 8

## Threat Surface Scan

No new threat flags — the module creates no network endpoints, auth paths, or file access patterns. The only security-relevant surface (log hygiene around GITHUB_PAT) is explicitly mitigated per T-07-03 and confirmed by the `test_warning_message_does_not_contain_pat_value` test.

## Self-Check: PASSED

- ✅ `python -m pytest tests/test_integrations/ -x -q` — 20 passed
- ✅ `python -m pytest tests/ -x -q` — 186 passed (166 existing + 20 new)
- ✅ `python -c "from pecp.integrations.base import IntegrationBase; from pecp.integrations.noop import NoOpIntegration; from pecp.integrations import INTEGRATION_REGISTRY, fire_integrations, IntegrationConfig, load_and_register_integrations; print('all symbols importable')"` — ok
- ✅ `ruff check src/pecp/integrations/ tests/test_integrations/` — All checks passed
- ✅ `mypy src/pecp/integrations/` — Success: no issues found in 3 source files

## Next Phase Readiness

- **Plan 02 (Route wiring):** Ready — `fire_integrations` and snapshot classes are importable. Plan 02 will wire `BackgroundTasks` into team/project/member routes.
- **Phase 8 (GitHub integration):** Ready — `IntegrationBase` ABC is locked, `IntegrationConfig` reads env vars, `load_and_register_integrations` has the `INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))` insertion point.
- All 166 prior tests remain green — zero regression risk as no existing source files were modified.

## User Setup Required

None — no external service configuration required. GITHUB_PAT/GITHUB_ORG env vars will be used by Phase 8.

---

*Phase: 07-integration-hook-framework*
*Completed: 2026-06-24*

---
phase: 07-integration-hook-framework
plan: 02
type: execute
wave: 2
subsystem: integrations
tags:
  - background-tasks
  - commit-before-hook
  - fastapi-lifespan
key-files:
  - src/pecp/api/main.py
  - src/pecp/api/routes/teams.py
  - src/pecp/api/routes/projects.py
  - tests/test_integrations/test_registry.py
  - tests/test_integrations/test_config.py
  - tests/test_integrations/test_commit_ordering.py
metrics:
  tests_added: 14
  tests_total: 194
  files_changed: 6
  commits: 3
self_check: PASSED
---

# Plan 07-02 Summary — Wire Integration Framework into Live API

## Objective

Wire the integration framework into the live API: register integrations during FastAPI lifespan startup, add BackgroundTasks to create_team and create_project, build snapshot dataclasses after commit, and schedule fire_integrations after session.commit() to enforce the commit-before-hook invariant.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | a19bdbe | feat(07-02): wire load_and_register_integrations into FastAPI lifespan (INTG-03) |
| 2 | d044df8 | feat(07-02): wire BackgroundTasks + snapshot dispatch into POST /teams (INTG-02) |
| 3 | 6061887 | feat(07-02): wire BackgroundTasks + snapshot dispatch into POST /projects (INTG-02) |

## Deviations

None.

## Self-Check

**PASSED**

- All 3 tasks committed atomically
- 6 files changed, 333 insertions, 5 deletions
- Full test suite: 194 passed
- Ruff: All checks passed
- mypy: No issues found (strict mode)
- App imports: `python -c "from pecp.api.main import app; print('ok')"` → ok
- Commit-before-hook invariant verified via awk structural checks
- 404/409 error paths exit before add_task (proven by integration tests)

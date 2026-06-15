---
phase: 04
slug: teams-projects-deployments
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-14
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.0 + pytest-asyncio |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"` (already set from Phase 3) |
| **Quick run command** | `pytest tests/test_api/ -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api/ -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-W0-teams | W0 | 0 | TEAM-01 | — | POST /teams requires name+owner | integration | `pytest tests/test_api/test_teams.py -x -q` | ❌ W0 | ⬜ pending |
| 04-W0-projects | W0 | 0 | TEAM-02 | — | POST /projects creates project | integration | `pytest tests/test_api/test_projects.py -x -q` | ❌ W0 | ⬜ pending |
| 04-W0-deployments | W0 | 0 | TEAM-03 | — | Deployment audit trail + env filter | integration | `pytest tests/test_api/test_deployments.py -x -q` | ❌ W0 | ⬜ pending |
| 04-W0-softdelete | W0 | 0 | TEAM-03 | — | Soft-delete invisible in list/get | integration | `pytest tests/test_api/test_soft_delete.py -x -q` | ❌ W0 | ⬜ pending |
| 04-W0-cli | W0 | 0 | CLI-05,06,07,08 | — | CLI team/project/deployment commands | unit | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 04-schema | 01 | 1 | TEAM-01,02,03 | — | N/A | integration | `pytest tests/test_api/ -x -q` | ❌ W0 | ⬜ pending |
| 04-teams-api | 02 | 2 | TEAM-01 | — | 409 on duplicate team name | integration | `pytest tests/test_api/test_teams.py -x -q` | ❌ W0 | ⬜ pending |
| 04-projects-api | 02 | 2 | TEAM-02 | — | resource_count via JOIN | integration | `pytest tests/test_api/test_projects.py -x -q` | ❌ W0 | ⬜ pending |
| 04-deployments-api | 02 | 2 | TEAM-03 | — | env filter excludes non-prod resources | integration | `pytest tests/test_api/test_deployments.py -x -q` | ❌ W0 | ⬜ pending |
| 04-softdelete-api | 02 | 2 | TEAM-03 | — | deleted_at set; row stays; FK intact | integration | `pytest tests/test_api/test_soft_delete.py -x -q` | ❌ W0 | ⬜ pending |
| 04-cli-team | 03 | 3 | CLI-05,06 | — | pecp team / team create render panel | unit | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 04-cli-projects | 03 | 3 | CLI-07 | — | pecp projects --json clean array | unit | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 04-cli-deployments | 03 | 3 | CLI-08 | — | pecp deployments sorted newest first | unit | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api/test_teams.py` — stubs for TEAM-01 (create + duplicate 409 + get by name)
- [ ] `tests/test_api/test_projects.py` — stubs for TEAM-02 (create project, list with resource_count)
- [ ] `tests/test_api/test_deployments.py` — stubs for TEAM-03 (audit trail, environment filter)
- [ ] `tests/test_api/test_soft_delete.py` — stubs for D-11 (soft-delete invisible, deleted_at filter on list/get)
- [ ] Extend `tests/test_api/test_cli.py` — team create, team show, projects, deployments, --json flag

*Existing infrastructure (pytest + pytest-asyncio + conftest session_factory fixture) covers all phase requirements — no new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich table output formatting for `pecp team <name>` | CLI-05 | Terminal rendering cannot be asserted in pytest | Run `pecp team payments` and visually confirm key-value panel + members table layout |
| `pecp deployments` sorted newest first in terminal | CLI-08 | Ordering visible only in terminal output | Run `pecp deployments --team payments --environment prod` and confirm timestamps descend |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-14

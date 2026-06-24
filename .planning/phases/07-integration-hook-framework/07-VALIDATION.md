---
phase: 7
slug: integration-hook-framework
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.4.x |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` (`asyncio_mode="auto"`, `pythonpath=["src"]`) |
| **Quick run command** | `python -m pytest tests/test_integrations/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5s quick / ~55s full |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_integrations/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green (≥ 166 + new tests)
- **Max feedback latency:** 55 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | INTG-01 | — | No external input enters hook layer; snapshots built from validated ORM objects | unit | `python -m pytest tests/test_integrations/test_base.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-02 | 01 | 1 | INTG-01 | — | NoOpIntegration records calls without side effects | unit | `python -m pytest tests/test_integrations/test_noop.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-03 | 01 | 1 | INTG-02 | T-07-02 | Hook errors caught in fire_integrations — never surfaced in API response | unit | `python -m pytest tests/test_integrations/test_registry.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-04 | 01 | 1 | INTG-03 | T-07-03 | Missing GITHUB_PAT/ORG logs warning only — PAT value never logged | unit | `python -m pytest tests/test_integrations/test_config.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-05 | 01 | 2 | INTG-02 | T-07-01 | background_tasks.add_task called only after session.commit() success path | integration | `python -m pytest tests/test_integrations/test_commit_ordering.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-06 | 01 | 2 | INTG-01, INTG-02 | — | on_team_create fires after POST /teams; on_project_create fires after POST /projects | integration | `python -m pytest tests/test_integrations/test_registry.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01-07 | 01 | 2 | — | — | All 166 prior tests pass without modification | regression | `python -m pytest tests/ -x -q` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_integrations/__init__.py` — package marker (empty file)
- [ ] `tests/test_integrations/test_base.py` — INTG-01: IntegrationBase ABC can be subclassed; snapshots typed correctly
- [ ] `tests/test_integrations/test_noop.py` — INTG-01: NoOpIntegration implements all 4 hooks, records calls
- [ ] `tests/test_integrations/test_registry.py` — INTG-02: registry dispatch, error isolation, registration order
- [ ] `tests/test_integrations/test_config.py` — INTG-03: missing env logs warning, does not crash, registry stays empty
- [ ] `tests/test_integrations/test_commit_ordering.py` — SC-4: DB row exists when on_team_create fires

*All Wave 0 files are new test stubs — no framework install needed (pytest already installed).*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 8
slug: github-integration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-24
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.4 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python -m pytest tests/test_integrations/test_github.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds (github tests only) / ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_integrations/test_github.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | GH-01, D-03, D-04 | T-08-01 | PAT never in log messages | unit | `python -c "from pecp.integrations.base import IntegrationBase; assert hasattr(IntegrationBase, 'aclose')"` | n/a (modify) | ⬜ pending |
| 08-01-02 | 01 | 1 | GH-01, GH-02, GH-03, GH-04, GH-05 | T-08-01, T-08-02, T-08-03 | Errors caught inside hooks, never propagated | unit | `python -c "from pecp.integrations.github import GitHubIntegration; from pecp.integrations import IntegrationConfig; inst = GitHubIntegration(IntegrationConfig(GITHUB_PAT='ghp_TEST', GITHUB_ORG='testorg')); assert hasattr(inst, 'on_team_create')"` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | GH-01, GH-02, GH-03, GH-05, D-01, D-07 | T-08-01 | Placeholder PAT in tests (ghp_FAKE) | unit | `python -m pytest tests/test_integrations/test_github.py::test_github_integration_is_integration_base tests/test_integrations/test_github.py::test_sanitize_transforms_name -x -q` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | GH-04, GH-05, D-02, D-05, D-06 | T-08-01, T-08-03 | 404 on DELETE treated as success; NULL slug skips gracefully | unit | `python -m pytest tests/test_integrations/test_github.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_integrations/test_github.py` — covers GH-01 through GH-05
- [ ] `src/pecp/integrations/github.py` — `GitHubIntegration` class + DB writeback helpers + sanitization + aclose()

*Existing infrastructure covers all other phase requirements (base.py, __init__.py, main.py are modifications to existing files).*

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

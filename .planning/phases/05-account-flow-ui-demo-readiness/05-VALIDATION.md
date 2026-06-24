---
phase: 05
slug: account-flow-ui-demo-readiness
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-22
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.0 + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_api/test_cli.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_api/test_cli.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-xx-01 | CLI | 1 | CLI-09 | — | Flag input validated by Typer types; no YAML injection on flag-only path | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "awsaccount" -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-02 | CLI | 1 | CLI-10 | — | N/A | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "awsaccount_status" -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-03 | CLI | 1 | CLI-10 | — | Exit code 2 if account not ready | unit (CliRunner + httpx mock) | `python -m pytest tests/test_api/test_cli.py -k "account_login" -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-04 | CLI | 1 | CLI-10 | — | N/A | unit (CliRunner + mock cycle) | `python -m pytest tests/test_api/test_cli.py -k "watch" -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-05 | API | 1 | UI-01 | — | N/A | integration (pytest + ASGI) | `python -m pytest tests/test_api/test_teams.py -k "list" -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-06 | Seed | 2 | ARCH-03 | — | N/A | integration (asyncio + in-memory DB) | `python -m pytest tests/test_seed.py -x` | ❌ Wave 0 | ⬜ pending |
| 05-xx-07 | API | 1 | UI-01 | — | N/A | integration (pytest + ASGI) | `python -m pytest tests/test_api/ -k "resources" -x` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist / Wave 0 disposition:** All implementation tasks carry `<automated>` verify commands. Wave 0 test scaffolds are embedded in each task's `<behavior>` section (TDD pattern) so the executor creates the failing tests before production code in the same task. The Wave 0 Requirements list below is satisfied by Plan 01 Task 1 + Task 2 (CLI + teams test stubs) and Plan 02 Task 1 (seed test stubs). No standalone Wave 0 plan is required because every behavior-adding task has `tdd="true"` and a `<behavior>` block.

---

## Wave 0 Requirements

- [x] `tests/test_api/test_cli.py` — extended in Plan 01 Task 2 (embedded TDD): `test_account_create_*`, `test_account_status_*`, `test_account_login_*`, `test_account_watch_*`, `test_status_awsaccount_subapp_registered`, `test_login_awsaccount_subapp_registered`
- [x] `tests/test_api/test_teams.py` — extended in Plan 01 Task 1 (embedded TDD): `test_list_teams_returns_all`, `test_list_teams_respects_limit`, `test_cors_allows_vite_dev_origin`
- [x] `tests/test_seed.py` — created in Plan 02 (embedded TDD): idempotency + lifecycle state coverage stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| React dashboard renders in browser with shadcn table | UI-02 | Browser UI — no Playwright in PoC | Run `cd ui && npm run dev`, open http://localhost:5173, select a team, verify table renders with status badges |
| `pecp status awsaccount --watch` prints timestamped lines live | CLI-10 | Interactive terminal output | Run `pecp status awsaccount --team customer-product-app --watch`, observe line-per-poll output |
| `eval $(pecp login awsaccount --team customer-product-app)` sets env vars | CLI-10 | Shell eval — not CliRunner testable | Run the eval command in a terminal, run `echo $AWS_ACCESS_KEY_ID` to verify |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (embedded TDD pattern — each task creates its own test stubs)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

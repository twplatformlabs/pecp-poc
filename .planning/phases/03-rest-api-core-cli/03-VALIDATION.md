---
phase: 3
slug: rest-api-core-cli
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8+ with pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` — `asyncio_mode = "auto"`) |
| **Quick run command** | `pytest tests/test_api/ -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api/ -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | CTRL-03 | T-3-02 | UniqueConstraint prevents duplicate resources | integration | `pytest tests/test_api/test_idempotency.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | CTRL-02 | — | BackgroundTasks dispatch transitions status | integration | `pytest tests/test_api/test_dispatch_wiring.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 0 | CTRL-04 | — | Notes append returns 201 with full list | integration | `pytest tests/test_api/test_notes.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | CTRL-01 | T-3-01 | POST /resources returns 202 with resource ID | integration | `pytest tests/test_api/test_routes.py -x -q` | ✅ (extend) | ⬜ pending |
| 3-02-02 | 02 | 1 | CTRL-03 | T-3-02 | Same-spec re-apply returns existing ID, no duplicate | integration | `pytest tests/test_api/test_idempotency.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 1 | CTRL-03 | — | Changed-spec re-apply updates spec_json, re-dispatches | integration | `pytest tests/test_api/test_idempotency.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-04 | 02 | 1 | CTRL-04 | — | Notes appear in GET /resources/{id} response | integration | `pytest tests/test_api/test_routes.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 1 | CLI-01 | — | pecp apply displays correct output for create vs no-op | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ✅ (extend) | ⬜ pending |
| 3-03-02 | 03 | 1 | CLI-02 | — | pecp get outputs Rich table with status badges | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-03 | 03 | 1 | CLI-03 | T-3-03 | pecp delete calls DELETE on correct resource ID after team verify | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-04 | 03 | 1 | CLI-04 | — | pecp status renders table + notes block | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-05 | 03 | 1 | CLI-11 | — | URL resolution: flag → env var → default | unit | `pytest tests/test_api/test_cli.py -x -q` | ✅ (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api/test_idempotency.py` — stubs for CTRL-03 (no-op and update paths)
- [ ] `tests/test_api/test_notes.py` — stubs for CTRL-04 (append note, return 201)
- [ ] `tests/test_api/test_dispatch_wiring.py` — stubs for CTRL-02 (BackgroundTasks triggers dispatch, status transitions)
- [ ] Extend `tests/test_api/test_routes.py` — add GET /resources/{id} and DELETE /resources/{id} stub test cases
- [ ] Extend `tests/test_api/test_cli.py` — add get, status, delete command stub test cases

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pecp status` Rich table renders correctly in terminal | CLI-04 | Terminal rendering not capturable in unit tests | Run `pecp status PECPLambda my-fn --team platform` against live server; verify colored status badge and notes block appear |
| Alembic migration applies cleanly to existing dev DB | CTRL-03 | DB file state depends on prior test runs | Run `alembic upgrade head` against `pecp.db`; verify no OperationalError |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

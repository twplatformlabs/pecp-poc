---
phase: 6
slug: data-model-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.0 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` (`asyncio_mode="auto"`, `pythonpath=["src"]`, `testpaths=["tests"]`) |
| **Quick run command** | `python -m pytest tests/test_migration.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~10s quick / ~55s full |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_migration.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 55 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | DATA-01, DATA-02 | — | ORM model uses `Mapped[]` typed columns; no raw SQL | regression | `python -m pytest tests/ -x -q` | ✅ existing | ⬜ pending |
| 06-01-02 | 01 | 1 | DATA-01, DATA-02, DATA-03 | — | Alembic DDL uses `op.create_table()`/`batch_alter_table()` — no `op.execute(raw_sql)` with interpolated values | schema smoke | `python -m pytest tests/test_migration.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-01-03 | 01 | 2 | DATA-01, DATA-02, DATA-03 | — | Test uses `monkeypatch.setenv` + `tmp_path` to isolate from live pecp.db | schema smoke | `python -m pytest tests/test_migration.py -x -q` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_migration.py` — smoke test covering DATA-01, DATA-02, DATA-03 (upgrade → inspect → downgrade)

*Framework install: not needed — pytest 9.1.0 already installed and configured.*

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

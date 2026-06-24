---
phase: 06-data-model-migration
reviewed: 2026-06-24T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - alembic/versions/0004_add_github_fields.py
  - src/pecp/persistence/models.py
  - tests/test_migration.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-06-24
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files were reviewed: the Alembic migration (`0004_add_github_fields.py`), the updated ORM models (`models.py`), and the new migration smoke test (`test_migration.py`).

The migration file and ORM models are correct and satisfy all locked decisions (D-01 through D-06) and threat mitigations (T-06-01 through T-06-SC). No `op.execute()` raw SQL, no `server_default`, no `ondelete`, correct downgrade order, correct FK target, correct constraint name — all confirmed by static read and runtime verification.

The critical gap is in the test file: `alembic.config.Config("alembic.ini")` uses a hardcoded relative path. pytest does not guarantee the working directory is the project root, so under any non-root invocation the config is not found or the wrong file is read — which risks Alembic falling back to `./pecp.db` (the live database), directly violating threat T-06-02. Two additional warnings concern teardown robustness and an unverified isolation assumption.

---

## Critical Issues

### CR-01: `alembic.config.Config("alembic.ini")` uses a relative path — test isolation can silently break

**File:** `tests/test_migration.py:29`

**Issue:** `cfg = alembic.config.Config("alembic.ini")` resolves `alembic.ini` relative to the process working directory at test runtime. pytest does not guarantee the cwd is the project root — it depends on how the test runner is invoked (e.g., `pytest tests/` from a subdirectory, or from a CI runner that sets its own working directory). When the file is not found, `alembic.config.Config` raises `FileNotFoundError`, which surfaces as a test error rather than a clean failure. More dangerously: if another `alembic.ini` is found in the cwd (or if a future config lookup falls back to a default), Alembic may silently target the live `./pecp.db` rather than the `tmp_path` file. This directly violates threat T-06-02 ("test must not write to live `pecp.db`"). The plan prescribes using `monkeypatch + tmp_path` to guarantee isolation, but that isolation is entirely defeated if Alembic reads the wrong config or cannot locate its script directory.

**Fix:** Resolve `alembic.ini` relative to the project root using `pathlib` based on the location of the test file itself:

```python
import pathlib

# Resolve project root relative to this file, not to cwd
PROJECT_ROOT = pathlib.Path(__file__).parent.parent  # tests/ -> project root

def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    ...
    cfg = alembic.config.Config(str(PROJECT_ROOT / "alembic.ini"))
```

This is cwd-independent and guarantees Alembic always finds the correct config regardless of how pytest is invoked.

---

## Warnings

### WR-01: Teardown `importlib.reload` is not protected — session contamination on assertion failure

**File:** `tests/test_migration.py:85`

**Issue:** The teardown reload (`importlib.reload(db_module)` at line 85) runs unconditionally only if all assertions above it pass. If any assertion raises `AssertionError` before line 85 — for example, the `github_team_slug` column assertion at line 39 — the teardown reload is skipped. At that point `db_module.DATABASE_URL` remains bound to the `tmp_path` async URL. `monkeypatch` will restore the environment variable after the test, but `db_module.DATABASE_URL` is a module-level attribute — it is not automatically restored by monkeypatch. Any test that subsequently imports `pecp.persistence.database` and reads `DATABASE_URL` (or uses the `engine` that was created from it at module load time) may behave unexpectedly. This is the open question acknowledged in RESEARCH.md (OQ-1) but was not addressed in the implementation.

**Fix:** Wrap the test body in `try/finally` to guarantee teardown:

```python
def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "test_migration.db"
    async_url = f"sqlite+aiosqlite:///{db_path}"
    sync_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("PECP_DATABASE_URL", async_url)
    import pecp.persistence.database as db_module
    importlib.reload(db_module)

    try:
        cfg = alembic.config.Config(str(PROJECT_ROOT / "alembic.ini"))
        alembic.command.upgrade(cfg, "head")

        engine = create_engine(sync_url)
        insp = inspect(engine)
        # ... assertions ...
        engine.dispose()

        alembic.command.downgrade(cfg, "-1")

        engine2 = create_engine(sync_url)
        insp2 = inspect(engine2)
        # ... assertions ...
        engine2.dispose()
    finally:
        importlib.reload(db_module)
```

Alternatively, use a pytest `autouse` fixture with `yield` to scope the reload.

---

### WR-02: `importlib.reload(db_module)` does not re-propagate `DATABASE_URL` into `alembic/env.py` if env.py is already in `sys.modules`

**File:** `tests/test_migration.py:26`

**Issue:** `alembic/env.py` executes `from pecp.persistence.database import DATABASE_URL` at module level (line 14 of `env.py`). This creates a local binding `DATABASE_URL` in `env.py`'s namespace — a separate reference copied from `pecp.persistence.database.DATABASE_URL` at import time. Reloading `pecp.persistence.database` rebinds the attribute on that module object, but does NOT update the already-copied reference inside `env.py` if `env.py` has already been executed in this Python process. Alembic re-executes `env.py` as a script (via `ScriptDirectory`) on each `upgrade`/`downgrade` call rather than using it as a cached module, so in practice the reload does work correctly for the Alembic command invocations. However, this is a latent fragility: the correctness depends entirely on Alembic's internal re-execution behavior, which is not part of the public API contract and could change between Alembic versions. RESEARCH.md labels this as assumption A1 with MEDIUM confidence.

**Fix:** Add a guard assertion immediately after the reload to confirm the isolation took effect before calling Alembic commands:

```python
monkeypatch.setenv("PECP_DATABASE_URL", async_url)
import pecp.persistence.database as db_module
importlib.reload(db_module)
# Verify the reload actually bound the test URL before proceeding
assert db_module.DATABASE_URL == async_url, (
    f"Module reload did not rebind DATABASE_URL; got {db_module.DATABASE_URL!r}"
)
```

This converts a silent mis-isolation into an immediate visible failure, and confirms the pattern is working as assumed.

---

## Info

### IN-01: No assertion that the temp database file was actually written to by Alembic

**File:** `tests/test_migration.py:32–34`

**Issue:** The test asserts schema contents after `upgrade()` but does not verify that the temp SQLite file (`db_path`) was created and is non-empty before inspecting it. If Alembic silently targeted a different database (for example, due to the relative-path issue in CR-01, or a future env.py change), the `create_engine(sync_url)` call would open an empty new file and all column/table assertions would fail with `sqlalchemy.exc.OperationalError: no such table: teams` rather than a clear message pointing to the isolation failure. A file-existence check provides an earlier and more diagnostic failure mode.

**Fix:** Add a path existence check after the upgrade call:

```python
alembic.command.upgrade(cfg, "head")

# Verify Alembic wrote to the expected temp file, not to some other target
assert db_path.exists() and db_path.stat().st_size > 0, (
    f"Expected Alembic to write to {db_path} but the file is missing or empty. "
    "Check that alembic.ini and env.py are resolving the correct DATABASE_URL."
)

engine = create_engine(sync_url)
```

---

_Reviewed: 2026-06-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

# Phase 6: Data Model + Migration - Research

**Researched:** 2026-06-24
**Domain:** Alembic migrations, SQLAlchemy 2.x ORM, SQLite schema extension
**Confidence:** HIGH (all claims verified against live codebase and installed library versions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `project_repos` table has a unique constraint on `(project_id, repo_name)` named `uq_project_repos_project_name`. Follows existing naming convention (`uq_projects_team_name`, `uq_teams_name`).
- **D-02:** The unique constraint covers `repo_name` only (not `repo_url`). The repo URL is derived from the name at creation time, so constraining on name is sufficient and non-redundant.
- **D-03:** Column type is `Text()` (nullable, no `server_default`). Matches all non-PK string columns in models.py. `NULL` is the correct sentinel for "not yet integrated with GitHub".
- **D-04:** The column is named `github_team_slug` (not `github_team_url`). The URL is derived at read time from `{org}/{slug}` — not stored.
- **D-05:** Phase 6 introduces `tests/test_migration.py` with a single smoke test: upgrade head → schema inspection → downgrade -1.
- **D-06:** Test file lives at `tests/test_migration.py` — top-level in `tests/`, separate from API/CLI tests.

### Claude's Discretion

- FK constraint on `project_repos.project_id → projects.id`: no explicit `ondelete` — matches the existing pattern.
- Index on `project_repos.project_id`: follow existing pattern — no explicit index on FK columns in current migrations. May add one if Phase 9 query pattern warrants it.
- ORM class name: `ProjectRepoRecord` to match the `*Record` suffix convention, mapped to `project_repos` table.
- Migration batch mode: `batch_alter_table` required for the `teams` column addition (SQLite). New `project_repos` table uses `op.create_table()` directly.

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | `TeamRecord` gains `github_team_slug VARCHAR` (nullable) — populated on team creation when GitHub integration is active | SQLAlchemy 2.x `Mapped[str \| None]` with `Text, nullable=True`; Alembic `batch_alter_table` add_column pattern for SQLite |
| DATA-02 | New `ProjectRepo` table: `id`, `project_id` (FK), `repo_name`, `repo_url`, `created_at` — one project maps to many repos | `op.create_table()` pattern from migration 0003; `UniqueConstraint` naming convention; FK without `ondelete` pattern |
| DATA-03 | Alembic migration adds both schema changes atomically | Single migration file 0004; batch mode for column add; direct `create_table` for new table; working `downgrade()` |
</phase_requirements>

## Summary

Phase 6 is a pure schema migration phase — no application logic, no route changes, no CLI changes. It delivers one Alembic migration file (`alembic/versions/0004_add_github_fields.py`) that makes two schema changes: adding a nullable `github_team_slug` column to the `teams` table, and creating a new `project_repos` table. Both changes are covered by a single test in `tests/test_migration.py`.

The codebase already has a fully established migration pattern in `0003_add_teams_projects_deployments.py`. Every convention for this phase — batch mode for existing table modifications, `op.create_table()` for new tables, FK without `ondelete`, reverse-order `downgrade()`, `Text` for string columns, named unique constraints — is directly modeled on 0003. This is a pattern-replication phase, not a pattern-invention phase.

The one non-obvious technical challenge is test isolation: `alembic/env.py` imports `DATABASE_URL` from `pecp.persistence.database`, which is bound at module import time from `PECP_DATABASE_URL`. The test must control this binding to point Alembic at a temp SQLite file rather than the in-memory or live DB. The correct approach is to monkeypatch `os.environ['PECP_DATABASE_URL']` and use `importlib.reload` on the database module before invoking Alembic commands in-process.

**Primary recommendation:** Copy migration 0003 structure exactly. The column add uses `batch_alter_table`; the new table uses `op.create_table()`. The test uses `monkeypatch` + `importlib.reload` to control the migration target DB, then `sqlalchemy.inspect()` with a sync engine for schema assertions.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema definition (ORM) | Database / Storage | — | `models.py` is the single source of truth for ORM types; migration DDL must match |
| Schema migration | Database / Storage | — | Alembic is the migration tool; no application code involved |
| Migration test | Test layer | Database / Storage | Tests invoke Alembic Python API against isolated temp SQLite; inspection is pure schema query |

## Standard Stack

### Core (all already installed in project)

| Library | Installed Version | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| `alembic` | 1.18.4 [VERIFIED: pip3 show] | Schema migrations | Project-standard; already used for 0000–0003 |
| `sqlalchemy` | 2.0.50 [VERIFIED: pip3 show] | ORM + DDL types in migration ops | Project-standard; DeclarativeBase + Mapped[] already in use |
| `aiosqlite` | installed [VERIFIED: pip3 show] | Async SQLite driver for Alembic env.py | Required for `sqlite+aiosqlite://` URL used by env.py |
| `pytest` | 9.1.0 [VERIFIED: pytest --version] | Test runner | Project-standard; asyncio_mode=auto configured |

### No New Packages Required

Phase 6 installs **zero new packages**. All required libraries are already dependencies in `pyproject.toml`.

## Package Legitimacy Audit

> Phase 6 installs no new packages. The packages below are already installed project dependencies verified via `pip3 show` and already in use across 165 passing tests.

| Package | Registry | Status | Verdict | Disposition |
|---------|----------|--------|---------|-------------|
| `alembic` | PyPI | Already installed v1.18.4; `github.com/sqlalchemy/alembic` | OK | In use — no action needed |
| `sqlalchemy` | PyPI | Already installed v2.0.50; `sqlalchemy.org` | OK | In use — no action needed |
| `aiosqlite` | PyPI | Already installed; async SQLite adapter | OK | In use — no action needed |
| `pytest` | PyPI | Already installed v9.1.0; `github.com/pytest-dev/pytest` | OK | In use — no action needed |

*Note: `gsd-tools` package-legitimacy seam returned `SUS` for all four packages due to `unknown-downloads` (PyPI download count API not available). These are canonical, well-known packages already installed and exercised by the existing test suite. The `SUS` signal is a seam limitation, not a real risk indicator for these packages.*

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious SUS:** none (seam limitation; packages pre-verified by project use)

## Architecture Patterns

### System Architecture Diagram

```
alembic upgrade head / downgrade -1
        │
        ▼
alembic/env.py (exec'd by ScriptDirectory)
  reads DATABASE_URL from pecp.persistence.database
        │
        ▼
alembic/versions/0004_add_github_fields.py
  upgrade():
    batch_alter_table("teams")  ──► ADD COLUMN github_team_slug TEXT NULL
    op.create_table("project_repos")  ──► NEW TABLE with FK + UniqueConstraint
  downgrade():
    op.drop_table("project_repos")
    batch_alter_table("teams")  ──► DROP COLUMN github_team_slug

  ┌──────────────────────────────────────────┐
  │  tests/test_migration.py                 │
  │  monkeypatch PECP_DATABASE_URL           │
  │  importlib.reload(pecp.persistence.database) │
  │  alembic.command.upgrade(cfg, 'head')    │
  │  inspect(sync_engine) → assert schema   │
  │  alembic.command.downgrade(cfg, '-1')    │
  │  inspect(sync_engine) → assert rolled back │
  └──────────────────────────────────────────┘
```

### Recommended Project Structure

No new directories needed. Changes are:

```
alembic/
└── versions/
    └── 0004_add_github_fields.py   # NEW — single migration file

src/pecp/persistence/
└── models.py                        # MODIFIED — add github_team_slug to TeamRecord,
                                     # add ProjectRepoRecord class

tests/
└── test_migration.py               # NEW — upgrade/downgrade smoke test
```

### Pattern 1: Adding a Nullable Column to Existing SQLite Table (batch mode)

**What:** `batch_alter_table` recreates the table under the hood to satisfy SQLite's DDL limitations.
**When to use:** Any time a column is added to an existing table. Required for SQLite.

```python
# Source: alembic/versions/0003_add_teams_projects_deployments.py (verified in codebase)
def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("github_team_slug", sa.Text(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("github_team_slug")
```

**Key detail:** No `server_default` — matches how `deleted_at`, `env`, `notes` were added. `NULL` is the correct value for existing rows.

### Pattern 2: Creating a New Table with FK and Unique Constraint

**What:** `op.create_table()` directly (no batch mode needed for new tables).
**When to use:** All new table creation.

```python
# Source: alembic/versions/0003_add_teams_projects_deployments.py (verified in codebase)
def upgrade() -> None:
    op.create_table(
        "project_repos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("repo_name", sa.Text(), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "repo_name", name="uq_project_repos_project_name"),
    )

def downgrade() -> None:
    op.drop_table("project_repos")
    # batch_alter_table for teams column drop goes after
```

**Key detail:** FK uses bare `ForeignKeyConstraint` with no `ondelete` — matches `team_members → teams.id`, `projects → teams.id`, `deployments → project_id` in migration 0003.

### Pattern 3: SQLAlchemy 2.x ORM Model for New Table

**What:** `DeclarativeBase` + `Mapped[]` typed column pattern.
**When to use:** All new ORM models in this project.

```python
# Source: src/pecp/persistence/models.py (verified in codebase)
class ProjectRepoRecord(Base):
    """ORM model for a project repository link.

    One project maps to many repos (one-to-many via project_id FK).
    Unique constraint on (project_id, repo_name) prevents duplicate repo creation.
    """

    __tablename__ = "project_repos"
    __table_args__ = (
        UniqueConstraint("project_id", "repo_name", name="uq_project_repos_project_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```

**Addition to TeamRecord** (append to existing class body):
```python
# In TeamRecord class — after created_at field
github_team_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Pattern 4: Migration Test with In-Process Alembic

**What:** Use Alembic's Python API with monkeypatched env var to run against a temp SQLite file.
**When to use:** Migration smoke tests — D-05 pattern.

```python
# Source: derived from verified analysis of alembic/env.py import model
# and alembic.command API signatures confirmed in Python environment
import importlib
import os
import pathlib

import alembic.command
import alembic.config
import pytest
from sqlalchemy import create_engine, inspect


def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "test_migration.db"
    async_url = f"sqlite+aiosqlite:///{db_path}"
    sync_url = f"sqlite:///{db_path}"

    # Point Alembic env.py at the temp DB.
    # env.py does 'from pecp.persistence.database import DATABASE_URL' at exec time;
    # reloading the module after patching the env var makes the new URL visible.
    monkeypatch.setenv("PECP_DATABASE_URL", async_url)
    import pecp.persistence.database as db_module
    importlib.reload(db_module)

    cfg = alembic.config.Config("alembic.ini")
    # script_location from alembic.ini ("alembic") is already correct.

    # Upgrade to head (runs all migrations 0000 → 0004)
    alembic.command.upgrade(cfg, "head")

    # Inspect schema — use sync engine (aiosqlite not needed for inspection)
    engine = create_engine(sync_url)
    insp = inspect(engine)

    # Assert github_team_slug added to teams
    col_names = [c["name"] for c in insp.get_columns("teams")]
    assert "github_team_slug" in col_names

    # Assert project_repos table exists with expected columns
    assert "project_repos" in insp.get_table_names()
    repo_col_names = [c["name"] for c in insp.get_columns("project_repos")]
    assert "id" in repo_col_names
    assert "project_id" in repo_col_names
    assert "repo_name" in repo_col_names
    assert "repo_url" in repo_col_names
    assert "created_at" in repo_col_names

    # Assert unique constraint present
    ucs = insp.get_unique_constraints("project_repos")
    uc_names = [uc["name"] for uc in ucs]
    assert "uq_project_repos_project_name" in uc_names

    engine.dispose()

    # Downgrade one step (back to 0003)
    alembic.command.downgrade(cfg, "-1")

    engine2 = create_engine(sync_url)
    insp2 = inspect(engine2)

    # Assert github_team_slug is gone from teams
    col_names_after = [c["name"] for c in insp2.get_columns("teams")]
    assert "github_team_slug" not in col_names_after

    # Assert project_repos table is gone
    assert "project_repos" not in insp2.get_table_names()

    engine2.dispose()
```

### Anti-Patterns to Avoid

- **Using `op.add_column()` directly (non-batch) for SQLite:** SQLite requires batch mode for `ALTER TABLE`. Direct `add_column` outside batch context will fail or silently produce incorrect results. Always use `batch_alter_table` for existing table modifications.
- **Adding `server_default` to nullable "not-yet-set" columns:** The project convention is no `server_default` on nullable sentinel columns (`deleted_at`, `env`, `notes`). Do not add `server_default=""` or `server_default=None` — omit `server_default` entirely.
- **Using `sqlalchemy.url` in alembic.ini for test DB override:** `env.py` bypasses `config.get_main_option('sqlalchemy.url')` and reads `DATABASE_URL` directly from the database module. Setting `sqlalchemy.url` in the config will be ignored. Use `PECP_DATABASE_URL` env var + module reload instead.
- **Using `sqlite+aiosqlite://` URL for schema inspection:** `sqlalchemy.inspect()` requires a sync engine. Use `sqlite:///` (not `sqlite+aiosqlite:///`) for the inspection engine even though Alembic used the async URL to run migrations.
- **Forgetting reverse order in `downgrade()`:** `project_repos` must be dropped before rolling back `teams` column changes. Reverse the `upgrade()` order.
- **Using `:memory:` SQLite for Alembic migration tests:** In-memory SQLite closes when the connection closes; Alembic opens multiple connections across upgrade/downgrade/inspect. Use a file-based temp path (`tmp_path` fixture from pytest).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite column addition | Manual `DROP TABLE / CREATE TABLE / INSERT` DDL | `batch_alter_table` | Alembic handles FK re-creation, constraint naming, data preservation |
| Migration version tracking | Custom version table | Alembic `alembic_version` table | Already managed by Alembic in this project |
| Schema inspection in tests | SQL `PRAGMA table_info` or raw queries | `sqlalchemy.inspect()` | Cross-engine API, returns structured dicts — already works against current pecp.db |
| DB URL isolation in tests | Separate alembic.ini file | `monkeypatch.setenv` + `importlib.reload` | Cleaner, no new files, matches pytest patterns used elsewhere |

**Key insight:** Every pattern in this phase is a direct copy of migration 0003. There is no new technical ground to cover.

## Common Pitfalls

### Pitfall 1: in-memory SQLite fails Alembic multi-connection test

**What goes wrong:** Using `sqlite+aiosqlite:///:memory:` or `sqlite:///:memory:` as the test migration DB causes "no such table" errors on the second connection (after upgrade), because in-memory SQLite state is connection-scoped.

**Why it happens:** Alembic opens multiple connections (one for the migration, one for the version table check, one implicit from inspection). In-memory DB disappears between connections.

**How to avoid:** Use `tmp_path / "test_migration.db"` (file-based). pytest's `tmp_path` fixture provides a unique directory per test that is cleaned up automatically.

**Warning signs:** `OperationalError: no such table: alembic_version` or empty table list after `upgrade()`.

### Pitfall 2: DATABASE_URL import-time binding bypasses cfg.set_main_option

**What goes wrong:** Calling `cfg.set_main_option('sqlalchemy.url', tmp_url)` has no effect because `alembic/env.py` does `from pecp.persistence.database import DATABASE_URL` — this reads the module attribute at env.py exec time, ignoring `config.get_main_option('sqlalchemy.url')`.

**Why it happens:** env.py was written to pull the URL from the application's database module, not from alembic.ini. This is correct for production but requires extra steps in tests.

**How to avoid:** Set `os.environ['PECP_DATABASE_URL'] = async_url` via `monkeypatch.setenv`, then call `importlib.reload(pecp.persistence.database)` before running Alembic commands. The reload re-executes `DATABASE_URL = os.getenv(...)` picking up the new value.

**Warning signs:** Alembic runs migrations against `./pecp.db` (the live DB) instead of the temp file. Verify by checking that `alembic_version` row does NOT appear in `./pecp.db` after the test runs.

### Pitfall 3: Existing tests break if `models.py` is modified incorrectly

**What goes wrong:** Tests use `Base.metadata.create_all()` (not Alembic) to create the test schema. If `ProjectRepoRecord` is added to models.py but its `__table_args__` has a typo or invalid FK reference, `create_all` fails for all tests using the `client` or `db_session` fixture.

**Why it happens:** All 165 existing tests use `Base.metadata.create_all()` via conftest. Adding a new model to `Base` means it gets included in test schema creation.

**How to avoid:** Write and test `ProjectRepoRecord` carefully. Ensure FK target `"projects.id"` is spelled exactly (matches `ProjectRecord.__tablename__ = "projects"`). Run `pytest tests/ -x` after adding the model — if any test breaks, the ORM model is the cause.

**Warning signs:** `OperationalError` or `SAWarning` on test collection; any existing test failing after `models.py` edit.

### Pitfall 4: Downgrade drops `project_repos` after `teams` batch — FK violation risk

**What goes wrong:** If `downgrade()` tries to drop the `github_team_slug` column from `teams` before dropping `project_repos`, and if any FK enforcement runs, the operation may fail.

**Why it happens:** `downgrade()` must reverse `upgrade()` in strict reverse order. Dropping a column first that other operations depend on causes issues.

**How to avoid:** In `downgrade()`, always drop the newest object first: `op.drop_table("project_repos")` then `batch_alter_table("teams")` with `drop_column`. This matches the pattern in 0003 (`drop_table("deployments")` → `drop_table("projects")` → `drop_table("team_members")` → `drop_table("teams")` → `batch_alter_table("resource_records")`).

**Warning signs:** `alembic downgrade -1` fails with an integrity constraint error.

## Code Examples

### Migration file skeleton

```python
# Source: alembic/versions/0003_add_teams_projects_deployments.py (verified in codebase)
"""Add github_team_slug to teams and create project_repos table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add nullable column to existing teams table — batch mode required for SQLite
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("github_team_slug", sa.Text(), nullable=True))

    # 2. Create new project_repos table — no batch mode needed for new tables
    op.create_table(
        "project_repos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("repo_name", sa.Text(), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "repo_name", name="uq_project_repos_project_name"),
    )


def downgrade() -> None:
    # Reverse order — drop newest first
    op.drop_table("project_repos")
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("github_team_slug")
```

### Inspect API for test assertions

```python
# Source: verified against live pecp.db via sqlalchemy 2.0.50 inspect() API
from sqlalchemy import create_engine, inspect

engine = create_engine(sync_url)  # sqlite:///path/to/file.db (sync, not async)
insp = inspect(engine)

# Check column exists
col_names = [c["name"] for c in insp.get_columns("teams")]
assert "github_team_slug" in col_names

# Check table exists
assert "project_repos" in insp.get_table_names()

# Check unique constraint
ucs = insp.get_unique_constraints("project_repos")
uc_names = [uc["name"] for uc in ucs]
assert "uq_project_repos_project_name" in uc_names

# Check FK
fks = insp.get_foreign_keys("project_repos")
assert any(fk["referred_table"] == "projects" for fk in fks)

engine.dispose()
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Manual `ALTER TABLE` SQL strings | `op.batch_alter_table()` in Alembic | Correct SQLite DDL, reversible, version-tracked |
| `declarative_base()` (SQLAlchemy 1.x) | `DeclarativeBase` + `Mapped[]` (SQLAlchemy 2.x) | Type-checked columns, IDE support |
| Raw `alembic upgrade head` subprocess in tests | `alembic.command.upgrade(cfg, 'head')` in-process | Faster tests, better error messages |

**Deprecated/outdated:**

- `declarative_base()`: replaced by `DeclarativeBase` class in SQLAlchemy 2.x. Project already uses 2.x pattern — do not use the old form.
- `Column()` inside `__init__` (imperative mapping): project uses declarative mapping exclusively.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `importlib.reload(pecp.persistence.database)` will cause env.py's `from pecp.persistence.database import DATABASE_URL` to pick up the reloaded module's value when alembic executes env.py | Common Pitfalls / Code Examples | Migration runs against wrong DB; test would touch live pecp.db. Mitigation: verify by asserting temp file exists and has `alembic_version` table after test. |

## Open Questions

1. **Module reload side effects on other tests in the same pytest session**
   - What we know: `importlib.reload(pecp.persistence.database)` rebinds `DATABASE_URL` in the module. `conftest.py` uses `os.environ.setdefault('PECP_DATABASE_URL', 'sqlite+aiosqlite:///:memory:')` which only sets if not already set.
   - What's unclear: If `test_migration.py` runs before other tests and `monkeypatch` does not fully restore the reloaded module state, other tests using `pecp.persistence.database.engine` could be affected.
   - Recommendation: Ensure `test_migration.py` uses `monkeypatch.setenv` (which auto-restores the env var after the test) AND explicitly reload the module again at test teardown (or rely on test ordering). Place `test_migration.py` after API tests in execution order, or add a finalizer to reload the module with the original URL.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.14.6 | — |
| alembic | Migration execution | ✓ | 1.18.4 | — |
| sqlalchemy | ORM + inspection | ✓ | 2.0.50 | — |
| aiosqlite | async SQLite driver in env.py | ✓ | installed | — |
| pytest | Test runner | ✓ | 9.1.0 | — |
| `pecp.db` (live SQLite) | Current migration state at 0003 | ✓ | confirmed via `alembic current` | — |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

All dependencies available. `alembic current` confirms the live DB is at revision 0003 (head). Migration 0004 will extend from exactly this state.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `pythonpath = ["src"]`, `testpaths = ["tests"]` |
| Quick run command | `python -m pytest tests/test_migration.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | `github_team_slug` column on `teams` after upgrade | schema smoke | `python -m pytest tests/test_migration.py -x -q` | ❌ Wave 0 |
| DATA-02 | `project_repos` table with correct columns + FK + UC after upgrade | schema smoke | `python -m pytest tests/test_migration.py -x -q` | ❌ Wave 0 |
| DATA-03 | `upgrade head` succeeds, `downgrade -1` removes both changes | schema smoke | `python -m pytest tests/test_migration.py -x -q` | ❌ Wave 0 |
| (regression) | All 165 existing tests pass after `models.py` changes | regression | `python -m pytest tests/ -x -q` | ✓ existing |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_migration.py -x -q` (fast, < 10s)
- **Per wave merge:** `python -m pytest tests/ -x -q` (full suite, ~55s baseline)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_migration.py` — covers DATA-01, DATA-02, DATA-03

*(Framework install: not needed — pytest already installed and configured)*

## Security Domain

> `security_enforcement: true` in config; `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 6 is schema-only, no auth logic |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No routes |
| V5 Input Validation | no | No user input in migration DDL |
| V6 Cryptography | no | No secrets |
| V1 Architecture (SQL injection) | yes | Alembic DDL uses parameterized ops, not string concatenation |

### Known Threat Patterns for Migration DDL

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unsafe YAML load in config or specs | Tampering | Project already enforces `yaml.safe_load`; not applicable to migration files |
| SQL injection via hand-rolled DDL strings | Tampering | Use Alembic `op.create_table()` / `batch_alter_table()` — never `op.execute(raw_sql)` with interpolated values |
| Migration touching prod DB accidentally in tests | Tampering | Use `monkeypatch.setenv` + `tmp_path` to isolate test DB from `./pecp.db` |

## Sources

### Primary (MEDIUM confidence — verified against codebase)

- `alembic/versions/0003_add_teams_projects_deployments.py` — template for 0004 upgrade/downgrade patterns
- `alembic/env.py` — DATABASE_URL binding model; confirmed import-time resolution
- `src/pecp/persistence/models.py` — `Mapped[]` column patterns, `*Record` naming, `Text` vs `String` convention
- `src/pecp/persistence/database.py` — `PECP_DATABASE_URL` env var resolution
- `alembic.ini` — `script_location = alembic` confirmed
- `pyproject.toml` — installed versions, test configuration

### Secondary (verified via runtime probing)

- `pip3 show alembic sqlalchemy` → versions 1.18.4 / 2.0.50 confirmed
- `python -m alembic current` → live DB at 0003 confirmed
- `python -m alembic history` → full chain 0000→0003 confirmed
- `sqlalchemy.inspect()` against live `pecp.db` → API shape verified
- `alembic.command.upgrade` / `downgrade` signatures introspected in Python
- `pytest --collect-only` → 165 existing tests confirmed passing

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages already installed and in use; versions verified via pip3 show
- Architecture: HIGH — derived entirely from existing codebase patterns; no speculation
- Pitfalls: HIGH — pitfalls identified via direct code inspection and runtime probing, not assumption
- Test isolation approach: MEDIUM — `importlib.reload` pattern is standard Python but has one open question (session ordering side effects)

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (Alembic/SQLAlchemy APIs are stable; short-lived PoC)

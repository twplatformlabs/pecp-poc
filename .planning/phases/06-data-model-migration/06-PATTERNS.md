# Phase 6: Data Model + Migration - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 3 (2 new, 1 modified)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/0004_add_github_fields.py` | migration | batch | `alembic/versions/0003_add_teams_projects_deployments.py` | exact |
| `src/pecp/persistence/models.py` | model | CRUD | `src/pecp/persistence/models.py` (existing classes) | exact |
| `tests/test_migration.py` | test | request-response | `tests/conftest.py` + Alembic Python API | role-match |

---

## Pattern Assignments

### `alembic/versions/0004_add_github_fields.py` (migration, batch)

**Analog:** `alembic/versions/0003_add_teams_projects_deployments.py`

**File header / imports pattern** (lines 1-15):
```python
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
```

**Batch column-add pattern for existing SQLite table** (0003 lines 19-23):
```python
def upgrade() -> None:
    # render_as_batch=True is already set in alembic/env.py — required for SQLite ALTER TABLE
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.add_column(sa.Column("project", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
```
Apply: use `batch_alter_table("teams")` + `batch_op.add_column(sa.Column("github_team_slug", sa.Text(), nullable=True))`. No `server_default` — matches `deleted_at`, `env`, `notes` pattern.

**New table with FK + UniqueConstraint pattern** (0003 lines 47-57):
```python
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("environments", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_projects_team_name"),
    )
```
Apply: use `op.create_table("project_repos", ...)` with bare `ForeignKeyConstraint(["project_id"], ["projects.id"])` (no `ondelete`) and `UniqueConstraint("project_id", "repo_name", name="uq_project_repos_project_name")`.

**Reverse-order downgrade pattern** (0003 lines 75-84):
```python
def downgrade() -> None:
    # Reverse order — satisfy FK constraints
    op.drop_table("deployments")
    op.drop_table("projects")
    op.drop_table("team_members")
    op.drop_table("teams")
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("project")
```
Apply: `op.drop_table("project_repos")` first, then `batch_alter_table("teams")` with `batch_op.drop_column("github_team_slug")`. Drop newest object first — FK dependent table before base table column.

---

### `src/pecp/persistence/models.py` (model, CRUD) — MODIFIED

**Analog:** Same file — existing `ProjectRecord` class (lines 95-114) as nearest model with FK + UniqueConstraint.

**Imports block** (lines 1-17) — no new imports needed; `Text`, `ForeignKey`, `UniqueConstraint`, `Mapped`, `mapped_column`, `datetime`, `timezone` are already imported:
```python
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
```

**Nullable column addition to TeamRecord** — follow `ResourceRecord.deleted_at` (line 52) and `ResourceRecord.env` (line 49) patterns:
```python
# ResourceRecord.env as nullable no-default pattern (line 49):
env: Mapped[str | None] = mapped_column(Text, nullable=True)

# ResourceRecord.deleted_at as nullable no-default datetime pattern (line 52):
deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```
Apply: append to `TeamRecord` after `created_at`:
```python
github_team_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**New ORM class with FK + UniqueConstraint** — follow `ProjectRecord` pattern (lines 95-114):
```python
class ProjectRecord(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("team_id", "name", name="uq_projects_team_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    environments: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```
Apply: new `ProjectRepoRecord` class follows this pattern exactly — `String` for `id` (PK), `String` for FK column, `Text` for all other string columns, `DateTime(timezone=True)` for `created_at`, `__table_args__` tuple with `UniqueConstraint`.

**Column type rules** (enforced throughout models.py):
- PK columns: `String` (not `Text`)
- FK columns: `String` (not `Text`) — see `team_id`, `resource_id`, `project_id`
- All other string columns: `Text` — see `name`, `owner_id`, `role`, `status`, `repo_name`, `repo_url`
- No `relationship()` on any model (none exist in codebase)

---

### `tests/test_migration.py` (test, batch) — NEW

**Analog:** `tests/conftest.py` (test DB setup patterns, lines 1-60) + Alembic Python API

**Test file structure** — follow `conftest.py` for pytest imports; follow Alembic Python API for migration commands:

**Conftest DB setup imports pattern** (conftest.py lines 1-14):
```python
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pecp.persistence.models import Base

os.environ.setdefault("PECP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
```
Apply: `test_migration.py` imports `importlib`, `os`, `alembic.command`, `alembic.config`, `pytest`, `sqlalchemy.create_engine`, `sqlalchemy.inspect`. Uses `monkeypatch.setenv` (not `os.environ.setdefault`) because it must override, not default.

**In-process Alembic invocation pattern** — no existing analog; use Alembic Python API:
```python
import alembic.command
import alembic.config

cfg = alembic.config.Config("alembic.ini")
alembic.command.upgrade(cfg, "head")
alembic.command.downgrade(cfg, "-1")
```
`alembic.ini` has `script_location = alembic` — correct for the project root working directory.

**SQLAlchemy inspect pattern for schema assertions** — sync engine only:
```python
from sqlalchemy import create_engine, inspect

engine = create_engine(sync_url)   # sqlite:///path — NOT sqlite+aiosqlite:///
insp = inspect(engine)
col_names = [c["name"] for c in insp.get_columns("teams")]
ucs = insp.get_unique_constraints("project_repos")
engine.dispose()
```

**Module reload pattern to isolate test DB from live DB** (critical — from RESEARCH.md pitfall analysis):
```python
monkeypatch.setenv("PECP_DATABASE_URL", async_url)
import pecp.persistence.database as db_module
importlib.reload(db_module)
```
`env.py` does `from pecp.persistence.database import DATABASE_URL` at exec time. The reload re-executes `DATABASE_URL = os.getenv(...)` with the monkeypatched value. `monkeypatch.setenv` auto-restores after test completes.

**File-based SQLite for multi-connection test** (conftest.py uses `:memory:` for `db_session` — test_migration.py must NOT do this):
```python
# conftest.py db_session fixture uses :memory: (line 52) — correct for single-connection async tests
engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

# test_migration.py MUST use file-based path — Alembic opens multiple connections
db_path = tmp_path / "test_migration.db"
async_url = f"sqlite+aiosqlite:///{db_path}"
sync_url = f"sqlite:///{db_path}"
```

---

## Shared Patterns

### Nullable Columns with No server_default
**Source:** `src/pecp/persistence/models.py` lines 49, 51, 52
**Apply to:** `TeamRecord.github_team_slug` addition, migration 0004 column spec
```python
# ORM: no server_default, no default= kwarg
env: Mapped[str | None] = mapped_column(Text, nullable=True)
deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

# Migration: no server_default kwarg
sa.Column("project", sa.Text(), nullable=True)
sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
```

### FK Without ondelete
**Source:** `alembic/versions/0003_add_teams_projects_deployments.py` lines 43, 54, 69-70
**Apply to:** `project_repos.project_id` FK in migration 0004 and `ProjectRepoRecord` ORM model
```python
# Migration pattern — bare ForeignKeyConstraint, no ondelete
sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),

# ORM pattern — bare ForeignKey, no ondelete
team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False)
```

### UniqueConstraint Naming Convention
**Source:** `alembic/versions/0003_add_teams_projects_deployments.py` lines 32, 56
**Apply to:** `uq_project_repos_project_name` in migration 0004 and `ProjectRepoRecord.__table_args__`
```python
# Pattern: uq_{tablename}_{col1}_{col2}
sa.UniqueConstraint("name", name="uq_teams_name"),
sa.UniqueConstraint("team_id", "name", name="uq_projects_team_name"),
# New: uq_project_repos_project_name covers (project_id, repo_name)
```

### ORM `__table_args__` with UniqueConstraint
**Source:** `src/pecp/persistence/models.py` lines 32-34, 63, 104
**Apply to:** `ProjectRepoRecord.__table_args__`
```python
__table_args__ = (UniqueConstraint("team_id", "name", name="uq_projects_team_name"),)
# Note: single-element tuple — trailing comma required
```

### `created_at` Default Pattern
**Source:** `src/pecp/persistence/models.py` lines 42-46
**Apply to:** `ProjectRepoRecord.created_at`
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=lambda: datetime.now(timezone.utc),
)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_migration.py` (Alembic in-process pattern) | test | batch | No existing test invokes Alembic Python API directly; conftest uses `Base.metadata.create_all()` instead. RESEARCH.md Pattern 4 provides the full reference. |

---

## Metadata

**Analog search scope:** `alembic/versions/`, `src/pecp/persistence/`, `tests/`
**Files scanned:** 4 (`0003_add_teams_projects_deployments.py`, `models.py`, `conftest.py`, `alembic/env.py` via RESEARCH.md analysis)
**Pattern extraction date:** 2026-06-24

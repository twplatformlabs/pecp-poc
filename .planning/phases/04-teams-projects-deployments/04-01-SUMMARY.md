---
phase: "04"
plan: "01"
subsystem: schema-and-test-scaffolds
tags:
  - schema
  - alembic
  - orm
  - test-scaffolds
  - wave-0
dependency_graph:
  requires:
    - "03-03: REST API core (resources.py, models.py, alembic/0002)"
  provides:
    - "TeamRecord, TeamMemberRecord, ProjectRecord, DeploymentRecord ORM classes"
    - "ResourceRecord.project and ResourceRecord.deleted_at columns"
    - "ResourceMetadata.project nullable Pydantic field"
    - "Alembic migration 0003"
    - "Wave 0 RED test scaffolds for all Phase 4 behaviors"
  affects:
    - "04-02: Team + project routes (reads new ORM classes)"
    - "04-03: Deployment audit + soft-delete + CLI (reads new columns + Wave 0 tests turn green)"
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy 2.x mapped_column with ForeignKey, PrimaryKeyConstraint, UniqueConstraint"
    - "Wave 0 TDD RED scaffolds — tests fail on missing routes, not import errors"
    - "Alembic batch_alter_table for SQLite column additions"
key_files:
  created:
    - alembic/versions/0003_add_teams_projects_deployments.py
    - tests/test_api/test_teams.py
    - tests/test_api/test_projects.py
    - tests/test_api/test_deployments.py
    - tests/test_api/test_soft_delete.py
  modified:
    - src/pecp/persistence/models.py
    - src/pecp/models/resource_spec.py
    - tests/test_api/test_cli.py
decisions:
  - "ForeignKey and PrimaryKeyConstraint imported from sqlalchemy (not sqlalchemy.orm) — matches existing import style"
  - "Ruff auto-fixed import block formatting on models.py (I001) — applied immediately, no behavior change"
  - "Wave 0 CLI tests use catch_exceptions=True (default) for team/project/deployment commands so 'No such command' exit codes are captured cleanly"
metrics:
  duration: "11 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_modified: 7
---

# Phase 04 Plan 01: Schema Foundation and Wave 0 Test Scaffolds Summary

**One-liner:** SQLAlchemy ORM with 4 new tables (teams/team_members/projects/deployments), 2 new ResourceRecord columns (project/deleted_at), Alembic migration 0003, and 31 Wave 0 RED test scaffolds for all Phase 4 behaviors.

## What Was Built

### ORM Extensions (`src/pecp/persistence/models.py`)

Added two new columns to `ResourceRecord`:
- `project: Mapped[str | None]` — nullable Text, stores project name for resource grouping (D-05)
- `deleted_at: Mapped[datetime | None]` — nullable DateTime(timezone=True), enables soft-delete (D-11)

Added four new ORM classes (all inheriting from `Base`):
- `TeamRecord` — `teams` table with `uq_teams_name` unique constraint
- `TeamMemberRecord` — `team_members` table with composite PK `(team_id, user_id)` and FK to `teams.id`
- `ProjectRecord` — `projects` table with `uq_projects_team_name` unique constraint and FK to `teams.id`
- `DeploymentRecord` — `deployments` table (append-only audit log), FK to `resource_records.id` and nullable FK to `projects.id`

### Pydantic Extension (`src/pecp/models/resource_spec.py`)

Added `project: str | None = None` to `ResourceMetadata` after `env` (D-08). Field order: `name`, `team`, `env`, `project`.

### Alembic Migration (`alembic/versions/0003_add_teams_projects_deployments.py`)

Revision `0003`, `down_revision = "0002"`. Upgrade:
1. `batch_alter_table("resource_records")` adds `project` (Text, nullable) and `deleted_at` (DateTime, nullable)
2. `create_table("teams")` with `uq_teams_name`
3. `create_table("team_members")` with composite PK and FK to teams
4. `create_table("projects")` with `uq_projects_team_name` and FK to teams
5. `create_table("deployments")` with FKs to resource_records and projects

Downgrade reverses in FK-safe order: deployments → projects → team_members → teams → drop columns.

### Wave 0 RED Test Scaffolds

| File | Tests | Requirement |
|------|-------|-------------|
| `tests/test_api/test_teams.py` | 5 | TEAM-01 |
| `tests/test_api/test_projects.py` | 5 | TEAM-02 |
| `tests/test_api/test_deployments.py` | 6 | TEAM-03 |
| `tests/test_api/test_soft_delete.py` | 5 | D-11/D-12 |
| `tests/test_api/test_cli.py` (extensions) | 10 | CLI-05/06/07/08 + D-17 |

Total: 31 new tests. All collect without errors. All FAIL intentionally (Wave 0 RED) because the routes and CLI commands they target do not yet exist.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend ORM + ResourceMetadata.project | 0eec969 | models.py, resource_spec.py |
| 2 | Author Alembic migration 0003 | 3358ee9 | 0003_add_teams_projects_deployments.py |
| 3 | Write Wave 0 RED test scaffolds | e5038d9 | test_teams.py, test_projects.py, test_deployments.py, test_soft_delete.py, test_cli.py |

## Verification Results

- `python -c "from pecp.persistence.models import TeamRecord, TeamMemberRecord, ProjectRecord, DeploymentRecord"` — PASSED
- `ResourceMetadata(name='x').project is None` — PASSED
- `alembic upgrade head` on fresh SQLite DB — PASSED (all 4 tables + 2 columns created)
- `alembic downgrade 0002` — PASSED (all changes reversed, verified via PRAGMA)
- `pytest ... --collect-only -q` on 4 new test files — 21 tests collected, no ERROR lines
- New CLI scaffolds collected — 10 tests collected, no errors
- `ruff check` on all 8 files — PASSED
- `mypy src/pecp/persistence/models.py src/pecp/models/resource_spec.py` — PASSED
- `pytest tests/test_api/test_idempotency.py tests/test_api/test_routes.py -x -q` — 12 PASSED (no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff I001 import sort on models.py**
- **Found during:** Task 1 verification
- **Issue:** Adding `ForeignKey` and `PrimaryKeyConstraint` to the SQLAlchemy import caused ruff I001 (unsorted import block)
- **Fix:** `ruff check --fix src/pecp/persistence/models.py` auto-sorted the import block into a multi-line parenthesized form
- **Files modified:** `src/pecp/persistence/models.py`
- **Commit:** 0eec969 (included in the Task 1 commit after the fix was applied)

No other deviations — plan executed as written.

## Known Stubs

None. This plan creates schema and test scaffolds only. No UI-rendering components or data sources were wired.

## Threat Flags

No new security-relevant surface introduced. Plan limited to ORM models, Alembic migration, and test files. No new network endpoints or auth paths added.

## Self-Check: PASSED

- `src/pecp/persistence/models.py` — EXISTS with TeamRecord, TeamMemberRecord, ProjectRecord, DeploymentRecord
- `src/pecp/models/resource_spec.py` — EXISTS with `project: str | None = None`
- `alembic/versions/0003_add_teams_projects_deployments.py` — EXISTS with `revision = "0003"`
- `tests/test_api/test_teams.py` — EXISTS with 5 test functions
- `tests/test_api/test_projects.py` — EXISTS with 5 test functions
- `tests/test_api/test_deployments.py` — EXISTS with 6 test functions
- `tests/test_api/test_soft_delete.py` — EXISTS with 5 test functions
- `tests/test_api/test_cli.py` — EXISTS with 10 new Wave 0 CLI test extensions
- Commits 0eec969, 3358ee9, e5038d9 — all in git log

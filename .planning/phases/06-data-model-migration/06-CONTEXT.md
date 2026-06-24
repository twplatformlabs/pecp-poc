# Phase 6: Data Model + Migration - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 delivers one Alembic migration (0004) that adds two schema changes:
1. `github_team_slug` column (nullable `Text`) on the `teams` table
2. New `project_repos` table with `id`, `project_id` (FK → projects.id), `repo_name`, `repo_url`, `created_at`, and a unique constraint on `(project_id, repo_name)`

Both changes land in a single migration file (`alembic/versions/0004_add_github_fields.py`) with a working `downgrade()`. A new `tests/test_migration.py` smoke test covers upgrade → schema inspection → downgrade.

**What's in:** DATA-01, DATA-02, DATA-03. One migration, two schema changes, one new test file, updated `src/pecp/persistence/models.py`.

**What's not in:** Any application logic, route changes, CLI changes, or integration code — those are Phases 7–10. No seed-data backfill (existing team rows will have `github_team_slug = NULL`, which is correct).

</domain>

<decisions>
## Implementation Decisions

### ProjectRepo Unique Constraint
- **D-01:** `project_repos` table has a unique constraint on `(project_id, repo_name)` named `uq_project_repos_project_name`. Follows existing naming convention (`uq_projects_team_name`, `uq_teams_name`). Calling `pecp project repo add <repo-name>` twice against the same project will fail at the DB layer — prevents duplicate GitHub repo creation in Phase 8.
- **D-02:** The unique constraint covers `repo_name` only (not `repo_url`). The repo URL is derived from the name at creation time, so constraining on name is sufficient and non-redundant.

### github_team_slug Column Type
- **D-03:** Column type is `Text()` (nullable, no `server_default`). Matches all non-PK string columns in models.py (`owner_id`, `name`, `role`, `repo_name`, etc.). `NULL` is the correct sentinel for "not yet integrated with GitHub" — matches how `deleted_at` was added in migration 0003 (nullable, no default). Existing team rows will have `NULL` after the migration.
- **D-04:** The column is named `github_team_slug` (not `github_team_url`). The URL is derived at read time from `{org}/{slug}` — not stored — to avoid org-rename staleness (decision logged in STATE.md).

### Migration Test Coverage
- **D-05:** Phase 6 introduces `tests/test_migration.py` with a single smoke test that:
  1. Runs `alembic upgrade head` against a fresh temp SQLite file
  2. Inspects the schema via `sqlalchemy.inspect()` — asserts `github_team_slug` column exists on `teams` and `project_repos` table exists with the expected columns
  3. Runs `alembic downgrade -1` and asserts both are gone
  This covers all three success criteria in one test and sets the pattern for Phases 7–10.
- **D-06:** Test file lives at `tests/test_migration.py` — top-level in `tests/`, separate from API/CLI tests. Easy to find and extend.

### Claude's Discretion
- FK constraint on `project_repos.project_id → projects.id`: no explicit `ondelete` — matches the existing pattern where no FK in the codebase (team_members, projects, deployments) specifies `ondelete`. Default DB behavior (RESTRICT) applies.
- Index on `project_repos.project_id`: follow existing pattern — no explicit index on FK columns in current migrations. Claude may add one if the query pattern in Phase 9 warrants it.
- ORM class name: `ProjectRepoRecord` to match the `*Record` suffix convention, mapped to `project_repos` table.
- Migration batch mode: `batch_alter_table` required for the `teams` column addition (SQLite). New `project_repos` table uses `op.create_table()` directly (no batch mode needed for table creation).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing schema and migration history
- `src/pecp/persistence/models.py` — current ORM models. Phase 6 adds `github_team_slug` to `TeamRecord` and new `ProjectRepoRecord` class. Follow existing `Mapped[]` typed column pattern.
- `alembic/versions/0003_add_teams_projects_deployments.py` — the most recent migration. Follow its patterns: `batch_alter_table` for existing table modifications, `op.create_table()` for new tables, reverse-order `downgrade()`, no `ondelete` on FK constraints.
- `alembic/env.py` — `render_as_batch=True` is already set (required for SQLite batch mode). No changes needed here.

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 6 covers DATA-01, DATA-02, DATA-03. Read each requirement text before planning.
- `.planning/ROADMAP.md` — Phase 6 success criteria (4 items):
  1. Existing team records not broken (github_team_slug is nullable)
  2. ProjectRepo row can be inserted with project_id FK, repo_name, repo_url, created_at
  3. Migration runs from scratch and rolls back cleanly
  4. All existing tests pass without modification
- `.planning/PROJECT.md` — constraints (Python, SQLite + SQLAlchemy async, Alembic migrations).

### Prior phase outputs (stable contracts Phase 6 builds on)
- `.planning/phases/04-teams-projects-deployments/04-CONTEXT.md` — D-01 to D-03 define TeamRecord schema; D-04 to D-06 define ProjectRecord schema. Phase 6 extends both without modifying existing columns.
- `.planning/phases/05-account-flow-ui-demo-readiness/05-CONTEXT.md` — confirms no migration was added in Phase 5 (Alembic is at 0003 going into Phase 6).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TeamRecord` at `src/pecp/persistence/models.py:45` — add `github_team_slug: Mapped[str | None] = mapped_column(Text, nullable=True)` here. No `relationship()` needed.
- Migration 0003 upgrade pattern (`alembic/versions/0003_add_teams_projects_deployments.py:18–84`) — exact template for the new migration: `batch_alter_table` for column addition, `op.create_table()` for new table, named constraints, reverse `downgrade()`.

### Established Patterns
- **Column types:** All non-PK string columns use `Text()`. PK columns use `String()`. Phase 6 follows this exactly.
- **Nullable columns:** No `server_default` on nullable columns that represent "not yet set" (`deleted_at`, `env`, `notes`). `github_team_slug` follows suit.
- **Unique constraint naming:** `uq_{tablename}_{column1}_{column2}` — `uq_project_repos_project_name` matches the convention.
- **FK without cascade:** `team_members → teams.id`, `projects → teams.id`, `deployments → project_id` all use bare `ForeignKeyConstraint` with no `ondelete`. Match this pattern.
- **Async ORM:** All models use `DeclarativeBase` + `Mapped[]` typed columns (SQLAlchemy 2.x async style). `ProjectRepoRecord` must follow the same pattern.
- **Test DB setup:** Existing tests use `Base.metadata.create_all()` — NOT Alembic. The new `test_migration.py` is the first to invoke Alembic directly. It uses a separate temp SQLite file to avoid interfering with the in-memory test DB.

### Integration Points
- Phase 6 has no API or CLI integration — it is schema-only. Downstream phases consume:
  - `TeamRecord.github_team_slug` (Phase 7+): set after GitHub team creation
  - `ProjectRepoRecord` (Phase 9): queried to populate `repos` list in `GET /teams/{name}` response
- `alembic/versions/0003_add_teams_projects_deployments.py` is the `down_revision` for 0004.

</code_context>

<specifics>
## Specific Ideas

- Migration file: `alembic/versions/0004_add_github_fields.py`. Docstring: "Add github_team_slug to teams and create project_repos table."
- `tests/test_migration.py` structure:
  ```python
  def test_migration_upgrade_and_downgrade(tmp_path):
      db_url = f"sqlite:///{tmp_path}/test_migration.db"
      # run upgrade head
      # inspect: teams has github_team_slug column, project_repos table exists
      # run downgrade -1
      # inspect: github_team_slug gone, project_repos table gone
  ```
  Uses `alembic.config.Config`, `alembic.command.upgrade`, `alembic.command.downgrade`, and `sqlalchemy.inspect`.
- `ProjectRepoRecord` table name: `project_repos` (SQLAlchemy `__tablename__ = "project_repos"`).
- `uq_project_repos_project_name` constraint covers `(project_id, repo_name)` — same DDL style as `sa.UniqueConstraint("team_id", "name", name="uq_projects_team_name")` in 0003.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-data-model-migration*
*Context gathered: 2026-06-24*

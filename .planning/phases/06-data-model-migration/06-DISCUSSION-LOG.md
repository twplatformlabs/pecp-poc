# Phase 6: Data Model + Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 6-data-model-migration
**Areas discussed:** ProjectRepo uniqueness, github_team_slug column type, Migration test coverage

---

## ProjectRepo Uniqueness

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — unique on (project_id, repo_name) | Matches existing naming pattern. Guards against duplicate GitHub repo creation in Phase 8. | ✓ |
| No unique constraint | Allow multiple entries with the same repo_name per project. | |

**User's choice:** Yes — unique on (project_id, repo_name)
**Notes:** Constraint name `uq_project_repos_project_name`. Covers `repo_name` only (not `repo_url`) — URL is derived from name so constraining both would be redundant.

### repo_name only vs. both columns

| Option | Description | Selected |
|--------|-------------|----------|
| repo_name only | Human-facing identifier; matches the GitHub slug used in Phase 8. | ✓ |
| Both repo_name and repo_url | Belt-and-suspenders, but redundant since URL is derived from name. | |

---

## github_team_slug Column Type

| Option | Description | Selected |
|--------|-------------|----------|
| Text() — match existing pattern | All non-PK string columns in models.py use Text(). Consistent. | ✓ |
| String() — match spec's "VARCHAR" wording | Would be the only non-PK column using String(). Inconsistent. | |

**User's choice:** Text() — match existing pattern

### server_default behavior

| Option | Description | Selected |
|--------|-------------|----------|
| NULL — no server_default | Existing rows get NULL = "not yet integrated." Same pattern as deleted_at. | ✓ |
| Empty string '' | Requires checking for NULL and '' in queries. Semantically incorrect. | |

**User's choice:** NULL — no server_default

---

## Migration Test Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add a migration smoke test | Single test: upgrade head → inspect schema → downgrade -1. Proves DDL is correct. | ✓ |
| No — manual verification only | Matches current state. Success criterion #3 untested in CI. | |

**User's choice:** Yes — add a migration smoke test

### Test scope

| Option | Description | Selected |
|--------|-------------|----------|
| upgrade → inspect schema → downgrade | Full round-trip with schema inspection. Catches no-op migrations. | ✓ |
| upgrade + downgrade only | No schema inspection — would pass for a no-op migration. | |

**User's choice:** upgrade → inspect schema → downgrade

### Test file location

| Option | Description | Selected |
|--------|-------------|----------|
| tests/test_migration.py | Top-level in tests/, dedicated to migration tests. Discoverable and extensible. | ✓ |
| Alongside existing persistence tests | Less discoverable. | |

**User's choice:** tests/test_migration.py

---

## Claude's Discretion

- FK `ondelete` on `project_repos.project_id`: no explicit `ondelete` — matches all existing FK constraints
- Index on `project_repos.project_id`: follow existing pattern (no explicit FK indices); planner may add if Phase 9 query analysis warrants it
- ORM class name: `ProjectRepoRecord` (matches `*Record` suffix convention)
- Migration batch mode: `batch_alter_table` for `teams` column addition (SQLite requirement); `op.create_table()` for `project_repos` (no batch needed)

## Deferred Ideas

None — discussion stayed within phase scope.

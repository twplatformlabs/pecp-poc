# Phase 4: Teams, Projects, Deployments - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 4-teams-projects-deployments
**Areas discussed:** Team & member storage, Project-resource binding, Deployment query model, Team CLI output design

---

## Team & member storage

| Option | Description | Selected |
|--------|-------------|----------|
| Two tables: teams + team_members | Standard relational model — matches SQLAlchemy async ORM pattern | ✓ |
| One teams table with JSON members | Like the notes pattern on ResourceRecord — simpler but not queryable | |
| No teams table | Team is just a string on resources; no DB table | |

**User's choice:** Two tables: teams + team_members

---

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: id, name, created_at | Keeps team record clean | |
| With description: id, name, description, created_at | Adds free-text description | |
| With owner_id: id, name, owner_id, created_at | Owner as first-class field | ✓ |

**User's choice:** With owner_id: id, name, owner_id, created_at

---

| Option | Description | Selected |
|--------|-------------|----------|
| From RequestContext.user_id | Whoever calls create becomes owner | |
| --owner flag on the create command | Explicit — PE can create teams on behalf of engineers | ✓ |

**User's choice:** --owner flag on the create command

---

| Option | Description | Selected |
|--------|-------------|----------|
| Fail with a clear error (409 Conflict) | Team names are unique identifiers; duplicates are almost always mistakes | ✓ |
| Idempotent — no-op if already exists | Consistent with pecp apply but could hide errors | |

**User's choice:** Fail with a clear error (409 Conflict)

---

## Project-resource binding

| Option | Description | Selected |
|--------|-------------|----------|
| project column on ResourceRecord | Like env — nullable Text column, follows established pattern | ✓ |
| Separate project_resources join table | More queryable but adds 2 extra tables | |
| Project inferred from env column only | No explicit project tracking | |

**User's choice:** project column on ResourceRecord

---

| Option | Description | Selected |
|--------|-------------|----------|
| Own table: projects (id, team_id, name, environments, created_at) | Structured metadata, supports pecp projects listing | ✓ |
| Just a string label — no projects table | Simpler, fewer migrations | |

**User's choice:** Own table: projects (id, team_id, name, environments, created_at)

---

| Option | Description | Selected |
|--------|-------------|----------|
| JSON Text column: environments | Same pattern as notes and activity_log | ✓ |
| Separate project_environments table | More queryable but adds a third table | |

**User's choice:** JSON Text column: environments (e.g., ["dev", "prod"])

---

| Option | Description | Selected |
|--------|-------------|----------|
| spec.metadata.project field in YAML | Declared in resource YAML | |
| --project flag on pecp apply | Explicit at CLI level | |
| Either — YAML takes precedence, flag overrides | Flexible | ✓ |

**User's choice:** Either — YAML spec.metadata.project takes precedence, --project flag overrides

---

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit CLI command: pecp project create | Project record exists before resources reference it | ✓ |
| Implicit only — project created on first resource apply | No create command needed | |

**User's choice:** Explicit CLI: pecp project create <name> --team <team> --env dev,prod

---

| Option | Description | Selected |
|--------|-------------|----------|
| Name, target environments, resource count | Matches TEAM-02 requirement | |
| Name, target environments, resource count, project ID | Includes UUID for reference in future commands | ✓ |
| Name and resource count only | Simpler output | |

**User's choice:** Name, target environments, resource count, project ID

---

## Deployment query model

| Option | Description | Selected |
|--------|-------------|----------|
| Filtered resource list — GET /resources?env= | Reuses existing route, no new entity | |
| Separate Deployment records per resource+environment | Full audit trail of all resource changes | ✓ |

**User's choice:** Separate Deployment records — compliance audit trail
**Notes:** User clarified: deployment record created on every explicit resource mutation (apply create, apply update, delete). Tracked for compliance to ensure a record of all changes made to resources.

---

| Option | Description | Selected |
|--------|-------------|----------|
| id, resource_id, environment, status, deployed_at | Basic fields | |
| id, resource_id, project_id, environment, status, deployed_at | Also links to project | ✓ |

**User's choice:** id, resource_id, project_id, environment, status, deployed_at

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — change_type: create | update | delete | Enables filtering by change type for compliance review | ✓ |
| No — all events are just deployments | No change_type field | |

**User's choice:** Yes — change_type: create | update | delete

---

| Option | Description | Selected |
|--------|-------------|----------|
| Resource name, kind, change_type, status, timestamp (newest first) | Full audit log view | ✓ |
| One row per resource — latest deployment only | Cleaner but loses history | |

**User's choice:** Audit log view: resource name, kind, change_type, status, deployed_at sorted newest first

---

| Option | Description | Selected |
|--------|-------------|----------|
| Soft-delete resources — mark as deleted but keep row | FK always resolves; filter by deleted_at IS NULL | ✓ |
| Hard-delete, deployment record keeps resource_name as string snapshot | FK-free but duplicates data | |
| Hard-delete, deployment FK nullable (SET NULL on delete) | FK goes NULL on delete — loses resource link | |

**User's choice:** Soft-delete — ResourceRecord gets deleted_at column

---

| Option | Description | Selected |
|--------|-------------|----------|
| No visible change — CLI says 'deleted', resource disappears from pecp get | Transparent soft-delete | ✓ |
| Show 'Deleted' status badge in pecp get | Clutters normal resource list | |

**User's choice:** No visible change — soft-delete is implementation detail

---

## Team CLI output design

| Option | Description | Selected |
|--------|-------------|----------|
| Two-section output: team metadata panel + members table | Follows pecp status pattern | |
| Single members table with metadata as header row | One Rich table | |
| Members table only, metadata on request | Minimal output | |

**User's choice (free-text):** "if this were a json output, then pecp team would show the team metadata as the top keys, and then a key called members which is an array list of the team members + their attributes."

---

| Option | Description | Selected |
|--------|-------------|----------|
| Rich terminal layout: team metadata at top, members table below | Consistent with pecp status Rich output | ✓ |
| Raw JSON output by default | Machine-readable JSON | |

**User's choice:** Rich terminal output as default, --json flag for override

---

| Option | Description | Selected |
|--------|-------------|----------|
| --json flag applies to all data commands | Single consistent pattern across all commands | ✓ |
| --json on just pecp team for now | Add to other commands later | |

**User's choice:** All commands that show data (get, status, projects, deployments, team)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata: name, owner, created_at. Members: user_id, role, joined_at | Minimal | |
| Metadata: name, owner, team_id, created_at. Members: user_id, role, joined_at | Includes team UUID | ✓ |

**User's choice:** Metadata panel: name, owner, team_id, created_at. Members table: user_id, role, joined_at

---

| Option | Description | Selected |
|--------|-------------|----------|
| Confirmation message with team ID: 'Team X created (id: abc-123)' | Simple success line | |
| Full team panel immediately after create | Same output as pecp team <name> | ✓ |

**User's choice:** Full team panel immediately after create

---

## Claude's Discretion

- API route design: `POST /teams`, `GET /teams/{name}` (by name, not UUID). `POST /projects`, `GET /projects?team=`. `GET /deployments?team=&environment=`.
- `team_members` composite PK on `(team_id, user_id)` — no separate ID column needed for PoC.
- `pecp project create` success output: confirmation line with project ID (not full panel — projects are simpler than teams).
- Alembic migration numbering follows Phase 3 convention.
- change_type values use lowercase strings: `create`, `update`, `delete`.

## Deferred Ideas

- PE approval flow for team creation (v2 — TEAM-V2-01).
- Team-configurable RBAC / policy engine (v2 — TEAM-V2-02).
- `pecp team add-member` command — post-creation member management.
- `pecp deployments` filtering by change_type (`--type delete`).
- `pecp status awsaccount --watch` polling — Phase 5.
- UI dashboard — Phase 5.

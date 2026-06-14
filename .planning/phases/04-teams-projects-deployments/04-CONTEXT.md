# Phase 4: Teams, Projects, Deployments - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Add multi-team support to the control plane: team creation and member management, project grouping of resources scoped to environments, a compliance-driven deployment audit trail, and 5 new CLI commands (`pecp team create`, `pecp team <name>`, `pecp project create`, `pecp projects --team`, `pecp deployments --team --environment`).

**What's in:** `teams` and `team_members` DB tables + Alembic migration. `projects` DB table + `project` column on `ResourceRecord` + `deleted_at` soft-delete column on `ResourceRecord` + `deployments` DB table + Alembic migration. REST API routes for teams, projects, deployments. CLI commands for all of the above. `--json` flag on all data-returning CLI commands. `pecp apply` gains optional `--project` flag.

**What's not in:** PE approval flow for team creation (v2 scope). Team-configurable RBAC (v2). Real member directory lookup (user_id is a free-text string in PoC). `--watch` on deployments. AWS account provisioning, UI dashboard — Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Team Data Model
- **D-01:** Two DB tables: `teams` (id UUID4, name Text NOT NULL UNIQUE, owner_id Text NOT NULL, created_at DateTime) and `team_members` (team_id FK → teams.id, user_id Text NOT NULL, role Text NOT NULL [owner|contributor], joined_at DateTime). Standard SQLAlchemy async ORM pattern — no embedded JSON for members.
- **D-02:** `POST /teams` requires `name` and `owner` in the request body. The `--owner` flag on `pecp team create <name> --owner alice` is explicit — the CLI caller specifies who the owner is rather than inferring from RequestContext. Owner is also auto-added as the first `team_members` row with `role="owner"`.
- **D-03:** Team names are unique. `POST /teams` returns `409 Conflict` if the name already exists — no idempotency. Team creation is a deliberate one-time act.

### Project Data Model
- **D-04:** Separate `projects` table: id UUID4, team_id FK → teams.id, name Text NOT NULL, environments Text NOT NULL (JSON-serialized list, e.g. `["dev", "staging", "prod"]`), created_at DateTime. Unique constraint on `(team_id, name)`.
- **D-05:** `project` column added to `ResourceRecord` as nullable Text. Stores the project name (not FK). Allows resources to reference projects by name without FK integrity overhead in PoC.
- **D-06:** `pecp project create <name> --team <team> --env dev,staging,prod` creates a project explicitly. Projects are not auto-created on first resource apply.
- **D-07:** `pecp apply` gains an optional `--project <name>` flag. Resolution order: `spec.metadata.project` from YAML, overridden by `--project` flag if provided. If neither is set, `resource.project` remains null.
- **D-08:** `ResourceMetadata` gains a nullable `project: str | None = None` field (alongside the existing `env` field pattern).

### Deployment Audit Model
- **D-09:** Separate `deployments` table: id UUID4, resource_id FK → resource_records.id, project_id FK → projects.id (nullable — resource may have no project), environment Text (nullable — mirrors resource.env at event time), status Text NOT NULL, change_type Text NOT NULL (values: `create`, `update`, `delete`), deployed_at DateTime NOT NULL.
- **D-10:** A deployment record is created on every explicit resource mutation: `pecp apply` (create or update path) and `pecp delete`. This is a compliance audit trail, not just a "deployed to env" tracker.
- **D-11:** `ResourceRecord` gains a `deleted_at` column (DateTime, nullable). `DELETE /resources/{id}` sets `deleted_at` rather than removing the row. All `GET /resources` queries and `pecp get` filter to `WHERE deleted_at IS NULL`. The FK from `deployments.resource_id` always resolves to a valid row.
- **D-12:** Soft-delete is invisible to CLI users — `pecp delete` still prints "deleted", resource disappears from `pecp get`. No "Deleted" status badge shown.

### CLI Commands
- **D-13:** `pecp team create <name> --owner <user_id>` — on success, renders the full team panel (same as `pecp team <name>`) immediately. No separate confirmation-then-query step.
- **D-14:** `pecp team <name>` — Rich output: top section shows team metadata as key-value pairs (name, owner, team_id, created_at), followed by a Rich members table (user_id, role, joined_at). Mirrors the `pecp status` pattern of panel + structured section.
- **D-15:** `pecp projects --team <team>` — Rich table columns: project_id, name, environments, resource_count (JOIN count). `--json` returns array of `{id, name, environments, resource_count}`.
- **D-16:** `pecp deployments --team <team> --environment <env>` — Rich table columns: resource_name, kind, change_type, status, deployed_at (sorted newest first). Audit log view — multiple rows per resource expected. `--json` returns array of deployment records.
- **D-17:** `--json` flag available on all data-returning commands: `pecp get`, `pecp status`, `pecp projects`, `pecp deployments`, `pecp team`. Returns structured JSON to stdout. Rich output remains the default.

### Claude's Discretion
- API routes for teams: `POST /teams`, `GET /teams/{name}`. Team lookup by name (not UUID) since name is the human-facing identifier.
- API routes for projects: `POST /projects`, `GET /projects?team=<name>`. Projects listed by team.
- API route for deployments: `GET /deployments?team=<name>&environment=<env>`. Returns deployment records joined with resource data for name/kind.
- Alembic migration numbering: follows Phase 3 migration naming convention.
- `team_members` has no separate ID primary key — `(team_id, user_id)` composite PK is sufficient for PoC.
- `pecp project create` on success: prints a confirmation line with project ID (not a full panel — projects are simpler than teams).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 outputs (stable contracts Phase 4 builds on)
- `src/pecp/persistence/models.py` — `ResourceRecord` ORM. Phase 4 adds `project` (Text, nullable) and `deleted_at` (DateTime, nullable) columns via Alembic migration. All existing columns unchanged.
- `src/pecp/models/resource_spec.py` — `ResourceMetadata`. Phase 4 adds `project: str | None = None` field (alongside existing `env`).
- `src/pecp/api/routes/resources.py` — existing `GET /resources`, `POST /resources`, `GET /resources/{id}`, `DELETE /resources/{id}`, `POST /resources/{id}/notes`. Phase 4 modifies DELETE to soft-delete, modifies POST to write deployment record, and extends GET to filter `WHERE deleted_at IS NULL`.
- `src/pecp/api/main.py` — FastAPI app entry point. New route modules for `/teams`, `/projects`, `/deployments` must be included here.
- `src/pecp/cli/main.py` — existing CLI commands. Phase 4 adds `team create`, `team`, `project create`, `projects`, `deployments` sub-commands. `--json` flag pattern established here.
- `.planning/phases/03-rest-api-core-cli/03-CONTEXT.md` — D-01 to D-12 from Phase 3 (env column, notes, idempotency, BackgroundTasks, CLI patterns). Read before touching existing routes or ORM.

### Requirements & scope
- `.planning/REQUIREMENTS.md` — Phase 4 covers: TEAM-01, TEAM-02, TEAM-03, CLI-05, CLI-06, CLI-07, CLI-08. Read each requirement text before planning.
- `.planning/ROADMAP.md` — Phase 4 success criteria (4 items). Treat as the acceptance test checklist.
- `.planning/PROJECT.md` — constraints (Python, no auth, all backends mocked, CLI wraps the API, auth stub designed for drop-in).

### Persistence patterns
- `src/pecp/persistence/database.py` — `AsyncSession` factory. All new tables use the same session pattern.
- `alembic/` — existing migration history. Phase 4 Alembic migration adds: `deleted_at` to `resource_records`, `project` to `resource_records`, new `teams` table, new `team_members` table, new `projects` table, new `deployments` table.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ResourceRecord` at `src/pecp/persistence/models.py` — add `project` (Text, nullable) and `deleted_at` (DateTime, nullable) columns here. Alembic migration follows the Phase 3 `env`/`notes` addition pattern.
- `RequestContext` / `ContextDep` at `src/pecp/api/dependencies.py` — `ctx.user_id` available but NOT used to set team owner (owner is explicit via `--owner` flag).
- `console = Console()` and `status_badge()` in `src/pecp/cli/main.py` — reuse for all new CLI commands. Rich table and key-value panel patterns from `pecp status` apply to `pecp team`.
- `STATUS_COLORS` dict in `src/pecp/cli/main.py` — already maps `pending/provisioning/ready/failed` to colors. Reuse for deployment status column.
- `_resolve_base_url()` in `src/pecp/cli/main.py` — URL resolution helper (flag → env var → default). All new CLI commands use this.

### Established Patterns
- Async-first: all route handlers are `async def`, session via `SessionDep`.
- `yaml.safe_load` only — no `yaml.load` anywhere.
- Team scope enforced via `team` query parameter — `400` if absent (ARCH-01). New team and project routes enforce this.
- JSON Text columns for structured data: `environments` on projects follows `notes`/`activity_log` pattern.
- `ctx: ContextDep` flows through every route handler (ARCH-02).

### Integration Points
- `POST /resources` (create path): after creating `ResourceRecord`, also create a `deployments` row with `change_type="create"`, `environment=resource.env`, `project_id=project.id` (if resource has a project).
- `POST /resources` (update path): after updating `ResourceRecord`, create a `deployments` row with `change_type="update"`.
- `DELETE /resources/{id}`: set `deleted_at=now()` instead of deleting. Create a `deployments` row with `change_type="delete"`.
- `GET /resources` (all list queries): add `WHERE resource_records.deleted_at IS NULL` to all existing queries.
- New `GET /deployments`: join `deployments` with `resource_records` for name/kind, filter by `team` (via JOIN to resource → team) and `environment`.

</code_context>

<specifics>
## Specific Ideas

- `pecp team create payments --owner alice` → on success, immediately renders the full team panel (identical to `pecp team payments` output): key-value panel (name, owner, team_id, created_at) + Rich members table showing alice as first owner member.
- `pecp team payments` output structure mirrors `pecp status` — metadata block first, then structured Rich table for members.
- `pecp deployments --team payments --environment prod` outputs Rich table sorted by `deployed_at DESC` — each row: resource_name, kind, change_type (colored?), status (colored badge), deployed_at timestamp.
- `--json` flag on any command pipes clean JSON to stdout. Example: `pecp projects --team payments --json` returns `[{"id": "...", "name": "...", "environments": ["dev", "prod"], "resource_count": 4}]`.
- `pecp project create payments-backend --team payments --env dev,staging,prod` → confirmation: `Project payments-backend created (id: abc-123)`.

</specifics>

<deferred>
## Deferred Ideas

- PE approval flow for team creation — `pecp team create` currently creates immediately; approval workflow is v2 (TEAM-V2-01).
- Team-configurable RBAC — flat owner/contributor roles sufficient for PoC; policy engine (OPA/Cedar) is v2 (TEAM-V2-02).
- `pecp team add-member` command — adding members post-creation not in Phase 4 requirements; can be folded in if trivial, otherwise Phase 5+.
- `pecp deployments` filtering by change_type (e.g., `--type delete`) — useful for audit but not in Phase 4 requirements.
- `pecp status awsaccount --watch` polling — Phase 5 scope.
- UI dashboard — Phase 5 scope.

</deferred>

---

*Phase: 4-teams-projects-deployments*
*Context gathered: 2026-06-14*

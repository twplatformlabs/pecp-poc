# Phase 4: Teams, Projects, Deployments - Research

**Researched:** 2026-06-14
**Domain:** SQLAlchemy 2.x multi-table ORM, Alembic migrations, FastAPI route modules, Typer CLI sub-command groups, soft-delete pattern, audit trail pattern, JSON `--flag` output pattern
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Two DB tables: `teams` (id UUID4, name Text NOT NULL UNIQUE, owner_id Text NOT NULL, created_at DateTime) and `team_members` (team_id FK → teams.id, user_id Text NOT NULL, role Text NOT NULL [owner|contributor], joined_at DateTime). Standard SQLAlchemy async ORM pattern — no embedded JSON for members.

**D-02:** `POST /teams` requires `name` and `owner` in the request body. The `--owner` flag on `pecp team create <name> --owner alice` is explicit — the CLI caller specifies who the owner is rather than inferring from RequestContext. Owner is also auto-added as the first `team_members` row with `role="owner"`.

**D-03:** Team names are unique. `POST /teams` returns `409 Conflict` if the name already exists — no idempotency. Team creation is a deliberate one-time act.

**D-04:** Separate `projects` table: id UUID4, team_id FK → teams.id, name Text NOT NULL, environments Text NOT NULL (JSON-serialized list, e.g. `["dev", "staging", "prod"]`), created_at DateTime. Unique constraint on `(team_id, name)`.

**D-05:** `project` column added to `ResourceRecord` as nullable Text. Stores the project name (not FK). Allows resources to reference projects by name without FK integrity overhead in PoC.

**D-06:** `pecp project create <name> --team <team> --env dev,staging,prod` creates a project explicitly. Projects are not auto-created on first resource apply.

**D-07:** `pecp apply` gains an optional `--project <name>` flag. Resolution order: `spec.metadata.project` from YAML, overridden by `--project` flag if provided. If neither is set, `resource.project` remains null.

**D-08:** `ResourceMetadata` gains a nullable `project: str | None = None` field (alongside the existing `env` field pattern).

**D-09:** Separate `deployments` table: id UUID4, resource_id FK → resource_records.id, project_id FK → projects.id (nullable — resource may have no project), environment Text (nullable — mirrors resource.env at event time), status Text NOT NULL, change_type Text NOT NULL (values: `create`, `update`, `delete`), deployed_at DateTime NOT NULL.

**D-10:** A deployment record is created on every explicit resource mutation: `pecp apply` (create or update path) and `pecp delete`. This is a compliance audit trail, not just a "deployed to env" tracker.

**D-11:** `ResourceRecord` gains a `deleted_at` column (DateTime, nullable). `DELETE /resources/{id}` sets `deleted_at` rather than removing the row. All `GET /resources` queries and `pecp get` filter to `WHERE deleted_at IS NULL`. The FK from `deployments.resource_id` always resolves to a valid row.

**D-12:** Soft-delete is invisible to CLI users — `pecp delete` still prints "deleted", resource disappears from `pecp get`. No "Deleted" status badge shown.

**D-13:** `pecp team create <name> --owner <user_id>` — on success, renders the full team panel (same as `pecp team <name>`) immediately. No separate confirmation-then-query step.

**D-14:** `pecp team <name>` — Rich output: top section shows team metadata as key-value pairs (name, owner, team_id, created_at), followed by a Rich members table (user_id, role, joined_at). Mirrors the `pecp status` pattern of panel + structured section.

**D-15:** `pecp projects --team <team>` — Rich table columns: project_id, name, environments, resource_count (JOIN count). `--json` returns array of `{id, name, environments, resource_count}`.

**D-16:** `pecp deployments --team <team> --environment <env>` — Rich table columns: resource_name, kind, change_type, status, deployed_at (sorted newest first). Audit log view — multiple rows per resource expected. `--json` returns array of deployment records.

**D-17:** `--json` flag available on all data-returning commands: `pecp get`, `pecp status`, `pecp projects`, `pecp deployments`, `pecp team`. Returns structured JSON to stdout. Rich output remains the default.

### Claude's Discretion

- API routes for teams: `POST /teams`, `GET /teams/{name}`. Team lookup by name (not UUID) since name is the human-facing identifier.
- API routes for projects: `POST /projects`, `GET /projects?team=<name>`. Projects listed by team.
- API route for deployments: `GET /deployments?team=<name>&environment=<env>`. Returns deployment records joined with resource data for name/kind.
- Alembic migration numbering: follows Phase 3 migration naming convention.
- `team_members` has no separate ID primary key — `(team_id, user_id)` composite PK is sufficient for PoC.
- `pecp project create` on success: prints a confirmation line with project ID (not a full panel — projects are simpler than teams).

### Deferred Ideas (OUT OF SCOPE)

- PE approval flow for team creation — `pecp team create` currently creates immediately; approval workflow is v2 (TEAM-V2-01).
- Team-configurable RBAC — flat owner/contributor roles sufficient for PoC; policy engine (OPA/Cedar) is v2 (TEAM-V2-02).
- `pecp team add-member` command — adding members post-creation not in Phase 4 requirements; can be folded in if trivial, otherwise Phase 5+.
- `pecp deployments` filtering by change_type (e.g., `--type delete`) — useful for audit but not in Phase 4 requirements.
- `pecp status awsaccount --watch` polling — Phase 5 scope.
- UI dashboard — Phase 5 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEAM-01 | Team can be created and queried — members, roles (owner/contributor), and metadata are visible via `pecp team <name>` | `teams` + `team_members` ORM tables; `POST /teams` + `GET /teams/{name}` routes; `pecp team create` + `pecp team` CLI commands |
| TEAM-02 | Resources can be grouped into named projects — a project has a name and a deployment context (target environments) | `projects` ORM table; `POST /projects` + `GET /projects?team=<name>` routes; `pecp project create` + `pecp projects` CLI commands; `project` nullable column on `ResourceRecord` |
| TEAM-03 | Deployment status for a team's resources is queryable per environment (`pecp deployments --team <team> --environment dev`) | `deployments` audit table; `GET /deployments?team=<name>&environment=<env>` route with JOIN to `resource_records`; soft-delete on `ResourceRecord` so FK always resolves |
| CLI-05 | `pecp team <name>` — shows team members, roles, and metadata | Typer callback on `team` group; `GET /teams/{name}` API call; Rich key-value + members table output |
| CLI-06 | `pecp team create <name>` — creates a new team | Typer sub-command `team create`; `POST /teams` API call; renders full team panel on success |
| CLI-07 | `pecp projects --team <team>` — lists projects for a team with environment and metadata | Typer `projects` command; `GET /projects?team=<name>` API call; Rich table with resource_count |
| CLI-08 | `pecp deployments --team <team> --environment <env>` — shows deployment status filtered by environment | Typer `deployments` command; `GET /deployments?team=<name>&environment=<env>` API call; Rich table sorted newest first |
</phase_requirements>

---

## Summary

Phase 4 is an additive, schema-heavy phase that introduces four new ORM models and five new API route modules atop the Phase 3 foundation. The Phase 3 codebase is fully complete and stable: `ResourceRecord` ORM, async session factory, BackgroundTasks dispatch wiring, all four CLI commands, and the Alembic migration chain up to revision `0002`. Phase 4 extends this in three areas: (1) schema migration adding `deleted_at` and `project` to `resource_records` plus four new tables (`teams`, `team_members`, `projects`, `deployments`); (2) new FastAPI route modules for `/teams`, `/projects`, `/deployments` and modifications to `/resources` for soft-delete and deployment record creation; (3) five new CLI commands plus the `--json` flag on all data-returning commands.

The most architecturally significant decision is the **deployment audit trail** (D-09, D-10): every resource mutation (`POST /resources` create path, `POST /resources` update path, `DELETE /resources/{id}`) must write a `deployments` row. This cross-cuts the existing `POST /resources` route, which is Phase 3's most complex handler. The second significant pattern is the **Typer sub-command group** for `pecp team create` vs `pecp team <name>` — these are not simple flat commands; they require a Typer `app.add_typer()` sub-application pattern.

The third notable item is the `GET /deployments` query: it requires a JOIN across `deployments` → `resource_records` → `teams` to filter by team name. SQLAlchemy 2.x async join syntax requires explicit `.join()` chains on the `select()` statement — there is no magic ORM relationship traversal in async mode without explicit `joinedload`.

**Primary recommendation:** Implement in three waves: Wave 1 = schema migration (single Alembic migration for all new tables + new columns), Wave 2 = API routes (teams, projects, deployments routes + modify existing resources routes), Wave 3 = CLI commands + `--json` flag backfill.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Team creation + member tracking | API / Backend | Database / Storage | Persistence and validation server-side; CLI is a thin caller |
| Project grouping | API / Backend | Database / Storage | Project-resource linkage stored as nullable text column on ResourceRecord (D-05); no FK integrity needed in PoC |
| Deployment audit trail | API / Backend | Database / Storage | Deployment rows written on every mutation server-side; client is unaware |
| Soft-delete of resources | API / Backend | Database / Storage | `deleted_at` set server-side on DELETE; all list queries filter `WHERE deleted_at IS NULL` |
| Team/project/deployment queries | API / Backend | — | JOIN logic belongs in route handlers with SQLAlchemy; CLI renders results only |
| CLI sub-command groups (`team create`, `team <name>`) | CLI Client | — | Typer `add_typer()` sub-app pattern; HTTP wrapping only |
| `--json` flag output | CLI Client | — | Presentation switch: dump response JSON vs. render Rich table |
| Schema evolution (new tables + columns) | Database / Storage | — | Single Alembic migration `0003` adds all new tables and columns |

---

## Standard Stack

### Core (all already in pyproject.toml — no new installs)

| Library | Version (installed) | Purpose | Why Standard |
|---------|---------------------|---------|--------------|
| `fastapi` | 0.137.0 | REST route modules for teams/projects/deployments | Already in use; `APIRouter` pattern established in resources.py |
| `sqlalchemy` | 2.0.50 | Multi-table ORM with ForeignKey, composite PK, async joins | Already in use; 2.x async select/join syntax is the standard |
| `alembic` | 1.18.4 | Schema migration for 4 new tables + 2 new columns on resource_records | Already configured with `render_as_batch=True`; migration `0002` is the template |
| `pydantic` | 2.13.4 | Request body models for POST /teams, POST /projects | Already in use; `NoteCreate` pattern in resources.py is the template |
| `typer` | 0.26.7 | CLI sub-command groups (`team create`, `team <name>`) | Already in use; `add_typer()` enables sub-application grouping |
| `rich` | 15.0.0 | Key-value panels + tables for team/project/deployment output | Already in use; `console`, `Table`, `Text`, `status_badge()` all reusable |
| `httpx` | 0.28.1 | CLI HTTP client for new team/project/deployment API calls | Already in use; same `httpx.get()`/`httpx.post()` pattern |

[VERIFIED: PyPI registry] — versions confirmed via `pip index versions` from venv on 2026-06-14.

### No New Packages Required

Phase 4 installs zero new dependencies. All required libraries are already declared in `pyproject.toml` and installed. No package legitimacy audit is needed.

---

## Package Legitimacy Audit

**No new packages** are introduced in Phase 4. All libraries used were vetted in prior phases and are already installed in the project venv.

| Package | Action |
|---------|--------|
| (none new) | — |

---

## Architecture Patterns

### System Architecture Diagram

```
CLI (pecp team create / team / projects / deployments / apply --project / get --json)
        │
        │  HTTP (httpx)
        ▼
FastAPI Route Handlers
  ├── /teams         (POST, GET /{name})
  ├── /projects      (POST, GET ?team=)
  ├── /deployments   (GET ?team=&environment=)
  └── /resources     (MODIFIED: soft-delete on DELETE, deployment row on POST create/update)
        │
        │  Session (SessionDep) — same async session factory
        ▼
SQLAlchemy AsyncSession
        │
        ├── resource_records   (+ deleted_at nullable, + project nullable)
        ├── teams              (id, name UNIQUE, owner_id, created_at)
        ├── team_members       (team_id FK, user_id, role, joined_at) — composite PK
        ├── projects           (id, team_id FK, name, environments JSON text, created_at)
        └── deployments        (id, resource_id FK, project_id FK nullable, environment, status, change_type, deployed_at)
```

**Data flow for `pecp apply --project payments-backend`:**
1. CLI resolves project from `--project` flag or `spec.metadata.project`
2. CLI POSTs to `/resources?team=X` with project in body or YAML
3. Route handler creates/updates `ResourceRecord` with `project=<name>`
4. Route handler writes `deployments` row with `change_type="create"` (or `"update"`)
5. BackgroundTask dispatches (unchanged from Phase 3)

**Data flow for `pecp deployments --team payments --environment prod`:**
1. CLI GETs `/deployments?team=payments&environment=prod`
2. Route handler JOINs: `deployments` → `resource_records` (for name/kind) → filter by `resource_records.team` and `deployments.environment`
3. Returns list sorted by `deployed_at DESC`
4. CLI renders Rich table (or JSON if `--json`)

### Recommended Project Structure (additions only)

```
src/pecp/
├── api/
│   ├── routes/
│   │   ├── resources.py      # MODIFIED: soft-delete, deployment row creation, deleted_at filter
│   │   ├── teams.py          # NEW: POST /teams, GET /teams/{name}
│   │   ├── projects.py       # NEW: POST /projects, GET /projects
│   │   └── deployments.py    # NEW: GET /deployments
│   └── main.py               # MODIFIED: include 3 new routers
├── cli/
│   └── main.py               # MODIFIED: team sub-group, projects, deployments commands; --json flag
├── models/
│   └── resource_spec.py      # MODIFIED: add project field to ResourceMetadata
└── persistence/
    └── models.py             # MODIFIED: add TeamRecord, TeamMemberRecord, ProjectRecord,
                              #           DeploymentRecord ORM classes; add deleted_at + project
                              #           columns to ResourceRecord

alembic/versions/
└── 0003_add_teams_projects_deployments.py   # NEW: single migration for all 6 changes

tests/
└── test_api/
    ├── test_teams.py          # NEW: Wave 0 scaffolds for team routes
    ├── test_projects.py       # NEW: Wave 0 scaffolds for project routes
    ├── test_deployments.py    # NEW: Wave 0 scaffolds for deployment routes
    ├── test_soft_delete.py    # NEW: Wave 0 scaffolds for soft-delete + audit trail
    └── test_cli.py            # MODIFIED: add team, projects, deployments CLI tests
```

### Pattern 1: Typer Sub-Command Group (`pecp team create` vs `pecp team <name>`)

**What:** `pecp team create <name>` and `pecp team <name>` look like one command with an optional sub-command. In Typer, this is implemented as a nested Typer app with a callback that handles the plain `pecp team <name>` case.

**When to use:** Any time a CLI group has both a named sub-command (`create`) AND a default behavior triggered by an argument (`pecp team payments`).

**Example:**
```python
# Source: Typer docs — app.add_typer() pattern [ASSUMED]
import typer

# In src/pecp/cli/main.py
team_app = typer.Typer(name="team", help="Team commands", no_args_is_help=False)
app.add_typer(team_app)

@team_app.command("create")
def team_create(
    name: str = typer.Argument(..., help="Team name"),
    owner: str = typer.Option(..., "--owner", help="Owner user_id"),
    api_url: str | None = typer.Option(None, "--api-url"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Create a new team and display its panel."""
    base = _resolve_base_url(api_url)
    response = httpx.post(f"{base}/teams", json={"name": name, "owner": owner}, timeout=10.0)
    # render full team panel (same as team_show)
    ...

@team_app.callback(invoke_without_command=True)
def team_show(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Team name to display"),
    api_url: str | None = typer.Option(None, "--api-url"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Show team metadata and members."""
    if ctx.invoked_subcommand is not None:
        return  # sub-command (create) handles it
    if name is None:
        raise typer.BadParameter("Team name is required")
    base = _resolve_base_url(api_url)
    response = httpx.get(f"{base}/teams/{name}", timeout=10.0)
    ...
```

[ASSUMED] — Typer callback + `invoke_without_command=True` is the documented pattern for mixed sub-command/default-argument groups.

### Pattern 2: SQLAlchemy 2.x Multi-Table Async SELECT with JOIN

**What:** `GET /deployments` must join `deployments` to `resource_records` to retrieve `name` and `kind` for each row. SQLAlchemy 2.x async requires explicit `.join()` on the `select()` statement.

**When to use:** Any route that needs data from multiple tables in a single query.

**Example:**
```python
# Source: SQLAlchemy 2.x async docs [ASSUMED]
from sqlalchemy import select
from sqlalchemy.future import select as future_select
from pecp.persistence.models import DeploymentRecord, ResourceRecord

# GET /deployments?team=payments&environment=prod
stmt = (
    select(
        DeploymentRecord.id,
        DeploymentRecord.change_type,
        DeploymentRecord.status,
        DeploymentRecord.deployed_at,
        ResourceRecord.name.label("resource_name"),
        ResourceRecord.kind,
    )
    .join(ResourceRecord, DeploymentRecord.resource_id == ResourceRecord.id)
    .where(ResourceRecord.team == team)
    .where(DeploymentRecord.environment == environment)
    .order_by(DeploymentRecord.deployed_at.desc())
)
result = await session.execute(stmt)
rows = result.all()
return [
    {
        "resource_name": row.resource_name,
        "kind": row.kind,
        "change_type": row.change_type,
        "status": row.status,
        "deployed_at": row.deployed_at.isoformat(),
    }
    for row in rows
]
```

[ASSUMED] — SQLAlchemy 2.x `select().join()` with explicit ON clause is the documented pattern for async sessions.

### Pattern 3: Resource Count in Projects List (Subquery / aggregate)

**What:** `GET /projects?team=<name>` must return `resource_count` — the count of active resources linked to each project. This requires either a subquery or a GROUP BY aggregation.

**When to use:** `GET /projects` list endpoint.

**Example:**
```python
# Source: SQLAlchemy 2.x docs — func.count + group_by [ASSUMED]
from sqlalchemy import func, select
from pecp.persistence.models import ProjectRecord, ResourceRecord

stmt = (
    select(
        ProjectRecord.id,
        ProjectRecord.name,
        ProjectRecord.environments,
        func.count(ResourceRecord.id).label("resource_count"),
    )
    .join(
        ResourceRecord,
        (ResourceRecord.project == ProjectRecord.name) &
        (ResourceRecord.team == team_name) &
        (ResourceRecord.deleted_at == None),  # noqa: E711 — SQLAlchemy None comparison
        isouter=True,
    )
    .join(teams, ProjectRecord.team_id == TeamRecord.id)
    .where(TeamRecord.name == team_name)
    .group_by(ProjectRecord.id)
)
```

Note: Because D-05 stores `project` as a name string (not FK), the join is on `ResourceRecord.project == ProjectRecord.name AND ResourceRecord.team == team_name`. This avoids FK complexity at the cost of a string match.

[ASSUMED] — SQLAlchemy `func.count()` with `group_by()` is the standard aggregation pattern.

### Pattern 4: Soft-Delete with `deleted_at` Filter

**What:** `DELETE /resources/{id}` sets `deleted_at = datetime.now(UTC)` instead of calling `session.delete()`. All list queries add `WHERE deleted_at IS NULL`.

**When to use:** `DELETE /resources/{id}` route (Phase 4 modification), `GET /resources` list query (Phase 4 modification).

**Example:**
```python
# Source: Existing resources.py delete_resource handler — modified for soft-delete [ASSUMED]
from datetime import datetime, timezone

@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    team: str | None = None,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
    background_tasks: BackgroundTasks = ...,
) -> None:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    result = await session.execute(
        select(ResourceRecord).where(
            ResourceRecord.id == resource_id,
            ResourceRecord.deleted_at == None,  # noqa: E711
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if record.team != team:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Soft-delete
    record.deleted_at = datetime.now(timezone.utc)

    # Audit trail (D-10)
    deployment = DeploymentRecord(
        id=uuid.uuid4().hex,
        resource_id=record.id,
        project_id=_resolve_project_id(record.project, session),  # may be None
        environment=record.env,
        status=record.status,
        change_type="delete",
        deployed_at=datetime.now(timezone.utc),
    )
    session.add(deployment)
    await session.commit()
    return None

# All list queries MUST include this filter:
stmt = select(ResourceRecord).where(
    ResourceRecord.team == team,
    ResourceRecord.deleted_at == None,  # noqa: E711
)
```

[ASSUMED] — Soft-delete pattern is standard; SQLAlchemy `None` comparison in where clauses is documented.

### Pattern 5: Deployment Row on Resource Create/Update

**What:** `POST /resources` create and update paths must write a `deployments` row after committing the `ResourceRecord`. The `project_id` requires a lookup by project name + team to find the UUID.

**When to use:** Both create and update branches of the `POST /resources` handler.

**Example:**
```python
# Source: Existing create_resource handler — modified for audit trail [ASSUMED]
async def _maybe_get_project_id(
    project_name: str | None,
    team: str,
    session: AsyncSession,
) -> str | None:
    """Look up project UUID by name + team. Returns None if no project."""
    if project_name is None:
        return None
    result = await session.execute(
        select(ProjectRecord.id)
        .join(TeamRecord, ProjectRecord.team_id == TeamRecord.id)
        .where(TeamRecord.name == team)
        .where(ProjectRecord.name == project_name)
    )
    row = result.scalar_one_or_none()
    return row  # UUID string or None

# In create_resource, after commit:
project_id = await _maybe_get_project_id(spec.metadata.project, team, session)
deployment = DeploymentRecord(
    id=uuid.uuid4().hex,
    resource_id=resource_id,
    project_id=project_id,
    environment=spec.metadata.env,
    status="pending",
    change_type="create",
    deployed_at=datetime.now(timezone.utc),
)
session.add(deployment)
await session.commit()
```

[ASSUMED] — Two-commit pattern (ResourceRecord then DeploymentRecord) vs. single commit with both objects added. Single commit (add both, commit once) is safer and avoids partial state.

### Pattern 6: Alembic Migration for Multi-Table Addition

**What:** Single migration `0003` adds 6 changes: `deleted_at` on `resource_records`, `project` on `resource_records`, new `teams` table, new `team_members` table, new `projects` table, new `deployments` table.

**When to use:** Wave 0 task — must run before any route implementation.

**Example:**
```python
# Source: alembic/versions/0002_add_env_notes_unique.py — Phase 3 template
revision = "0003"
down_revision = "0002"

def upgrade() -> None:
    # 1. Modify resource_records (batch mode required for SQLite)
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.add_column(sa.Column("project", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Create teams
    op.create_table(
        "teams",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_teams_name"),
    )

    # 3. Create team_members
    op.create_table(
        "team_members",
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )

    # 4. Create projects
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

    # 5. Create deployments
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["resource_records.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
```

[ASSUMED] — Migration structure follows Phase 3 template (`0002_add_env_notes_unique.py`); `render_as_batch=True` is already set in `alembic/env.py`.

### Pattern 7: `--json` Flag Output Mode

**What:** All data-returning CLI commands accept `--json` and dump the raw API response JSON to stdout instead of rendering a Rich table.

**When to use:** All new commands (teams, projects, deployments) and backfill to existing `pecp get` and `pecp status`.

**Example:**
```python
# Source: Established CLI pattern in cli/main.py — extended for --json [ASSUMED]
import json

@app.command("projects")
def projects(
    team: str = typer.Option(..., "--team", help="Team name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    api_url: str | None = typer.Option(None, "--api-url"),
) -> None:
    base = _resolve_base_url(api_url)
    try:
        response = httpx.get(f"{base}/projects", params={"team": team}, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)

    data = response.json()

    if json_output:
        # Print clean JSON to stdout — no Rich markup
        print(json.dumps(data, indent=2))
        return

    # Rich table rendering
    table = Table(title=f"Projects — team: {team}")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Environments")
    table.add_column("Resources")
    for p in data:
        table.add_row(
            p["id"][:8] + "...",
            p["name"],
            ", ".join(p["environments"]),
            str(p["resource_count"]),
        )
    console.print(table)
```

[ASSUMED] — `print(json.dumps(...))` bypasses Rich console so output is clean JSON pipe-able to `jq`.

### Anti-Patterns to Avoid

- **Putting `project_id` lookup inside BackgroundTasks:** The project lookup must happen in the route handler (same session, before background task is enqueued) so the `DeploymentRecord` can be committed atomically with the `ResourceRecord` creation. Never pass session state into BackgroundTasks.
- **Forgetting `deleted_at IS NULL` filter on `GET /resources`:** Any `select(ResourceRecord)` without this filter will return soft-deleted resources, breaking `pecp get` and `pecp status`. All three existing queries in `resources.py` (list, get_by_id for status, delete) must be updated.
- **Using `session.delete()` for soft-delete:** The existing `delete_resource` handler calls `await session.delete(record)`. Phase 4 replaces this with `record.deleted_at = datetime.now(UTC)`. Forgetting to remove the `session.delete()` call will hard-delete the row, breaking the FK constraint from `deployments.resource_id`.
- **`json.dumps` with `console.print` for `--json` output:** Rich's `console.print()` adds markup and may buffer. Use plain `print(json.dumps(data))` for `--json` output to ensure clean stdout for piping.
- **Composite PK on `team_members` without explicit PrimaryKeyConstraint:** SQLAlchemy 2.x requires `__table_args__ = (PrimaryKeyConstraint("team_id", "user_id"),)` when using composite PKs with `Mapped` columns. Declaring both as `primary_key=True` in `mapped_column()` is equivalent and simpler.
- **Resolving project_id when no project is set:** `deployments.project_id` is nullable (D-09). When `spec.metadata.project` is `None`, skip the project lookup and set `project_id=None`. Never fail the request because a resource has no project.
- **`pecp team <name>` conflicting with `pecp team create`:** Typer's `callback(invoke_without_command=True)` with `ctx.invoked_subcommand` check is the correct pattern. Without checking `ctx.invoked_subcommand`, the callback fires for `pecp team create` before the sub-command, causing double-execution.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resource count per project | Python loop over resources, count matching | SQLAlchemy `func.count()` + GROUP BY in single query | N+1 query per project; aggregation is O(1) at DB level |
| Team name → team_id lookup | String search across all teams | `SELECT id FROM teams WHERE name = :name` indexed lookup | Name is UNIQUE (D-01); O(1) indexed lookup is correct |
| JSON serialization of `environments` list | Custom encoding | `json.dumps(environments_list)` / `json.loads(record.environments)` | Matches existing `notes`/`activity_log` pattern — no new mechanism needed |
| Deployment record creation | Custom event system or triggers | Write `DeploymentRecord` inline in the route handler after committing the resource | DB triggers not available in SQLite; inline is explicit and testable |
| CLI JSON output | Custom serializer | `print(json.dumps(response.json(), indent=2))` | API already returns JSON; no re-serialization needed |
| Sub-command groups | Custom CLI dispatch | `typer.Typer()` + `app.add_typer()` | Typer handles sub-command routing, help text, and error messages |

**Key insight:** Every "hard" problem in Phase 4 (aggregations, soft-delete, audit trail, sub-command groups) has a well-established solution in the existing stack. The implementation risk is in correctly wiring the cross-cutting deployment trail and in the Typer sub-command callback pattern — not in algorithmic complexity.

---

## Common Pitfalls

### Pitfall 1: `deleted_at IS NULL` Missing from Existing Queries (CRITICAL)

**What goes wrong:** `GET /resources` and `GET /resources/{id}` continue returning soft-deleted resources. `pecp get` shows "deleted" resources. `pecp status` works on deleted resources.

**Why it happens:** The `delete_resource` handler is the only change from hard-delete to soft-delete — but three other query sites (`list_resources`, `get_resource`, and any future queries) also need the filter.

**How to avoid:** In the Alembic Wave 0 task that adds the `deleted_at` column, immediately update ALL select statements in `resources.py` to include `.where(ResourceRecord.deleted_at == None)`. Treat it as a migration paired with code change — not a separate task.

**Warning signs:** `pecp get` lists resources that were `pecp delete`d in the same session.

### Pitfall 2: Deployment Record Not Committed Atomically

**What goes wrong:** `ResourceRecord` is committed but `DeploymentRecord` is not (or vice versa) due to an error between two separate `session.commit()` calls. The audit trail has gaps.

**Why it happens:** Temptation to commit `ResourceRecord` first (to ensure idempotency logic is correct), then add `DeploymentRecord` and commit again. If the second commit fails, no deployment record exists.

**How to avoid:** Add both `ResourceRecord` and `DeploymentRecord` to the session before the single `session.commit()` call. SQLAlchemy will write both in the same transaction. The `project_id` lookup must happen before the commit so it can be passed to `DeploymentRecord.__init__`.

**Warning signs:** Deployment records missing for resources that definitely exist and have `status=ready`.

### Pitfall 3: `pecp team <name>` Callback Fires for Sub-Commands

**What goes wrong:** `pecp team create payments --owner alice` invokes the callback (which tries to `GET /teams/create`) before invoking the `create` sub-command.

**Why it happens:** Typer's `callback(invoke_without_command=True)` fires for ALL invocations of the `team` group, including those that have a sub-command. Without checking `ctx.invoked_subcommand`, the callback runs the "show team" logic with `name="create"`.

**How to avoid:** In the callback:
```python
@team_app.callback(invoke_without_command=True)
def team_show(ctx: typer.Context, name: str = typer.Argument(None), ...) -> None:
    if ctx.invoked_subcommand is not None:
        return  # Let the sub-command handle it
    if name is None:
        raise typer.BadParameter("Team name is required")
    ...
```

**Warning signs:** `GET /teams/create` 404 error when running `pecp team create`.

### Pitfall 4: `environments` JSON Column Round-Trip

**What goes wrong:** `pecp project create payments-backend --team payments --env dev,staging,prod` stores `["dev", "staging", "prod"]` as a JSON string. `GET /projects` deserializes and returns a list. But `pecp deployments` output and `pecp projects` Rich table receive the raw JSON string if the route handler forgets to `json.loads()` before returning.

**Why it happens:** The `environments` column is stored as `Text` containing JSON (matching `notes`/`activity_log` pattern). Unlike those columns, `environments` is shown directly in the table — so the route handler must deserialize it before returning the API response.

**How to avoid:** In `GET /projects` handler: `"environments": json.loads(project.environments)`. In `POST /projects` handler: `environments=json.dumps(env_list)` when storing.

**Warning signs:** `pecp projects` Rich table shows `["dev", "staging"]` as a literal string instead of `dev, staging`.

### Pitfall 5: Soft-Deleted Resources Appearing in `GET /resources/{id}`

**What goes wrong:** `pecp status PECPLambda my-fn --team payments` works after `pecp delete` because `GET /resources/{id}` returns the soft-deleted record (no `deleted_at IS NULL` filter on the single-record lookup).

**Why it happens:** `GET /resources/{id}` fetches by primary key, not by team. The original implementation has no `deleted_at` filter because the column didn't exist.

**How to avoid:** Add `ResourceRecord.deleted_at == None` to the `WHERE` clause in `get_resource`. Alternatively, check `record.deleted_at is not None` after fetch and return 404 in that case.

**Warning signs:** `pecp status` returns data for a resource that `pecp get` no longer lists.

### Pitfall 6: Project Lookup Fails When Resource Has No Team Yet Stored

**What goes wrong:** `_maybe_get_project_id` JOINs `projects` to `teams`, but if the team does not exist in the `teams` table (it's identified by the `team` query param, which is a free-text string on `ResourceRecord`), the lookup returns `None` even when a project of that name exists.

**Why it happens:** Phase 3 resources use the `team` query param as a free-text string — they are not FK-linked to the `teams` table. Phase 4 adds the `teams` table, but old resources may have `team` values that don't have corresponding rows in `teams`.

**How to avoid:** In the PoC, require the team to exist in the `teams` table before applying resources (Success Criterion 4: `POST /resources` with no team context returns 400 — but this criterion is about missing team param, not missing team record). For simplicity: `_maybe_get_project_id` returns `None` if no matching project is found (not an error). The deployment record is still written with `project_id=None`.

**Warning signs:** `GET /deployments` returns no `project_id` for resources that should have a project.

---

## Code Examples

### ORM Models for New Tables

```python
# Source: Existing ResourceRecord in src/pecp/persistence/models.py — extended pattern [ASSUMED]
import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TeamRecord(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("name", name="uq_teams_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TeamMemberRecord(Base):
    __tablename__ = "team_members"
    __table_args__ = (PrimaryKeyConstraint("team_id", "user_id"),)

    team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # "owner" | "contributor"
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ProjectRecord(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("team_id", "name", name="uq_projects_team_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    environments: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class DeploymentRecord(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resource_id: Mapped[str] = mapped_column(String, ForeignKey("resource_records.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String, ForeignKey("projects.id"), nullable=True)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)  # create|update|delete
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### `POST /teams` Route Handler

```python
# Source: Existing NoteCreate + POST /resources/{id}/notes pattern [ASSUMED]
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

router = APIRouter(prefix="/teams", tags=["teams"])

class TeamCreate(BaseModel):
    name: str
    owner: str

@router.post("", status_code=201)
async def create_team(
    body: TeamCreate,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, object]:
    team_id = uuid.uuid4().hex
    team = TeamRecord(id=team_id, name=body.name, owner_id=body.owner)
    member = TeamMemberRecord(team_id=team_id, user_id=body.owner, role="owner")
    session.add(team)
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")
    return _render_team_response(team, [member])
```

### `GET /teams/{name}` Route Handler

```python
@router.get("/{name}")
async def get_team(
    name: str,
    ctx: ContextDep = ...,
    session: SessionDep = ...,
) -> dict[str, object]:
    result = await session.execute(
        select(TeamRecord).where(TeamRecord.name == name)
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    members_result = await session.execute(
        select(TeamMemberRecord).where(TeamMemberRecord.team_id == team.id)
    )
    members = members_result.scalars().all()
    return {
        "id": team.id,
        "name": team.name,
        "owner_id": team.owner_id,
        "created_at": team.created_at.isoformat(),
        "members": [
            {"user_id": m.user_id, "role": m.role, "joined_at": m.joined_at.isoformat()}
            for m in members
        ],
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-delete (`session.delete()`) | Soft-delete (`deleted_at` column) | Phase 4 (D-11) | FK integrity preserved for audit trail |
| Flat CLI commands only | Sub-command groups (`pecp team create`, `pecp team <name>`) | Phase 4 (D-13/D-14) | Logical grouping of related commands |
| All queries return everything | `WHERE deleted_at IS NULL` filter on all list queries | Phase 4 (D-11) | Consistent visibility model |
| No deployment history | Append-only `deployments` table per mutation | Phase 4 (D-10) | Full audit trail for compliance |
| Resource `team` as free-text column only | `teams` + `team_members` tables (TEAM-01) | Phase 4 | Structured team ownership and member roles |

**Deprecated/outdated in this project's context:**
- `session.delete(record)` in `delete_resource`: replaced by `record.deleted_at = now()` in Phase 4.
- Hard-coded `team` as a raw string query param with no team record: still valid for resource scoping, but Phase 4 adds team records alongside it.

---

## Runtime State Inventory

Phase 4 is not a rename/refactor phase. This section is omitted. The phase adds new tables and modifies existing ones via Alembic migration — no runtime state (stored user_ids, service configs, OS registrations) is affected.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 + pytest-asyncio |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` (already set from Phase 3) |
| Quick run command | `pytest tests/test_api/ -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TEAM-01 | `POST /teams` returns 201 with team + member; `GET /teams/{name}` returns members | integration | `pytest tests/test_api/test_teams.py -x -q` | ❌ Wave 0 |
| TEAM-01 | `POST /teams` with duplicate name returns 409 | integration | `pytest tests/test_api/test_teams.py -x -q` | ❌ Wave 0 |
| TEAM-02 | `POST /projects` creates project; `GET /projects?team=` returns list with resource_count | integration | `pytest tests/test_api/test_projects.py -x -q` | ❌ Wave 0 |
| TEAM-03 | `GET /deployments?team=&environment=prod` returns only prod deployments | integration | `pytest tests/test_api/test_deployments.py -x -q` | ❌ Wave 0 |
| TEAM-03 | `DELETE /resources/{id}` writes deployment row with `change_type="delete"` | integration | `pytest tests/test_api/test_soft_delete.py -x -q` | ❌ Wave 0 |
| TEAM-03 | `GET /resources` filters out soft-deleted resources (`WHERE deleted_at IS NULL`) | integration | `pytest tests/test_api/test_soft_delete.py -x -q` | ❌ Wave 0 |
| TEAM-03 | `POST /resources` writes deployment row with `change_type="create"` | integration | `pytest tests/test_api/test_deployments.py -x -q` | ❌ Wave 0 |
| CLI-05 | `pecp team <name>` renders key-value panel + members table | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 (extend) |
| CLI-06 | `pecp team create <name> --owner alice` renders full team panel on success | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 (extend) |
| CLI-07 | `pecp projects --team X` renders Rich table with resource_count | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 (extend) |
| CLI-07 | `pecp projects --team X --json` prints clean JSON array | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 (extend) |
| CLI-08 | `pecp deployments --team X --environment prod` renders Rich table sorted newest first | unit (mock HTTP) | `pytest tests/test_api/test_cli.py -x -q` | ❌ Wave 0 (extend) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_api/ -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_api/test_teams.py` — covers TEAM-01 (create + duplicate + get)
- [ ] `tests/test_api/test_projects.py` — covers TEAM-02 (create project, list with resource_count)
- [ ] `tests/test_api/test_deployments.py` — covers TEAM-03 (deployment audit trail, environment filter)
- [ ] `tests/test_api/test_soft_delete.py` — covers D-11 (soft-delete invisible, deleted_at filter on list/get)
- [ ] Extend `tests/test_api/test_cli.py` — team create, team show, projects, deployments, --json flag

---

## Security Domain

`security_enforcement` is enabled (absent = enabled), `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Auth is stubbed for PoC; `RequestContext` is the hook |
| V3 Session Management | No | Stateless API; no user sessions |
| V4 Access Control | Partial | Team scoping on resources enforced (ARCH-01); team membership is not enforced in PoC (owner is free-text) |
| V5 Input Validation | Yes | Pydantic models for `TeamCreate`, `ProjectCreate` request bodies; `yaml.safe_load` already enforced |
| V6 Cryptography | No | No secrets or sensitive data in PoC |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `POST /teams` without owner validation | Elevation of Privilege | Owner is free-text in PoC (by design — no auth); `RequestContext` stub is the hook for future JWT check |
| `GET /deployments` without team filter returns all deployments | Information Disclosure | Require `team` query param; return 400 if absent (same pattern as ARCH-01 on `/resources`) |
| `POST /resources` without team returns 400 (Success Criterion 4) | Information Disclosure | Already enforced via ARCH-01 check in `create_resource`; verify check is retained after soft-delete modification |
| Soft-deleted resource accessible via `GET /resources/{id}` | Information Disclosure | Add `deleted_at IS NULL` check to `get_resource` single-record handler (Pitfall 5) |
| SQL injection via ORM | Tampering | SQLAlchemy parameterized queries — already in use; no change needed |

**ASVS Level 1 note:** The one new security control Phase 4 must add is the `team` requirement on `GET /deployments` — return 400 if `team` query param is absent, matching the existing ARCH-01 pattern on `/resources`. Without this, a caller could enumerate all deployment records across all teams.

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies). Phase 4 is code/config/schema only. All tools (Python venv, pytest, alembic) are already available from Phase 3.

---

## Open Questions

1. **`pecp apply --project` flag placement and `--json` backfill scope**
   - What we know: D-07 says `pecp apply` gains optional `--project` flag. D-17 says `--json` on all data-returning commands including `pecp get` and `pecp status`.
   - What's unclear: Does "backfill `--json` on existing commands" (get, status) require modifying existing route responses, or only the CLI rendering layer?
   - Recommendation: `--json` is CLI-only — the API already returns JSON. The CLI just needs to add the flag and switch between `print(json.dumps(...))` and Rich table. No route changes needed for `--json`. Existing `pecp get` and `pecp status` JSON output is just the raw response body.

2. **Resource count in `GET /projects`: aggregate at DB or Python?**
   - What we know: D-15 requires `resource_count` per project in the projects list.
   - What's unclear: Whether to use a SQLAlchemy GROUP BY aggregation or do a Python-level count with N+1 queries.
   - Recommendation: Use `func.count()` + GROUP BY in a single SQL query (Pattern 3 above). N+1 is unacceptable even in PoC as project lists may have many entries.

3. **`pecp team create` success output is "full team panel" — but `project_id` requires a live GET**
   - What we know: D-13 says on success, render the full team panel immediately (no separate confirm-then-query step).
   - What's unclear: The `POST /teams` response can return the full team data directly (members list included in the response body) without requiring a second `GET /teams/{name}` call from the CLI.
   - Recommendation: `POST /teams` response body includes the full `{id, name, owner_id, created_at, members: [...]}` shape. CLI renders from the POST response directly — no second GET needed. This is simpler and avoids a race condition.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Typer `callback(invoke_without_command=True)` with `ctx.invoked_subcommand` check is the correct pattern for `pecp team <name>` vs `pecp team create` | Architecture Patterns (Pattern 1) | Medium: CLI routing breaks — `pecp team create` triggers show-team logic with `name="create"` |
| A2 | SQLAlchemy `func.count()` + GROUP BY works correctly with LEFT OUTER JOIN for projects with no resources (should return 0) | Architecture Patterns (Pattern 3) | Low: projects with zero resources might be excluded from the list instead of showing `resource_count=0` |
| A3 | Single commit with both `ResourceRecord` and `DeploymentRecord` added to session is atomic in SQLite | Common Pitfalls (Pitfall 2) | Medium: if not atomic, audit trail has gaps |
| A4 | `None` comparison in SQLAlchemy WHERE (`ResourceRecord.deleted_at == None`) generates correct `IS NULL` SQL | Common Pitfalls (Pitfall 1) | Low: well-documented SQLAlchemy behavior; alternative is `is_(None)` |
| A5 | `PrimaryKeyConstraint("team_id", "user_id")` in `__table_args__` is the correct SQLAlchemy 2.x pattern for composite PK with `Mapped` columns | Code Examples | Low: alternative is `primary_key=True` on both `mapped_column()` declarations |

---

## Sources

### Primary (HIGH confidence)

- Existing codebase — read directly: `src/pecp/persistence/models.py`, `src/pecp/api/routes/resources.py`, `src/pecp/cli/main.py`, `src/pecp/api/main.py`, `src/pecp/api/dependencies.py`, `alembic/versions/0002_add_env_notes_unique.py`, `alembic/env.py`, `tests/conftest.py`, `tests/test_api/test_cli.py`, `tests/test_api/test_idempotency.py`
- `pip index versions` from project venv — confirmed: fastapi 0.137.0, sqlalchemy 2.0.50, alembic 1.18.4, typer 0.26.7, rich 15.0.0, httpx 0.28.1, pydantic 2.13.4, pytest 9.1.0 on 2026-06-14 [VERIFIED: PyPI registry]
- `04-CONTEXT.md` — locked decisions D-01 through D-17 consumed verbatim [HIGH]

### Secondary (MEDIUM confidence)

- Phase 3 CONTEXT.md and RESEARCH.md — established patterns (async session, BackgroundTasks, batch_alter_table, CLI URL resolution) [CITED: .planning/phases/03-rest-api-core-cli/03-RESEARCH.md]

### Tertiary (LOW confidence / ASSUMED)

- Typer sub-command group callback pattern (A1) — Typer documentation pattern; not verified via code execution
- SQLAlchemy `func.count()` LEFT OUTER JOIN for zero-count rows (A2) — standard SQL aggregation knowledge
- SQLite atomic multi-row commit (A3) — standard SQLite transaction behavior

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` apply to Phase 4 planning and implementation:

| Directive | Impact on Phase 4 |
|-----------|-------------------|
| Python only — org standard | All new code is Python; no Node.js or other languages |
| All backends mocked — no real cloud access | Teams/projects/deployments are local SQLite only; no external calls |
| `yaml.safe_load` only — never `yaml.load` | Applies to any YAML parsing (none new in Phase 4, but existing routes must not regress) |
| No `SQLModel` | Phase 4 uses SQLAlchemy 2.x ORM directly (same as all prior phases) |
| No `MongoDB` or document stores | SQLite + Alembic for all new tables |
| `async def` for all route handlers | All new route handlers in `teams.py`, `projects.py`, `deployments.py` must be `async def` |
| `ctx: ContextDep` flows through every route handler (ARCH-02) | All new route handlers must accept `ctx: ContextDep` |
| ARCH-01: All resource API endpoints enforce team scope at server | `GET /deployments` must require `team` query param; return 400 if absent |
| Auth designed for drop-in (no enforcement in PoC) | `owner` is free-text; `RequestContext` stub unchanged |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed; versions confirmed from venv PyPI
- Architecture: HIGH — existing codebase provides all patterns; Phase 4 is additive with well-understood SQLAlchemy/Typer patterns
- Pitfalls: HIGH — soft-delete FK implications, Typer callback behavior, and multi-table commit ordering are documented patterns with clear solutions
- Security: HIGH — ASVS Level 1; minimal new controls needed (team enforcement on deployments route)

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable stack; no fast-moving dependencies)

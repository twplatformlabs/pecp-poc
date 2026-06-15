# Phase 4: Teams, Projects, Deployments - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 11 (new/modified)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pecp/persistence/models.py` | model | CRUD | `src/pecp/persistence/models.py` (self — extend) | exact |
| `alembic/versions/0003_add_teams_projects_deployments.py` | migration | batch | `alembic/versions/0002_add_env_notes_unique.py` | exact |
| `src/pecp/models/resource_spec.py` | model | transform | `src/pecp/models/resource_spec.py` (self — extend) | exact |
| `src/pecp/api/routes/teams.py` | route | request-response | `src/pecp/api/routes/resources.py` | exact |
| `src/pecp/api/routes/projects.py` | route | request-response | `src/pecp/api/routes/resources.py` | exact |
| `src/pecp/api/routes/deployments.py` | route | request-response | `src/pecp/api/routes/resources.py` | exact |
| `src/pecp/api/routes/resources.py` | route | request-response | `src/pecp/api/routes/resources.py` (self — modify) | exact |
| `src/pecp/api/main.py` | config | request-response | `src/pecp/api/main.py` (self — modify) | exact |
| `src/pecp/cli/main.py` | CLI client | request-response | `src/pecp/cli/main.py` (self — extend) | exact |
| `tests/test_api/test_teams.py` | test | CRUD | `tests/test_api/test_cli.py` | role-match |
| `tests/test_api/test_projects.py` | test | CRUD | `tests/test_api/test_cli.py` | role-match |
| `tests/test_api/test_deployments.py` | test | CRUD | `tests/test_api/test_cli.py` | role-match |
| `tests/test_api/test_soft_delete.py` | test | CRUD | `tests/test_api/test_cli.py` | role-match |

---

## Pattern Assignments

### `src/pecp/persistence/models.py` (model, CRUD — MODIFIED)

**Analog:** `src/pecp/persistence/models.py` (extend in place)

**Existing ORM class structure to follow** (lines 1–44):
```python
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ResourceRecord(Base):
    __tablename__ = "resource_records"
    __table_args__ = (
        UniqueConstraint("team", "kind", "name", name="uq_resource_team_kind_name"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team: Mapped[str] = mapped_column(String, index=True, nullable=False)
    # ... all existing columns unchanged ...
    env: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
```

**New columns to ADD to ResourceRecord** (follow `env`/`notes` pattern):
```python
    project: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**New ORM classes to ADD** (after ResourceRecord, same file):
```python
from sqlalchemy import ForeignKey, PrimaryKeyConstraint

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
    environments: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list via json.dumps/loads
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
    change_type: Mapped[str] = mapped_column(Text, nullable=False)  # create | update | delete
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

---

### `alembic/versions/0003_add_teams_projects_deployments.py` (migration, batch — NEW)

**Analog:** `alembic/versions/0002_add_env_notes_unique.py`

**Header pattern** (lines 1–14):
```python
"""Add teams, team_members, projects, deployments tables and extend resource_records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None
```

**Upgrade pattern — batch_alter_table for SQLite column additions** (lines 18–27 of 0002):
```python
def upgrade() -> None:
    # 1. Extend resource_records — batch mode required for SQLite
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.add_column(sa.Column("project", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 2–5. Create new tables with op.create_table() (no batch needed for new tables)
    op.create_table("teams", ...)
    op.create_table("team_members", ...)
    op.create_table("projects", ...)
    op.create_table("deployments", ...)
```

**Downgrade pattern** (lines 31–34 of 0002):
```python
def downgrade() -> None:
    op.drop_table("deployments")
    op.drop_table("projects")
    op.drop_table("team_members")
    op.drop_table("teams")
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("project")
```

---

### `src/pecp/models/resource_spec.py` (model, transform — MODIFIED)

**Analog:** `src/pecp/models/resource_spec.py` (extend in place)

**Existing ResourceMetadata pattern** (lines 92–95):
```python
class ResourceMetadata(BaseModel):
    name: str
    team: str | None = None
    env: str | None = None
```

**Add `project` field following the `env` nullable pattern:**
```python
class ResourceMetadata(BaseModel):
    name: str
    team: str | None = None
    env: str | None = None
    project: str | None = None  # D-08: optional project grouping
```

---

### `src/pecp/api/routes/teams.py` (route, request-response — NEW)

**Analog:** `src/pecp/api/routes/resources.py`

**Imports pattern** (copy from resources.py lines 1–27, adapted):
```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from pecp.api.dependencies import ContextDep
from pecp.persistence.database import SessionDep
from pecp.persistence.models import TeamMemberRecord, TeamRecord

router = APIRouter(prefix="/teams", tags=["teams"])
```

**Pydantic request body pattern** (copy from NoteCreate pattern, resources.py lines 30–32):
```python
class TeamCreate(BaseModel):
    name: str
    owner: str
```

**POST handler pattern** (copy from create_resource structure, resources.py lines 84–191):
```python
@router.post("", status_code=201)
async def create_team(
    body: TeamCreate,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    team_id = uuid.uuid4().hex
    team = TeamRecord(id=team_id, name=body.name, owner_id=body.owner)
    member = TeamMemberRecord(team_id=team_id, user_id=body.owner, role="owner",
                              joined_at=datetime.now(timezone.utc))
    session.add(team)
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")
    return _render_team(team, [member])
```

**GET handler pattern** (copy from get_resource structure, resources.py lines 194–224):
```python
@router.get("/{name}")
async def get_team(
    name: str,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    members_result = await session.execute(
        select(TeamMemberRecord).where(TeamMemberRecord.team_id == team.id)
    )
    members = members_result.scalars().all()
    return _render_team(team, members)
```

**Error handling pattern** (copy from resources.py IntegrityError catch lines 164–183):
```python
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=...)
```

---

### `src/pecp/api/routes/projects.py` (route, request-response — NEW)

**Analog:** `src/pecp/api/routes/resources.py`

**Imports pattern:**
```python
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from pecp.api.dependencies import ContextDep
from pecp.persistence.database import SessionDep
from pecp.persistence.models import ProjectRecord, ResourceRecord, TeamRecord

router = APIRouter(prefix="/projects", tags=["projects"])
```

**ARCH-01 team guard pattern** (copy from list_resources, resources.py lines 62–63):
```python
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
```

**JSON text column round-trip pattern** (follows `notes`/`activity_log` in resources.py lines 222, 282–290):
```python
# Store: json.dumps(list) → Text column
environments = json.dumps(env_list)

# Retrieve: json.loads(Text column) → list
"environments": json.loads(project.environments)
```

**Resource count via SQLAlchemy aggregation** (Pattern 3 from RESEARCH.md):
```python
from sqlalchemy import func

stmt = (
    select(
        ProjectRecord.id,
        ProjectRecord.name,
        ProjectRecord.environments,
        func.count(ResourceRecord.id).label("resource_count"),
    )
    .join(TeamRecord, ProjectRecord.team_id == TeamRecord.id)
    .join(
        ResourceRecord,
        (ResourceRecord.project == ProjectRecord.name)
        & (ResourceRecord.team == team_name)
        & (ResourceRecord.deleted_at.is_(None)),
        isouter=True,
    )
    .where(TeamRecord.name == team_name)
    .group_by(ProjectRecord.id)
)
result = await session.execute(stmt)
rows = result.all()
```

---

### `src/pecp/api/routes/deployments.py` (route, request-response — NEW)

**Analog:** `src/pecp/api/routes/resources.py`

**Imports pattern:**
```python
from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select

from pecp.api.dependencies import ContextDep
from pecp.persistence.database import SessionDep
from pecp.persistence.models import DeploymentRecord, ResourceRecord

router = APIRouter(prefix="/deployments", tags=["deployments"])
```

**ARCH-01 team guard pattern** (same as list_resources, resources.py lines 62–63):
```python
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
```

**Multi-table JOIN pattern** (Pattern 2 from RESEARCH.md):
```python
stmt = (
    select(
        DeploymentRecord.id,
        DeploymentRecord.change_type,
        DeploymentRecord.status,
        DeploymentRecord.deployed_at,
        DeploymentRecord.environment,
        ResourceRecord.name.label("resource_name"),
        ResourceRecord.kind,
    )
    .join(ResourceRecord, DeploymentRecord.resource_id == ResourceRecord.id)
    .where(ResourceRecord.team == team)
    .where(ResourceRecord.deleted_at.is_(None))
    .order_by(DeploymentRecord.deployed_at.desc())
)
if environment:
    stmt = stmt.where(DeploymentRecord.environment == environment)
result = await session.execute(stmt)
rows = result.all()
```

---

### `src/pecp/api/routes/resources.py` (route, request-response — MODIFIED)

**Analog:** self (existing file, targeted surgical changes)

**Soft-delete modification to `delete_resource`** (replace lines 255–257):
```python
# BEFORE (hard-delete — remove this):
await session.delete(record)
await session.commit()

# AFTER (soft-delete + audit trail):
record.deleted_at = datetime.now(timezone.utc)
deployment = DeploymentRecord(
    id=uuid.uuid4().hex,
    resource_id=record.id,
    project_id=await _maybe_get_project_id(record.project, record.team, session),
    environment=record.env,
    status=record.status,
    change_type="delete",
    deployed_at=datetime.now(timezone.utc),
)
session.add(deployment)
await session.commit()
```

**Add `deleted_at IS NULL` filter to ALL existing select statements:**
```python
# list_resources — line 65: add filter
stmt = select(ResourceRecord).where(
    ResourceRecord.team == team,
    ResourceRecord.deleted_at.is_(None),  # D-11
)

# get_resource — after line 208: add check
if record is None or record.deleted_at is not None:
    raise HTTPException(status_code=404, detail="Resource not found")

# delete_resource — line 244: add filter in initial lookup
select(ResourceRecord).where(
    ResourceRecord.id == resource_id,
    ResourceRecord.deleted_at.is_(None),
)
```

**Deployment row on create/update** (add after create commit, lines 165–185):
```python
async def _maybe_get_project_id(
    project_name: str | None, team: str, session: AsyncSession
) -> str | None:
    if project_name is None:
        return None
    result = await session.execute(
        select(ProjectRecord.id)
        .join(TeamRecord, ProjectRecord.team_id == TeamRecord.id)
        .where(TeamRecord.name == team)
        .where(ProjectRecord.name == project_name)
    )
    return result.scalar_one_or_none()

# After committing ResourceRecord (new create path):
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

**Also add `project` field to ResourceRecord on create/update:**
```python
# Create path (after line 162):
record = ResourceRecord(
    ...
    env=spec.metadata.env,
    project=spec.metadata.project,  # D-07
)

# Update path (after line 141):
existing.env = spec.metadata.env
existing.project = spec.metadata.project  # D-07
```

---

### `src/pecp/api/main.py` (config, request-response — MODIFIED)

**Analog:** `src/pecp/api/main.py` (extend in place)

**Router registration pattern** (lines 12–13, 29):
```python
# BEFORE:
from pecp.api.routes import resources
app.include_router(resources.router)

# AFTER — add three new imports and include_router calls:
from pecp.api.routes import deployments, projects, resources, teams

app.include_router(resources.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(deployments.router)
```

---

### `src/pecp/cli/main.py` (CLI client, request-response — MODIFIED)

**Analog:** `src/pecp/cli/main.py` (extend in place)

**Existing app/console/helpers pattern** (lines 25–52) — reuse unchanged:
```python
app = typer.Typer(name="pecp", help="...", no_args_is_help=True)
console = Console()
STATUS_COLORS: dict[str, str] = {...}
def status_badge(status: str) -> Text: ...
def _resolve_base_url(api_url: str | None) -> str: ...
```

**`--json` flag pattern** — add to all data-returning commands:
```python
import json  # already imported via `import os` block — add json

# On each command (get, status, projects, deployments, team):
json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),

# At render point:
if json_output:
    print(json.dumps(data, indent=2))  # plain print, NOT console.print — pipes cleanly
    return
# else: Rich table rendering as normal
```

**`pecp apply --project` flag pattern** (follow `--team` flag pattern, lines 70–75):
```python
project: str | None = typer.Option(
    None,
    "--project",
    help="Project to associate with this resource (overrides spec.metadata.project)",
),
# Resolution: project flag overrides YAML spec.metadata.project
# Pass via request body or separate mechanism — spec is raw YAML bytes
```

**Typer sub-command group pattern for `pecp team`** (Pattern 1 from RESEARCH.md):
```python
team_app = typer.Typer(name="team", help="Team management commands", no_args_is_help=False)
app.add_typer(team_app)

@team_app.callback(invoke_without_command=True)
def team_show(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Team name to display"),
    api_url: str | None = typer.Option(None, "--api-url"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show team metadata and members."""
    if ctx.invoked_subcommand is not None:
        return  # Let sub-command (create) handle it
    if name is None:
        raise typer.BadParameter("Team name is required")
    base = _resolve_base_url(api_url)
    try:
        response = httpx.get(f"{base}/teams/{name}", timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc
    # ... render team panel

@team_app.command("create")
def team_create(
    name: str = typer.Argument(..., help="Team name"),
    owner: str = typer.Option(..., "--owner", help="Owner user_id"),
    api_url: str | None = typer.Option(None, "--api-url"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new team and display its panel."""
    base = _resolve_base_url(api_url)
    try:
        response = httpx.post(f"{base}/teams", json={"name": name, "owner": owner}, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc
    # ... render team panel (same helper as team_show)
```

**Rich key-value panel pattern** (mirrors `pecp status` table at lines 199–218):
```python
# For pecp team <name> — top section: key-value table
table = Table(title=f"Team: {name}")
table.add_column("Field")
table.add_column("Value")
for field in ["id", "name", "owner_id", "created_at"]:
    table.add_row(field, str(data.get(field) or "—"))
console.print(table)

# Bottom section: members table
members_table = Table(title="Members")
members_table.add_column("user_id")
members_table.add_column("role")
members_table.add_column("joined_at")
for m in data.get("members", []):
    members_table.add_row(m["user_id"], m["role"], m["joined_at"])
console.print(members_table)
```

**HTTP error handling pattern** (copy from get/status commands, lines 127–131):
```python
    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)
```

---

### `tests/test_api/test_teams.py`, `test_projects.py`, `test_deployments.py`, `test_soft_delete.py` (test, CRUD — NEW)

**Analog:** `tests/test_api/test_cli.py`

**Test file structure pattern** (lines 1–16 of test_cli.py):
```python
"""Tests for <feature>."""

from pathlib import Path
import unittest.mock as mock

import httpx
from typer.testing import CliRunner

from pecp.cli.main import app

runner = CliRunner()
```

**HTTP mock pattern** (lines 34–45 of test_cli.py):
```python
mock_response = mock.MagicMock(spec=httpx.Response)
mock_response.status_code = 201
mock_response.json.return_value = {"id": "...", "name": "...", ...}

with mock.patch("httpx.post", return_value=mock_response) as mock_post:
    result = runner.invoke(app, [...], catch_exceptions=False)

assert result.exit_code == 0
mock_post.assert_called_once_with(...)
```

**FastAPI integration test pattern** — check `tests/conftest.py` for the `AsyncClient` fixture used in API-level tests (not CLI tests). Use the same `AsyncClient` fixture from conftest for `test_teams.py`, `test_projects.py`, `test_deployments.py`, `test_soft_delete.py`.

---

## Shared Patterns

### ARCH-01: Team Scope Enforcement
**Source:** `src/pecp/api/routes/resources.py` lines 62–63
**Apply to:** `teams.py` (GET /teams/{name} does not need it — name is not team-scoped), `projects.py` GET handler, `deployments.py` GET handler
```python
if not team:
    raise HTTPException(status_code=400, detail="team parameter is required")
```

### ARCH-02: ContextDep in Every Route Handler
**Source:** `src/pecp/api/dependencies.py` lines 15–28 + `resources.py` lines 54–55
**Apply to:** All new route handlers in `teams.py`, `projects.py`, `deployments.py`
```python
ctx: ContextDep = ...,  # type: ignore[assignment]
```

### Async Session Pattern
**Source:** `src/pecp/api/routes/resources.py` lines 54–55, 68–70
**Apply to:** All new route handlers
```python
session: SessionDep = ...,  # type: ignore[assignment]

result = await session.execute(stmt)
rows = result.scalars().all()
```

### JSON Text Column Serialization
**Source:** `src/pecp/api/routes/resources.py` lines 222, 282–290
**Apply to:** `projects.py` (environments column), `resources.py` modifications
```python
# Store list as JSON string:
record.environments = json.dumps(env_list)

# Retrieve as list:
json.loads(record.environments or "[]")
```

### IntegrityError → 409 Pattern
**Source:** `src/pecp/api/routes/resources.py` lines 164–183
**Apply to:** `teams.py` POST (duplicate team name), `projects.py` POST (duplicate project within team)
```python
try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise HTTPException(status_code=409, detail="...")
```

### CLI httpx.RequestError Handling
**Source:** `src/pecp/cli/main.py` lines 83–92 (apply command)
**Apply to:** All new CLI commands in team_app, projects, deployments commands
```python
try:
    response = httpx.get(f"{base}/...", timeout=10.0)
except httpx.RequestError as exc:
    console.print(f"[red]Connection error[/red]: {exc}")
    raise typer.Exit(code=1) from exc
```

### CLI `--api-url` Flag Pattern
**Source:** `src/pecp/cli/main.py` lines 71–75 (apply) and 49–52 (helper)
**Apply to:** All new CLI commands
```python
api_url: str | None = typer.Option(
    None,
    "--api-url",
    help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
)
base = _resolve_base_url(api_url)
```

---

## No Analog Found

All files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively.

---

## Metadata

**Analog search scope:** `src/pecp/`, `alembic/versions/`, `tests/`
**Files scanned:** 9 source files read directly
**Pattern extraction date:** 2026-06-14

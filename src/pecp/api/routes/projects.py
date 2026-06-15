"""POST and GET route handlers for /projects (TEAM-02).

Projects belong to a team via team_id FK; duplicate (team, name) returns 409
(D-04 uq_projects_team_name constraint).
environments stored as JSON Text and deserialized to list on read (Pitfall 4).
resource_count computed via LEFT OUTER JOIN + func.count + GROUP BY (Pattern 3).
ARCH-01 enforced on GET: team parameter required.
ARCH-02: every handler accepts ctx: ContextDep.
"""

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


class ProjectCreate(BaseModel):
    """Request body schema for POST /projects."""

    name: str
    team: str
    environments: list[str]


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    """Create a project scoped to a team with a list of environments (TEAM-02).

    Returns 201 with project body: {id, team_id, name, environments (list), created_at}.
    Returns 404 if the team does not exist.
    Returns 409 if a project with the same (team, name) already exists (D-04).
    Returns 422 if required fields are missing or environments is not a list.
    """
    # Lookup the team to get team_id FK and validate existence
    team_result = await session.execute(select(TeamRecord).where(TeamRecord.name == body.team))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team '{body.team}' not found")

    project_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    project = ProjectRecord(
        id=project_id,
        team_id=team.id,
        name=body.name,
        environments=json.dumps(body.environments),  # JSON Text column (Pitfall 4)
        created_at=now,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Project '{body.name}' already exists in team '{body.team}'",
        )

    return {
        "id": project.id,
        "team_id": project.team_id,
        "name": project.name,
        "environments": json.loads(project.environments),  # Pitfall 4: deserialize
        "created_at": project.created_at.isoformat(),
    }


@router.get("")
async def list_projects(
    team: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, object]]:
    """Return all projects for a team with resource_count (TEAM-02).

    ARCH-01: team query parameter is required — returns 400 if absent.
    resource_count is computed via LEFT OUTER JOIN to resource_records so that
    projects with zero resources still appear with resource_count=0 (Pattern 3).
    environments is returned as a JSON list (not a string) — Pitfall 4.
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    # Pattern 3: LEFT OUTER JOIN + func.count + GROUP BY for resource_count
    # Join ProjectRecord → TeamRecord (to filter by team name)
    # LEFT OUTER JOIN ResourceRecord on composite condition:
    #   resource.project == project.name AND resource.team == team AND deleted_at IS NULL
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
            & (ResourceRecord.team == team)
            & (ResourceRecord.deleted_at.is_(None)),
            isouter=True,  # LEFT OUTER JOIN so zero-resource projects still appear
        )
        .where(TeamRecord.name == team)
        .group_by(ProjectRecord.id)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "id": row.id,
            "name": row.name,
            "environments": json.loads(row.environments),  # Pitfall 4: deserialize
            "resource_count": int(row.resource_count),  # explicit int for Decimal safety
        }
        for row in rows
    ]

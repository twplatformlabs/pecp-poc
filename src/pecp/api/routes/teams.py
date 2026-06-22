"""POST and GET route handlers for /teams (TEAM-01).

Teams are unique by name — duplicate POST returns 409 (D-03, uq_teams_name constraint).
The owner is auto-added as the first team_members row with role="owner" (D-02).
Every handler accepts ctx: ContextDep (ARCH-02).
"""

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


class TeamCreate(BaseModel):
    """Request body schema for POST /teams."""

    name: str
    owner: str


def _render_team(team: TeamRecord, members: list[TeamMemberRecord]) -> dict[str, object]:
    """Return a consistent dict representation for both POST and GET /teams responses."""
    return {
        "id": team.id,
        "name": team.name,
        "owner_id": team.owner_id,
        "created_at": team.created_at.isoformat(),
        "members": [
            {
                "user_id": m.user_id,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
            }
            for m in members
        ],
    }


@router.get("")
async def list_teams(
    limit: int = 50,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    """Return all teams for the dashboard team dropdown (D-07).

    GET /teams?limit=50 — no auth required for PoC.
    Returns [{id, name}] — dashboard does not need full team body (T-05-06).
    """
    result = await session.execute(select(TeamRecord).limit(limit))
    rows = result.scalars().all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.post("", status_code=201)
async def create_team(
    body: TeamCreate,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    """Create a team and auto-seed the owner as the first member (D-02).

    Returns 201 with the full team body (id, name, owner_id, created_at, members[]).
    Returns 409 if a team with the same name already exists (D-03).
    Returns 422 if required fields (name, owner) are missing (Pydantic validation).
    """
    team_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    team = TeamRecord(id=team_id, name=body.name, owner_id=body.owner, created_at=now)
    member = TeamMemberRecord(
        team_id=team_id,
        user_id=body.owner,
        role="owner",
        joined_at=now,
    )
    session.add(team)
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")
    return _render_team(team, [member])


@router.get("/{name}")
async def get_team(
    name: str,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    """Return a team by name with all current members.

    Returns 200 with the full team body (id, name, owner_id, created_at, members[]).
    Returns 404 if no team with the given name exists.
    """
    result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    members_result = await session.execute(
        select(TeamMemberRecord).where(TeamMemberRecord.team_id == team.id)
    )
    members = members_result.scalars().all()
    return _render_team(team, list(members))

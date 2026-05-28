"""GET and POST /resources route handlers.

Enforces team-scope (ARCH-01): both handlers require a `team` query parameter
and return HTTP 400 if it is absent.

Every handler receives `ctx: ContextDep` (ARCH-02).
YAML bodies are parsed with yaml.safe_load() exclusively (T-01-01).
"""

import uuid

import yaml
from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError
from sqlalchemy.future import select

from pecp.api.dependencies import ContextDep
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.database import SessionDep
from pecp.persistence.models import ResourceRecord

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
async def list_resources(
    team: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    """Return all resources for a team.

    ARCH-01: `team` query parameter is required — returns 400 if absent.
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.team == team)
    )
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "team": row.team,
            "kind": row.kind,
            "name": row.name,
            "status": row.status,
        }
        for row in rows
    ]


@router.post("", status_code=202)
async def create_resource(
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, str]:
    """Parse a YAML resource spec and persist it.

    ARCH-01: `team` query parameter is required — returns 400 if absent.
    YAML body is parsed with yaml.safe_load (T-01-01).
    Returns 202 with the new resource id, kind, name, and status=pending.
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {exc}") from exc

    try:
        spec = ResourceSpec.model_validate(parsed)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resource_id = uuid.uuid4().hex
    record = ResourceRecord(
        id=resource_id,
        team=team,
        kind=spec.kind,
        name=spec.metadata.name,
        status="pending",
        spec_json=spec.model_dump_json(),
    )
    session.add(record)
    await session.commit()

    return {
        "id": resource_id,
        "status": "pending",
        "kind": spec.kind,
        "name": spec.metadata.name,
    }

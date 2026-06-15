"""GET and POST /resources route handlers.

Enforces team-scope (ARCH-01): both handlers require a `team` query parameter
and return HTTP 400 if it is absent.

Every handler receives `ctx: ContextDep` (ARCH-02).
YAML bodies are parsed with yaml.safe_load() exclusively (T-01-01).
"""

import json
import uuid
from datetime import datetime, timezone

import yaml
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import pecp.persistence.database as _db
from pecp.api.dependencies import ContextDep
from pecp.dispatcher import dispatch
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.database import SessionDep
from pecp.persistence.models import (
    DeploymentRecord,
    ProjectRecord,
    ResourceRecord,
    TeamRecord,
)

router = APIRouter(prefix="/resources", tags=["resources"])


class NoteCreate(BaseModel):
    """Request body schema for POST /resources/{id}/notes (Pitfall 5 — prevents 500 on bad body)."""

    text: str


async def _dispatch_with_session(resource_id: str) -> None:
    """BackgroundTasks wrapper that opens its own AsyncSession (Pitfall 1 — never reuse request session).

    Opens a fresh AsyncSessionLocal so the request session lifetime does not
    affect the background task. The Dispatcher writes terminal status on failure,
    so no try/except is needed here.

    Accesses AsyncSessionLocal via the module reference (`_db.AsyncSessionLocal`) so
    that test fixtures that reload pecp.persistence.database are respected.
    """
    async with _db.AsyncSessionLocal() as session:
        await dispatch(resource_id, session)


async def _maybe_get_project_id(
    project_name: str | None, team: str, session: AsyncSession
) -> str | None:
    """Resolve a project name to its ID for the given team, or return None if not found.

    Pitfall 6: when no matching project exists (wrong name, wrong team, or team not yet
    created), return None gracefully — do NOT raise an error. The deployment audit row
    records project_id=None in that case, which is valid.
    """
    if project_name is None:
        return None
    result = await session.execute(
        select(ProjectRecord.id)
        .join(TeamRecord, ProjectRecord.team_id == TeamRecord.id)
        .where(TeamRecord.name == team)
        .where(ProjectRecord.name == project_name)
    )
    return result.scalar_one_or_none()


@router.get("")
async def list_resources(
    team: str | None = None,
    kind: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, str]]:
    """Return all resources for a team, with optional kind filter.

    ARCH-01: `team` query parameter is required — returns 400 if absent.
    When `kind` is provided, filters results to the specified resource kind.
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    stmt = select(ResourceRecord).where(
        ResourceRecord.team == team,
        ResourceRecord.deleted_at.is_(None),  # D-11: filter out soft-deleted rows (Pitfall 1)
    )
    if kind is not None:
        stmt = stmt.where(ResourceRecord.kind == kind)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "team": row.team,
            "kind": row.kind,
            "name": row.name,
            "status": row.status,
            "env": row.env or "",
        }
        for row in rows
    ]


@router.post("", status_code=202)
async def create_resource(
    background_tasks: BackgroundTasks,
    team: str | None = None,
    body: bytes = Body(b"", media_type="application/x-yaml"),
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, str]:
    """Parse a YAML resource spec and persist it with idempotency (CTRL-01, CTRL-02, CTRL-03).

    ARCH-01: `team` query parameter is required — returns 400 if absent.
    YAML body is parsed with yaml.safe_load (T-01-01).
    Returns 202 with the resource id, kind, name, and status.

    Idempotency (CTRL-03):
    - Same (team, kind, name) + same spec_json → no-op, return existing record.
    - Same (team, kind, name) + different spec_json → update spec, re-enqueue dispatch.
    - New (team, kind, name) → create row, enqueue dispatch via BackgroundTasks.
    - Concurrent race (IntegrityError) → rollback, re-fetch winner, return no-op.
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

    new_spec_json = spec.model_dump_json()

    # Idempotency lookup: check for existing (team, kind, name)
    result = await session.execute(
        select(ResourceRecord).where(
            ResourceRecord.team == team,
            ResourceRecord.kind == spec.kind,
            ResourceRecord.name == spec.metadata.name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        if existing.spec_json == new_spec_json:
            # D-09: no-op — same spec, return existing record unchanged
            return {
                "id": existing.id,
                "status": existing.status,
                "kind": existing.kind,
                "name": existing.name,
            }
        else:
            # D-10: spec changed — update in place, reset status, re-enqueue
            existing.spec_json = new_spec_json
            existing.status = "pending"
            existing.env = spec.metadata.env
            existing.project = spec.metadata.project  # D-07 / D-08: project field population
            deployment = DeploymentRecord(
                id=uuid.uuid4().hex,
                resource_id=existing.id,
                project_id=await _maybe_get_project_id(spec.metadata.project, team, session),
                environment=spec.metadata.env,
                status="pending",
                change_type="update",
                deployed_at=datetime.now(timezone.utc),
            )
            session.add(deployment)
            await session.commit()  # atomic: update + deployment insert in one transaction
            background_tasks.add_task(_dispatch_with_session, existing.id)
            return {
                "id": existing.id,
                "status": "pending",
                "kind": spec.kind,
                "name": spec.metadata.name,
            }

    # New resource — create row
    resource_id = uuid.uuid4().hex
    record = ResourceRecord(
        id=resource_id,
        team=team,
        kind=spec.kind,
        name=spec.metadata.name,
        status="pending",
        spec_json=new_spec_json,
        env=spec.metadata.env,
        project=spec.metadata.project,  # D-07 / D-08: project field from spec metadata
    )
    session.add(record)
    deployment = DeploymentRecord(
        id=uuid.uuid4().hex,
        resource_id=resource_id,
        project_id=await _maybe_get_project_id(spec.metadata.project, team, session),
        environment=spec.metadata.env,
        status="pending",
        change_type="create",
        deployed_at=datetime.now(timezone.utc),
    )
    session.add(deployment)
    try:
        await session.commit()  # atomic: resource + deployment insert in one transaction (Pitfall 2)
    except IntegrityError:
        # Concurrent POST race: another request committed the same (team, kind, name)
        # before us. Roll back and return the winner's record as a no-op response.
        # NOTE: do NOT write a deployment row here — the winner already wrote one (audit integrity).
        await session.rollback()
        race_result = await session.execute(
            select(ResourceRecord).where(
                ResourceRecord.team == team,
                ResourceRecord.kind == spec.kind,
                ResourceRecord.name == spec.metadata.name,
            )
        )
        winner = race_result.scalar_one()
        return {
            "id": winner.id,
            "status": winner.status,
            "kind": winner.kind,
            "name": winner.name,
        }

    background_tasks.add_task(_dispatch_with_session, resource_id)
    return {
        "id": resource_id,
        "status": "pending",
        "kind": spec.kind,
        "name": spec.metadata.name,
    }


@router.get("/{resource_id}")
async def get_resource(
    resource_id: str,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, object]:
    """Return full detail for a single resource by id (CTRL-01).

    Returns 404 if no resource matches the given id.
    Includes all fields: id, team, kind, name, status, env, created_at,
    provider_metadata, activity_log, notes.
    """
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one_or_none()
    if record is None or record.deleted_at is not None:  # Pitfall 5: hide soft-deleted rows
        raise HTTPException(status_code=404, detail="Resource not found")

    return {
        "id": record.id,
        "team": record.team,
        "kind": record.kind,
        "name": record.name,
        "status": record.status,
        "env": record.env,
        "created_at": record.created_at.isoformat(),
        "provider_metadata": json.loads(record.provider_metadata or "{}"),
        "activity_log": json.loads(record.activity_log or "[]"),
        "notes": json.loads(record.notes or "[]"),
    }


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    team: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> None:
    """Soft-delete a resource by id (D-11).

    ARCH-01: `team` query parameter is required — returns 400 if absent.
    Assumption A5: Returns 404 (not 403) when team mismatch to avoid leaking
    existence of resources in other teams (T-3-02-03).
    Returns 204 with empty body on success.
    Soft-delete: sets deleted_at instead of hard-deleting — the row stays in DB
    for the deployment audit trail FK (D-11). Second DELETE returns 404 because
    the initial lookup filters deleted_at IS NULL.
    Writes a DeploymentRecord(change_type=delete) atomically in the same commit (D-10).
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    result = await session.execute(
        select(ResourceRecord).where(
            ResourceRecord.id == resource_id,
            ResourceRecord.deleted_at.is_(None),  # D-11: filter so second DELETE returns 404
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    if record.team != team:
        # Collapse team mismatch into 404 to avoid leaking cross-team resource existence (A5)
        raise HTTPException(status_code=404, detail="Resource not found")

    now = datetime.now(timezone.utc)
    record.deleted_at = now  # soft-delete: set deleted_at instead of session.delete (D-11)

    deployment = DeploymentRecord(
        id=uuid.uuid4().hex,
        resource_id=record.id,
        project_id=await _maybe_get_project_id(record.project, record.team, session),
        environment=record.env,
        status=record.status,
        change_type="delete",
        deployed_at=now,  # same timestamp as deleted_at for audit clarity
    )
    session.add(deployment)
    await session.commit()  # atomic: soft-delete update + deployment insert in one transaction
    return None


@router.post("/{resource_id}/notes", status_code=201)
async def add_note(
    resource_id: str,
    body: NoteCreate,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> dict[str, list[dict[str, str]]]:
    """Append a PE note to a resource (CTRL-04).

    Author is inferred from ctx.user_id (D-04, no user-supplied author).
    Timestamp is set server-side in UTC (D-06).
    Returns 201 with the full notes list after appending.
    Returns 404 if no resource matches the given id.
    Returns 422 if the request body is missing `text` (Pitfall 5 — NoteCreate model).
    """
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    current_notes: list[dict[str, str]] = json.loads(record.notes or "[]")
    current_notes.append(
        {
            "author": ctx.user_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "text": body.text,
        }
    )
    record.notes = json.dumps(current_notes)
    await session.commit()
    return {"notes": current_notes}

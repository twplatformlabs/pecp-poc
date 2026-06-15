"""GET handler for /deployments (TEAM-03).

JOINs deployments → resource_records to surface resource name/kind.
Sorted by deployed_at DESC (D-16).
ARCH-01 enforced: team parameter required, returns 400 if absent.
ARCH-02: handler accepts ctx: ContextDep.
Note: deleted_at filter intentionally NOT applied — deployment audit trail
must remain visible even after resource is soft-deleted (D-11 preserves the
row so the deployment FK and audit trail keep working).
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select

from pecp.api.dependencies import ContextDep
from pecp.persistence.database import SessionDep
from pecp.persistence.models import DeploymentRecord, ResourceRecord

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("")
async def list_deployments(
    team: str | None = None,
    environment: str | None = None,
    ctx: ContextDep = ...,  # type: ignore[assignment]
    session: SessionDep = ...,  # type: ignore[assignment]
) -> list[dict[str, object]]:
    """Return deployment audit rows for a team, optionally filtered by environment.

    ARCH-01: team query parameter is required — returns 400 if absent.
    environment is optional — when absent, all environments are returned.
    Rows are JOIN'd to resource_records to include resource_name and kind.
    Results are sorted by deployed_at DESC (newest first, D-16).
    Soft-deleted resources are NOT filtered out — the audit trail is immutable.
    """
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")

    # Pattern 2: multi-table JOIN — deployments → resource_records
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
        .order_by(DeploymentRecord.deployed_at.desc())  # D-16
    )

    if environment is not None:
        stmt = stmt.where(DeploymentRecord.environment == environment)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "resource_name": row.resource_name,
            "kind": row.kind,
            "change_type": row.change_type,
            "status": row.status,
            "deployed_at": row.deployed_at.isoformat(),
            "environment": row.environment,
        }
        for row in rows
    ]

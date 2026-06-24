"""Tests for commit-before-hook invariant (Phase 7 SC-4, T-07-01).

Proves that the DB row created by POST /teams exists and is queryable
when on_team_create hook fires — verifying BackgroundTasks executes AFTER
session.commit().
"""

from httpx import AsyncClient
from sqlalchemy.future import select

import pecp.persistence.database as _db
from pecp.integrations import INTEGRATION_REGISTRY
from pecp.integrations.base import IntegrationBase, TeamSnapshot
from pecp.persistence.models import TeamRecord


class DbCheckIntegration(IntegrationBase):
    """Integration that verifies the team row exists when its hook runs.

    Opens its own session inside on_team_create and issues a SELECT for the
    team by name. Stores findings on the instance for test assertions.
    """

    def __init__(self) -> None:
        self.row_exists_when_hook_ran: bool = False
        self.row_id: str | None = None

    async def on_team_create(self, team: TeamSnapshot) -> None:
        async with _db.AsyncSessionLocal() as session:
            result = await session.execute(
                select(TeamRecord).where(TeamRecord.name == team.name)
            )
            row = result.scalar_one_or_none()
            self.row_exists_when_hook_ran = row is not None
            self.row_id = row.id if row is not None else None


async def test_hook_fires_after_commit(client: AsyncClient) -> None:
    """Prove commit-before-hook: DB row exists inside on_team_create.

    DbCheckIntegration opens its own session and queries TeamRecord by name.
    If the row is found, it proves session.commit() completed before the
    BackgroundTasks hook executed.
    """
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        dbcheck = DbCheckIntegration()
        INTEGRATION_REGISTRY.append(dbcheck)

        response = await client.post(
            "/teams",
            json={"name": "commit-order-team", "owner": "alice"},
        )
        assert response.status_code == 201
        team_id = response.json()["id"]

        # The hook ran inline (BackgroundTasks via ASGITransport) — assert findings
        assert dbcheck.row_exists_when_hook_ran is True, (
            "Team record was NOT found inside on_team_create — "
            "hook may have fired before session.commit()"
        )
        assert dbcheck.row_id == team_id, (
            f"Row id mismatch: hook saw {dbcheck.row_id}, "
            f"response returned {team_id}"
        )
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)

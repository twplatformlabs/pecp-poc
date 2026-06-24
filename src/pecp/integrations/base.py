"""IntegrationBase ABC and snapshot dataclasses for PECP lifecycle hooks (INTG-01)."""

from abc import ABC
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TeamSnapshot:
    """Data snapshot passed to on_team_create hooks (avoids DetachedInstanceError)."""

    id: str
    name: str
    owner_id: str
    created_at: datetime
    github_team_slug: str | None = None


@dataclass
class ProjectSnapshot:
    """Data snapshot passed to on_project_create hooks."""

    id: str
    name: str
    team_id: str
    environments: list[str]
    created_at: datetime


@dataclass
class MemberSnapshot:
    """Data snapshot passed to on_member_add / on_member_remove hooks."""

    user_id: str
    role: str


class IntegrationBase(ABC):
    """Contract for all PECP lifecycle integrations (INTG-01).

    All hooks are optional — default implementations are no-ops.
    Errors MUST NOT propagate to callers; the dispatcher wraps each call.
    """

    async def on_team_create(self, team: TeamSnapshot) -> None:
        pass

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        pass

    async def aclose(self) -> None:
        """Close the integration's resources (e.g. httpx.AsyncClient connection pool).

        Called from FastAPI lifespan shutdown. Default is a no-op —
        integrations that own resources override this method.
        """
        pass

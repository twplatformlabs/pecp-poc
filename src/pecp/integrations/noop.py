"""NoOpIntegration — call-recording spy for tests and reference implementation (INTG-01)."""

from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)


class NoOpIntegration(IntegrationBase):
    """No-op integration for tests and as a reference implementation.

    Records calls for assertion in tests via self.calls list.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def on_team_create(self, team: TeamSnapshot) -> None:
        self.calls.append(("on_team_create", team))

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_project_create", project))

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_member_add", user))

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        self.calls.append(("on_member_remove", user))

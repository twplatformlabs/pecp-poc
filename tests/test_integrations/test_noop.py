"""Tests for NoOpIntegration spy (INTG-01)."""

from datetime import datetime, timezone

from pecp.integrations.base import MemberSnapshot, ProjectSnapshot, TeamSnapshot
from pecp.integrations.noop import NoOpIntegration


def test_noop_calls_starts_empty() -> None:
    """NoOpIntegration().calls is an empty list at construction."""
    noop = NoOpIntegration()
    assert noop.calls == []


async def test_noop_records_on_team_create() -> None:
    """Awaiting on_team_create records the call and snapshot."""
    noop = NoOpIntegration()
    team = TeamSnapshot(
        id="t1",
        name="test-team",
        owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )
    await noop.on_team_create(team)
    assert noop.calls == [("on_team_create", team)]


async def test_noop_records_on_project_create() -> None:
    """on_project_create records only the project snapshot (first positional arg)."""
    noop = NoOpIntegration()
    project = ProjectSnapshot(
        id="p1",
        name="test-project",
        team_id="t1",
        environments=["dev"],
        created_at=datetime.now(timezone.utc),
    )
    team = TeamSnapshot(
        id="t1",
        name="test-team",
        owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )
    await noop.on_project_create(project, team)
    assert noop.calls == [("on_project_create", project)]


async def test_noop_records_on_member_add_and_remove_in_order() -> None:
    """Call add then remove; verify the call order is preserved."""
    noop = NoOpIntegration()
    user = MemberSnapshot(user_id="alice", role="contributor")
    team = TeamSnapshot(
        id="t1",
        name="test-team",
        owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )

    await noop.on_member_add(user, team)
    await noop.on_member_remove(user, team)

    assert noop.calls == [
        ("on_member_add", user),
        ("on_member_remove", user),
    ]

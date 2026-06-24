"""Tests for IntegrationBase ABC (INTG-01)."""

import dataclasses
from datetime import datetime, timezone

from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)


def test_integration_base_subclass_with_no_overrides_instantiates() -> None:
    """IntegrationBase can be subclassed with zero overrides (hooks are NOT @abstractmethod)."""

    class BareIntegration(IntegrationBase):
        pass

    obj = BareIntegration()
    assert obj is not None


async def test_default_on_team_create_is_no_op() -> None:
    """Default on_team_create returns None and raises no exception."""

    class BareIntegration(IntegrationBase):
        pass

    obj = BareIntegration()
    team = TeamSnapshot(
        id="t1",
        name="test-team",
        owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )
    result = await obj.on_team_create(team)
    assert result is None


def test_partial_subclass_with_only_on_team_create_instantiates() -> None:
    """A subclass overriding only on_team_create still instantiates; other hooks are no-ops."""

    class PartialIntegration(IntegrationBase):
        async def on_team_create(self, team: TeamSnapshot) -> None:
            pass

    obj = PartialIntegration()
    assert obj is not None


def test_team_snapshot_fields() -> None:
    """TeamSnapshot is a dataclass with expected fields; github_team_slug defaults to None."""
    snap = TeamSnapshot(
        id="t1",
        name="toxins-research",
        owner_id="alice",
        created_at=datetime.now(timezone.utc),
    )
    assert dataclasses.is_dataclass(snap)
    assert snap.id == "t1"
    assert snap.name == "toxins-research"
    assert snap.owner_id == "alice"
    assert snap.github_team_slug is None


def test_project_snapshot_fields() -> None:
    """ProjectSnapshot is a dataclass with expected fields including environments list."""
    snap = ProjectSnapshot(
        id="p1",
        name="nexus-dashboard",
        team_id="t1",
        environments=["dev", "prod"],
        created_at=datetime.now(timezone.utc),
    )
    assert dataclasses.is_dataclass(snap)
    assert snap.id == "p1"
    assert snap.name == "nexus-dashboard"
    assert snap.team_id == "t1"
    assert snap.environments == ["dev", "prod"]


def test_member_snapshot_fields() -> None:
    """MemberSnapshot is a dataclass with user_id and role fields."""
    snap = MemberSnapshot(user_id="alice", role="owner")
    assert dataclasses.is_dataclass(snap)
    assert snap.user_id == "alice"
    assert snap.role == "owner"

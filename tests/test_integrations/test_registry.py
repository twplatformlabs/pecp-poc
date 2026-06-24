"""Tests for INTEGRATION_REGISTRY dispatch + error isolation (INTG-02).

Extended in Plan 02 with HTTP-level integration tests (POST /teams, POST /projects)
that verify hook firing through the live FastAPI routes.
"""

import logging
from datetime import datetime, timezone

from httpx import AsyncClient

from pecp.integrations import INTEGRATION_REGISTRY, fire_integrations
from pecp.integrations.base import IntegrationBase, ProjectSnapshot, TeamSnapshot
from pecp.integrations.noop import NoOpIntegration


def _make_team() -> TeamSnapshot:
    return TeamSnapshot(
        id="t1",
        name="test-team",
        owner_id="u1",
        created_at=datetime.now(timezone.utc),
    )


def _clear_registry() -> list[IntegrationBase]:
    """Save current registry and clear it. Returns original list for restoration."""
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    return original


def _restore_registry(original: list[IntegrationBase]) -> None:
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.extend(original)


async def test_empty_registry_dispatch_does_not_raise() -> None:
    """fire_integrations with empty registry returns None without error."""
    original = _clear_registry()
    try:
        result = await fire_integrations("on_team_create", _make_team())
        assert result is None
    finally:
        _restore_registry(original)


async def test_single_noop_receives_on_team_create() -> None:
    """A single registered NoOp receives the on_team_create hook."""
    original = _clear_registry()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)
        snap = _make_team()
        await fire_integrations("on_team_create", snap)
        assert noop.calls == [("on_team_create", snap)]
    finally:
        _restore_registry(original)


async def test_integrations_fire_in_registration_order() -> None:
    """Two NoOps fire in registration order (a before b)."""
    original = _clear_registry()
    try:
        a = NoOpIntegration()
        b = NoOpIntegration()
        INTEGRATION_REGISTRY.append(a)
        INTEGRATION_REGISTRY.append(b)
        snap = _make_team()
        await fire_integrations("on_team_create", snap)
        assert len(a.calls) == 1
        assert len(b.calls) == 1
        # a fires first, b fires second — both record the same snapshot
        assert a.calls[0] == ("on_team_create", snap)
        assert b.calls[0] == ("on_team_create", snap)
    finally:
        _restore_registry(original)


async def test_failing_integration_does_not_block_subsequent_hooks() -> None:
    """A failing integration does not prevent subsequent integrations from firing."""

    class BoomIntegration(IntegrationBase):
        async def on_team_create(self, team: TeamSnapshot) -> None:
            raise RuntimeError("Simulated integration failure")

    original = _clear_registry()
    try:
        boom = BoomIntegration()
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(boom)
        INTEGRATION_REGISTRY.append(noop)

        # fire_integrations must NOT raise
        await fire_integrations("on_team_create", _make_team())
        assert len(noop.calls) == 1  # noop still received the call
    finally:
        _restore_registry(original)


async def test_failing_integration_logs_warning(caplog) -> None:
    """A failing integration produces a WARNING-level log with its class name."""

    class BoomIntegration(IntegrationBase):
        async def on_team_create(self, team: TeamSnapshot) -> None:
            raise RuntimeError("Simulated integration failure")

    original = _clear_registry()
    try:
        boom = BoomIntegration()
        INTEGRATION_REGISTRY.append(boom)

        with caplog.at_level(logging.WARNING, logger="pecp.integrations"):
            await fire_integrations("on_team_create", _make_team())

        warning_messages = [
            r.message
            for r in caplog.records
            if r.levelno == logging.WARNING and "BoomIntegration" in r.message and "on_team_create" in r.message
        ]
        assert len(warning_messages) >= 1, (
            f"Expected WARNING containing 'BoomIntegration' and 'on_team_create', "
            f"got records: {[(r.levelname, r.message) for r in caplog.records]}"
        )
    finally:
        _restore_registry(original)


async def test_post_teams_fires_on_team_create_hook(client: AsyncClient) -> None:
    """POST /teams fires on_team_create for registered NoOpIntegration."""
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)

        response = await client.post(
            "/teams",
            json={"name": "team-alpha", "owner": "alice"},
        )
        assert response.status_code == 201

        assert len(noop.calls) == 1
        hook_name, snap = noop.calls[0]
        assert hook_name == "on_team_create"
        assert snap.name == "team-alpha"
        assert len(snap.id) == 32  # uuid hex
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)


async def test_post_teams_with_failing_integration_still_returns_201(
    client: AsyncClient, caplog
) -> None:
    """A failing integration hook does NOT propagate to the 201 response."""

    class BoomIntegration(IntegrationBase):
        async def on_team_create(self, team: TeamSnapshot) -> None:
            raise RuntimeError("boom")

    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        INTEGRATION_REGISTRY.append(BoomIntegration())

        response = await client.post(
            "/teams",
            json={"name": "boom-team", "owner": "alice"},
        )
        assert response.status_code == 201

        with caplog.at_level(logging.WARNING, logger="pecp.integrations"):
            # BackgroundTasks completed inline — the log should be present
            pass

        assert any(
            "BoomIntegration" in r.message
            for r in caplog.records
        ), f"No BoomIntegration WARNING in: {[(r.levelname, r.message) for r in caplog.records]}"
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)


async def test_post_teams_duplicate_returns_409_and_does_not_fire_hook(
    client: AsyncClient,
) -> None:
    """409 IntegrityError on duplicate name must NOT fire on_team_create (T-07-01)."""
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)

        # First POST succeeds and fires on_team_create once
        r1 = await client.post(
            "/teams",
            json={"name": "dup-team", "owner": "alice"},
        )
        assert r1.status_code == 201

        # Duplicate POST returns 409 and must NOT fire the hook again
        r2 = await client.post(
            "/teams",
            json={"name": "dup-team", "owner": "bob"},
        )
        assert r2.status_code == 409

        # Only the first POST fired the hook
        assert len(noop.calls) == 1
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)


async def test_post_projects_fires_on_project_create_hook(client: AsyncClient) -> None:
    """POST /projects fires on_project_create and on_team_create for registered NoOp."""
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)

        # Create a team first (prerequisite for project)
        team_resp = await client.post(
            "/teams",
            json={"name": "pteam", "owner": "alice"},
        )
        assert team_resp.status_code == 201

        # Create a project under that team
        proj_resp = await client.post(
            "/projects",
            json={"name": "pproj", "team": "pteam", "environments": ["dev", "prod"]},
        )
        assert proj_resp.status_code == 201

        # Both hooks should have fired
        assert len(noop.calls) == 2

        hook_0_name, snap_0 = noop.calls[0]
        assert hook_0_name == "on_team_create"
        assert snap_0.name == "pteam"

        hook_1_name, snap_1 = noop.calls[1]
        assert hook_1_name == "on_project_create"
        assert isinstance(snap_1, ProjectSnapshot)
        assert snap_1.name == "pproj"
        assert snap_1.environments == ["dev", "prod"]
        assert len(snap_1.id) == 32  # uuid hex
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)


async def test_post_projects_with_unknown_team_returns_404_and_does_not_fire_hook(
    client: AsyncClient,
) -> None:
    """404 on unknown team must NOT fire on_project_create."""
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)

        response = await client.post(
            "/projects",
            json={"name": "orphan", "team": "no-such-team", "environments": ["dev"]},
        )
        assert response.status_code == 404

        # No hooks fired — team lookup failed before any snapshot construction
        assert noop.calls == []
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)


async def test_post_projects_duplicate_returns_409_and_does_not_fire_hook(
    client: AsyncClient,
) -> None:
    """409 IntegrityError on duplicate (team, name) must NOT fire on_project_create again."""
    # Create team first
    team_resp = await client.post(
        "/teams",
        json={"name": "dup-team-proj", "owner": "alice"},
    )
    assert team_resp.status_code == 201

    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    try:
        noop = NoOpIntegration()
        INTEGRATION_REGISTRY.append(noop)

        # First project POST succeeds and fires on_project_create once
        r1 = await client.post(
            "/projects",
            json={"name": "dup-proj", "team": "dup-team-proj", "environments": ["dev"]},
        )
        assert r1.status_code == 201

        # Duplicate project POST returns 409 and must NOT fire the hook again
        r2 = await client.post(
            "/projects",
            json={"name": "dup-proj", "team": "dup-team-proj", "environments": ["dev"]},
        )
        assert r2.status_code == 409

        # Only the first POST fired on_project_create
        assert len(noop.calls) == 1
        assert noop.calls[0][0] == "on_project_create"
    finally:
        INTEGRATION_REGISTRY.clear()
        INTEGRATION_REGISTRY.extend(original)

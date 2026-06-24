"""Tests for GitHubIntegration (GH-01 through GH-05)."""

from datetime import datetime, timezone

import httpx
import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy.future import select

import pecp.persistence.database as _db
from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)
from pecp.integrations.github import GitHubIntegration, _sanitize
from pecp.integrations import IntegrationConfig
from pecp.persistence.models import Base, ProjectRecord, ProjectRepoRecord, TeamRecord

FAKE_CONFIG = IntegrationConfig(GITHUB_PAT="ghp_FAKE", GITHUB_ORG="acme")


@pytest.fixture(autouse=True)
async def _ensure_schema() -> None:
    """Drop and recreate all tables on the module-level engine before each test.

    DB writeback helpers (_write_team_slug, _write_project_repo, _fetch_team_slug)
    use AsyncSessionLocal from the module-level engine. This autouse fixture
    ensures a clean schema on the module-level engine before each test.
    """
    async with _db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def _make_team(**overrides: object) -> TeamSnapshot:
    defaults = {
        "id": "t1",
        "name": "Toxins Research",
        "owner_id": "u1",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return TeamSnapshot(**defaults)


def _make_project(**overrides: object) -> ProjectSnapshot:
    defaults = {
        "id": "p1",
        "name": "ML Platform",
        "team_id": "t1",
        "environments": ["dev"],
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return ProjectSnapshot(**defaults)


def _make_member(**overrides: object) -> MemberSnapshot:
    defaults = {"user_id": "alice", "role": "contributor"}
    defaults.update(overrides)
    return MemberSnapshot(**defaults)


# ── GH-01: Class structure ──────────────────────────────────────────────


async def test_github_integration_is_integration_base() -> None:
    """GH-01: GitHubIntegration implements IntegrationBase."""
    integration = GitHubIntegration(FAKE_CONFIG)
    assert isinstance(integration, IntegrationBase)
    for name in ("on_team_create", "on_project_create", "on_member_add", "on_member_remove", "aclose"):
        assert callable(getattr(integration, name, None))


# ── D-07: Name sanitization ────────────────────────────────────────────


async def test_sanitize_transforms_name() -> None:
    """D-07: _sanitize lowercases and replaces spaces with hyphens."""
    assert _sanitize("Toxins Research") == "toxins-research"
    assert _sanitize("ML Platform") == "ml-platform"
    assert _sanitize("already-lower") == "already-lower"
    assert _sanitize("UPPER CASE") == "upper-case"


# ── GH-02: Team creation ────────────────────────────────────────────────


async def test_on_team_create_creates_team_and_writes_slug(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-02: on_team_create calls POST /orgs/{org}/teams and writes slug to DB."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        json={"slug": "toxins-research", "name": "toxins-research"},
        status_code=201,
    )

    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    integration = GitHubIntegration(FAKE_CONFIG)
    team = _make_team()
    await integration.on_team_create(team)

    async with _db.AsyncSessionLocal() as session:
        result = await session.execute(select(TeamRecord).where(TeamRecord.id == "t1"))
        row = result.scalar_one()
        assert row.github_team_slug == "toxins-research"


async def test_on_team_create_422_is_non_fatal(httpx_mock: HTTPXMock) -> None:
    """GH-05, D-01: 422 on team create is logged and skipped — does not crash."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        status_code=422,
        json={"message": "Validation Failed"},
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    team = _make_team()
    await integration.on_team_create(team)
    # No exception raised — D-01: 422 is logged-and-skip


# ── GH-03: Project/repo creation ────────────────────────────────────────


async def test_on_project_create_creates_repo_and_writes_url(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-03: on_project_create calls POST /orgs/{org}/repos and inserts ProjectRepoRecord."""

    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/repos",
        json={
            "html_url": "https://github.com/acme/toxins-research-ml-platform",
            "name": "toxins-research-ml-platform",
        },
        status_code=201,
    )

    async with _db.AsyncSessionLocal() as session:
        project_record = ProjectRecord(
            id="p1", team_id="t1", name="ML Platform",
            environments='["dev"]', created_at=datetime.now(timezone.utc),
        )
        session.add(project_record)
        await session.commit()

    integration = GitHubIntegration(FAKE_CONFIG)
    team = _make_team()
    project = _make_project()
    await integration.on_project_create(project, team)

    async with _db.AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProjectRepoRecord).where(ProjectRepoRecord.project_id == "p1")
        )
        repo = result.scalar_one_or_none()
    assert repo is not None
    assert repo.repo_name == "toxins-research-ml-platform"
    assert repo.repo_url == "https://github.com/acme/toxins-research-ml-platform"


async def test_on_project_create_422_is_non_fatal(httpx_mock: HTTPXMock) -> None:
    """GH-05, D-01: 422 on repo create is logged and skipped — does not crash."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/repos",
        status_code=422,
        json={"message": "Validation Failed"},
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    project = _make_project()
    team = _make_team()
    await integration.on_project_create(project, team)
    # No exception raised — D-01: 422 is logged-and-skip


# ── GH-04: Member sync ─────────────────────────────────────────────────


async def test_on_member_add_syncs_to_github(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-04: on_member_add calls PUT memberships endpoint."""
    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            github_team_slug="toxins-research",
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    httpx_mock.add_response(
        method="PUT",
        url="https://api.github.com/orgs/acme/teams/toxins-research/memberships/alice",
        json={"state": "active", "role": "member"},
        status_code=200,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    user = _make_member()
    team = _make_team()
    await integration.on_member_add(user, team)
    # No exception means success


async def test_on_member_add_null_slug_skips_gracefully(
    httpx_mock: HTTPXMock, caplog,
) -> None:
    """GH-04, D-05, D-06: on_member_add skips when github_team_slug is NULL."""
    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            github_team_slug=None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    caplog.set_level("WARNING")
    integration = GitHubIntegration(FAKE_CONFIG)
    user = _make_member()
    team = _make_team()
    await integration.on_member_add(user, team)

    assert any("no github_team_slug" in rec.message for rec in caplog.records)


async def test_on_member_remove_syncs_to_github(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-04: on_member_remove calls DELETE memberships endpoint."""
    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            github_team_slug="toxins-research",
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    httpx_mock.add_response(
        method="DELETE",
        url="https://api.github.com/orgs/acme/teams/toxins-research/memberships/alice",
        status_code=204,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    user = _make_member()
    team = _make_team()
    await integration.on_member_remove(user, team)
    # No exception means success


async def test_on_member_remove_404_is_idempotent(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-04, GH-05, D-02: 404 on DELETE membership is treated as success."""
    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            github_team_slug="toxins-research",
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    httpx_mock.add_response(
        method="DELETE",
        url="https://api.github.com/orgs/acme/teams/toxins-research/memberships/alice",
        status_code=404,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    user = _make_member()
    team = _make_team()
    await integration.on_member_remove(user, team)
    # No exception — D-02: 404 means user already not a member


async def test_on_member_add_user_not_found_is_non_fatal(
    httpx_mock: HTTPXMock,
) -> None:
    """GH-05: 404 on PUT membership raises HTTPStatusError (caught by fire_integrations)."""
    async with _db.AsyncSessionLocal() as session:
        record = TeamRecord(
            id="t1", name="Toxins Research", owner_id="u1",
            github_team_slug="toxins-research",
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    httpx_mock.add_response(
        method="PUT",
        url="https://api.github.com/orgs/acme/teams/toxins-research/memberships/alice",
        status_code=404,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    user = _make_member()
    team = _make_team()
    with pytest.raises(httpx.HTTPStatusError):
        await integration.on_member_add(user, team)


# ── GH-05: Error handling ──────────────────────────────────────────────


async def test_rate_limit_is_non_fatal(httpx_mock: HTTPXMock) -> None:
    """GH-05: 429 rate limit raises HTTPStatusError (caught by fire_integrations)."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.github.com/orgs/acme/teams",
        status_code=429,
    )

    integration = GitHubIntegration(FAKE_CONFIG)
    team = _make_team()
    with pytest.raises(httpx.HTTPStatusError):
        await integration.on_team_create(team)


# ── D-03: Resource cleanup ─────────────────────────────────────────────


async def test_aclose_closes_client() -> None:
    """D-03: aclose() does not raise."""
    integration = GitHubIntegration(FAKE_CONFIG)
    await integration.aclose()

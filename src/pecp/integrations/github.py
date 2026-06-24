"""GitHubIntegration — provisions GitHub teams, repos, and memberships (GH-01 through GH-05)."""

import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.future import select

import pecp.persistence.database as _db
from pecp.integrations import IntegrationConfig
from pecp.integrations.base import (
    IntegrationBase,
    MemberSnapshot,
    ProjectSnapshot,
    TeamSnapshot,
)

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _sanitize(name: str) -> str:
    """Lowercase and replace spaces with hyphens for GitHub API consumption (D-07)."""
    return name.lower().replace(" ", "-")


async def _write_team_slug(team_id: str, slug: str) -> None:
    """Open a fresh AsyncSession to write github_team_slug back to TeamRecord.

    A new session is required because the request-scoped session is closed
    by the time this background task runs.
    """
    from pecp.persistence.models import TeamRecord

    async with _db.AsyncSessionLocal() as session:
        result = await session.execute(select(TeamRecord).where(TeamRecord.id == team_id))
        record = result.scalar_one_or_none()
        if record is not None:
            record.github_team_slug = slug
            await session.commit()
        else:
            logger.warning("_write_team_slug: TeamRecord %s not found", team_id)


async def _write_project_repo(project_id: str, repo_name: str, repo_url: str) -> None:
    """Open a fresh AsyncSession to insert a ProjectRepoRecord.

    A new session is required because the request-scoped session is closed
    by the time this background task runs.
    """
    from pecp.persistence.models import ProjectRepoRecord

    async with _db.AsyncSessionLocal() as session:
        repo = ProjectRepoRecord(
            id=uuid.uuid4().hex,
            project_id=project_id,
            repo_name=repo_name,
            repo_url=repo_url,
            created_at=datetime.now(timezone.utc),
        )
        session.add(repo)
        await session.commit()


async def _fetch_team_slug(team_id: str) -> str | None:
    """Re-fetch github_team_slug from DB to avoid race conditions.

    on_team_create's DB writeback may not have completed before a member
    hook fires, so we re-fetch rather than relying on TeamSnapshot value (D-05, D-06).
    """
    from pecp.persistence.models import TeamRecord

    async with _db.AsyncSessionLocal() as session:
        result = await session.execute(select(TeamRecord).where(TeamRecord.id == team_id))
        record = result.scalar_one_or_none()
        if record is not None:
            return record.github_team_slug
        logger.warning("_fetch_team_slug: TeamRecord %s not found", team_id)
        return None


class GitHubIntegration(IntegrationBase):
    """GitHub integration that provisions teams, repos, and memberships (GH-01).

    Uses httpx.AsyncClient with Bearer token auth. All errors are caught
    inside hooks and re-raised — fire_integrations prevents propagation.
    """

    def __init__(self, config: IntegrationConfig) -> None:
        self._org = config.GITHUB_ORG
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {config.GITHUB_PAT}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def on_team_create(self, team: TeamSnapshot) -> None:
        """Create a GitHub team with a sanitized name (GH-02, D-01, D-07)."""
        sanitized = _sanitize(team.name)
        try:
            resp = await self._client.post(
                f"/orgs/{self._org}/teams",
                json={"name": sanitized, "privacy": "closed"},
            )
            if resp.status_code == 422:
                logger.warning(
                    "GitHub team creation 422 (already exists) for team %s — skipping (D-01)",
                    team.name,
                )
                return
            resp.raise_for_status()
            slug: str = resp.json()["slug"]
            await _write_team_slug(team.id, slug)
        except Exception:
            logger.exception("GitHubIntegration.on_team_create failed for team %s", team.name)
            raise

    async def on_project_create(self, project: ProjectSnapshot, team: TeamSnapshot) -> None:
        """Create an empty GitHub repo named {team-name}-{project-name} (GH-03, D-01, D-07)."""
        repo_name = _sanitize(f"{team.name}-{project.name}")
        try:
            resp = await self._client.post(
                f"/orgs/{self._org}/repos",
                json={"name": repo_name, "private": False, "auto_init": False},
            )
            if resp.status_code == 422:
                logger.warning(
                    "GitHub repo creation 422 (already exists) for %s — skipping (D-01)",
                    repo_name,
                )
                return
            resp.raise_for_status()
            repo_url: str = resp.json()["html_url"]
            await _write_project_repo(project.id, repo_name, repo_url)
        except Exception:
            logger.exception(
                "GitHubIntegration.on_project_create failed for project %s", project.name
            )
            raise

    async def on_member_add(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        """Add a GitHub user to the team via PUT membership (GH-04, D-05, D-06)."""
        slug = await _fetch_team_slug(team.id)
        if slug is None:
            logger.warning(
                "on_member_add: team %s has no github_team_slug — skipping (D-06)",
                team.name,
            )
            return
        try:
            resp = await self._client.put(
                f"/orgs/{self._org}/teams/{slug}/memberships/{user.user_id}",
                json={"role": "member"},
            )
            resp.raise_for_status()
        except Exception:
            logger.exception(
                "GitHubIntegration.on_member_add failed for user %s on team %s",
                user.user_id,
                team.name,
            )
            raise

    async def on_member_remove(self, user: MemberSnapshot, team: TeamSnapshot) -> None:
        """Remove a GitHub user from the team via DELETE membership (GH-04, D-02, D-05, D-06)."""
        slug = await _fetch_team_slug(team.id)
        if slug is None:
            logger.warning(
                "on_member_remove: team %s has no github_team_slug — skipping (D-06)",
                team.name,
            )
            return
        try:
            resp = await self._client.delete(
                f"/orgs/{self._org}/teams/{slug}/memberships/{user.user_id}",
            )
            if resp.status_code not in (204, 404):
                resp.raise_for_status()
        except Exception:
            logger.exception(
                "GitHubIntegration.on_member_remove failed for user %s on team %s",
                user.user_id,
                team.name,
            )
            raise

    async def aclose(self) -> None:
        """Close the httpx.AsyncClient connection pool (D-03)."""
        await self._client.aclose()

"""Tests for API routes (ARCH-01, ARCH-02).

The context dependency test (test_context_dependency_callable) calls
get_request_context() directly — no running app needed.

The three route tests use the `client` fixture and require src/pecp/api/main.py
to exist (created in Plan 03). They were previously SKIPPED and are now active.
"""

from httpx import AsyncClient

from pecp.api.dependencies import get_request_context


async def test_context_dependency_callable() -> None:
    """ARCH-02: get_request_context() returns expected stub values (no app needed)."""
    ctx = await get_request_context()
    assert ctx.user_id == "stub-user"
    assert "platform" in ctx.team_memberships
    assert ctx.is_pe_admin is False


async def test_get_resources_without_team_returns_400(client: AsyncClient) -> None:
    """ARCH-01: GET /resources without team param returns 400."""
    response = await client.get("/resources")
    assert response.status_code == 400
    assert response.json()["detail"] == "team parameter is required"


async def test_get_resources_with_team_returns_200(client: AsyncClient) -> None:
    """ARCH-01: GET /resources with team param returns 200 with a JSON list."""
    response = await client.get("/resources", params={"team": "platform"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_post_resource_without_team_returns_400(client: AsyncClient) -> None:
    """ARCH-01: POST /resources without team param returns 400."""
    response = await client.post("/resources", content=b"")
    assert response.status_code == 400
    assert response.json()["detail"] == "team parameter is required"

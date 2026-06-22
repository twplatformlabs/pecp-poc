"""Tests for TEAM-01 — team creation, member tracking, duplicate-name rejection.

Wave 0 scaffolds — FAIL intentionally until Plan 02 implements team routes.
"""

from httpx import AsyncClient


async def test_list_teams_returns_all(client: AsyncClient) -> None:
    """Phase 5 Plan 01: GET /teams returns a JSON list of all teams (D-07)."""
    # Seed 3 teams
    await client.post("/teams", json={"name": "alpha-team", "owner": "alice"})
    await client.post("/teams", json={"name": "beta-team", "owner": "bob"})
    await client.post("/teams", json={"name": "gamma-team", "owner": "carol"})

    response = await client.get("/teams")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 3
    # Each element must have exactly id and name keys
    for item in body:
        assert "id" in item
        assert "name" in item


async def test_list_teams_respects_limit(client: AsyncClient) -> None:
    """Phase 5 Plan 01: GET /teams?limit=2 returns only 2 teams."""
    # Seed 5 teams
    for i in range(5):
        await client.post("/teams", json={"name": f"team-{i}", "owner": "admin"})

    response = await client.get("/teams?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2


async def test_cors_allows_vite_dev_origin(client: AsyncClient) -> None:
    """Phase 5 Plan 01: CORS preflight from http://localhost:5173 returns correct header (D-06)."""
    response = await client.options(
        "/resources",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight should return 200 with the allow-origin header
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_post_teams_creates_team_and_owner_member(client: AsyncClient) -> None:
    """TEAM-01: POST /teams returns 201 with team body including members list."""
    response = await client.post("/teams", json={"name": "payments", "owner": "alice"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "payments"
    assert body["owner_id"] == "alice"
    assert "id" in body
    assert "created_at" in body
    members = body["members"]
    assert len(members) == 1
    assert members[0]["user_id"] == "alice"
    assert members[0]["role"] == "owner"
    assert "joined_at" in members[0]


async def test_post_teams_duplicate_name_returns_409(client: AsyncClient) -> None:
    """TEAM-01 / D-03: POST /teams with duplicate name returns 409 Conflict."""
    first = await client.post("/teams", json={"name": "payments", "owner": "alice"})
    assert first.status_code == 201

    second = await client.post("/teams", json={"name": "payments", "owner": "bob"})
    assert second.status_code == 409


async def test_get_teams_by_name_returns_members(client: AsyncClient) -> None:
    """TEAM-01: GET /teams/{name} returns 200 with team body including members list."""
    create = await client.post("/teams", json={"name": "payments", "owner": "alice"})
    assert create.status_code == 201

    response = await client.get("/teams/payments")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "payments"
    assert body["owner_id"] == "alice"
    assert "id" in body
    assert "created_at" in body
    members = body["members"]
    assert len(members) == 1
    assert members[0]["user_id"] == "alice"
    assert members[0]["role"] == "owner"


async def test_get_teams_unknown_name_returns_404(client: AsyncClient) -> None:
    """TEAM-01: GET /teams/{name} for unknown name returns 404."""
    response = await client.get("/teams/nonexistent-team-xyz")
    assert response.status_code == 404


async def test_post_teams_missing_owner_returns_422(client: AsyncClient) -> None:
    """TEAM-01: POST /teams without owner field returns 422 (Pydantic validation)."""
    response = await client.post("/teams", json={"name": "payments"})
    assert response.status_code == 422

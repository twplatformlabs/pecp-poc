"""Tests for TEAM-02 — project creation, listing with resource_count.

Wave 0 scaffolds — FAIL intentionally until Plan 03 implements project routes.
"""

from httpx import AsyncClient


def _make_lambda_yaml(name: str, project: str | None = None) -> bytes:
    """Create a unique PECPLambda YAML with the given name to avoid constraint collisions."""
    project_line = f"  project: {project}\n" if project else ""
    return (
        f"apiVersion: pecp/v1\n"
        f"kind: PECPLambda\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  team: payments\n"
        f"{project_line}"
        f"spec:\n"
        f"  name: {name}\n"
        f"  exposure: private\n"
        f"  api-gateway: /{name}\n"
        f"  source-code: github://myorg/lambda-code\n"
    ).encode()


async def test_post_projects_creates_project_with_environments(client: AsyncClient) -> None:
    """TEAM-02: POST /projects returns 201 with project body including environments as list."""
    # Precondition: create a team
    team_resp = await client.post("/teams", json={"name": "payments", "owner": "alice"})
    assert team_resp.status_code == 201

    response = await client.post(
        "/projects",
        json={"name": "payments-backend", "team": "payments", "environments": ["dev", "staging", "prod"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "payments-backend"
    assert "id" in body
    # environments must be a JSON list in the response
    assert body["environments"] == ["dev", "staging", "prod"]


async def test_get_projects_lists_team_projects_with_resource_count(client: AsyncClient) -> None:
    """TEAM-02: GET /projects?team=payments returns list with resource_count == 0 when empty."""
    # Precondition: create team and project
    await client.post("/teams", json={"name": "payments", "owner": "alice"})
    await client.post(
        "/projects",
        json={"name": "payments-backend", "team": "payments", "environments": ["dev", "prod"]},
    )

    response = await client.get("/projects", params={"team": "payments"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    project = body[0]
    assert project["name"] == "payments-backend"
    assert project["resource_count"] == 0


async def test_get_projects_with_resource_returns_count_one(client: AsyncClient) -> None:
    """TEAM-02: GET /projects?team= returns resource_count == 1 after one resource is created.

    Will FAIL until Plan 03 implements the project write path on POST /resources.
    """
    # Precondition: create team and project
    await client.post("/teams", json={"name": "payments", "owner": "alice"})
    await client.post(
        "/projects",
        json={"name": "payments-backend", "team": "payments", "environments": ["dev", "prod"]},
    )

    # Create a resource associated with the project
    await client.post(
        "/resources",
        content=_make_lambda_yaml("resource-count-test", project="payments-backend"),
        params={"team": "payments"},
        headers={"Content-Type": "application/x-yaml"},
    )

    response = await client.get("/projects", params={"team": "payments"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["resource_count"] == 1


async def test_get_projects_without_team_returns_400(client: AsyncClient) -> None:
    """ARCH-01: GET /projects without team param returns 400."""
    response = await client.get("/projects")
    assert response.status_code == 400
    assert response.json()["detail"] == "team parameter is required"


async def test_post_projects_duplicate_name_in_same_team_returns_409(client: AsyncClient) -> None:
    """TEAM-02 / D-04: POST /projects with duplicate (team, name) returns 409."""
    await client.post("/teams", json={"name": "payments", "owner": "alice"})
    first = await client.post(
        "/projects",
        json={"name": "payments-backend", "team": "payments", "environments": ["dev"]},
    )
    assert first.status_code == 201

    second = await client.post(
        "/projects",
        json={"name": "payments-backend", "team": "payments", "environments": ["prod"]},
    )
    assert second.status_code == 409

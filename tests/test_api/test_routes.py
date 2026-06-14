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


# ---------------------------------------------------------------------------
# Wave 0 test scaffolds — FAIL intentionally until Wave 2 implements routes
# ---------------------------------------------------------------------------

def _make_lambda_yaml(name: str) -> bytes:
    """Create a unique PECPLambda YAML with the given name to avoid constraint collisions."""
    return (
        f"apiVersion: pecp/v1\n"
        f"kind: PECPLambda\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  team: platform\n"
        f"spec:\n"
        f"  name: {name}\n"
        f"  exposure: private\n"
        f"  api-gateway: /{name}\n"
        f"  source-code: github://myorg/lambda-code\n"
    ).encode()


def _make_container_yaml(name: str) -> bytes:
    """Create a unique PECPContainer YAML with the given name."""
    return (
        f"apiVersion: pecp/v1\n"
        f"kind: PECPContainer\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  team: platform\n"
        f"spec:\n"
        f"  name: {name}\n"
        f"  exposure: private\n"
        f"  image: myorg/container:latest\n"
    ).encode()


async def test_get_resource_by_id_returns_full_record(client: AsyncClient) -> None:
    """GET /resources/{id} returns record with all expected fields."""
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("get-by-id-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    response = await client.get(f"/resources/{resource_id}")
    assert response.status_code == 200
    body = response.json()
    for key in ("id", "team", "kind", "name", "status", "env", "created_at",
                "provider_metadata", "activity_log", "notes"):
        assert key in body, f"Expected key '{key}' in response"


async def test_get_resource_by_id_not_found_returns_404(client: AsyncClient) -> None:
    """GET /resources/nonexistent returns 404."""
    response = await client.get("/resources/nonexistent-id-xyz")
    assert response.status_code == 404


async def test_delete_resource_returns_204_when_team_matches(
    client: AsyncClient,
) -> None:
    """DELETE /resources/{id}?team=platform returns 204; subsequent GET returns 404."""
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("delete-204-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    get_after = await client.get(f"/resources/{resource_id}")
    assert get_after.status_code == 404


async def test_delete_resource_returns_404_when_team_mismatch(
    client: AsyncClient,
) -> None:
    """Security A5: DELETE with wrong team returns 404 (cross-team delete blocked)."""
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("delete-404-mismatch-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "other-team"})
    assert delete.status_code == 404


async def test_list_resources_kind_filter(client: AsyncClient) -> None:
    """GET /resources?team=platform&kind=PECPLambda returns only Lambda resources."""
    # Create a Lambda resource
    lambda_resp = await client.post(
        "/resources",
        content=_make_lambda_yaml("kind-filter-lambda"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert lambda_resp.status_code == 202

    # Create a Container resource
    container_resp = await client.post(
        "/resources",
        content=_make_container_yaml("kind-filter-container"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert container_resp.status_code == 202

    # Filter by kind=PECPLambda
    filtered = await client.get(
        "/resources",
        params={"team": "platform", "kind": "PECPLambda"},
    )
    assert filtered.status_code == 200
    results = filtered.json()
    assert isinstance(results, list)
    # All returned resources must be PECPLambda
    assert all(r["kind"] == "PECPLambda" for r in results)
    # Our lambda must be in the list
    lambda_id = lambda_resp.json()["id"]
    assert any(r["id"] == lambda_id for r in results)

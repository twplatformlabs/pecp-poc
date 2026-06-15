"""Tests for TEAM-03 — deployment audit trail and environment filter.

Wave 0 scaffolds — FAIL intentionally until Plan 03 implements deployment trail.
"""

import asyncio

from httpx import AsyncClient


def _make_lambda_yaml(name: str, env: str = "dev", team: str = "platform") -> bytes:
    """Create a unique PECPLambda YAML with the given name and env."""
    return (
        f"apiVersion: pecp/v1\n"
        f"kind: PECPLambda\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  team: {team}\n"
        f"  env: {env}\n"
        f"spec:\n"
        f"  name: {name}\n"
        f"  exposure: private\n"
        f"  api-gateway: /{name}\n"
        f"  source-code: github://myorg/lambda-code\n"
    ).encode()


def _make_lambda_yaml_changed(name: str, env: str = "dev", team: str = "platform") -> bytes:
    """Create a changed PECPLambda YAML (exposure: public) to trigger update path."""
    return (
        f"apiVersion: pecp/v1\n"
        f"kind: PECPLambda\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  team: {team}\n"
        f"  env: {env}\n"
        f"spec:\n"
        f"  name: {name}\n"
        f"  exposure: public\n"
        f"  api-gateway: /{name}\n"
        f"  source-code: github://myorg/lambda-code\n"
    ).encode()


async def test_post_resources_writes_deployment_row_with_change_type_create(
    client: AsyncClient,
) -> None:
    """TEAM-03: POST /resources creates a deployment row with change_type=create.

    Will FAIL until Plan 03 wires deployment row creation into POST /resources.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("deploy-create-test", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202

    deployments = await client.get("/deployments", params={"team": "platform", "environment": "dev"})
    assert deployments.status_code == 200
    body = deployments.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    create_rows = [r for r in body if r["change_type"] == "create"]
    assert len(create_rows) >= 1


async def test_delete_resources_writes_deployment_row_with_change_type_delete(
    client: AsyncClient,
) -> None:
    """TEAM-03: DELETE /resources/{id} creates a deployment row with change_type=delete.

    Will FAIL until Plan 03 wires deployment row creation into DELETE /resources/{id}.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("deploy-delete-test", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    deployments = await client.get("/deployments", params={"team": "platform", "environment": "dev"})
    assert deployments.status_code == 200
    body = deployments.json()
    delete_rows = [r for r in body if r["change_type"] == "delete"]
    assert len(delete_rows) >= 1


async def test_post_resources_changed_spec_writes_deployment_row_with_change_type_update(
    client: AsyncClient,
) -> None:
    """TEAM-03: POST /resources with changed spec creates a deployment row with change_type=update.

    Will FAIL until Plan 03 wires deployment row creation into the POST /resources update path.
    """
    await client.post(
        "/resources",
        content=_make_lambda_yaml("deploy-update-test", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )

    await client.post(
        "/resources",
        content=_make_lambda_yaml_changed("deploy-update-test", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )

    deployments = await client.get("/deployments", params={"team": "platform", "environment": "dev"})
    assert deployments.status_code == 200
    body = deployments.json()
    update_rows = [r for r in body if r["change_type"] == "update"]
    assert len(update_rows) >= 1


async def test_get_deployments_filters_by_environment(client: AsyncClient) -> None:
    """TEAM-03: GET /deployments?team=X&environment=prod returns only prod rows.

    Will FAIL until Plan 03 implements GET /deployments with environment filter.
    """
    # Create resource in prod
    await client.post(
        "/resources",
        content=_make_lambda_yaml("env-filter-prod", env="prod"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )

    # Create resource in dev
    await client.post(
        "/resources",
        content=_make_lambda_yaml("env-filter-dev", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )

    prod_deployments = await client.get(
        "/deployments", params={"team": "platform", "environment": "prod"}
    )
    assert prod_deployments.status_code == 200
    body = prod_deployments.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    # All returned rows should be for prod environment
    for row in body:
        assert row["environment"] == "prod"


async def test_get_deployments_without_team_returns_400(client: AsyncClient) -> None:
    """ARCH-01: GET /deployments without team param returns 400.

    Will FAIL until Plan 03 implements GET /deployments with team guard.
    """
    response = await client.get("/deployments")
    assert response.status_code == 400
    assert response.json()["detail"] == "team parameter is required"


async def test_get_deployments_sorted_newest_first(client: AsyncClient) -> None:
    """TEAM-03 / D-16: GET /deployments returns rows sorted by deployed_at DESC.

    Will FAIL until Plan 03 implements GET /deployments with ORDER BY deployed_at DESC.
    """
    # Create two resources with a slight time gap
    await client.post(
        "/resources",
        content=_make_lambda_yaml("sort-test-first", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    await asyncio.sleep(0.01)
    await client.post(
        "/resources",
        content=_make_lambda_yaml("sort-test-second", env="dev"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )

    deployments = await client.get("/deployments", params={"team": "platform", "environment": "dev"})
    assert deployments.status_code == 200
    body = deployments.json()
    assert len(body) >= 2
    # Verify sorted newest first
    assert body[0]["deployed_at"] >= body[1]["deployed_at"]

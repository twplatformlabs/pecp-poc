"""Tests for D-11 / D-12 — soft-delete invisibility and deleted_at filter.

Wave 0 scaffolds — FAIL intentionally until Plan 03 modifies resources.py for soft-delete.
"""

from httpx import AsyncClient


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


async def test_delete_resource_sets_deleted_at_not_hard_delete(client: AsyncClient) -> None:
    """D-11: DELETE /resources/{id} soft-deletes (sets deleted_at); subsequent GET returns 404.

    Will FAIL until Plan 03 changes the DELETE handler to set deleted_at instead of hard-delete.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("soft-delete-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    # Soft-deleted resource must not be visible via GET /resources/{id}
    get_after = await client.get(f"/resources/{resource_id}")
    assert get_after.status_code == 404


async def test_get_resources_filters_out_soft_deleted(client: AsyncClient) -> None:
    """D-11: GET /resources?team= does not return soft-deleted resources.

    Will FAIL until Plan 03 adds WHERE deleted_at IS NULL to list_resources query.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("soft-delete-list-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    list_response = await client.get("/resources", params={"team": "platform"})
    assert list_response.status_code == 200
    resources = list_response.json()
    assert all(r["id"] != resource_id for r in resources)


async def test_get_resource_by_id_returns_404_when_soft_deleted(client: AsyncClient) -> None:
    """D-11: GET /resources/{id} returns 404 for soft-deleted resources.

    Will FAIL until Plan 03 adds deleted_at IS NOT NULL check to get_resource handler.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("soft-delete-get-by-id-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    get = await client.get(f"/resources/{resource_id}")
    assert get.status_code == 404


async def test_pecp_get_does_not_show_deleted_resources(client: AsyncClient) -> None:
    """D-11 / D-12: Soft-deleted resources are invisible at the API surface (CLI-facing).

    Will FAIL until Plan 03 filters soft-deleted rows from all list queries.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("soft-delete-cli-surface-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    # Verify it appears in the list before deletion
    list_before = await client.get("/resources", params={"team": "platform"})
    assert any(r["id"] == resource_id for r in list_before.json())

    delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert delete.status_code == 204

    # After deletion, it must not appear in the list
    list_after = await client.get("/resources", params={"team": "platform"})
    assert all(r["id"] != resource_id for r in list_after.json())


async def test_double_delete_returns_404_second_time(client: AsyncClient) -> None:
    """D-11: Second DELETE on an already-soft-deleted resource returns 404.

    Will FAIL until Plan 03 checks deleted_at IS NULL in the DELETE lookup query.
    """
    create = await client.post(
        "/resources",
        content=_make_lambda_yaml("double-delete-test"),
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    first_delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert first_delete.status_code == 204

    second_delete = await client.delete(f"/resources/{resource_id}", params={"team": "platform"})
    assert second_delete.status_code == 404

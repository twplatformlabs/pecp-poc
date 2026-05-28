"""End-to-end walking skeleton test: POST then GET round trip.

Proves that the entire stack works — YAML body is parsed, persisted via
SQLAlchemy async, and retrievable via the list endpoint.
Uses an isolated in-memory database via the PECP_DATABASE_URL env var.
"""

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def isolated_client() -> AsyncClient:  # type: ignore[return]
    """Client backed by a fresh in-memory SQLite database for each test."""
    os.environ["PECP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    # Import after setting env var so the engine uses the in-memory URL.
    import importlib

    import pecp.persistence.database as db_module

    importlib.reload(db_module)

    from pecp.api.main import app
    from pecp.persistence.database import init_schema

    await init_schema()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


async def test_apply_then_list_round_trip(isolated_client: AsyncClient) -> None:
    """POST example.yaml then GET /resources?team=payments — proves DB persistence (Behavior 7)."""
    example_path = Path(__file__).parent.parent.parent / "example.yaml"
    yaml_bytes = example_path.read_bytes()

    # POST the resource
    post_response = await isolated_client.post(
        "/resources",
        params={"team": "payments"},
        headers={"Content-Type": "application/x-yaml"},
        content=yaml_bytes,
    )
    assert post_response.status_code == 202, post_response.text
    post_data = post_response.json()
    assert "id" in post_data
    assert post_data["kind"] == "PECPLambda"
    assert post_data["name"] == "hello-world"
    assert post_data["status"] == "pending"

    resource_id = post_data["id"]

    # GET the resource list and find our new resource
    get_response = await isolated_client.get(
        "/resources",
        params={"team": "payments"},
    )
    assert get_response.status_code == 200, get_response.text
    resources = get_response.json()
    assert isinstance(resources, list)
    ids = [r["id"] for r in resources]
    assert resource_id in ids, f"Expected {resource_id} in {ids}"

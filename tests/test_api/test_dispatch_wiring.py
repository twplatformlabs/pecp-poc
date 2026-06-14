"""Tests for BackgroundTasks dispatch wiring (CTRL-02).

Wave 0 scaffolds — these tests FAIL until Wave 2 wires BackgroundTasks dispatch
in POST /resources and the GET /resources/{id} route returns full status details.
Failures are intentional RED.
"""

import asyncio
import unittest.mock as mock

import pytest
from httpx import AsyncClient

LAMBDA_YAML = b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: dispatch-test-lambda
  team: platform
spec:
  name: dispatch-test-lambda
  exposure: private
  api-gateway: /dispatch-test
  source-code: github://myorg/lambda-code
"""


async def test_post_resources_enqueues_background_dispatch(
    client: AsyncClient,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """CTRL-02: POST /resources enqueues _dispatch_with_session as BackgroundTask."""
    dispatch_mock = mock.AsyncMock()
    monkeypatch.setattr(
        "pecp.api.routes.resources._dispatch_with_session",
        dispatch_mock,
    )

    response = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert response.status_code == 202
    resource_id = response.json()["id"]

    # BackgroundTasks runs inline in test client — assert called with resource_id
    dispatch_mock.assert_called_once_with(resource_id)


async def test_dispatch_transitions_pending_to_ready_with_fresh_session(
    client: AsyncClient,
) -> None:
    """CTRL-02: After POST /resources, status eventually transitions to 'ready'."""
    response = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert response.status_code == 202
    resource_id = response.json()["id"]

    # Poll up to 30 times (3 seconds) for status == "ready"
    status = "pending"
    for _ in range(30):
        detail = await client.get(f"/resources/{resource_id}")
        assert detail.status_code == 200
        status = detail.json().get("status", "pending")
        if status == "ready":
            break
        await asyncio.sleep(0.1)

    assert status == "ready", f"Expected status='ready', got status='{status}'"

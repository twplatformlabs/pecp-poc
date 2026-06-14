"""Tests for PE notes append endpoint (CTRL-04).

Wave 0 scaffolds — these tests FAIL until Wave 2 implements POST /resources/{id}/notes
and the GET /resources/{id} route returns a notes field. Failures are intentional RED.
"""

from httpx import AsyncClient

LAMBDA_YAML = b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: notes-test-lambda
  team: platform
spec:
  name: notes-test-lambda
  exposure: private
  api-gateway: /notes-test
  source-code: github://myorg/lambda-code
"""


async def test_post_notes_appends_and_returns_201_with_full_list(
    client: AsyncClient,
) -> None:
    """CTRL-04: POST /resources/{id}/notes returns 201 with full notes list (D-05)."""
    create = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    response = await client.post(
        f"/resources/{resource_id}/notes",
        json={"text": "rolling out v2"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "notes" in body
    assert isinstance(body["notes"], list)
    assert len(body["notes"]) == 1
    note = body["notes"][0]
    assert "author" in note
    assert "timestamp" in note
    assert "text" in note
    assert note["text"] == "rolling out v2"


async def test_get_resource_id_includes_notes_list(
    client: AsyncClient,
) -> None:
    """CTRL-04: GET /resources/{id} returns notes field with appended note (D-07)."""
    create = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    # Append a note
    note_resp = await client.post(
        f"/resources/{resource_id}/notes",
        json={"text": "initial note"},
    )
    assert note_resp.status_code == 201

    # GET full detail should include notes
    detail = await client.get(f"/resources/{resource_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert "notes" in body
    notes = body["notes"]
    assert isinstance(notes, list)
    assert len(notes) >= 1
    assert notes[0]["text"] == "initial note"


async def test_post_notes_missing_text_returns_422(
    client: AsyncClient,
) -> None:
    """Pitfall 5: Missing text key returns 422 (Pydantic validation), not 500/KeyError."""
    create = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert create.status_code == 202
    resource_id = create.json()["id"]

    response = await client.post(
        f"/resources/{resource_id}/notes",
        json={"foo": "bar"},
    )
    assert response.status_code == 422

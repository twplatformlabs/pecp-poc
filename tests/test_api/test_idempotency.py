"""Tests for resource idempotency (CTRL-03).

Wave 0 scaffolds — these tests FAIL until Wave 2 implements idempotency logic
in POST /resources. Failures are intentional RED; Wave 2 will turn them green.
"""

import pytest
import sqlalchemy.exc
from httpx import AsyncClient

from pecp.persistence.models import ResourceRecord

LAMBDA_YAML = b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
  team: platform
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""

LAMBDA_YAML_CHANGED = b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
  team: platform
spec:
  name: hello-world
  exposure: public
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""


async def test_post_resources_same_spec_returns_existing_id(
    client: AsyncClient,
) -> None:
    """CTRL-03 no-op path: POST same spec twice returns same id and 202."""
    first = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert first.status_code == 202
    first_id = first.json()["id"]

    second = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert second.status_code == 202
    assert second.json()["id"] == first_id


async def test_post_resources_changed_spec_updates_and_redispatches(
    client: AsyncClient,
) -> None:
    """CTRL-03 update path: POST changed spec returns same id, status=pending (D-10)."""
    first = await client.post(
        "/resources",
        content=LAMBDA_YAML,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert first.status_code == 202
    first_id = first.json()["id"]

    second = await client.post(
        "/resources",
        content=LAMBDA_YAML_CHANGED,
        params={"team": "platform"},
        headers={"Content-Type": "application/x-yaml"},
    )
    assert second.status_code == 202
    assert second.json()["id"] == first_id
    assert second.json()["status"] == "pending"


async def test_post_resources_unique_constraint_blocks_duplicate_team_kind_name(
    db_session: "sqlalchemy.ext.asyncio.AsyncSession",
) -> None:
    """D-08: DB-level UniqueConstraint(team, kind, name) raises IntegrityError on duplicate."""
    import datetime

    record1 = ResourceRecord(
        id="aaaabbbb1111",
        team="platform",
        kind="PECPLambda",
        name="dup-test",
        status="pending",
        spec_json='{"test": 1}',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    record2 = ResourceRecord(
        id="ccccdddd2222",
        team="platform",
        kind="PECPLambda",
        name="dup-test",
        status="pending",
        spec_json='{"test": 2}',
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(record1)
    await db_session.flush()

    db_session.add(record2)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()

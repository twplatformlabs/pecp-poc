"""Tests for Dispatcher state machine (D-03, D-04, ADPT-02, KINDS-01)."""

import json

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from pecp import dispatcher
from pecp.adapters.base import AdapterBase
from pecp.dispatcher import ADAPTER_REGISTRY, dispatch
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.models import ResourceRecord

LAMBDA_YAML = """
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: test-fn
  team: toxins-research
spec:
  name: test-fn
  exposure: private
  api-gateway: /test
  source-code: github://myorg/test-repo
"""


def _spec_json() -> str:
    return ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML)).model_dump_json()


async def test_dispatch_drives_pending_to_ready(db_session: AsyncSession) -> None:
    record = ResourceRecord(
        id="test-id-001",
        team="toxins-research",
        kind="PECPLambda",
        name="test-fn",
        status="pending",
        spec_json=_spec_json(),
    )
    db_session.add(record)
    await db_session.commit()

    with patch("asyncio.sleep", return_value=None):
        await dispatch("test-id-001", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "test-id-001")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.ready.value
    log = json.loads(updated.activity_log or "[]")
    assert len(log) >= 1
    assert log[0].startswith("Would call:")
    metadata = json.loads(updated.provider_metadata or "{}")
    assert "function_arn" in metadata


async def test_dispatch_writes_provisioning_before_adapter_returns(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ProbeAdapter(AdapterBase):
        observed_status_during_provision: str | None = None

        async def provision(self, resource: ResourceSpec) -> ProvisionResult:
            # Read back the status from the same session to verify PROVISIONING was committed
            result = await db_session.execute(
                select(ResourceRecord).where(ResourceRecord.id == "test-id-002")
            )
            row = result.scalar_one()
            ProbeAdapter.observed_status_during_provision = row.status
            return ProvisionResult(
                status=ResourceStatus.ready,
                activity_log=["Would call: probe"],
            )

        async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

        async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

    monkeypatch.setitem(ADAPTER_REGISTRY, "PECPLambda", ProbeAdapter())

    record = ResourceRecord(
        id="test-id-002",
        team="toxins-research",
        kind="PECPLambda",
        name="test-fn",
        status="pending",
        spec_json=_spec_json(),
    )
    db_session.add(record)
    await db_session.commit()

    await dispatch("test-id-002", db_session)

    assert ProbeAdapter.observed_status_during_provision == ResourceStatus.provisioning.value

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "test-id-002")
    )
    final = result.scalar_one()
    assert final.status == ResourceStatus.ready.value


async def test_dispatch_unknown_kind_writes_failed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = ResourceRecord(
        id="test-id-003",
        team="toxins-research",
        kind="PECPLambda",
        name="test-fn",
        status="pending",
        spec_json=_spec_json(),
    )
    db_session.add(record)
    await db_session.commit()

    monkeypatch.setattr(dispatcher, "ADAPTER_REGISTRY", {})

    with patch("asyncio.sleep", return_value=None):
        await dispatch("test-id-003", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "test-id-003")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.failed.value
    assert "PECPLambda" in (updated.activity_log or "")

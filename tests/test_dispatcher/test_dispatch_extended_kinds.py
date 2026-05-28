"""Dispatcher integration tests for non-AWS kinds (ADPT-02, KINDS-05, KINDS-06)."""

import json
from unittest.mock import patch

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pecp.dispatcher import dispatch
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.models import ResourceRecord

SALESFORCE_YAML = """
apiVersion: pecp/v1
kind: PECPSalesforce
metadata:
  name: demo-sf
  team: toxins-research
spec:
  config:
    connected_app: demo
"""

KUBERNETES_YAML = """
apiVersion: pecp/v1
kind: PECPKubernetes
metadata:
  name: demo-k8s
  team: toxins-research
spec:
  config:
    namespace: custom-ns
"""

DATADOG_YAML = """
apiVersion: pecp/v1
kind: PECPDatadog
metadata:
  name: demo-dd
  team: toxins-research
spec:
  config:
    monitor_name: fn-errors
"""


def _spec_json(yaml_text: str) -> str:
    return ResourceSpec.model_validate(yaml.safe_load(yaml_text)).model_dump_json()


async def test_dispatch_drives_salesforce_pending_to_ready(db_session: AsyncSession) -> None:
    record = ResourceRecord(
        id="sf-id-001",
        kind="PECPSalesforce",
        name="demo-sf",
        team="toxins-research",
        status="pending",
        spec_json=_spec_json(SALESFORCE_YAML),
    )
    db_session.add(record)
    await db_session.commit()

    with patch("asyncio.sleep", return_value=None):
        await dispatch("sf-id-001", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "sf-id-001")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.ready.value
    log = json.loads(updated.activity_log or "[]")
    assert any("Would provision Salesforce resource for team" in entry for entry in log)
    metadata = json.loads(updated.provider_metadata or "{}")
    assert metadata.get("system") == "salesforce"


async def test_dispatch_drives_kubernetes_pending_to_ready(db_session: AsyncSession) -> None:
    record = ResourceRecord(
        id="k8s-id-001",
        kind="PECPKubernetes",
        name="demo-k8s",
        team="toxins-research",
        status="pending",
        spec_json=_spec_json(KUBERNETES_YAML),
    )
    db_session.add(record)
    await db_session.commit()

    with patch("asyncio.sleep", return_value=None):
        await dispatch("k8s-id-001", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "k8s-id-001")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.ready.value
    log = json.loads(updated.activity_log or "[]")
    assert any("kubectl create namespace pecp-toxins-research" in entry for entry in log)
    metadata = json.loads(updated.provider_metadata or "{}")
    assert metadata.get("namespace") == "pecp-toxins-research"


async def test_dispatch_drives_datadog_pending_to_ready(db_session: AsyncSession) -> None:
    record = ResourceRecord(
        id="dd-id-001",
        kind="PECPDatadog",
        name="demo-dd",
        team="toxins-research",
        status="pending",
        spec_json=_spec_json(DATADOG_YAML),
    )
    db_session.add(record)
    await db_session.commit()

    with patch("asyncio.sleep", return_value=None):
        await dispatch("dd-id-001", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "dd-id-001")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.ready.value
    log = json.loads(updated.activity_log or "[]")
    assert any("Would provision Datadog resource for team toxins-research" in entry for entry in log)
    metadata = json.loads(updated.provider_metadata or "{}")
    assert metadata.get("system") == "datadog"

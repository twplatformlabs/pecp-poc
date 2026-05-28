"""Tests for DatadogMockAdapter (ADPT-02, ADPT-03)."""

from unittest.mock import patch

import yaml

from pecp.adapters.mock.datadog import DatadogMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

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

DATADOG_NO_TEAM_YAML = """
apiVersion: pecp/v1
kind: PECPDatadog
metadata:
  name: demo-dd
spec:
  config:
    monitor_name: fn-errors
"""

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


async def test_datadog_provision_returns_team_scoped_log() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(DATADOG_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0] == "Would provision Datadog resource for team toxins-research"


async def test_datadog_provision_team_unknown_when_metadata_team_none() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(DATADOG_NO_TEAM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.activity_log[0] == "Would provision Datadog resource for team unknown"


async def test_datadog_provision_patches_sleep() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(DATADOG_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_datadog_deprovision_returns_team_scoped_log() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(DATADOG_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would deprovision Datadog resource for team")


async def test_datadog_get_status_returns_ready_no_metadata() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(DATADOG_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_datadog_rejects_non_datadog_spec_returns_failed() -> None:
    adapter = DatadogMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

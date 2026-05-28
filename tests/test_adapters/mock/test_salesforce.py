"""Tests for SalesforceMockAdapter (ADPT-02, ADPT-03, KINDS-05)."""

from unittest.mock import patch

import yaml

from pecp.adapters.mock.salesforce import SalesforceMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

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

SALESFORCE_NO_TEAM_YAML = """
apiVersion: pecp/v1
kind: PECPSalesforce
metadata:
  name: demo-sf
spec:
  config:
    connected_app: demo
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


async def test_salesforce_provision_returns_team_scoped_log() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(SALESFORCE_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0] == "Would provision Salesforce resource for team toxins-research"


async def test_salesforce_provision_team_unknown_when_metadata_team_none() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(SALESFORCE_NO_TEAM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.activity_log[0] == "Would provision Salesforce resource for team unknown"


async def test_salesforce_provision_patches_sleep() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(SALESFORCE_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_salesforce_deprovision_returns_team_scoped_log() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(SALESFORCE_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would deprovision Salesforce resource for team")


async def test_salesforce_get_status_returns_ready_no_metadata() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(SALESFORCE_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_salesforce_rejects_non_salesforce_spec_returns_failed() -> None:
    adapter = SalesforceMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

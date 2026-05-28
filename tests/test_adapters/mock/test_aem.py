"""Tests for AemMockAdapter (ADPT-02, ADPT-03, KINDS-06)."""

from unittest.mock import patch

import yaml

from pecp.adapters.mock.aem import AemMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

AEM_YAML = """
apiVersion: pecp/v1
kind: PECPAem
metadata:
  name: demo-aem
  team: toxins-research
spec:
  config:
    site: my-site
"""

AEM_NO_TEAM_YAML = """
apiVersion: pecp/v1
kind: PECPAem
metadata:
  name: demo-aem
spec:
  config:
    site: my-site
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


async def test_aem_provision_returns_team_scoped_log() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(AEM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0] == "Would provision AEM resource for team toxins-research"


async def test_aem_provision_team_unknown_when_metadata_team_none() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(AEM_NO_TEAM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.activity_log[0] == "Would provision AEM resource for team unknown"


async def test_aem_provision_patches_sleep() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(AEM_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_aem_deprovision_returns_team_scoped_log() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(AEM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would deprovision AEM resource for team")


async def test_aem_get_status_returns_ready_no_metadata() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(AEM_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_aem_rejects_non_aem_spec_returns_failed() -> None:
    adapter = AemMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

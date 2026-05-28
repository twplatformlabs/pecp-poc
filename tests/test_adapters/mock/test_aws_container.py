"""Tests for AwsContainerMockAdapter (ADPT-02, ADPT-03, KINDS-02)."""

from unittest.mock import patch

import yaml

from pecp.adapters.mock.aws_container import AwsContainerMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

CONTAINER_YAML = """
apiVersion: pecp/v1
kind: PECPContainer
metadata:
  name: my-svc
  team: toxins-research
spec:
  name: my-svc
  exposure: public
  image: nginx:1.27
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


async def test_aws_container_provision_returns_ready_with_image_in_log() -> None:
    adapter = AwsContainerMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(CONTAINER_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) >= 2
    for entry in result.activity_log:
        assert entry.startswith("Would call:"), f"Expected 'Would call:' prefix, got: {entry!r}"
    assert any("nginx:1.27" in entry for entry in result.activity_log)
    assert result.provider_metadata["image"] == "nginx:1.27"


async def test_aws_container_provision_patches_sleep() -> None:
    adapter = AwsContainerMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(CONTAINER_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_aws_container_deprovision_returns_delete_log() -> None:
    adapter = AwsContainerMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(CONTAINER_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would call: aws ecs delete-service")


async def test_aws_container_get_status_returns_ready_no_metadata() -> None:
    adapter = AwsContainerMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(CONTAINER_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_aws_container_rejects_non_container_spec_returns_failed() -> None:
    adapter = AwsContainerMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

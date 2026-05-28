"""Tests for AwsLambdaMockAdapter (ADPT-02, ADPT-03, KINDS-01)."""

import pytest
import yaml
from unittest.mock import patch

from pecp.adapters.mock.aws_lambda import AwsLambdaMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

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

CONTAINER_YAML = """
apiVersion: pecp/v1
kind: PECPContainer
metadata:
  name: test-container
  team: toxins-research
spec:
  name: test-container
  exposure: private
  image: myorg/test-image:latest
"""


async def test_aws_lambda_provision_returns_ready_with_activity_log() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) >= 2
    for entry in result.activity_log:
        assert entry.startswith("Would call:"), f"Expected 'Would call:' prefix, got: {entry!r}"
    assert result.provider_metadata != {}
    assert "function_arn" in result.provider_metadata


async def test_aws_lambda_provision_patches_sleep() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_aws_lambda_deprovision_returns_delete_log() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would call: aws lambda delete-function")


async def test_aws_lambda_get_status_returns_ready_no_metadata() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_aws_lambda_rejects_non_lambda_spec_returns_failed() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(CONTAINER_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

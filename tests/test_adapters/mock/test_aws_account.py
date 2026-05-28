"""Tests for AwsAccountMockAdapter (ADPT-02, ADPT-03, KINDS-04 slow-path)."""

from unittest.mock import call, patch

import yaml

from pecp.adapters.mock.aws_account import AwsAccountMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

ACCOUNT_YAML = """
apiVersion: pecp/v1
kind: PECPAccount
metadata:
  name: aws-account-toxins-research
  team: toxins-research
spec: {}
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

ACCOUNT_NO_TEAM_YAML = """
apiVersion: pecp/v1
kind: PECPAccount
metadata:
  name: aws-account-no-team
spec: {}
"""


async def test_aws_account_provision_calls_sleep_3_seconds() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_args == call(3)


async def test_aws_account_provision_returns_ready_with_synthetic_metadata() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata["account_id"] == "123456789012"
    assert result.provider_metadata["account_email"] == "aws+toxins-research@example.com"
    assert "account_name" in result.provider_metadata
    assert "management_console_url" in result.provider_metadata


async def test_aws_account_provision_activity_log_has_organizations_create_account() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert any(
        entry.startswith("Would call: aws organizations create-account")
        for entry in result.activity_log
    )


async def test_aws_account_provision_team_unknown_when_metadata_team_none() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_NO_TEAM_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.provider_metadata["account_email"] == "aws+unknown@example.com"


async def test_aws_account_deprovision_returns_close_account_log() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_YAML))
    result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert "close-account" in result.activity_log[0]


async def test_aws_account_get_status_returns_ready_no_metadata() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(ACCOUNT_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_aws_account_rejects_non_account_spec_returns_failed() -> None:
    adapter = AwsAccountMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

"""Tests for AwsDataMockAdapter (ADPT-02, ADPT-03, KINDS-03)."""

from unittest.mock import patch

import pytest

from pecp.adapters.mock.aws_data import AwsDataMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import DataServiceSubtype, ResourceSpec


def _build_spec(subtype: str, name: str = "my-data") -> ResourceSpec:
    """Construct a valid ResourceSpec for a PECPDataService with the given subtype."""
    return ResourceSpec.model_validate(
        {
            "apiVersion": "pecp/v1",
            "kind": "PECPDataService",
            "metadata": {"name": name, "team": "toxins-research"},
            "spec": {"name": name, "subtype": subtype},
        }
    )


LAMBDA_YAML_DICT = {
    "apiVersion": "pecp/v1",
    "kind": "PECPLambda",
    "metadata": {"name": "test-fn", "team": "toxins-research"},
    "spec": {
        "name": "test-fn",
        "exposure": "private",
        "api-gateway": "/test",
        "source-code": "github://myorg/test-repo",
    },
}


@pytest.mark.parametrize(
    "subtype,expected_log_prefix,expected_metadata_key",
    [
        ("s3", "Would call: aws s3api create-bucket", "bucket_arn"),
        ("sqs", "Would call: aws sqs create-queue", "queue_url"),
        ("sns", "Would call: aws sns create-topic", "topic_arn"),
        ("rds", "Would call: aws rds create-db-instance", "db_instance_arn"),
        ("dynamodb", "Would call: aws dynamodb create-table", "table_arn"),
    ],
)
async def test_aws_data_provision_branches_per_subtype(
    subtype: str, expected_log_prefix: str, expected_metadata_key: str
) -> None:
    adapter = AwsDataMockAdapter()
    spec = _build_spec(subtype)
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) >= 1
    assert result.activity_log[0].startswith(expected_log_prefix), (
        f"Expected log starting with {expected_log_prefix!r}, got {result.activity_log[0]!r}"
    )
    assert expected_metadata_key in result.provider_metadata, (
        f"Expected {expected_metadata_key!r} in provider_metadata, got {result.provider_metadata}"
    )


async def test_aws_data_provision_patches_sleep() -> None:
    adapter = AwsDataMockAdapter()
    spec = _build_spec("s3")
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_aws_data_deprovision_returns_delete_log() -> None:
    adapter = AwsDataMockAdapter()
    spec = _build_spec("s3")
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) >= 1
    assert "delete-resource" in result.activity_log[0]


async def test_aws_data_get_status_returns_ready_no_metadata() -> None:
    adapter = AwsDataMockAdapter()
    spec = _build_spec("dynamodb")
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_aws_data_rejects_non_data_spec_returns_failed() -> None:
    adapter = AwsDataMockAdapter()
    spec = ResourceSpec.model_validate(LAMBDA_YAML_DICT)
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

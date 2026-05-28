"""Tests for ResourceSpec discriminated union (D-09, D-10, D-11)."""

import pytest
import yaml
from pydantic import ValidationError

from pecp.models.resource_spec import (
    AccountSpec,
    AemSpec,
    ContainerSpec,
    DataServiceSpec,
    DataServiceSubtype,
    LambdaSpec,
    ResourceSpec,
    SalesforceSpec,
)

EXAMPLE_YAML = """
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""


def test_lambda_spec_parses_from_example_yaml() -> None:
    """D-10: example.yaml round-trip with hyphenated alias preserved."""
    data = yaml.safe_load(EXAMPLE_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPLambda"
    assert isinstance(resource.spec, LambdaSpec)
    assert resource.spec.source_code == "github://myorg/lambda-code"
    assert resource.spec.api_gateway == "/hello"


def test_invalid_kind_raises_validation_error() -> None:
    """D-10: Mutating kind to invalid value raises ValidationError."""
    data = yaml.safe_load(EXAMPLE_YAML)
    data["kind"] = "InvalidKind"
    data["spec"]["kind"] = "InvalidKind"
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)


def test_lambda_spec_missing_required_field_raises_validation_error() -> None:
    """D-10, Pitfall 3: Removing source-code raises ValidationError."""
    data = yaml.safe_load(EXAMPLE_YAML)
    del data["spec"]["source-code"]
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)


def test_all_six_kinds_constructable() -> None:
    """D-09: All 6 resource kinds can be constructed."""
    ContainerSpec(kind="PECPContainer", name="x", exposure="public", image="nginx")
    DataServiceSpec(
        kind="PECPDataService", name="y", subtype=DataServiceSubtype.s3
    )
    AccountSpec(kind="PECPAccount")
    SalesforceSpec(kind="PECPSalesforce")
    AemSpec(kind="PECPAem")


def test_lambda_spec_extra_field_rejected() -> None:
    """T-01-02: extra='forbid' on LambdaSpec prevents undeclared fields."""
    data = yaml.safe_load(EXAMPLE_YAML)
    data["spec"]["unexpected_field"] = "should_fail"
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)

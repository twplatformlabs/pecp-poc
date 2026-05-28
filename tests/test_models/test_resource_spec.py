"""Tests for ResourceSpec discriminated union (D-09, D-10, D-11)."""

import pytest
import yaml
from pydantic import ValidationError

from pecp.models.resource_spec import (
    AccountSpec,
    AemSpec,
    ContainerSpec,
    DatadogSpec,
    DataServiceSpec,
    DataServiceSubtype,
    JFrogSpec,
    KubernetesSpec,
    LambdaSpec,
    ResourceSpec,
    SalesforceSpec,
    ServiceNowSpec,
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
    """D-09: All 10 resource kinds can be constructed (6 original + 4 new)."""
    ContainerSpec(kind="PECPContainer", name="x", exposure="public", image="nginx")
    DataServiceSpec(
        kind="PECPDataService", name="y", subtype=DataServiceSubtype.s3
    )
    AccountSpec(kind="PECPAccount")
    SalesforceSpec(kind="PECPSalesforce")
    AemSpec(kind="PECPAem")
    KubernetesSpec(kind="PECPKubernetes")
    DatadogSpec(kind="PECPDatadog")
    ServiceNowSpec(kind="PECPServiceNow")
    JFrogSpec(kind="PECPJFrog")


def test_lambda_spec_extra_field_rejected() -> None:
    """T-01-02: extra='forbid' on LambdaSpec prevents undeclared fields."""
    data = yaml.safe_load(EXAMPLE_YAML)
    data["spec"]["unexpected_field"] = "should_fail"
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)


KUBERNETES_YAML = """
apiVersion: pecp/v1
kind: PECPKubernetes
metadata:
  name: team-deploy
  team: toxins-research
spec:
  config:
    namespace: team-ns
"""


def test_kubernetes_spec_parses_with_team_scope() -> None:
    """PECPKubernetes round-trips through YAML and parses as KubernetesSpec."""
    data = yaml.safe_load(KUBERNETES_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPKubernetes"
    assert isinstance(resource.spec, KubernetesSpec)
    assert resource.spec.config == {"namespace": "team-ns"}


DATADOG_YAML = """
apiVersion: pecp/v1
kind: PECPDatadog
metadata:
  name: fn-monitor
  team: toxins-research
spec:
  config:
    monitor_name: fn-errors
"""


def test_datadog_spec_parses_with_team_scope() -> None:
    """PECPDatadog round-trips through YAML and parses as DatadogSpec."""
    data = yaml.safe_load(DATADOG_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPDatadog"
    assert isinstance(resource.spec, DatadogSpec)
    assert resource.spec.config == {"monitor_name": "fn-errors"}


SERVICENOW_YAML = """
apiVersion: pecp/v1
kind: PECPServiceNow
metadata:
  name: change-request
  team: toxins-research
spec:
  config:
    ticket_type: change
"""


def test_servicenow_spec_parses_with_team_scope() -> None:
    """PECPServiceNow round-trips through YAML and parses as ServiceNowSpec."""
    data = yaml.safe_load(SERVICENOW_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPServiceNow"
    assert isinstance(resource.spec, ServiceNowSpec)
    assert resource.spec.config == {"ticket_type": "change"}


JFROG_YAML = """
apiVersion: pecp/v1
kind: PECPJFrog
metadata:
  name: team-artifacts
  team: toxins-research
spec:
  config:
    repo_name: team-artifacts
"""


def test_jfrog_spec_parses_with_team_scope() -> None:
    """PECPJFrog round-trips through YAML and parses as JFrogSpec."""
    data = yaml.safe_load(JFROG_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPJFrog"
    assert isinstance(resource.spec, JFrogSpec)
    assert resource.spec.config == {"repo_name": "team-artifacts"}

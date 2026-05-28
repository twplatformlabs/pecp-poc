"""Tests for KubernetesMockAdapter (ADPT-02, ADPT-03)."""

from unittest.mock import patch

import yaml

from pecp.adapters.mock.kubernetes import KubernetesMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

KUBERNETES_YAML = """
apiVersion: pecp/v1
kind: PECPKubernetes
metadata:
  name: my-app
  team: toxins-research
spec:
  config:
    namespace: custom-ns
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


async def test_kubernetes_provision_returns_ready_with_namespace() -> None:
    adapter = KubernetesMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(KUBERNETES_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) >= 2
    assert "kubectl create namespace pecp-toxins-research" in result.activity_log[0]
    assert result.provider_metadata["namespace"] == "pecp-toxins-research"


async def test_kubernetes_provision_patches_sleep() -> None:
    adapter = KubernetesMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(KUBERNETES_YAML))
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await adapter.provision(spec)
    assert mock_sleep.call_count >= 1


async def test_kubernetes_deprovision_returns_delete_namespace_log() -> None:
    adapter = KubernetesMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(KUBERNETES_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.deprovision(spec)
    assert result.status == ResourceStatus.ready
    assert result.activity_log[0].startswith("Would call: kubectl delete namespace")


async def test_kubernetes_get_status_returns_ready_no_metadata() -> None:
    adapter = KubernetesMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(KUBERNETES_YAML))
    result = await adapter.get_status(spec)
    assert result.status == ResourceStatus.ready
    assert result.provider_metadata == {}


async def test_kubernetes_rejects_non_k8s_spec_returns_failed() -> None:
    adapter = KubernetesMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.failed
    assert result.error is not None
    assert "Unexpected spec type" in result.error

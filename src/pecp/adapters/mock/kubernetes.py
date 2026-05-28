"""Mock adapter for PECPKubernetes resources (ADPT-02, ADPT-03)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import KubernetesSpec, ResourceSpec


class KubernetesMockAdapter(AdapterBase):
    """Mock adapter for PECPKubernetes resources. Simulates Kubernetes namespace and manifest provisioning."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, KubernetesSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "namespace": f"pecp-{team}",
                "manifest_path": f"/var/manifests/{team}/manifest.yaml",
                "team": team,
                "system": "kubernetes",
            },
            activity_log=[
                f"Would call: kubectl create namespace pecp-{team}",
                f"Would call: kubectl apply -f /var/manifests/{team}/manifest.yaml --namespace pecp-{team}",
                f"Would call: kubectl get pods -n pecp-{team}",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, KubernetesSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                f"Would call: kubectl delete namespace pecp-{team}",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

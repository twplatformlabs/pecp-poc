"""Mock adapter for PECPContainer resources (ADPT-02, ADPT-03, KINDS-02)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ContainerSpec, ResourceSpec


class AwsContainerMockAdapter(AdapterBase):
    """Mock adapter for PECPContainer resources. Simulates AWS ECS provisioning."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, ContainerSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "task_definition_arn": (
                    f"arn:aws:ecs:us-east-1:123456789012:task-definition/pecp-{spec.name}:1"
                ),
                "cluster": f"pecp-{spec.name}-cluster",
                "image": spec.image,
                "exposure": spec.exposure,
            },
            activity_log=[
                f"Would call: aws ecs register-task-definition"
                f" --family pecp-{spec.name}"
                f" --container-definitions name={spec.name},image={spec.image}",
                f"Would call: aws ecs create-service"
                f" --cluster pecp-{spec.name}-cluster"
                f" --service-name {spec.name}"
                f" --desired-count 1",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, ContainerSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                f"Would call: aws ecs delete-service"
                f" --cluster pecp-{spec.name}-cluster"
                f" --service {spec.name}"
                f" --force",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

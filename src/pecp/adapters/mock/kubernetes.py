"""Mock adapter for PECPKubernetes resources.

Placeholder implementation — real body implemented in Plan 04.
"""

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec


class KubernetesMockAdapter(AdapterBase):
    """Mock adapter for PECPKubernetes resources (placeholder -- implemented in plan 03 or 04)."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=["Would call: (placeholder -- implemented in plan 03 or 04)"],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=["Would call: (placeholder -- implemented in plan 03 or 04)"],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(status=ResourceStatus.ready)

"""Mock adapter for PECPAem resources (ADPT-02, ADPT-03, KINDS-06 — generic team-scoped placeholder per D-01)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import AemSpec, ResourceSpec


class AemMockAdapter(AdapterBase):
    """Mock adapter for PECPAem resources. Generic team-scoped placeholder per D-01."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, AemSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={"team": team, "system": "aem"},
            activity_log=[f"Would provision AEM resource for team {team}"],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, AemSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[f"Would deprovision AEM resource for team {team}"],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

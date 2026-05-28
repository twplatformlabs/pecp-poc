"""Mock adapter for PECPServiceNow resources (ADPT-02, ADPT-03 — generic team-scoped placeholder per D-01 pattern)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec, ServiceNowSpec


class ServiceNowMockAdapter(AdapterBase):
    """Mock adapter for PECPServiceNow resources. Generic team-scoped placeholder per D-01 pattern."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, ServiceNowSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={"team": team, "system": "servicenow"},
            activity_log=[f"Would provision ServiceNow resource for team {team}"],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, ServiceNowSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[f"Would deprovision ServiceNow resource for team {team}"],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

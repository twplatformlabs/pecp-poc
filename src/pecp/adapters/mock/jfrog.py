"""Mock adapter for PECPJFrog resources (ADPT-02, ADPT-03 — generic team-scoped placeholder per D-01 pattern)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import JFrogSpec, ResourceSpec


class JFrogMockAdapter(AdapterBase):
    """Mock adapter for PECPJFrog resources. Generic team-scoped placeholder per D-01 pattern."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, JFrogSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={"team": team, "system": "jfrog"},
            activity_log=[f"Would provision JFrog resource for team {team}"],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, JFrogSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[f"Would deprovision JFrog resource for team {team}"],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

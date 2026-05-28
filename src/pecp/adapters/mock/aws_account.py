"""Mock adapter for PECPAccount resources (ADPT-02, ADPT-03, KINDS-04 slow-path)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import AccountSpec, ResourceSpec


class AwsAccountMockAdapter(AdapterBase):
    """Mock adapter for PECPAccount resources. Simulates AWS Organizations account creation."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        spec = resource.spec
        if not isinstance(spec, AccountSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        team = resource.metadata.team or "unknown"
        # KINDS-04: dwell in PROVISIONING for >= 3 seconds — inline sleep, Dispatcher does NOT poll
        await asyncio.sleep(3)
        account_id = "123456789012"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "account_id": account_id,
                "account_email": f"aws+{team}@example.com",
                "account_name": f"pecp-{team}",
                "management_console_url": (
                    f"https://console.aws.amazon.com/switch-role?account={account_id}"
                ),
            },
            activity_log=[
                f"Would call: aws organizations create-account"
                f" --email aws+{team}@example.com --account-name pecp-{team}",
                f"Would call: aws organizations describe-create-account-status"
                f" --create-account-request-id car-{account_id}",
                f"Would call: aws sts assume-role"
                f" --role-arn arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
                f" --role-session-name pecp-{team}",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        # Deprovision is fast — no sleep; closing an account is a manual PE action
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                "Would call: aws organizations close-account (manual PE action required)",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

"""PECP Dispatcher — drives ResourceRecord through PENDING → PROVISIONING → READY|FAILED (D-03 through D-06)."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pecp.adapters.base import AdapterBase
from pecp.adapters.mock.aem import AemMockAdapter
from pecp.adapters.mock.aws_account import AwsAccountMockAdapter
from pecp.adapters.mock.aws_container import AwsContainerMockAdapter
from pecp.adapters.mock.aws_data import AwsDataMockAdapter
from pecp.adapters.mock.aws_lambda import AwsLambdaMockAdapter
from pecp.adapters.mock.datadog import DatadogMockAdapter
from pecp.adapters.mock.jfrog import JFrogMockAdapter
from pecp.adapters.mock.kubernetes import KubernetesMockAdapter
from pecp.adapters.mock.salesforce import SalesforceMockAdapter
from pecp.adapters.mock.servicenow import ServiceNowMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.models import ResourceRecord


class AdapterNotFoundError(KeyError):
    def __init__(self, kind: str) -> None:
        super().__init__(
            f"No adapter registered for kind: {kind!r}. Check ADAPTER_REGISTRY in dispatcher.py."
        )
        self.kind = kind


ADAPTER_REGISTRY: dict[str, AdapterBase] = {
    "PECPLambda": AwsLambdaMockAdapter(),
    "PECPContainer": AwsContainerMockAdapter(),
    "PECPDataService": AwsDataMockAdapter(),
    "PECPAccount": AwsAccountMockAdapter(),
    "PECPKubernetes": KubernetesMockAdapter(),
    "PECPSalesforce": SalesforceMockAdapter(),
    "PECPAem": AemMockAdapter(),
    "PECPDatadog": DatadogMockAdapter(),
    "PECPServiceNow": ServiceNowMockAdapter(),
    "PECPJFrog": JFrogMockAdapter(),
}


async def dispatch(resource_id: str, session: AsyncSession) -> None:
    """Drive a resource through PENDING → PROVISIONING → READY|FAILED."""
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one()

    spec = ResourceSpec.model_validate_json(record.spec_json)

    # Transition: PENDING → PROVISIONING (committed before adapter call)
    record.status = ResourceStatus.provisioning.value
    await session.commit()

    # Route to adapter — missing kinds result in structured failure, not uncaught KeyError
    if spec.kind not in ADAPTER_REGISTRY:
        record.status = ResourceStatus.failed.value
        record.activity_log = json.dumps([f"No adapter registered for kind: {spec.kind!r}"])
        await session.commit()
        return

    adapter = ADAPTER_REGISTRY[spec.kind]
    provision_result = await adapter.provision(spec)

    # Transition: PROVISIONING → READY|FAILED
    record.status = provision_result.status.value
    record.provider_metadata = json.dumps(provision_result.provider_metadata)
    record.activity_log = json.dumps(provision_result.activity_log)
    await session.commit()

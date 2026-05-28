"""Mock adapter for PECPDataService resources (ADPT-02, ADPT-03, KINDS-03)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import DataServiceSpec, DataServiceSubtype, ResourceSpec


class AwsDataMockAdapter(AdapterBase):
    """Mock adapter for PECPDataService resources. Branches on subtype for 5 AWS data services."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, DataServiceSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        name = spec.name
        account_id = "123456789012"
        region = "us-east-1"

        if spec.subtype == DataServiceSubtype.s3:
            log_line = f"Would call: aws s3api create-bucket --bucket pecp-{name}"
            metadata = {
                "bucket_arn": f"arn:aws:s3:::pecp-{name}",
                "name": name,
                "subtype": spec.subtype.value,
            }
        elif spec.subtype == DataServiceSubtype.sqs:
            log_line = f"Would call: aws sqs create-queue --queue-name pecp-{name}"
            metadata = {
                "queue_url": (
                    f"https://sqs.{region}.amazonaws.com/{account_id}/pecp-{name}"
                ),
                "name": name,
                "subtype": spec.subtype.value,
            }
        elif spec.subtype == DataServiceSubtype.sns:
            log_line = f"Would call: aws sns create-topic --name pecp-{name}"
            metadata = {
                "topic_arn": f"arn:aws:sns:{region}:{account_id}:pecp-{name}",
                "name": name,
                "subtype": spec.subtype.value,
            }
        elif spec.subtype == DataServiceSubtype.rds:
            log_line = (
                f"Would call: aws rds create-db-instance"
                f" --db-instance-identifier pecp-{name}"
            )
            metadata = {
                "db_instance_arn": (
                    f"arn:aws:rds:{region}:{account_id}:db:pecp-{name}"
                ),
                "name": name,
                "subtype": spec.subtype.value,
            }
        else:  # DataServiceSubtype.dynamodb
            log_line = (
                f"Would call: aws dynamodb create-table --table-name pecp-{name}"
            )
            metadata = {
                "table_arn": (
                    f"arn:aws:dynamodb:{region}:{account_id}:table/pecp-{name}"
                ),
                "name": name,
                "subtype": spec.subtype.value,
            }

        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata=metadata,
            activity_log=[log_line],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, DataServiceSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                f"Would call: aws {spec.subtype.value} delete-resource"
                f" --name pecp-{spec.name}",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

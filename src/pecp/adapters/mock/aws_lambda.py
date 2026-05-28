"""Mock adapter for PECPLambda resources (ADPT-02, ADPT-03, KINDS-01)."""

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import LambdaSpec, ResourceSpec


class AwsLambdaMockAdapter(AdapterBase):
    """Mock adapter for PECPLambda resources. Simulates AWS Lambda provisioning."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        if not isinstance(spec, LambdaSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        fn_name = spec.name
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "function_arn": f"arn:aws:lambda:us-east-1:123456789012:function:{fn_name}",
                "region": "us-east-1",
                "runtime": "python3.12",
            },
            activity_log=[
                f"Would call: aws lambda create-function"
                f" --function-name {fn_name}"
                f" --runtime python3.12"
                f" --code S3Bucket=pecp-deploys,S3Key={spec.source_code}",
                f"Would call: aws lambda add-permission"
                f" --function-name {fn_name}"
                f" --statement-id AllowAPIGateway"
                f" --action lambda:InvokeFunction",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        if not isinstance(spec, LambdaSpec):
            return ProvisionResult(
                status=ResourceStatus.failed,
                error=f"Unexpected spec type: {type(spec).__name__}",
            )
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                f"Would call: aws lambda delete-function --function-name {spec.name}",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        # Per Phase 1 D-03: get_status returns minimal result — no sleep, no metadata, no log
        return ProvisionResult(status=ResourceStatus.ready)

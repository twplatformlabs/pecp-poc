"""Pydantic v2 discriminated union covering all 10 resource kinds (D-09, D-10, D-11)."""

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataServiceSubtype(str, Enum):
    s3 = "s3"
    sqs = "sqs"
    sns = "sns"
    rds = "rds"
    dynamodb = "dynamodb"


class LambdaSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["PECPLambda"]
    name: str
    exposure: Literal["public", "private"]
    api_gateway: str = Field(alias="api-gateway")
    source_code: str = Field(alias="source-code")  # Proprietary URI: github://org/repo


class ContainerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["PECPContainer"]
    name: str
    exposure: Literal["public", "private"]
    image: str


class DataServiceSpec(BaseModel):
    kind: Literal["PECPDataService"]
    name: str
    subtype: DataServiceSubtype


class AccountSpec(BaseModel):
    kind: Literal["PECPAccount"]
    # No additional spec fields — account request is identified by team in metadata


class SalesforceSpec(BaseModel):
    kind: Literal["PECPSalesforce"]
    config: dict[str, Any] = Field(default_factory=dict)


class AemSpec(BaseModel):
    kind: Literal["PECPAem"]
    config: dict[str, Any] = Field(default_factory=dict)


class KubernetesSpec(BaseModel):
    kind: Literal["PECPKubernetes"]
    config: dict[str, Any] = Field(default_factory=dict)


class DatadogSpec(BaseModel):
    kind: Literal["PECPDatadog"]
    config: dict[str, Any] = Field(default_factory=dict)


class ServiceNowSpec(BaseModel):
    kind: Literal["PECPServiceNow"]
    config: dict[str, Any] = Field(default_factory=dict)


class JFrogSpec(BaseModel):
    kind: Literal["PECPJFrog"]
    config: dict[str, Any] = Field(default_factory=dict)


AnySpec = Annotated[
    Union[
        LambdaSpec,
        ContainerSpec,
        DataServiceSpec,
        AccountSpec,
        SalesforceSpec,
        AemSpec,
        KubernetesSpec,
        DatadogSpec,
        ServiceNowSpec,
        JFrogSpec,
    ],
    Field(discriminator="kind"),
]


class ResourceMetadata(BaseModel):
    name: str
    team: str | None = None
    env: str | None = None
    project: str | None = None  # D-08: optional project grouping


class ResourceSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: ResourceMetadata
    spec: AnySpec

    @model_validator(mode="before")
    @classmethod
    def inject_kind_into_spec(cls, data: Any) -> Any:
        """
        Inject top-level `kind` into `spec` dict so the discriminated union
        can find it. The YAML wire format (example.yaml) omits `kind` from the
        spec block — it lives at the top level only.
        """
        if isinstance(data, dict):
            top_kind = data.get("kind")
            spec = data.get("spec")
            if isinstance(spec, dict) and top_kind is not None and "kind" not in spec:
                data = {**data, "spec": {**spec, "kind": top_kind}}
        return data

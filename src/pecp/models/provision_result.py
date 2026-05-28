"""ProvisionResult model — return type for all adapter methods (D-01, D-02, D-03)."""

from typing import Any

from pydantic import BaseModel, Field

from pecp.models.enums import ResourceStatus


class ProvisionResult(BaseModel):
    status: ResourceStatus
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    activity_log: list[str] = Field(default_factory=list)
    error: str | None = None

"""Tests for AdapterBase ABC (ADPT-01)."""

import pytest

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec


def test_adapter_base_raises_type_error_without_provision() -> None:
    """ADPT-01: Instantiating an incomplete adapter raises TypeError."""

    class IncompleteAdapter(AdapterBase):
        async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:  # type: ignore[override]
            ...

        async def get_status(self, resource: ResourceSpec) -> ProvisionResult:  # type: ignore[override]
            ...
        # provision() intentionally omitted

    with pytest.raises(TypeError, match="provision"):
        IncompleteAdapter()


def test_complete_adapter_instantiates_without_error() -> None:
    """ADPT-01: A fully-implemented adapter instantiates successfully."""

    class FullAdapter(AdapterBase):
        async def provision(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

        async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

        async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

    adapter = FullAdapter()
    assert adapter is not None

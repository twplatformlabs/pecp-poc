"""AdapterBase ABC — contract for all PECP backing-system adapters (ADPT-01, D-04)."""

from abc import ABC, abstractmethod

from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec


class AdapterBase(ABC):
    """
    Contract for all PECP backing-system adapters.

    Rules (from CONTEXT.md D-04):
    - Always return ProvisionResult. Do NOT raise exceptions for expected failures.
    - Set status=FAILED and populate error= for failure cases.
    - The Dispatcher reads the result; it does not use try/except over adapter calls.
    """

    @abstractmethod
    async def provision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def get_status(self, resource: ResourceSpec) -> ProvisionResult: ...

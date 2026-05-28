"""RequestContext FastAPI dependency stub (ARCH-02)."""

from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel


class RequestContext(BaseModel):
    user_id: str
    team_memberships: list[str]
    is_pe_admin: bool


async def get_request_context() -> RequestContext:
    """
    Auth stub. Hardcoded for PoC.
    To add JWT: replace this function body only.
    Route signatures (ContextDep parameter) do not change.
    """
    return RequestContext(
        user_id="stub-user",
        team_memberships=["platform"],
        is_pe_admin=False,
    )


ContextDep = Annotated[RequestContext, Depends(get_request_context)]

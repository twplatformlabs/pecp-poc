"""Tests for RequestContext FastAPI dependency (ARCH-02)."""

from pecp.api.dependencies import get_request_context


async def test_context_dependency_returns_stub_values() -> None:
    """ARCH-02: get_request_context() returns hardcoded stub values."""
    ctx = await get_request_context()
    assert ctx.user_id == "stub-user"
    assert "platform" in ctx.team_memberships
    assert ctx.is_pe_admin is False

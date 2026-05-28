"""Tests for API routes (ARCH-01, ARCH-02).

The context dependency test (test_context_dependency_callable) calls
get_request_context() directly — no running app needed.

The three route tests are RED placeholders pending Plan 03, which creates
src/pecp/api/main.py and wires the FastAPI routes.
"""

import pytest

from pecp.api.dependencies import get_request_context


async def test_context_dependency_callable() -> None:
    """ARCH-02: get_request_context() returns expected stub values (no app needed)."""
    ctx = await get_request_context()
    assert ctx.user_id == "stub-user"
    assert "platform" in ctx.team_memberships
    assert ctx.is_pe_admin is False


async def test_get_resources_without_team_returns_400() -> None:
    """ARCH-01: GET /resources without team param returns 400. (Pending Plan 03)"""
    pytest.skip(
        reason="Pending Plan 03: FastAPI app instance and /resources route not yet created"
    )


async def test_get_resources_with_team_returns_200() -> None:
    """ARCH-01: GET /resources with team param returns 200. (Pending Plan 03)"""
    pytest.skip(
        reason="Pending Plan 03: FastAPI app instance and /resources route not yet created"
    )


async def test_post_resource_without_team_returns_400() -> None:
    """ARCH-01: POST /resources without team param returns 400. (Pending Plan 03)"""
    pytest.skip(
        reason="Pending Plan 03: FastAPI app instance and /resources route not yet created"
    )

"""Shared pytest fixtures for the PECP test suite."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Guard: only import the FastAPI app once Plan 03 creates src/pecp/api/main.py.
    # importorskip skips the test requesting this fixture until the module exists.
    main = pytest.importorskip(
        "pecp.api.main",
        reason="Pending Plan 03: FastAPI app instance not yet created",
    )
    app = main.app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

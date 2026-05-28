"""Shared pytest fixtures for the PECP test suite."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# Set the in-memory database URL before any pecp.persistence modules are
# imported. This ensures the engine is created with the test URL.
os.environ.setdefault("PECP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Guard: only import the FastAPI app once Plan 03 creates src/pecp/api/main.py.
    # importorskip skips the test requesting this fixture until the module exists.
    main = pytest.importorskip(
        "pecp.api.main",
        reason="Pending Plan 03: FastAPI app instance not yet created",
    )
    app = main.app

    # Initialize schema for the in-memory test database.
    from pecp.persistence.database import init_schema

    await init_schema()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

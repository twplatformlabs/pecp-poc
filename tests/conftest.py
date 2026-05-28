"""Shared pytest fixtures for the PECP test suite."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pecp.persistence.models import Base

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


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session backed by an in-memory SQLite database.

    Uses Base.metadata.create_all so all ORM columns (including provider_metadata
    and activity_log added in Phase 2) are available without running Alembic.
    expire_on_commit=False is mandatory in async context (avoids MissingGreenlet).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

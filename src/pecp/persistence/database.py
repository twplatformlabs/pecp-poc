"""Async SQLAlchemy engine, session factory, and schema initializer for PECP.

DATABASE_URL defaults to a local SQLite file but can be overridden via
the PECP_DATABASE_URL environment variable (used in tests for in-memory DBs).
"""

import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pecp.persistence.models import Base

DATABASE_URL: str = os.getenv(
    "PECP_DATABASE_URL", "sqlite+aiosqlite:///./pecp.db"
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def init_schema() -> None:
    """Create all tables defined in Base.metadata if they do not exist.

    Called from the FastAPI lifespan event on startup.
    Safe to call multiple times — SQLAlchemy uses CREATE TABLE IF NOT EXISTS.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and closes it after use."""
    async with AsyncSessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

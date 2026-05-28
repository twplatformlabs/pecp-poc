"""Tests for the SQLAlchemy async persistence layer.

Uses an in-memory SQLite database so tests are fully isolated and fast.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select

from pecp.persistence.database import init_schema
from pecp.persistence.models import Base, ResourceRecord

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session() -> AsyncSession:  # type: ignore[return]
    """Yield an async session backed by an in-memory SQLite database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_schema_creates_resource_records_table() -> None:
    """Calling init_schema() creates the resource_records table (Behavior 3)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    await engine.dispose()
    assert "resource_records" in table_names


async def test_round_trip_resource_record(db_session: AsyncSession) -> None:
    """A ResourceRecord inserts and retrieves correctly (Behavior 4, 5)."""
    record = ResourceRecord(
        id="r-test-1",
        team="payments",
        kind="PECPLambda",
        name="hello-world",
        status="pending",
        spec_json='{"kind": "PECPLambda"}',
    )
    db_session.add(record)
    await db_session.commit()

    result = await db_session.execute(select(ResourceRecord))
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].team == "payments"
    assert rows[0].kind == "PECPLambda"
    assert rows[0].name == "hello-world"
    assert rows[0].status == "pending"
    assert rows[0].spec_json == '{"kind": "PECPLambda"}'

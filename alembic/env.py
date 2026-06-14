"""Alembic async-compatible environment configuration for PECP.

Uses create_async_engine to run migrations against the same DATABASE_URL
used by the application and test suite. Offline mode is not supported
because aiosqlite / asyncpg require an async engine.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from pecp.persistence.database import DATABASE_URL
from pecp.persistence.models import Base

# Alembic Config object, which provides access to the values within the .ini file.
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    raise RuntimeError("Offline migration mode not supported for async engine")
else:
    run_migrations_online()

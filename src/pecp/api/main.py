"""FastAPI application instance for the PECP Control Plane API.

The lifespan event initializes the SQLite schema on startup so the
resource_records table exists before the first request is served.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pecp.api.routes import deployments, projects, resources, teams
from pecp.persistence.database import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database schema on startup."""
    await init_schema()
    yield


app = FastAPI(
    title="PECP Control Plane",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(resources.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(deployments.router)

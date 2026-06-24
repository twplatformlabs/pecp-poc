"""FastAPI application instance for the PECP Control Plane API.

The lifespan event initializes the SQLite schema on startup so the
resource_records table exists before the first request is served.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pecp.api.routes import deployments, projects, resources, teams
from pecp.integrations import load_and_register_integrations
from pecp.persistence.database import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database schema and load integrations on startup."""
    await init_schema()
    load_and_register_integrations()
    yield


app = FastAPI(
    title="PECP Control Plane",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS must be added BEFORE include_router calls (Pitfall 7 / D-06 / T-05-01)
# Whitelist only the Vite dev server origin — never use ["*"] (T-05-01)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resources.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(deployments.router)

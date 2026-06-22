"""Tests for the idempotent demo seed script (ARCH-03).

All tests run against an isolated in-memory SQLite database so they never
touch the dev pecp.db file. The AsyncSessionLocal used by seed.main() is
monkeypatched to the test factory before each invocation.
"""

import importlib
import json
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import StaticPool

# Ensure the src package is importable (mirrors the sys.path guard in seed.py)
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pecp.persistence.models import (  # noqa: E402
    Base,
    ProjectRecord,
    ResourceRecord,
    TeamRecord,
)


# ---------------------------------------------------------------------------
# Fixture: isolated in-memory async DB + patched AsyncSessionLocal
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_session_factory() -> AsyncGenerator[async_sessionmaker, None]:
    """Create an isolated in-memory async engine and return its session factory.

    Uses StaticPool so all connections share the same in-memory DB instance.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _run_seed(factory: async_sessionmaker) -> None:
    """Import (or reload) scripts.seed and run main() with the test factory."""
    # Ensure scripts/ directory is importable
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir.parent))

    # Force a fresh module load so the patch targets the right object
    if "scripts.seed" in sys.modules:
        del sys.modules["scripts.seed"]

    import scripts.seed as seed_module  # noqa: PLC0415

    with patch.object(seed_module, "AsyncSessionLocal", factory):
        await seed_module.main()


# ---------------------------------------------------------------------------
# Test 1: all 4 teams are created
# ---------------------------------------------------------------------------


async def test_seed_creates_all_teams(seed_session_factory: async_sessionmaker) -> None:
    """After seeding, TeamRecord rows exist for all 4 required teams (D-12)."""
    await _run_seed(seed_session_factory)
    async with seed_session_factory() as session:
        result = await session.execute(select(TeamRecord))
        teams = {r.name for r in result.scalars().all()}

    assert "customer-product-app" in teams
    assert "data-processing-app" in teams
    assert "data-platform" in teams
    assert "platform-engineering" in teams
    assert len(teams) >= 4


# ---------------------------------------------------------------------------
# Test 2: exactly 3 projects are created
# ---------------------------------------------------------------------------


async def test_seed_creates_all_projects(seed_session_factory: async_sessionmaker) -> None:
    """After seeding, exactly 3 ProjectRecord rows exist (D-12)."""
    await _run_seed(seed_session_factory)
    async with seed_session_factory() as session:
        result = await session.execute(select(ProjectRecord))
        projects = result.scalars().all()

    assert len(projects) == 3


# ---------------------------------------------------------------------------
# Test 3: resources cover all four lifecycle states with required kinds
# ---------------------------------------------------------------------------


async def test_seed_creates_resources_covering_all_lifecycle_states(
    seed_session_factory: async_sessionmaker,
) -> None:
    """After seeding, at least one resource exists for each of the four lifecycle states.

    Kinds must include PECPLambda, PECPContainer, PECPDataService, PECPAccount (D-12).
    """
    await _run_seed(seed_session_factory)
    async with seed_session_factory() as session:
        result = await session.execute(select(ResourceRecord))
        resources = result.scalars().all()

    statuses = {r.status for r in resources}
    kinds = {r.kind for r in resources}

    assert "pending" in statuses, f"No 'pending' resource found. Statuses: {statuses}"
    assert "provisioning" in statuses, f"No 'provisioning' resource found. Statuses: {statuses}"
    assert "ready" in statuses, f"No 'ready' resource found. Statuses: {statuses}"
    assert "failed" in statuses, f"No 'failed' resource found. Statuses: {statuses}"

    assert "PECPLambda" in kinds, f"PECPLambda kind missing. Kinds: {kinds}"
    assert "PECPContainer" in kinds, f"PECPContainer kind missing. Kinds: {kinds}"
    assert "PECPDataService" in kinds, f"PECPDataService kind missing. Kinds: {kinds}"
    assert "PECPAccount" in kinds, f"PECPAccount kind missing. Kinds: {kinds}"


# ---------------------------------------------------------------------------
# Test 4: PECPAccount for customer-product-app has PE notes in provisioning state
# ---------------------------------------------------------------------------


async def test_seed_account_resource_has_pe_notes_in_provisioning(
    seed_session_factory: async_sessionmaker,
) -> None:
    """The PECPAccount for customer-product-app is in provisioning state with 2-3 PE notes (D-13, D-14)."""
    await _run_seed(seed_session_factory)
    async with seed_session_factory() as session:
        result = await session.execute(
            select(ResourceRecord).where(
                ResourceRecord.team == "customer-product-app",
                ResourceRecord.kind == "PECPAccount",
                ResourceRecord.name == "pecp-customer-product-app",
            )
        )
        record = result.scalar_one_or_none()

    assert record is not None, "PECPAccount 'pecp-customer-product-app' not found for customer-product-app"
    assert record.status == "provisioning", f"Expected status='provisioning', got '{record.status}'"

    notes = json.loads(record.notes or "[]")
    assert len(notes) >= 2, f"Expected >= 2 PE notes, got {len(notes)}: {notes}"
    assert len(notes) <= 3, f"Expected <= 3 PE notes, got {len(notes)}: {notes}"

    for note in notes:
        assert "author" in note, f"Note missing 'author' key: {note}"
        assert "timestamp" in note, f"Note missing 'timestamp' key: {note}"
        assert "text" in note, f"Note missing 'text' key: {note}"


# ---------------------------------------------------------------------------
# Test 5: second run is idempotent — no new rows, no IntegrityError
# ---------------------------------------------------------------------------


async def test_seed_is_idempotent_second_run_skips_existing(
    seed_session_factory: async_sessionmaker,
) -> None:
    """Running seed.main() twice produces identical row counts (D-11).

    No IntegrityError is raised on the second run.
    """
    await _run_seed(seed_session_factory)

    # Capture counts after first run
    async with seed_session_factory() as session:
        teams_after_run1 = (await session.execute(select(TeamRecord))).scalars().all()
        projects_after_run1 = (await session.execute(select(ProjectRecord))).scalars().all()
        resources_after_run1 = (await session.execute(select(ResourceRecord))).scalars().all()

    team_count_1 = len(teams_after_run1)
    project_count_1 = len(projects_after_run1)
    resource_count_1 = len(resources_after_run1)

    # Second run — must not raise IntegrityError
    await _run_seed(seed_session_factory)

    async with seed_session_factory() as session:
        teams_after_run2 = (await session.execute(select(TeamRecord))).scalars().all()
        projects_after_run2 = (await session.execute(select(ProjectRecord))).scalars().all()
        resources_after_run2 = (await session.execute(select(ResourceRecord))).scalars().all()

    assert len(teams_after_run2) == team_count_1, (
        f"Team count changed after second run: {team_count_1} → {len(teams_after_run2)}"
    )
    assert len(projects_after_run2) == project_count_1, (
        f"Project count changed after second run: {project_count_1} → {len(projects_after_run2)}"
    )
    assert len(resources_after_run2) == resource_count_1, (
        f"Resource count changed after second run: {resource_count_1} → {len(resources_after_run2)}"
    )


# ---------------------------------------------------------------------------
# Test 6: stdout summary line matches expected format
# ---------------------------------------------------------------------------


async def test_seed_reports_counts_on_stdout(
    seed_session_factory: async_sessionmaker,
    capsys: pytest.CaptureFixture,
) -> None:
    """seed.main() prints a summary line matching 'Seeded: N teams, N projects, N resources' (D-12)."""
    import re

    await _run_seed(seed_session_factory)
    captured = capsys.readouterr()
    pattern = r"Seeded: \d+ teams, \d+ projects, \d+ resources"
    assert re.search(pattern, captured.out), (
        f"Expected stdout to match '{pattern}', got:\n{captured.out!r}"
    )

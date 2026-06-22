"""Demo seed script for PECP (ARCH-03).

Populates the database with 4 teams, 3 projects, and resources spanning all
four lifecycle states — so a stakeholder session can start from a clean
database with one command.

Run from the repo root:
    python scripts/seed.py

Safe to run repeatedly — idempotent by design (D-11).
Affects local pecp.db only. Do not run against a shared or production DB.

Design decisions enforced here:
    D-10: imports DB models and AsyncSessionLocal directly; no HTTP calls
    D-11: get-or-create helpers skip existing entities without error
    D-12: 4 teams, 3 projects, resources in all four lifecycle states
    D-13: PECPAccount for customer-product-app seeded with 3 PE notes
    D-14: PECPAccount seeded in 'provisioning' state for the demo watch flow
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path guard (Pitfall 5 / T-05-02-05)
# Insert <repo>/src so `pecp.*` imports work when the script is run directly
# from the repo root without `pip install -e .`.  When pip install -e . has
# already been run this insert is a harmless no-op.
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.future import select  # noqa: E402

from pecp.persistence.database import AsyncSessionLocal  # noqa: E402
from pecp.persistence.models import (  # noqa: E402
    Base,
    ProjectRecord,
    ResourceRecord,
    TeamMemberRecord,
    TeamRecord,
)

# ---------------------------------------------------------------------------
# Module-level seed data constants
# ---------------------------------------------------------------------------

TEAMS: list[dict[str, str]] = [
    {"name": "customer-product-app", "owner": "pe-admin"},
    {"name": "data-processing-app", "owner": "pe-admin"},
    {"name": "data-platform", "owner": "pe-admin"},
    {"name": "platform-engineering", "owner": "pe-admin"},
]

PROJECTS: list[dict[str, object]] = [
    {"team": "customer-product-app", "name": "cpa-core", "envs": ["dev", "staging", "prod"]},
    {"team": "data-processing-app", "name": "dp-pipeline", "envs": ["dev", "prod"]},
    {"team": "platform-engineering", "name": "infra-baseline", "envs": ["prod"]},
]

# PE notes injected into the PECPAccount notes column (D-13)
ACCOUNT_NOTES: list[dict[str, str]] = [
    {
        "author": "pe-admin",
        "timestamp": "2026-06-22 09:00",
        "text": "[PE team] Account provisioning request received — routing to AWS Organizations",
    },
    {
        "author": "pe-admin",
        "timestamp": "2026-06-22 09:02",
        "text": "[PE team] Account creation in progress, expected 10-15 min",
    },
    {
        "author": "pe-admin",
        "timestamp": "2026-06-22 09:14",
        "text": "[PE team] Account ready — ID 123456789012 assigned",
    },
]

# Provider metadata matching aws_account.py ProvisionResult shape exactly
# (verify: account_id, account_email, account_name, management_console_url)
ACCOUNT_PROVIDER_METADATA: dict[str, str] = {
    "account_id": "123456789012",
    "account_email": "aws+customer-product-app@example.com",
    "account_name": "pecp-customer-product-app",
    "management_console_url": "https://console.aws.amazon.com/switch-role?account=123456789012",
}

# Resources: one entry per resource row to seed.
# Shape: team, kind, name, status, env, project, notes_json, provider_metadata_json, spec_json
RESOURCES: list[dict[str, str | None]] = [
    # -----------------------------------------------------------------------
    # customer-product-app — demo PECPAccount in 'provisioning' state (D-14)
    # -----------------------------------------------------------------------
    {
        "team": "customer-product-app",
        "kind": "PECPAccount",
        "name": "pecp-customer-product-app",
        "status": "provisioning",
        "env": "prod",
        "project": "cpa-core",
        "notes_json": json.dumps(ACCOUNT_NOTES),
        "provider_metadata_json": json.dumps(ACCOUNT_PROVIDER_METADATA),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPAccount",
                "metadata": {
                    "name": "pecp-customer-product-app",
                    "team": "customer-product-app",
                    "env": "prod",
                    "project": "cpa-core",
                },
                "spec": {},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # customer-product-app — PECPLambda in 'ready' state
    # -----------------------------------------------------------------------
    {
        "team": "customer-product-app",
        "kind": "PECPLambda",
        "name": "cpa-api-handler",
        "status": "ready",
        "env": "prod",
        "project": "cpa-core",
        "notes_json": json.dumps([]),
        "provider_metadata_json": json.dumps(
            {"function_arn": "arn:aws:lambda:us-east-1:123456789012:function:cpa-api-handler"}
        ),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPLambda",
                "metadata": {
                    "name": "cpa-api-handler",
                    "team": "customer-product-app",
                    "env": "prod",
                    "project": "cpa-core",
                },
                "spec": {"runtime": "python3.12", "handler": "handler.main"},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # customer-product-app — PECPContainer in 'ready' state
    # -----------------------------------------------------------------------
    {
        "team": "customer-product-app",
        "kind": "PECPContainer",
        "name": "cpa-frontend",
        "status": "ready",
        "env": "staging",
        "project": "cpa-core",
        "notes_json": json.dumps([]),
        "provider_metadata_json": json.dumps(
            {"service_arn": "arn:aws:ecs:us-east-1:123456789012:service/cpa-frontend"}
        ),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPContainer",
                "metadata": {
                    "name": "cpa-frontend",
                    "team": "customer-product-app",
                    "env": "staging",
                    "project": "cpa-core",
                },
                "spec": {"image": "cpa-frontend:latest", "port": 8080},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # data-processing-app — PECPLambda in 'pending' state
    # -----------------------------------------------------------------------
    {
        "team": "data-processing-app",
        "kind": "PECPLambda",
        "name": "dp-ingestion-worker",
        "status": "pending",
        "env": "dev",
        "project": "dp-pipeline",
        "notes_json": json.dumps([]),
        "provider_metadata_json": json.dumps({}),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPLambda",
                "metadata": {
                    "name": "dp-ingestion-worker",
                    "team": "data-processing-app",
                    "env": "dev",
                    "project": "dp-pipeline",
                },
                "spec": {"runtime": "python3.12", "handler": "worker.main"},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # data-processing-app — PECPDataService in 'ready' state
    # -----------------------------------------------------------------------
    {
        "team": "data-processing-app",
        "kind": "PECPDataService",
        "name": "dp-event-store",
        "status": "ready",
        "env": "prod",
        "project": "dp-pipeline",
        "notes_json": json.dumps([]),
        "provider_metadata_json": json.dumps(
            {"bucket_arn": "arn:aws:s3:::dp-event-store"}
        ),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPDataService",
                "metadata": {
                    "name": "dp-event-store",
                    "team": "data-processing-app",
                    "env": "prod",
                    "project": "dp-pipeline",
                },
                "spec": {"engine": "s3"},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # data-platform — PECPDataService in 'failed' state
    # -----------------------------------------------------------------------
    {
        "team": "data-platform",
        "kind": "PECPDataService",
        "name": "dp-analytics-db",
        "status": "failed",
        "env": "dev",
        "project": None,
        "notes_json": json.dumps(
            [
                {
                    "author": "pe-admin",
                    "timestamp": "2026-06-21 14:30",
                    "text": "[PE team] Provisioning failed — IAM quota exceeded. Retrying.",
                }
            ]
        ),
        "provider_metadata_json": json.dumps({}),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPDataService",
                "metadata": {
                    "name": "dp-analytics-db",
                    "team": "data-platform",
                    "env": "dev",
                },
                "spec": {"engine": "aurora-postgres"},
            }
        ),
    },
    # -----------------------------------------------------------------------
    # platform-engineering — PECPContainer in 'ready' state
    # -----------------------------------------------------------------------
    {
        "team": "platform-engineering",
        "kind": "PECPContainer",
        "name": "pe-control-plane",
        "status": "ready",
        "env": "prod",
        "project": "infra-baseline",
        "notes_json": json.dumps([]),
        "provider_metadata_json": json.dumps(
            {"service_arn": "arn:aws:ecs:us-east-1:123456789012:service/pe-control-plane"}
        ),
        "spec_json": json.dumps(
            {
                "apiVersion": "pecp/v1",
                "kind": "PECPContainer",
                "metadata": {
                    "name": "pe-control-plane",
                    "team": "platform-engineering",
                    "env": "prod",
                    "project": "infra-baseline",
                },
                "spec": {"image": "pecp:latest", "port": 8000},
            }
        ),
    },
]


# ---------------------------------------------------------------------------
# Idempotent helper: get-or-create team
# ---------------------------------------------------------------------------


async def get_or_create_team(
    session, name: str, owner: str
) -> tuple[TeamRecord, bool]:
    """Return (TeamRecord, created). Skips insert if name already exists (D-11)."""
    result = await session.execute(select(TeamRecord).where(TeamRecord.name == name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, False

    now = datetime.now(timezone.utc)
    team_id = uuid.uuid4().hex
    team = TeamRecord(id=team_id, name=name, owner_id=owner, created_at=now)
    member = TeamMemberRecord(
        team_id=team_id,
        user_id=owner,
        role="owner",
        joined_at=now,
    )
    session.add(team)
    session.add(member)
    return team, True


# ---------------------------------------------------------------------------
# Idempotent helper: get-or-create project
# ---------------------------------------------------------------------------


async def get_or_create_project(
    session, team_name: str, project_name: str, envs: list[str]
) -> tuple[ProjectRecord, bool]:
    """Return (ProjectRecord, created). Skips insert if (team_name, name) already exists (D-11)."""
    # Resolve team_id by name
    team_result = await session.execute(
        select(TeamRecord).where(TeamRecord.name == team_name)
    )
    team = team_result.scalar_one_or_none()
    if team is None:
        raise ValueError(f"Team '{team_name}' not found — seed teams before projects")

    result = await session.execute(
        select(ProjectRecord).where(
            ProjectRecord.team_id == team.id,
            ProjectRecord.name == project_name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, False

    project = ProjectRecord(
        id=uuid.uuid4().hex,
        team_id=team.id,
        name=project_name,
        environments=json.dumps(envs),
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    return project, True


# ---------------------------------------------------------------------------
# Idempotent helper: get-or-create resource
# ---------------------------------------------------------------------------


async def get_or_create_resource(
    session,
    team: str,
    kind: str,
    name: str,
    status: str,
    env: str | None,
    project: str | None,
    notes_json: str,
    provider_metadata_json: str,
    spec_json: str,
) -> tuple[ResourceRecord, bool]:
    """Return (ResourceRecord, created). Skips insert if (team, kind, name) already exists (D-11)."""
    result = await session.execute(
        select(ResourceRecord).where(
            ResourceRecord.team == team,
            ResourceRecord.kind == kind,
            ResourceRecord.name == name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, False

    record = ResourceRecord(
        id=uuid.uuid4().hex,
        team=team,
        kind=kind,
        name=name,
        status=status,
        spec_json=spec_json,
        env=env,
        project=project,
        notes=notes_json,
        provider_metadata=provider_metadata_json,
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    return record, True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Seed the database with demo data. Idempotent — safe to run multiple times.

    Creates the schema if it does not yet exist (safe no-op when tables already exist).
    This allows the script to be run against a fresh DB without running Alembic first.
    """
    # Import the engine through the module reference so tests that patch
    # AsyncSessionLocal can also supply a compatible engine. When running
    # standalone, this uses the module-level engine tied to PECP_DATABASE_URL.
    import pecp.persistence.database as _db  # noqa: PLC0415

    async with _db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    teams_created = 0
    projects_created = 0
    resources_created = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        # 1. Seed teams (must come before projects and resources)
        for t in TEAMS:
            _, created = await get_or_create_team(session, t["name"], t["owner"])
            if created:
                teams_created += 1
            else:
                skipped += 1

        # Flush teams so project helpers can resolve team_id FKs
        await session.flush()

        # 2. Seed projects
        for p in PROJECTS:
            _, created = await get_or_create_project(
                session,
                team_name=str(p["team"]),
                project_name=str(p["name"]),
                envs=list(p["envs"]),  # type: ignore[arg-type]
            )
            if created:
                projects_created += 1
            else:
                skipped += 1

        # 3. Seed resources
        for r in RESOURCES:
            _, created = await get_or_create_resource(
                session,
                team=str(r["team"]),
                kind=str(r["kind"]),
                name=str(r["name"]),
                status=str(r["status"]),
                env=r.get("env"),  # type: ignore[arg-type]
                project=r.get("project"),  # type: ignore[arg-type]
                notes_json=str(r.get("notes_json", "[]")),
                provider_metadata_json=str(r.get("provider_metadata_json", "{}")),
                spec_json=str(r["spec_json"]),
            )
            if created:
                resources_created += 1
            else:
                skipped += 1

        await session.commit()

    print(
        f"Seeded: {teams_created} teams, {projects_created} projects, "
        f"{resources_created} resources ({skipped} already existed — skipped)."
    )


if __name__ == "__main__":
    asyncio.run(main())

# Phase 2: Core Engine - Research

**Researched:** 2026-05-28
**Domain:** Python async adapter pattern, SQLAlchemy async migrations, Dispatcher state machine
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Salesforce + AEM Mock Strategy**
- D-01: `SalesforceMockAdapter` and `AemMockAdapter` use generic team-scoped placeholder log messages. No Salesforce Connected App or AEM site provisioning domain research needed — the goal is proving adapter wiring, not domain fidelity. Specs stay `config: dict[str, Any]`. Example log: `"Would provision Salesforce resource for team toxins-research"`.
- D-02: `SalesforceMockAdapter` and `AemMockAdapter` are separate classes — no shared `GenericMockAdapter` base. When real specs arrive, they diverge cleanly without refactoring. Matches the pattern of all other adapters.

**Dispatcher Design**
- D-03: The Dispatcher writes resource status to SQLite in Phase 2. Signature: `async def dispatch(resource_id: str, session: AsyncSession) -> None`. It reads the `ResourceRecord`, routes to the correct adapter, and writes all status transitions (`PENDING → PROVISIONING → READY/FAILED`) plus `provider_metadata` and `activity_log` back to the record. Phase 3 calls this function from `BackgroundTasks` with no changes to the Dispatcher itself.
- D-04: `ResourceRecord` gains two new columns: `provider_metadata` (Text, JSON-serialized dict) and `activity_log` (Text, JSON-serialized list[str]). An Alembic migration is generated for these additions. Schema evolution via Alembic from Phase 2 onward.
- D-05: Dispatcher lives at `src/pecp/dispatcher.py` — a top-level module, not inside `api/`. This keeps it callable from tests, BackgroundTasks, and future CLI commands without importing the API layer.
- D-06: Adapter routing via a dict registry defined at the top of `dispatcher.py`: `ADAPTER_REGISTRY: dict[str, AdapterBase] = {"PECPLambda": AwsLambdaMockAdapter(), "PECPContainer": AwsContainerMockAdapter(), ...}`. The Dispatcher does `adapter = ADAPTER_REGISTRY[resource.kind]`. Missing kinds raise a clear `KeyError`-derived error.

**Claude's Discretion**
- PECPAccount slow-path: The `AwsAccountMockAdapter.provision()` uses `await asyncio.sleep(3)` internally to simulate slow account creation. Tests mock this sleep. The Dispatcher does not poll `get_status()` — the adapter handles the dwell inline and transitions to `READY` when done.
- Activity log format: Keep `activity_log: list[str]` with a consistent prefix format — `"Would call: aws lambda create-function --function-name my-fn ..."`. Structured dicts would add deserialization complexity in Phase 5; the prefix convention is parseable without committing to a structured schema now.
- Mock adapter file layout: Each backing system gets its own file under `src/pecp/adapters/mock/` (e.g., `aws_lambda.py`, `aws_container.py`, `aws_data.py`, `aws_account.py`, `kubernetes.py`, `salesforce.py`, `aem.py`, `datadog.py`, `servicenow.py`, `jfrog.py`). The `__init__.py` re-exports all adapter classes.
- Test strategy: `asyncio.sleep` is patched via `unittest.mock.patch("asyncio.sleep")` for all tests — no real latency in the test suite. One integration-style test per adapter calls `provision()` and asserts `ProvisionResult.status == READY` and `activity_log` is non-empty.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADPT-02 | Mock adapters for all 7 backing systems: AWS (Lambda/Container/Data/Account), Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog | 10-file layout under `src/pecp/adapters/mock/`; each subclasses `AdapterBase`; `ADAPTER_REGISTRY` in `dispatcher.py` maps all 10 kinds |
| ADPT-03 | Mock adapters simulate realistic latency (3–10s), produce structured activity logs, return synthetic provider metadata | `asyncio.sleep()` for latency; `ProvisionResult.activity_log: list[str]`; `ProvisionResult.provider_metadata: dict[str, Any]` |
| KINDS-01 | PECPLambda — with `exposure`, `api-gateway`, `source-code` | `LambdaSpec` already defined; `AwsLambdaMockAdapter` uses `spec.source_code`, `spec.api_gateway` in log |
| KINDS-02 | PECPContainer — with `exposure`, `image`, deployment context | `ContainerSpec` already defined; `AwsContainerMockAdapter` uses `spec.image` |
| KINDS-03 | PECPDataService — managed data with `subtype` (s3/sqs/sns/rds/dynamodb) | `DataServiceSpec` + `DataServiceSubtype` enum already defined; `AwsDataMockAdapter` branches on `spec.subtype` |
| KINDS-04 | PECPAccount — async AWS account provisioning with ≥3s dwell in PROVISIONING | `AccountSpec` already defined; `AwsAccountMockAdapter` uses `asyncio.sleep(3)` inline; Dispatcher writes transitions |
| KINDS-05 | PECPSalesforce — placeholder spec, team-scoped provisioning | `SalesforceSpec(config: dict)` already defined; `SalesforceMockAdapter` uses `resource.metadata.team` in log |
| KINDS-06 | PECPAem — placeholder spec, team-scoped provisioning | `AemSpec(config: dict)` already defined; `AemMockAdapter` uses `resource.metadata.team` in log |
</phase_requirements>

---

## Summary

Phase 2 builds the async provisioning engine on top of the Phase 1 contracts without touching the HTTP layer. Every piece Phase 2 needs is already installed and proven: `AdapterBase` ABC at `src/pecp/adapters/base.py`, `ProvisionResult` and `ResourceSpec` models, the `ResourceStatus` enum, and the `AsyncSession` setup. No new external packages are required — this phase uses only libraries already declared in `pyproject.toml`.

The two new artifacts this phase introduces are: (1) 10 mock adapter classes under `src/pecp/adapters/mock/`, each subclassing `AdapterBase` and implementing the `provision`, `deprovision`, and `get_status` methods with simulated latency and structured activity logs; and (2) the `Dispatcher` at `src/pecp/dispatcher.py`, a standalone async function that drives a `ResourceRecord` through the `PENDING → PROVISIONING → READY/FAILED` lifecycle, with all status writes exclusively owned by the Dispatcher. The Dispatcher is the only code that mutates `ResourceRecord.status` after Phase 2 — the API route handler sets `status="pending"` on creation only. A third supporting artifact is the Alembic migration that adds `provider_metadata` and `activity_log` Text columns to `resource_records`.

The phase is testable in complete isolation: no running HTTP server, no CLI, no BackgroundTasks. Tests use in-memory SQLite (`sqlite+aiosqlite:///:memory:`), patch `asyncio.sleep` to eliminate real latency, and assert on `ProvisionResult` fields. The success criteria are mechanical checks against these invariants.

**Primary recommendation:** Build the Dispatcher and a single end-to-end integration test first (slice: `PECPLambda` adapter + Dispatcher + Alembic migration). Confirm the full state machine works before expanding to all 10 adapters. The adapter implementations are structurally identical — once one works end-to-end, the remaining 9 are low-risk replication.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Resource lifecycle state machine | Dispatcher (Python module) | — | Dispatcher is the sole writer of `status`; no other code path mutates it after creation |
| Mock provisioning logic | Adapter (Python class) | — | Adapters own all backing-system simulation; Dispatcher only routes and persists results |
| Activity log production | Adapter | Dispatcher (persists) | Adapters generate log strings; Dispatcher writes them to `ResourceRecord.activity_log` |
| Provider metadata | Adapter | Dispatcher (persists) | Adapters return synthetic metadata; Dispatcher persists to `ResourceRecord.provider_metadata` |
| Schema migration | Alembic | — | New columns (`provider_metadata`, `activity_log`) require a versioned migration, not `create_all` |
| Adapter routing | Dispatcher (ADAPTER_REGISTRY) | — | dict-based registry in `dispatcher.py`; single mapping point for kind → adapter |
| Async latency simulation | Adapter (asyncio.sleep) | — | Sleep lives inside the adapter; Dispatcher does not know about timing |
| Validation of resource specs | Pydantic (ResourceSpec) | — | Pydantic rejects invalid specs before the Dispatcher or any adapter is invoked |
| Test session management | Test conftest (in-memory SQLite) | — | Tests use a separate session factory bound to `:memory:`; production code unchanged |

---

## Standard Stack

Phase 2 introduces no new packages. All dependencies are already installed and verified.

### Core (already installed)

| Library | Installed Version | Purpose | Slopcheck |
|---------|------------------|---------|-----------|
| `sqlalchemy` | 2.0.43 | ORM + async session for Dispatcher DB writes | [OK] |
| `alembic` | 1.18.4 | Versioned schema migration for new columns | [OK] |
| `aiosqlite` | 0.21.0 | Async SQLite driver (dev + test) | [OK] |
| `pydantic` | 2.13.4 | ResourceSpec validation before adapter dispatch | [OK] |
| `pytest-asyncio` | 1.4.0 | Async test execution (`asyncio_mode = "auto"`) | [OK] |

### No New Installs Required

Phase 2 is purely implementation using the stack locked in Phase 1. The `pyproject.toml` already declares all required dependencies.

---

## Package Legitimacy Audit

No new packages are installed in Phase 2. The audit covers packages that Phase 2 code actively uses (beyond what was audited in Phase 1).

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| `sqlalchemy` | PyPI | [VERIFIED: OK] | Approved — already installed, 2.0.43 |
| `alembic` | PyPI | [VERIFIED: OK] | Approved — already installed, 1.18.4 |
| `aiosqlite` | PyPI | [VERIFIED: OK] | Approved — already installed, 0.21.0 |
| `pydantic` | PyPI | [VERIFIED: OK] | Approved — already installed, 2.13.4 |
| `pytest-asyncio` | PyPI | [VERIFIED: OK] | Approved — already installed, 1.4.0 |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │             Phase 2 Core Engine              │
                    └─────────────────────────────────────────────┘

  YAML spec (test)
       │
       ▼
  yaml.safe_load()
       │
       ▼
  ResourceSpec.model_validate()   ──── invalid spec ────► ValidationError
  (Pydantic discriminated union)                          (raised before any
       │ valid spec                                        adapter is called)
       ▼
  dispatch(resource_id, session)
  src/pecp/dispatcher.py
       │
       ├─► SELECT ResourceRecord by id
       │
       ├─► Write status = PROVISIONING  ──────────────────► SQLite resource_records
       │   (session.commit)
       │
       ├─► ADAPTER_REGISTRY[resource.kind]
       │   │
       │   ├─ "PECPLambda"       → AwsLambdaMockAdapter
       │   ├─ "PECPContainer"    → AwsContainerMockAdapter
       │   ├─ "PECPDataService"  → AwsDataMockAdapter
       │   ├─ "PECPAccount"      → AwsAccountMockAdapter (asyncio.sleep(3))
       │   ├─ "PECPKubernetes"   → KubernetesMockAdapter
       │   ├─ "PECPSalesforce"   → SalesforceMockAdapter
       │   ├─ "PECPAem"          → AemMockAdapter
       │   ├─ "PECPDatadog"      → DatadogMockAdapter
       │   ├─ "PECPServiceNow"   → ServiceNowMockAdapter
       │   └─ "PECPJFrog"        → JFrogMockAdapter
       │
       ├─► adapter.provision(resource_spec)
       │       │
       │       └─► ProvisionResult(
       │               status=READY|FAILED,
       │               provider_metadata={...},
       │               activity_log=["Would call: ..."]
       │           )
       │
       └─► Write status = READY|FAILED
           Write provider_metadata (JSON-serialized dict)
           Write activity_log (JSON-serialized list[str])
           session.commit()
                 │
                 ▼
           SQLite resource_records
           (provider_metadata TEXT, activity_log TEXT — added by Alembic migration)
```

### Recommended Project Structure

```
src/
└── pecp/
    ├── adapters/
    │   ├── __init__.py          # re-exports AdapterBase
    │   ├── base.py              # AdapterBase ABC (Phase 1 — do not modify)
    │   └── mock/
    │       ├── __init__.py      # re-exports all 10 adapter classes
    │       ├── aws_lambda.py    # AwsLambdaMockAdapter
    │       ├── aws_container.py # AwsContainerMockAdapter
    │       ├── aws_data.py      # AwsDataMockAdapter
    │       ├── aws_account.py   # AwsAccountMockAdapter (asyncio.sleep(3))
    │       ├── kubernetes.py    # KubernetesMockAdapter
    │       ├── salesforce.py    # SalesforceMockAdapter
    │       ├── aem.py           # AemMockAdapter
    │       ├── datadog.py       # DatadogMockAdapter
    │       ├── servicenow.py    # ServiceNowMockAdapter
    │       └── jfrog.py         # JFrogMockAdapter
    ├── dispatcher.py            # dispatch() function + ADAPTER_REGISTRY
    └── persistence/
        └── models.py            # ResourceRecord gains provider_metadata + activity_log

alembic/
├── env.py                       # async-compatible Alembic env
├── script.py.mako
└── versions/
    └── 0001_add_provider_cols.py  # adds provider_metadata + activity_log

tests/
├── conftest.py                  # gains db_session fixture for Dispatcher tests
├── test_adapters/
│   └── mock/
│       ├── __init__.py
│       ├── test_aws_lambda.py
│       ├── test_aws_container.py
│       ├── test_aws_data.py
│       ├── test_aws_account.py
│       ├── test_kubernetes.py
│       ├── test_salesforce.py
│       ├── test_aem.py
│       ├── test_datadog.py
│       ├── test_servicenow.py
│       └── test_jfrog.py
└── test_dispatcher/
    ├── __init__.py
    └── test_dispatch.py
```

### Pattern 1: Mock Adapter — Standard Implementation

**What:** Every mock adapter subclasses `AdapterBase`, implements all three methods, simulates latency with `asyncio.sleep()`, and returns a `ProvisionResult` with synthetic metadata and an activity log. Adapters never raise for expected failure modes.

**When to use:** All 10 mock adapter classes.

```python
# Source: AdapterBase ABC (src/pecp/adapters/base.py) + CONTEXT.md decisions
# src/pecp/adapters/mock/aws_lambda.py

import asyncio
from typing import Any

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import LambdaSpec, ResourceSpec


class AwsLambdaMockAdapter(AdapterBase):
    """Mock adapter for PECPLambda resources. Simulates AWS Lambda provisioning."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        assert isinstance(spec, LambdaSpec)  # narrowed for mypy
        fn_name = spec.name
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "function_arn": f"arn:aws:lambda:us-east-1:123456789012:function:{fn_name}",
                "region": "us-east-1",
                "runtime": "python3.12",
            },
            activity_log=[
                f"Would call: aws lambda create-function"
                f" --function-name {fn_name}"
                f" --runtime python3.12"
                f" --code S3Bucket=pecp-deploys,S3Key={spec.source_code}",
                f"Would call: aws lambda add-permission"
                f" --function-name {fn_name}"
                f" --statement-id AllowAPIGateway"
                f" --action lambda:InvokeFunction",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        spec = resource.spec
        assert isinstance(spec, LambdaSpec)
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=[
                f"Would call: aws lambda delete-function --function-name {spec.name}",
            ],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(status=ResourceStatus.ready)
```

### Pattern 2: AwsAccountMockAdapter — Slow-Path Simulation

**What:** The `PECPAccount` adapter dwells in `PROVISIONING` state for at least 3 seconds. The adapter handles the dwell inline with `asyncio.sleep(3)` — the Dispatcher does not poll.

**When to use:** Only `AwsAccountMockAdapter`.

```python
# Source: CONTEXT.md Claude's Discretion (PECPAccount slow-path)
# src/pecp/adapters/mock/aws_account.py

import asyncio

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import AccountSpec, ResourceSpec


class AwsAccountMockAdapter(AdapterBase):
    """Mock adapter for PECPAccount. Simulates slow AWS Organizations account creation."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        team = resource.metadata.team or "unknown"
        # KINDS-04: dwell in PROVISIONING for ≥3 seconds
        # The Dispatcher writes status=PROVISIONING BEFORE calling this method.
        # This sleep simulates the real account creation delay (typically 10-15 min).
        await asyncio.sleep(3)
        account_id = "123456789012"  # synthetic
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={
                "account_id": account_id,
                "account_email": f"aws+{team}@example.com",
                "account_name": f"pecp-{team}",
                "management_console_url": f"https://console.aws.amazon.com/switch-role?account={account_id}",
            },
            activity_log=[
                f"Would call: aws organizations create-account"
                f" --email aws+{team}@example.com --account-name pecp-{team}",
                f"Would call: aws organizations describe-create-account-status"
                f" (polling until SUCCEEDED)",
                f"Would call: aws sts assume-role --role-arn"
                f" arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole"
                f" --role-session-name pecp-bootstrap",
            ],
        )

    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(
            status=ResourceStatus.ready,
            activity_log=["Would call: aws organizations close-account (manual PE action required)"],
        )

    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        return ProvisionResult(status=ResourceStatus.ready)
```

### Pattern 3: Dispatcher — State Machine

**What:** The Dispatcher reads a `ResourceRecord`, writes the `PENDING → PROVISIONING` transition, invokes the correct adapter, then writes the final state and persists `provider_metadata` and `activity_log`.

**When to use:** `src/pecp/dispatcher.py` — the single dispatch function Phase 3 calls from BackgroundTasks.

```python
# Source: CONTEXT.md D-03 through D-06
# src/pecp/dispatcher.py

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pecp.adapters.base import AdapterBase
from pecp.adapters.mock.aws_lambda import AwsLambdaMockAdapter
from pecp.adapters.mock.aws_container import AwsContainerMockAdapter
from pecp.adapters.mock.aws_data import AwsDataMockAdapter
from pecp.adapters.mock.aws_account import AwsAccountMockAdapter
from pecp.adapters.mock.kubernetes import KubernetesMockAdapter
from pecp.adapters.mock.salesforce import SalesforceMockAdapter
from pecp.adapters.mock.aem import AemMockAdapter
from pecp.adapters.mock.datadog import DatadogMockAdapter
from pecp.adapters.mock.servicenow import ServiceNowMockAdapter
from pecp.adapters.mock.jfrog import JFrogMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec
from pecp.persistence.models import ResourceRecord


class AdapterNotFoundError(KeyError):
    def __init__(self, kind: str) -> None:
        super().__init__(
            f"No adapter registered for kind: {kind!r}. Check ADAPTER_REGISTRY in dispatcher.py."
        )
        self.kind = kind


ADAPTER_REGISTRY: dict[str, AdapterBase] = {
    "PECPLambda": AwsLambdaMockAdapter(),
    "PECPContainer": AwsContainerMockAdapter(),
    "PECPDataService": AwsDataMockAdapter(),
    "PECPAccount": AwsAccountMockAdapter(),
    "PECPKubernetes": KubernetesMockAdapter(),
    "PECPSalesforce": SalesforceMockAdapter(),
    "PECPAem": AemMockAdapter(),
    "PECPDatadog": DatadogMockAdapter(),
    "PECPServiceNow": ServiceNowMockAdapter(),
    "PECPJFrog": JFrogMockAdapter(),
}


async def dispatch(resource_id: str, session: AsyncSession) -> None:
    """Drive a resource through PENDING → PROVISIONING → READY|FAILED.

    All status writes are exclusive to this function.
    Phase 3 calls this from FastAPI BackgroundTasks — signature must not change.
    """
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one()

    # Reconstruct the ResourceSpec from persisted JSON
    spec = ResourceSpec.model_validate_json(record.spec_json)

    # Transition: PENDING → PROVISIONING
    record.status = ResourceStatus.provisioning.value
    await session.commit()

    # Route to the correct adapter
    if spec.kind not in ADAPTER_REGISTRY:
        record.status = ResourceStatus.failed.value
        record.activity_log = json.dumps([f"No adapter registered for kind: {spec.kind!r}"])
        await session.commit()
        return

    adapter = ADAPTER_REGISTRY[spec.kind]
    provision_result = await adapter.provision(spec)

    # Transition: PROVISIONING → READY|FAILED
    record.status = provision_result.status.value
    record.provider_metadata = json.dumps(provision_result.provider_metadata)
    record.activity_log = json.dumps(provision_result.activity_log)
    await session.commit()
```

### Pattern 4: Alembic Async Migration

**What:** Alembic must be initialized for the first time and configured with an async-compatible `env.py`. The migration adds two nullable Text columns with JSON defaults.

**When to use:** One-time setup for Alembic initialization, then the specific migration for Phase 2 columns.

```python
# Source: SQLAlchemy 2.x + Alembic async integration pattern
# alembic/env.py (async-compatible version)

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from pecp.persistence.database import DATABASE_URL
from pecp.persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
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
```

```python
# Source: Alembic column addition ops
# alembic/versions/0001_add_provider_cols.py (generated, then edited)

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resource_records",
        sa.Column("provider_metadata", sa.Text(), nullable=True, server_default="{}"),
    )
    op.add_column(
        "resource_records",
        sa.Column("activity_log", sa.Text(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("resource_records", "activity_log")
    op.drop_column("resource_records", "provider_metadata")
```

### Pattern 5: ResourceRecord ORM — New Columns

**What:** `ResourceRecord` gains two `Mapped[str | None]` columns. The ORM model change must match the Alembic migration.

```python
# Source: SQLAlchemy 2.x mapped_column API
# Addition to src/pecp/persistence/models.py

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class ResourceRecord(Base):
    # ... existing columns ...
    provider_metadata: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
    activity_log: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
```

### Pattern 6: Dispatcher Test — In-Memory Session Fixture

**What:** The Dispatcher tests need an `AsyncSession` bound to an in-memory SQLite database, not the production database URL. Add a `db_session` fixture to `conftest.py`.

```python
# Source: SQLAlchemy 2.x async session + pytest-asyncio asyncio_mode="auto"
# Addition to tests/conftest.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pecp.persistence.models import Base

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()
```

### Pattern 7: Mock Adapter Test — asyncio.sleep Patching

**What:** Every adapter test patches `asyncio.sleep` to avoid real latency. The patch must target the import location where `sleep` is resolved — `asyncio.sleep` itself, not the adapter module's reference.

```python
# Source: CONTEXT.md Claude's Discretion (test strategy) + verified via Bash
# tests/test_adapters/mock/test_aws_lambda.py

import pytest
from unittest.mock import patch
import yaml

from pecp.adapters.mock.aws_lambda import AwsLambdaMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec

LAMBDA_YAML = """
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: test-fn
  team: toxins-research
spec:
  name: test-fn
  exposure: private
  api-gateway: /test
  source-code: github://myorg/test-repo
"""

async def test_aws_lambda_provision_returns_ready() -> None:
    adapter = AwsLambdaMockAdapter()
    spec = ResourceSpec.model_validate(yaml.safe_load(LAMBDA_YAML))
    with patch("asyncio.sleep", return_value=None):
        result = await adapter.provision(spec)
    assert result.status == ResourceStatus.ready
    assert len(result.activity_log) > 0
    assert result.activity_log[0].startswith("Would call:")
    assert result.provider_metadata != {}
```

### Pattern 8: Dispatcher End-to-End Test

**What:** Tests that the Dispatcher correctly drives a resource from PENDING to READY through the full state machine, using an in-memory session.

```python
# Source: D-03, D-04 dispatcher design decisions + verified SQLAlchemy session pattern
# tests/test_dispatcher/test_dispatch.py

import json
import pytest
from unittest.mock import patch
from sqlalchemy import select

from pecp.dispatcher import dispatch
from pecp.models.enums import ResourceStatus
from pecp.persistence.models import ResourceRecord

LAMBDA_SPEC_JSON = '{"api_version":"pecp/v1","kind":"PECPLambda","metadata":{"name":"test-fn","team":"toxins-research"},"spec":{"kind":"PECPLambda","name":"test-fn","exposure":"private","api-gateway":"/test","source-code":"github://myorg/test-repo"}}'

async def test_dispatch_drives_pending_to_ready(db_session) -> None:
    # Insert a pending record
    record = ResourceRecord(
        id="test-id-001",
        team="toxins-research",
        kind="PECPLambda",
        name="test-fn",
        status="pending",
        spec_json=LAMBDA_SPEC_JSON,
    )
    db_session.add(record)
    await db_session.commit()

    with patch("asyncio.sleep", return_value=None):
        await dispatch("test-id-001", db_session)

    result = await db_session.execute(
        select(ResourceRecord).where(ResourceRecord.id == "test-id-001")
    )
    updated = result.scalar_one()
    assert updated.status == ResourceStatus.ready.value
    log = json.loads(updated.activity_log or "[]")
    assert len(log) > 0
    assert log[0].startswith("Would call:")
    metadata = json.loads(updated.provider_metadata or "{}")
    assert metadata != {}
```

### Anti-Patterns to Avoid

- **Adapter raises exceptions for expected failures:** All adapter methods must return `ProvisionResult(status=ResourceStatus.failed, error="...")` — never `raise`. The Dispatcher does not wrap adapter calls in try/except for expected failures (D-04 from Phase 1).
- **Status written outside the Dispatcher:** Only `dispatcher.dispatch()` writes `ResourceRecord.status` after Phase 2. The API route handler sets `status="pending"` at creation only. Any other code path setting status breaks the invariant that D-03 establishes for Phase 3.
- **Dispatcher imports from `api/`:** `dispatcher.py` lives at `src/pecp/dispatcher.py`, not inside `api/`. It must not import any FastAPI dependency (`BackgroundTasks`, `Depends`, etc.) — those are Phase 3 concerns.
- **Activity log as unstructured prose:** All log entries must start with `"Would call: "` prefix. This enables Phase 5 parsing without a full schema change. Do not use unstructured or multi-sentence descriptions.
- **Alembic `create_all` instead of migrations:** Phase 2 uses Alembic migrations from here on. `init_schema()` in `database.py` calls `Base.metadata.create_all` which is correct for test setup; production uses `alembic upgrade head`. Do not modify `init_schema()` for the new columns.
- **Shared GenericMockAdapter base for Salesforce/AEM:** D-02 explicitly prohibits this. Use separate classes even though they are similar today.
- **Using `yaml.load()` anywhere:** Always `yaml.safe_load()`. This is a CLAUDE.md explicit prohibition and applies to all test fixtures that parse YAML specs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema column additions | Manual `ALTER TABLE` SQL | Alembic `op.add_column()` migration | Versioned, reversible, team-reproducible; manual SQL is not tracked |
| JSON column serialization | Custom serializer class | `json.dumps()` / `json.loads()` inline | Text columns with JSON strings are the locked decision (D-04); no ORM JSON type needed for SQLite PoC |
| Async test fixtures | `asyncio.get_event_loop()` manual setup | `pytest-asyncio` with `asyncio_mode = "auto"` | pytest-asyncio 1.4.0 removed the old event_loop fixture; `asyncio_mode = "auto"` is already configured |
| Adapter routing conditional | `if kind == "PECPLambda": ... elif kind == "PECPContainer": ...` | `ADAPTER_REGISTRY` dict lookup | O(1) lookup, single edit point when adding adapters, no branching logic in Dispatcher |
| Mock latency | `time.sleep()` | `asyncio.sleep()` | sync sleep blocks the event loop; async sleep yields correctly; also patchable in tests |

**Key insight:** The Dispatcher's job is pure routing and state writing. Any logic beyond "read record → look up adapter → call provision → write result" belongs in the adapter, not the Dispatcher.

---

## Common Pitfalls

### Pitfall 1: Alembic Not Initialized — `alembic.ini` Does Not Exist
**What goes wrong:** Running `alembic revision --autogenerate` before `alembic init` fails with a file-not-found error.
**Why it happens:** Alembic requires `alembic.ini` and the `alembic/` directory to exist. Phase 1 used `Base.metadata.create_all` only — no Alembic setup was needed.
**How to avoid:** Phase 2 must run `alembic init alembic` first, then replace `env.py` with the async-compatible version before running `alembic revision`.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'alembic.ini'`

### Pitfall 2: Alembic env.py Uses Sync Engine
**What goes wrong:** The default `env.py` generated by `alembic init` creates a sync SQLAlchemy engine. Using it with `sqlite+aiosqlite://` raises `sqlalchemy.exc.ArgumentError`.
**Why it happens:** Alembic's default template assumes a synchronous engine. The project uses `aiosqlite` which requires `create_async_engine`.
**How to avoid:** Replace `env.py` entirely with the async pattern (see Pattern 4 above): `create_async_engine` + `connection.run_sync(do_run_migrations)`.
**Warning signs:** `Argument 'aiosqlite' ... not supported` or `AttributeError: 'AsyncConnection' object has no attribute 'execute'`

### Pitfall 3: ResourceRecord Missing New Columns After Migration
**What goes wrong:** Tests that use `db_session` fixture (which calls `Base.metadata.create_all`) do NOT apply Alembic migrations — they reflect the ORM model. If `provider_metadata` and `activity_log` are not added to the ORM model in `models.py`, the test schema will also lack them.
**Why it happens:** `create_all` reads the current ORM model state. The Alembic migration only applies when running `alembic upgrade head` against a real database file.
**How to avoid:** Add `provider_metadata` and `activity_log` columns to `ResourceRecord` in `models.py` AT THE SAME TIME as writing the Alembic migration. The ORM model and the migration file must be consistent.
**Warning signs:** `OperationalError: table resource_records has no column named provider_metadata`

### Pitfall 4: Dispatcher Writes Stale Data After `expire_on_commit=False`
**What goes wrong:** After a `session.commit()`, the `record` object may be stale if the session was created with default settings (`expire_on_commit=True`). Accessing `record.status` after commit would trigger a lazy reload, which fails in async context.
**Why it happens:** SQLAlchemy's default `expire_on_commit=True` expires all attributes after commit, requiring a reload. Async sessions cannot lazy-reload.
**How to avoid:** The session factory already uses `expire_on_commit=False` (set in Phase 1's `database.py`). Test fixtures must also use `expire_on_commit=False`.
**Warning signs:** `MissingGreenlet: greenlet_spawn has not been called` or `DetachedInstanceError`

### Pitfall 5: asyncio.sleep Patch Target Is Wrong
**What goes wrong:** Patching `pecp.adapters.mock.aws_account.asyncio.sleep` instead of `asyncio.sleep` has no effect — the sleep still runs for 3 seconds.
**Why it happens:** The adapter module imports `asyncio` and calls `asyncio.sleep`. The patch must target the `sleep` attribute on the `asyncio` module object itself, not a module-level import alias.
**How to avoid:** Always patch `"asyncio.sleep"` (the canonical location). Verified: `with patch("asyncio.sleep", return_value=None)` works correctly for this pattern.
**Warning signs:** Test takes 3+ seconds to run; mock_sleep.call_count is 0.

### Pitfall 6: isinstance() Type Narrowing Breaks mypy in Strict Mode
**What goes wrong:** In `provision(self, resource: ResourceSpec) -> ProvisionResult`, the `resource.spec` is typed as `AnySpec` (the discriminated union). Accessing `spec.source_code` without an isinstance check fails mypy strict.
**Why it happens:** mypy cannot infer that a specific adapter only ever receives a specific spec kind — the interface accepts `ResourceSpec` which carries all 6 spec types.
**How to avoid:** Each adapter must guard spec access with `assert isinstance(spec, LambdaSpec)` (for mypy narrowing) or use a pattern match. `assert isinstance(...)` is the simplest; for full correctness, return `ProvisionResult(status=FAILED, error=f"Unexpected spec type: {type(spec)}")` as a fallback branch.
**Warning signs:** `mypy error: Item "ContainerSpec" of "LambdaSpec | ContainerSpec | ..." has no attribute "source_code"`

### Pitfall 7: spec_json Model Validate Fails Due to Kind Injection
**What goes wrong:** Calling `ResourceSpec.model_validate_json(record.spec_json)` in the Dispatcher fails validation because the stored JSON was serialized with the `kind` injected into the `spec` block (by `model_dump_json()`), but the validator's `inject_kind_into_spec` model_validator checks if `kind` is already present and skips injection. This should round-trip correctly.
**Why it happens:** `model_dump_json()` on `ResourceSpec` outputs the `spec` block including the `kind` literal field (e.g., `"kind": "PECPLambda"`). On deserialization, `inject_kind_into_spec` sees `kind` already in spec and skips injection — the discriminated union resolves correctly.
**How to avoid:** No action needed — this is the correct behavior. The concern is moot because the validator checks `"kind" not in spec` before injecting. Verify with a round-trip test: `ResourceSpec.model_validate_json(spec.model_dump_json())`.
**Warning signs:** `ValidationError` on `model_validate_json` of a stored spec. If seen, check that `spec_json` was generated by `model_dump_json()` and not by `json.dumps(raw_dict)` without the kind field.

---

## Code Examples

Verified patterns from official sources and codebase inspection:

### Dispatcher spec reconstitution
```python
# Source: verified against pecp.models.resource_spec (Phase 1 output)
spec = ResourceSpec.model_validate_json(record.spec_json)
# spec.kind == "PECPLambda", spec.spec is LambdaSpec, etc.
# resource.metadata.team is available for SalesforceMockAdapter / AemMockAdapter
```

### JSON persistence for provider_metadata and activity_log
```python
# Source: verified via Bash — json.dumps/loads round-trip confirmed
record.provider_metadata = json.dumps(provision_result.provider_metadata)
record.activity_log = json.dumps(provision_result.activity_log)
await session.commit()

# Reading back:
metadata = json.loads(record.provider_metadata or "{}")
log = json.loads(record.activity_log or "[]")
```

### ResourceSpec.model_validate_json round-trip
```python
# Source: Pydantic v2 model_dump_json / model_validate_json
spec = ResourceSpec.model_validate(yaml.safe_load(yaml_text))
stored = spec.model_dump_json()                      # stored in ResourceRecord.spec_json
restored = ResourceSpec.model_validate_json(stored)  # Dispatcher reconstitutes this
assert restored.kind == spec.kind                    # round-trip stable
```

### asyncio.sleep patching (verified)
```python
# Source: verified via Bash — patch("asyncio.sleep") intercepts await asyncio.sleep(N)
from unittest.mock import patch

with patch("asyncio.sleep", return_value=None) as mock_sleep:
    result = await adapter.provision(spec)
assert mock_sleep.call_count == 1
assert mock_sleep.call_args[0][0] == 3  # for AwsAccountMockAdapter
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alembic sync engine in env.py | Async engine + `connection.run_sync()` | SQLAlchemy 2.x + aiosqlite | Required for `sqlite+aiosqlite://` URL; default alembic init template must be replaced |
| `Optional[str]` type hint | `str \| None` union syntax | Python 3.10+ | Phase 1 already uses this; all Phase 2 code must continue the pattern |
| `@validator` Pydantic v1 | `@field_validator` Pydantic v2 | Pydantic v2 | Phase 1 already uses v2; do not import v1 validators |
| `asyncio_mode = "strict"` | `asyncio_mode = "auto"` | pytest-asyncio 0.21+ | Already configured in pyproject.toml; do not add `@pytest.mark.asyncio` to individual tests |

**Deprecated/outdated:**
- `Base.metadata.create_all` for schema changes: correct for test setup only; for production schema evolution use `alembic upgrade head`
- `event_loop` fixture override: removed in pytest-asyncio 0.21+; `asyncio_mode = "auto"` makes it unnecessary

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `PECPKubernetes` is the kind string used for the Kubernetes adapter in `ADAPTER_REGISTRY` (not `PECPKubernetes` vs `PECPKube`) | Standard Stack / ADAPTER_REGISTRY | Dispatcher routing fails for Kubernetes resources; easy to fix if kind string is confirmed |
| A2 | `PECPDatadog`, `PECPServiceNow`, `PECPJFrog` are the kind strings for the three additional adapters listed in ADPT-02 | Standard Stack / ADAPTER_REGISTRY | Dispatcher routing fails for these kinds; REQUIREMENTS.md ADPT-02 lists them but does not define the exact kind strings |

**Note on A1 and A2:** The `ResourceSpec` discriminated union defined in Phase 1 covers only 6 kinds: `PECPLambda`, `PECPContainer`, `PECPDataService`, `PECPAccount`, `PECPSalesforce`, `PECPAem`. ADPT-02 adds 3 new adapters (Datadog, ServiceNow, JFrog). These need either: (a) new spec kinds added to the discriminated union, or (b) a generic catch-all spec. CONTEXT.md D-06 lists the full 10-entry registry but doesn't specify whether new `ResourceSpec` kinds are required. See Open Questions.

---

## Open Questions

1. **Do Datadog, ServiceNow, and JFrog need new ResourceSpec kinds?**
   - What we know: Phase 1's `ResourceSpec` discriminated union has 6 kinds. ADPT-02 adds 3 more adapters. CONTEXT.md D-06 shows the full 10-entry `ADAPTER_REGISTRY`.
   - What's unclear: Whether `PECPDatadog`, `PECPServiceNow`, `PECPJFrog` require new Pydantic spec classes (like `DatadogSpec`, `ServiceNowSpec`, `JFrogSpec`) analogous to `SalesforceSpec` and `AemSpec`, or whether they route through the existing generic `SalesforceSpec`-style catch-all.
   - Recommendation: Add three new minimal spec classes (`DatadogSpec`, `ServiceNowSpec`, `JFrogSpec`) with `config: dict[str, Any]` fields — exactly the same pattern as `SalesforceSpec` and `AemSpec` (Phase 1 D-11). Extend the `AnySpec` union. This is the lowest-friction path and matches the established pattern.

2. **Does `alembic.ini` need a `sqlalchemy.url` that works for both file and in-memory databases?**
   - What we know: `alembic.ini` typically hardcodes a DB URL. Tests use `:memory:`. Production uses `./pecp.db`.
   - What's unclear: Whether the Alembic env.py should read from `PECP_DATABASE_URL` env var (as `database.py` does) or from `alembic.ini`.
   - Recommendation: Override `alembic.ini`'s `sqlalchemy.url` in `env.py` by reading `DATABASE_URL` from `pecp.persistence.database` — the same env var (`PECP_DATABASE_URL`) controls both runtime and migration database. Set `alembic.ini`'s `sqlalchemy.url` to the default file path as a fallback.

---

## Environment Availability

All dependencies verified present on the development machine.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.12.5 | — |
| pytest / pytest-asyncio | Test suite | Yes | 9.0.2 / 1.4.0 | — |
| SQLAlchemy | Dispatcher, persistence | Yes | 2.0.43 | — |
| alembic | Schema migration | Yes | 1.18.4 | — |
| aiosqlite | Async SQLite driver | Yes | 0.21.0 | — |
| pydantic | Resource spec validation | Yes | 2.13.4 | — |
| asyncio (stdlib) | Adapter latency simulation | Yes | stdlib | — |
| unittest.mock (stdlib) | asyncio.sleep patching in tests | Yes | stdlib | — |

**Missing dependencies with no fallback:** None

**Missing dependencies with fallback:** None

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` section |
| Quick run command | `python -m pytest tests/test_adapters/mock/ tests/test_dispatcher/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADPT-02 | All 10 adapters instantiate without error | unit | `python -m pytest tests/test_adapters/mock/ -x` | No — Wave 0 |
| ADPT-02 | ADAPTER_REGISTRY contains all 10 kind keys | unit | `python -m pytest tests/test_dispatcher/test_dispatch.py::test_registry_contains_all_kinds -x` | No — Wave 0 |
| ADPT-03 | provision() returns ProvisionResult with non-empty activity_log and provider_metadata | unit | `python -m pytest tests/test_adapters/mock/ -x` | No — Wave 0 |
| ADPT-03 | Activity log entries start with "Would call:" prefix | unit | `python -m pytest tests/test_adapters/mock/ -x` | No — Wave 0 |
| KINDS-01 | LambdaSpec missing source-code raises ValidationError | unit | `python -m pytest tests/test_models/test_resource_spec.py::test_lambda_spec_missing_required_field_raises_validation_error -x` | Yes |
| KINDS-04 | AwsAccountMockAdapter.provision() calls asyncio.sleep(3) | unit | `python -m pytest tests/test_adapters/mock/test_aws_account.py::test_account_sleeps_three_seconds -x` | No — Wave 0 |
| KINDS-04 | Dispatcher writes status=PROVISIONING before calling adapter.provision() | integration | `python -m pytest tests/test_dispatcher/test_dispatch.py::test_dispatch_writes_provisioning_before_adapter -x` | No — Wave 0 |
| D-03 | dispatch() drives PENDING → PROVISIONING → READY | integration | `python -m pytest tests/test_dispatcher/test_dispatch.py::test_dispatch_drives_pending_to_ready -x` | No — Wave 0 |
| D-03 | dispatch() drives PENDING → PROVISIONING → FAILED on adapter failure | integration | `python -m pytest tests/test_dispatcher/test_dispatch.py::test_dispatch_drives_pending_to_failed -x` | No — Wave 0 |
| D-04 | provider_metadata and activity_log written to ResourceRecord after dispatch | integration | `python -m pytest tests/test_dispatcher/test_dispatch.py -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_adapters/mock/ tests/test_dispatcher/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green (`25 existing + new Phase 2 tests`) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_adapters/mock/__init__.py` — empty, needed for pytest collection
- [ ] `tests/test_dispatcher/__init__.py` — empty, needed for pytest collection
- [ ] `tests/test_adapters/mock/test_aws_lambda.py` — covers ADPT-02, ADPT-03, KINDS-01
- [ ] `tests/test_adapters/mock/test_aws_account.py` — covers KINDS-04 sleep assertion
- [ ] `tests/test_adapters/mock/test_aws_container.py` — covers ADPT-02, ADPT-03, KINDS-02
- [ ] `tests/test_adapters/mock/test_aws_data.py` — covers ADPT-02, ADPT-03, KINDS-03
- [ ] `tests/test_adapters/mock/test_kubernetes.py` — covers ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_salesforce.py` — covers ADPT-02, ADPT-03, KINDS-05
- [ ] `tests/test_adapters/mock/test_aem.py` — covers ADPT-02, ADPT-03, KINDS-06
- [ ] `tests/test_adapters/mock/test_datadog.py` — covers ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_servicenow.py` — covers ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_jfrog.py` — covers ADPT-02, ADPT-03
- [ ] `tests/test_dispatcher/test_dispatch.py` — covers D-03, D-04, KINDS-04 (Dispatcher flow)
- [ ] `db_session` fixture in `tests/conftest.py` — shared for Dispatcher tests
- [ ] `src/pecp/adapters/mock/__init__.py` — re-exports all adapter classes

---

## Security Domain

> `security_enforcement: true` in config.json, ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable — no HTTP layer in Phase 2 |
| V3 Session Management | No | Not applicable — no user sessions |
| V4 Access Control | No | Not applicable — Dispatcher is internal module |
| V5 Input Validation | Yes | Pydantic v2 `model_validate` / `model_validate_json` — ResourceSpec validated before adapter dispatch |
| V6 Cryptography | No | No secrets or encryption in Phase 2 |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Invalid resource spec injection into adapter | Tampering | Pydantic `model_validate_json` in Dispatcher reconstructs ResourceSpec from stored JSON — invalid stored specs raise ValidationError before adapter is called |
| YAML unsafe load in tests | Tampering / Code Execution | All test fixtures must use `yaml.safe_load()` — CLAUDE.md explicit prohibition; `yaml.load()` allows arbitrary code execution |
| Adapter registry lookup on arbitrary kind strings | Spoofing | Dispatcher checks `if spec.kind not in ADAPTER_REGISTRY` and returns FAILED result rather than raising unhandled KeyError; `AdapterNotFoundError` wraps the message safely |
| JSON injection in activity_log strings | Information Disclosure | Activity log strings are developer-written constants, not user input — low risk in PoC; `json.dumps()` handles any embedded special characters correctly |

---

## Project Constraints (from CLAUDE.md)

| Directive | Category | Enforcement |
|-----------|----------|-------------|
| Python only — org standard | Tech stack | All Phase 2 code is Python |
| All backends mocked — no real cloud access | Scope | Adapters simulate with asyncio.sleep and synthetic data only |
| `yaml.load` (unsafe) is forbidden — always `yaml.safe_load` | Security | All test fixtures and adapter code that handles YAML must use `safe_load` |
| No Marshmallow/Cerberus — Pydantic v2 only | Validation | ResourceSpec validation uses Pydantic; adapters use isinstance on spec fields |
| No Celery — FastAPI BackgroundTasks only (PoC) | Async tasks | Dispatcher is a standalone async function; no broker; BackgroundTasks integration in Phase 3 only |
| No SQLModel — SQLAlchemy 2.x async + Alembic | Data storage | `ResourceRecord` uses `mapped_column`; Alembic for migrations |
| Auth must be designed out (stub only) | Architecture | Dispatcher signature has no auth parameters; auth context not passed to adapters |
| GSD workflow enforcement | Process | Phase work runs through `/gsd-execute-phase` |

---

## Sources

### Primary (HIGH confidence)
- Phase 1 codebase — `src/pecp/adapters/base.py`, `src/pecp/models/`, `src/pecp/persistence/` — read directly and verified
- Phase 2 CONTEXT.md — decisions D-01 through D-06 and Claude's Discretion items — read directly
- `pyproject.toml` — installed dependency versions confirmed via `pip show`
- Alembic 1.18.4 installed — `alembic.command`, `Operations.add_column` verified via Python import
- SQLAlchemy 2.0.43 — `async_sessionmaker`, `AsyncSession`, `mapped_column` verified via Python
- pytest-asyncio 1.4.0 — `asyncio_mode = "auto"` in pyproject.toml confirmed working (25 tests pass)

### Secondary (MEDIUM confidence)
- [ASSUMED] `PECPKubernetes`, `PECPDatadog`, `PECPServiceNow`, `PECPJFrog` as kind strings — derived from naming convention in CONTEXT.md D-06 registry listing; not present in ResourceSpec discriminated union yet

### Tertiary (LOW confidence)
- None — all factual claims are verified against the installed codebase or official Python stdlib

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified installed at exact versions via pip show
- Architecture: HIGH — directly derived from locked CONTEXT.md decisions D-03 through D-06
- Pitfalls: HIGH — confirmed via live Bash verification (asyncio.sleep patching, session patterns, Alembic init gap)
- Open questions: MEDIUM — Datadog/ServiceNow/JFrog kind strings are inferred from naming convention

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (stable Python ecosystem; Alembic/SQLAlchemy APIs do not change rapidly)

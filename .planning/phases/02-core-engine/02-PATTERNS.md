# Phase 2: Core Engine - Pattern Map

**Mapped:** 2026-05-28
**Files analyzed:** 17 new/modified files
**Analogs found:** 17 / 17

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/pecp/adapters/mock/__init__.py` | module-init | — | `src/pecp/adapters/__init__.py` | exact |
| `src/pecp/adapters/mock/aws_lambda.py` | adapter | request-response | `src/pecp/adapters/base.py` + `tests/test_adapters/test_adapter_base.py` | role-match |
| `src/pecp/adapters/mock/aws_container.py` | adapter | request-response | `src/pecp/adapters/mock/aws_lambda.py` (to be created) | exact |
| `src/pecp/adapters/mock/aws_data.py` | adapter | request-response | `src/pecp/adapters/mock/aws_lambda.py` (to be created) | exact |
| `src/pecp/adapters/mock/aws_account.py` | adapter | request-response | `src/pecp/adapters/mock/aws_lambda.py` (to be created) | exact |
| `src/pecp/adapters/mock/kubernetes.py` | adapter | request-response | `src/pecp/adapters/mock/aws_lambda.py` (to be created) | exact |
| `src/pecp/adapters/mock/salesforce.py` | adapter | request-response | `src/pecp/adapters/mock/aws_lambda.py` (to be created) | exact |
| `src/pecp/adapters/mock/aem.py` | adapter | request-response | `src/pecp/adapters/mock/salesforce.py` (to be created, same pattern) | exact |
| `src/pecp/adapters/mock/datadog.py` | adapter | request-response | `src/pecp/adapters/mock/salesforce.py` (to be created) | exact |
| `src/pecp/adapters/mock/servicenow.py` | adapter | request-response | `src/pecp/adapters/mock/salesforce.py` (to be created) | exact |
| `src/pecp/adapters/mock/jfrog.py` | adapter | request-response | `src/pecp/adapters/mock/salesforce.py` (to be created) | exact |
| `src/pecp/dispatcher.py` | service | event-driven | `src/pecp/api/routes/resources.py` (SQLAlchemy session pattern) | partial |
| `src/pecp/models/resource_spec.py` | model | transform | `src/pecp/models/resource_spec.py` (modify existing) | exact |
| `src/pecp/persistence/models.py` | model | CRUD | `src/pecp/persistence/models.py` (modify existing) | exact |
| `alembic/` (init + env.py + migration) | config/migration | batch | no analog — Alembic not yet initialized | no-analog |
| `tests/conftest.py` | test | — | `tests/test_persistence/test_database.py` (db_session fixture) | role-match |
| `tests/test_adapters/mock/test_*.py` (10 files) | test | request-response | `tests/test_adapters/test_adapter_base.py` | role-match |
| `tests/test_dispatcher/test_dispatch.py` | test | event-driven | `tests/test_persistence/test_database.py` | role-match |

---

## Pattern Assignments

### `src/pecp/adapters/mock/__init__.py` (module-init)

**Analog:** `src/pecp/adapters/__init__.py` (empty file — 1 line)

The existing `src/pecp/adapters/__init__.py` is empty. The mock `__init__.py` must re-export all 10 adapter classes. Use explicit `__all__` and named imports so that `from pecp.adapters.mock import AwsLambdaMockAdapter` works.

**Import/export pattern:**
```python
"""Re-exports for all PECP mock adapters."""

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

__all__ = [
    "AwsLambdaMockAdapter",
    "AwsContainerMockAdapter",
    "AwsDataMockAdapter",
    "AwsAccountMockAdapter",
    "KubernetesMockAdapter",
    "SalesforceMockAdapter",
    "AemMockAdapter",
    "DatadogMockAdapter",
    "ServiceNowMockAdapter",
    "JFrogMockAdapter",
]
```

---

### `src/pecp/adapters/mock/aws_lambda.py` (adapter, request-response)

**Analog:** `src/pecp/adapters/base.py` (lines 1-27) + `tests/test_adapters/test_adapter_base.py` (lines 1-41)

This is the template adapter. All other adapters copy this structure.

**Imports pattern** (from `src/pecp/adapters/base.py` lines 1-6 + project conventions):
```python
"""Mock adapter for PECPLambda resources (ADPT-02, ADPT-03, KINDS-01)."""

import asyncio
from typing import Any

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import LambdaSpec, ResourceSpec
```

**Core adapter pattern** — subclass `AdapterBase`, implement all three abstract methods, never raise for expected failures (from `src/pecp/adapters/base.py` lines 9-26 docstring, `tests/test_adapters/test_adapter_base.py` lines 26-40):
```python
class AwsLambdaMockAdapter(AdapterBase):
    """Mock adapter for PECPLambda resources. Simulates AWS Lambda provisioning."""

    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(2)  # ADPT-03: simulate provisioning latency
        spec = resource.spec
        assert isinstance(spec, LambdaSpec)  # narrows type for mypy strict
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

**Error/failure pattern** — return FAILED result, never raise (from `src/pecp/adapters/base.py` lines 12-16, `src/pecp/models/provision_result.py` line 14):
```python
# When a spec type mismatch occurs (defensive fallback):
return ProvisionResult(
    status=ResourceStatus.failed,
    error=f"Unexpected spec type: {type(resource.spec).__name__}",
)
```

**Activity log convention** — all entries start with `"Would call: "` prefix (CONTEXT.md Claude's Discretion):
```python
activity_log=[
    "Would call: aws lambda create-function --function-name my-fn --runtime python3.12",
]
```

---

### `src/pecp/adapters/mock/aws_account.py` (adapter, request-response — slow-path variant)

**Analog:** `src/pecp/adapters/base.py` (same base) — slow-path variant

Identical structure to `aws_lambda.py` except `provision()` uses `asyncio.sleep(3)` to satisfy KINDS-04 (≥3s dwell in PROVISIONING). The sleep is inside the adapter, not in the Dispatcher.

**Slow-path provision pattern:**
```python
async def provision(self, resource: ResourceSpec) -> ProvisionResult:
    team = resource.metadata.team or "unknown"
    # KINDS-04: dwell in PROVISIONING for >= 3 seconds
    # Dispatcher writes status=PROVISIONING BEFORE calling this.
    await asyncio.sleep(3)
    account_id = "123456789012"
    return ProvisionResult(
        status=ResourceStatus.ready,
        provider_metadata={
            "account_id": account_id,
            "account_email": f"aws+{team}@example.com",
            "account_name": f"pecp-{team}",
        },
        activity_log=[
            f"Would call: aws organizations create-account"
            f" --email aws+{team}@example.com --account-name pecp-{team}",
        ],
    )
```

Note: `resource.metadata.team` (not `resource.spec.team`) — see `src/pecp/models/resource_spec.py` lines 61-63 for `ResourceMetadata` definition.

---

### `src/pecp/adapters/mock/salesforce.py` and `aem.py` (adapter, request-response — generic team-scoped variant)

**Analog:** `src/pecp/adapters/base.py` + CONTEXT.md D-01, D-02

These are the simplest adapters. `spec.config` is `dict[str, Any]` — no kind-specific fields to access. Use `resource.metadata.team` for team-scoped log messages. No `isinstance` narrowing needed beyond confirming the correct spec type.

**Generic team-scoped pattern** (from `src/pecp/models/resource_spec.py` lines 45-52):
```python
from pecp.models.resource_spec import SalesforceSpec, ResourceSpec

class SalesforceMockAdapter(AdapterBase):
    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        await asyncio.sleep(1)
        team = resource.metadata.team or "unknown"
        return ProvisionResult(
            status=ResourceStatus.ready,
            provider_metadata={"team": team, "system": "salesforce"},
            activity_log=[
                f"Would provision Salesforce resource for team {team}",
            ],
        )
```

`AemMockAdapter`, `DatadogMockAdapter`, `ServiceNowMockAdapter`, `JFrogMockAdapter` follow the identical structure, substituting the system name and log message.

---

### `src/pecp/adapters/mock/aws_data.py` (adapter, request-response — branching variant)

**Analog:** `src/pecp/adapters/mock/aws_lambda.py` (to be created)

Adds a branch on `spec.subtype` (from `src/pecp/models/resource_spec.py` lines 34-38, `DataServiceSubtype` enum lines 9-15).

**Subtype branching pattern:**
```python
from pecp.models.resource_spec import DataServiceSpec, DataServiceSubtype, ResourceSpec

async def provision(self, resource: ResourceSpec) -> ProvisionResult:
    await asyncio.sleep(2)
    spec = resource.spec
    assert isinstance(spec, DataServiceSpec)
    # Branch on subtype for kind-specific metadata/log
    if spec.subtype == DataServiceSubtype.s3:
        log_line = f"Would call: aws s3api create-bucket --bucket pecp-{spec.name}"
        metadata = {"bucket_arn": f"arn:aws:s3:::pecp-{spec.name}"}
    elif spec.subtype == DataServiceSubtype.dynamodb:
        log_line = f"Would call: aws dynamodb create-table --table-name pecp-{spec.name}"
        metadata = {"table_arn": f"arn:aws:dynamodb:us-east-1:123456789012:table/pecp-{spec.name}"}
    else:
        log_line = f"Would call: aws {spec.subtype.value} provision --name pecp-{spec.name}"
        metadata = {"name": spec.name, "subtype": spec.subtype.value}
    return ProvisionResult(
        status=ResourceStatus.ready,
        provider_metadata=metadata,
        activity_log=[log_line],
    )
```

---

### `src/pecp/dispatcher.py` (service, event-driven)

**Analog:** `src/pecp/api/routes/resources.py` (SQLAlchemy async session pattern, lines 1-97) + `src/pecp/persistence/database.py` (session factory, lines 1-47)

The Dispatcher uses the same `AsyncSession` + `select()` + `session.commit()` pattern as the route handler. Key difference: the Dispatcher owns status writes; routes only set `status="pending"` at creation.

**Imports pattern** (derived from `src/pecp/api/routes/resources.py` lines 1-20 and `src/pecp/persistence/database.py` lines 1-17):
```python
"""PECP Dispatcher — drives ResourceRecord through PENDING → PROVISIONING → READY|FAILED."""

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
```

**Registry pattern** (CONTEXT.md D-06):
```python
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
```

**Core dispatch function** — session pattern mirrors `src/pecp/api/routes/resources.py` lines 39-50 (`session.execute` + `result.scalars()`) and lines 81-89 (`session.add` + `await session.commit()`):
```python
async def dispatch(resource_id: str, session: AsyncSession) -> None:
    """Drive a resource through PENDING → PROVISIONING → READY|FAILED."""
    result = await session.execute(
        select(ResourceRecord).where(ResourceRecord.id == resource_id)
    )
    record = result.scalar_one()

    spec = ResourceSpec.model_validate_json(record.spec_json)

    # Transition: PENDING → PROVISIONING
    record.status = ResourceStatus.provisioning.value
    await session.commit()

    # Route to adapter
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

**Critical:** `dispatcher.py` must NOT import from `pecp.api.*`. No `FastAPI`, `BackgroundTasks`, or `Depends` — those are Phase 3 concerns (CONTEXT.md D-05).

---

### `src/pecp/models/resource_spec.py` — extend with 3 new spec kinds (model, transform)

**Analog:** `src/pecp/models/resource_spec.py` (existing file, lines 45-52 — `SalesforceSpec` and `AemSpec` are the exact templates)

Three new spec classes follow the same `config: dict[str, Any]` pattern as `SalesforceSpec`/`AemSpec`. Add them to the `AnySpec` union.

**New spec class pattern** (copy from `src/pecp/models/resource_spec.py` lines 45-52):
```python
class DatadogSpec(BaseModel):
    kind: Literal["PECPDatadog"]
    config: dict[str, Any] = Field(default_factory=dict)


class ServiceNowSpec(BaseModel):
    kind: Literal["PECPServiceNow"]
    config: dict[str, Any] = Field(default_factory=dict)


class JFrogSpec(BaseModel):
    kind: Literal["PECPJFrog"]
    config: dict[str, Any] = Field(default_factory=dict)
```

**Updated AnySpec union** (extend `src/pecp/models/resource_spec.py` lines 55-58):
```python
AnySpec = Annotated[
    Union[
        LambdaSpec, ContainerSpec, DataServiceSpec, AccountSpec,
        SalesforceSpec, AemSpec, DatadogSpec, ServiceNowSpec, JFrogSpec,
    ],
    Field(discriminator="kind"),
]
```

---

### `src/pecp/persistence/models.py` — add two columns (model, CRUD)

**Analog:** `src/pecp/persistence/models.py` (existing file, lines 17-36)

Two new `Mapped[str | None]` columns using the same `mapped_column` pattern as `spec_json` (line 31) and `status` (line 30). Must be added to `ResourceRecord` simultaneously with the Alembic migration.

**New column pattern** (copy `mapped_column(Text, ...)` from `src/pecp/persistence/models.py` line 31):
```python
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Add to ResourceRecord class after existing columns:
provider_metadata: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
activity_log: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
```

The `str | None` union syntax (not `Optional[str]`) matches the existing column type pattern in the file (e.g., `team: str | None = None` in `ResourceMetadata`).

---

### `alembic/` initialization + `env.py` + migration (config, migration)

**No analog in codebase** — Alembic has not been initialized. The project uses `Base.metadata.create_all` for schema setup (see `src/pecp/persistence/database.py` lines 31-38). Phase 2 introduces Alembic for the first time.

**Setup sequence** (from RESEARCH.md Pitfall 1 and Pitfall 2):
1. `alembic init alembic` — creates `alembic.ini` and `alembic/` directory with default `env.py`
2. Replace `alembic/env.py` entirely with async-compatible version
3. Run `alembic revision --autogenerate -m "add_provider_cols"`
4. Edit generated migration to confirm `op.add_column` targets match model

**Async env.py pattern** (RESEARCH.md Pattern 4):
```python
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

**Migration file pattern** (RESEARCH.md Pattern 4):
```python
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

---

### `tests/conftest.py` — add `db_session` fixture (test)

**Analog:** `tests/test_persistence/test_database.py` (lines 17-29) — this file contains the definitive `db_session` fixture pattern the Dispatcher tests need.

The existing `tests/conftest.py` (lines 1-33) has only a `client` fixture. Add `db_session` so Dispatcher tests can share it without duplicating the setup.

**Current conftest structure** (`tests/conftest.py` lines 1-33):
```python
"""Shared pytest fixtures for the PECP test suite."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("PECP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    ...
```

**New `db_session` fixture to add** (copy pattern from `tests/test_persistence/test_database.py` lines 17-29, updated for `AsyncGenerator` typing from conftest style):
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pecp.persistence.models import Base

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session backed by an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

Note: `expire_on_commit=False` is critical — matches `src/pecp/persistence/database.py` line 27 and avoids `MissingGreenlet` errors in async context (RESEARCH.md Pitfall 4).

---

### `tests/test_adapters/mock/test_aws_lambda.py` (and other adapter tests) (test, request-response)

**Analog:** `tests/test_adapters/test_adapter_base.py` (lines 1-41) + `tests/test_models/test_resource_spec.py` (YAML fixture pattern, lines 18-27)

**Imports pattern** (from `tests/test_adapters/test_adapter_base.py` lines 1-9 + `tests/test_models/test_resource_spec.py` lines 1-17):
```python
"""Tests for AwsLambdaMockAdapter (ADPT-02, ADPT-03, KINDS-01)."""

import pytest
from unittest.mock import patch
import yaml

from pecp.adapters.mock.aws_lambda import AwsLambdaMockAdapter
from pecp.models.enums import ResourceStatus
from pecp.models.resource_spec import ResourceSpec
```

**YAML fixture pattern** (copy from `tests/test_models/test_resource_spec.py` lines 18-28, which uses `yaml.safe_load` as required by CLAUDE.md):
```python
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
```

**Core test pattern** — asyncio.sleep patched at `"asyncio.sleep"` (not module-level alias):
```python
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

No `@pytest.mark.asyncio` decorator — `asyncio_mode = "auto"` in `pyproject.toml` line 63 covers all async test functions automatically.

---

### `tests/test_dispatcher/test_dispatch.py` (test, event-driven)

**Analog:** `tests/test_persistence/test_database.py` (lines 46-67 — round-trip pattern with `db_session` fixture)

Uses the shared `db_session` fixture from conftest. Inserts a `ResourceRecord` manually (same pattern as `tests/test_persistence/test_database.py` lines 46-57), calls `dispatch()`, then asserts final state.

**Imports pattern:**
```python
"""Tests for Dispatcher state machine (D-03, D-04, KINDS-04)."""

import json
import pytest
from unittest.mock import patch
from sqlalchemy import select

from pecp.dispatcher import dispatch, ADAPTER_REGISTRY
from pecp.models.enums import ResourceStatus
from pecp.persistence.models import ResourceRecord
```

**Core test pattern** (mirrors `tests/test_persistence/test_database.py` lines 46-67):
```python
async def test_dispatch_drives_pending_to_ready(db_session: AsyncSession) -> None:
    record = ResourceRecord(
        id="test-id-001",
        team="toxins-research",
        kind="PECPLambda",
        name="test-fn",
        status="pending",
        spec_json='{"api_version":"pecp/v1","kind":"PECPLambda","metadata":{"name":"test-fn","team":"toxins-research"},"spec":{"kind":"PECPLambda","name":"test-fn","exposure":"private","api-gateway":"/test","source-code":"github://myorg/test-repo"}}',
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

`spec_json` must be produced by `spec.model_dump_json()` — not hand-rolled JSON — to ensure the discriminated union round-trips correctly (RESEARCH.md Pitfall 7).

---

## Shared Patterns

### Async-First: all methods are `async def`
**Source:** `src/pecp/adapters/base.py` lines 19-26
**Apply to:** All 10 mock adapter classes, `dispatcher.py`, all tests
```python
@abstractmethod
async def provision(self, resource: ResourceSpec) -> ProvisionResult: ...
@abstractmethod
async def deprovision(self, resource: ResourceSpec) -> ProvisionResult: ...
@abstractmethod
async def get_status(self, resource: ResourceSpec) -> ProvisionResult: ...
```

### Return-Never-Raise
**Source:** `src/pecp/adapters/base.py` lines 12-16 (docstring), `src/pecp/models/provision_result.py` line 14
**Apply to:** All 10 mock adapter `provision()`, `deprovision()`, `get_status()` methods
```python
# On any expected failure:
return ProvisionResult(status=ResourceStatus.failed, error="<message>")
# NOT: raise SomeException(...)
```

### SQLAlchemy Async Session Pattern
**Source:** `src/pecp/api/routes/resources.py` lines 37-50 (read) and lines 80-90 (write/commit)
**Apply to:** `src/pecp/dispatcher.py`, `tests/conftest.py`, `tests/test_dispatcher/test_dispatch.py`
```python
# Read:
result = await session.execute(select(ResourceRecord).where(...))
record = result.scalar_one()
# Write:
record.status = ResourceStatus.ready.value
await session.commit()
```

### `expire_on_commit=False` on all test session factories
**Source:** `src/pecp/persistence/database.py` line 27, `tests/test_persistence/test_database.py` line 25
**Apply to:** `tests/conftest.py` db_session fixture
```python
factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

### `yaml.safe_load()` — never `yaml.load()`
**Source:** `src/pecp/api/routes/resources.py` line 71, `tests/test_models/test_resource_spec.py` line 33
**Apply to:** All test files that load YAML spec fixtures
```python
spec = ResourceSpec.model_validate(yaml.safe_load(YAML_STRING))
```

### asyncio.sleep patching
**Source:** RESEARCH.md Pattern 7 (verified against project test framework)
**Apply to:** All 10 adapter tests, `tests/test_dispatcher/test_dispatch.py`
```python
with patch("asyncio.sleep", return_value=None):
    result = await adapter.provision(spec)
```
Patch target is `"asyncio.sleep"` — not the module-level import path of the adapter.

### No `@pytest.mark.asyncio` — `asyncio_mode = "auto"` is already configured
**Source:** `pyproject.toml` line 63
**Apply to:** All new test functions
```python
# pyproject.toml already has:
[tool.pytest.ini_options]
asyncio_mode = "auto"
# Do NOT add @pytest.mark.asyncio to individual test functions
```

### `str | None` type syntax (not `Optional[str]`)
**Source:** `src/pecp/models/resource_spec.py` line 63, `src/pecp/persistence/models.py` line 30
**Apply to:** All new Python 3.12 code including new ORM columns and adapter type hints
```python
# Correct (matches project style):
provider_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
# Not:
provider_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `alembic/env.py` | config | batch | Alembic not initialized; no `alembic.ini` or `alembic/` directory exists in the project root |
| `alembic/versions/0001_add_provider_cols.py` | migration | batch | First Alembic migration; no prior migration files exist |

**Planner note for these files:** Use RESEARCH.md Pattern 4 directly. The async `env.py` pattern and migration ops are well-specified there. The only prerequisite is running `alembic init alembic` first (RESEARCH.md Pitfall 1).

---

## Metadata

**Analog search scope:** `src/pecp/`, `tests/`
**Files scanned:** 18 source + test files
**Pattern extraction date:** 2026-05-28

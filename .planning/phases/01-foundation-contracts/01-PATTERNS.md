# Phase 1: Foundation + Contracts - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 18 (new/modified)
**Analogs found:** 0 / 18 — new project, no existing source code

---

## Codebase Analog Search

The project root contains only `example.yaml`, `CLAUDE.md`, and planning artifacts.
`src/pecp/` does not exist. There are no Python files to search.

**All patterns come from RESEARCH.md code examples and canonical library documentation.**
Every file below is marked "No existing analog — new project."

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | — | No existing analog — new project | none |
| `src/pecp/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/models/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/models/enums.py` | model | — | No existing analog — new project | none |
| `src/pecp/models/provision_result.py` | model | request-response | No existing analog — new project | none |
| `src/pecp/models/resource_spec.py` | model | transform | No existing analog — new project | none |
| `src/pecp/adapters/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/adapters/base.py` | middleware | event-driven | No existing analog — new project | none |
| `src/pecp/api/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/api/dependencies.py` | middleware | request-response | No existing analog — new project | none |
| `src/pecp/api/main.py` | controller | request-response | No existing analog — new project | none |
| `src/pecp/api/routes/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/api/routes/resources.py` | controller | request-response | No existing analog — new project | none |
| `src/pecp/cli/__init__.py` | config | — | No existing analog — new project | none |
| `src/pecp/cli/main.py` | utility | request-response | No existing analog — new project | none |
| `tests/conftest.py` | test | request-response | No existing analog — new project | none |
| `tests/test_models/test_resource_spec.py` | test | transform | No existing analog — new project | none |
| `tests/test_models/test_provision_result.py` | test | request-response | No existing analog — new project | none |
| `tests/test_adapters/test_adapter_base.py` | test | event-driven | No existing analog — new project | none |
| `tests/test_api/test_routes.py` | test | request-response | No existing analog — new project | none |
| `docs/DEMO-SCRIPT.md` | config | — | No existing analog — new project | none |

---

## Pattern Assignments

### `pyproject.toml` (config)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / pyproject.toml"

**Complete pattern:**
```toml
[build-system]
requires = ["setuptools>=77.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pecp"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.136",
    "uvicorn[standard]>=0.48",
    "pydantic>=2.13",
    "pyyaml>=6.0",
    "typer>=0.26",
    "rich>=15",
    "httpx>=0.28",
    "python-multipart>=0.0.29",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-asyncio>=1.4",
    "mypy>=2.1",
    "ruff>=0.15",
]

[project.scripts]
pecp = "pecp.cli.main:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
strict = true
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = ["yaml"]
ignore_missing_imports = true

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]
```

**Key constraints:**
- D-07: `pyproject.toml` only — no `requirements.txt`, no `setup.cfg`, no separate tool config files
- `asyncio_mode = "auto"` is mandatory: pytest-asyncio 1.4.0 removed the old `event_loop` fixture pattern
- `pythonpath = ["src"]` enables `from pecp.models import ...` in tests without a full `pip install -e .` but install is still required for the `pecp` CLI entrypoint

---

### `src/pecp/models/enums.py` (model)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / ResourceStatus Enum"

**Pattern:**
```python
# src/pecp/models/enums.py
from enum import Enum


class ResourceStatus(str, Enum):
    pending = "pending"
    provisioning = "provisioning"
    ready = "ready"
    failed = "failed"
```

**Key constraints:**
- D-12: Single source of truth for status values — imported by adapters, Dispatcher, and API; never redefined elsewhere
- `str` mixin ensures JSON serialization returns the string value, not `"ResourceStatus.ready"`
- Four values only: `pending`, `provisioning`, `ready`, `failed`

---

### `src/pecp/models/provision_result.py` (model, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / ProvisionResult Model"

**Pattern:**
```python
# src/pecp/models/provision_result.py
from typing import Any

from pydantic import BaseModel, Field

from pecp.models.enums import ResourceStatus


class ProvisionResult(BaseModel):
    status: ResourceStatus
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    activity_log: list[str] = Field(default_factory=list)
    error: str | None = None
```

**Key constraints:**
- D-01: All three adapter methods (`provision`, `deprovision`, `get_status`) return this single type — no separate StatusResult
- D-02: `error` field carries failure reason; adapters set `status=FAILED, error="..."` rather than raising exceptions (D-04)
- D-03: `get_status()` reuses this model; `activity_log` and `provider_metadata` may be empty on status-only calls
- `Field(default_factory=dict/list)` is required — mutable defaults must not be shared across instances

---

### `src/pecp/models/resource_spec.py` (model, transform)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / Complete Discriminated Union" + `example.yaml`

**The `example.yaml` file (the only existing file) defines the canonical wire format:**
```yaml
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
```

**Pattern:**
```python
# src/pecp/models/resource_spec.py
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class DataServiceSubtype(str, Enum):
    s3 = "s3"
    sqs = "sqs"
    sns = "sns"
    rds = "rds"
    dynamodb = "dynamodb"


class LambdaSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    kind: Literal["PECPLambda"]
    name: str
    exposure: Literal["public", "private"]
    api_gateway: str = Field(alias="api-gateway")
    source_code: str = Field(alias="source-code")  # Proprietary URI: github://org/repo


class ContainerSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    kind: Literal["PECPContainer"]
    name: str
    exposure: Literal["public", "private"]
    image: str


class DataServiceSpec(BaseModel):
    kind: Literal["PECPDataService"]
    name: str
    subtype: DataServiceSubtype


class AccountSpec(BaseModel):
    kind: Literal["PECPAccount"]
    # No spec fields — account request is identified by team in metadata


class SalesforceSpec(BaseModel):
    kind: Literal["PECPSalesforce"]
    config: dict[str, Any] = Field(default_factory=dict)


class AemSpec(BaseModel):
    kind: Literal["PECPAem"]
    config: dict[str, Any] = Field(default_factory=dict)


AnySpec = Annotated[
    Union[LambdaSpec, ContainerSpec, DataServiceSpec, AccountSpec, SalesforceSpec, AemSpec],
    Field(discriminator="kind"),
]


class ResourceMetadata(BaseModel):
    name: str
    team: str | None = None


class ResourceSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: ResourceMetadata
    spec: AnySpec
```

**Key constraints:**
- D-10: Discriminated union on `kind` — Pydantic selects the sub-model and validates fields per-kind at parse time; do NOT use a flat `Union` without `discriminator`
- D-09: All 6 kinds defined now so Phase 2 adapter authors have complete models
- D-11: `SalesforceSpec` and `AemSpec` use `config: dict[str, Any]` as minimal stubs
- `Field(alias="api-gateway")` + `Field(alias="source-code")` are required to parse the hyphenated keys from `example.yaml`
- `model_config = ConfigDict(populate_by_name=True)` allows test construction using Python names (`api_gateway`) or YAML aliases (`api-gateway`)
- Parse flow: `data = yaml.safe_load(yaml_text)` then `ResourceSpec.model_validate(data)` — never `yaml.load()`, never `model_construct()`
- SECURITY: Consider adding `model_config = ConfigDict(extra="forbid")` to spec models to prevent undeclared field injection (RESEARCH.md security domain)

---

### `src/pecp/adapters/base.py` (middleware, event-driven)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Architecture Patterns / Pattern 2: AdapterBase ABC" and "Code Examples / AdapterBase ABC"

**Pattern:**
```python
# src/pecp/adapters/base.py
from abc import ABC, abstractmethod

from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec


class AdapterBase(ABC):
    """
    Contract for all PECP backing-system adapters.

    Rules (from CONTEXT.md D-04):
    - Always return ProvisionResult. Do NOT raise exceptions for expected failures.
    - Set status=FAILED and populate error= for failure cases.
    - The Dispatcher reads the result; it does not use try/except over adapter calls.
    """

    @abstractmethod
    async def provision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult: ...

    @abstractmethod
    async def get_status(self, resource: ResourceSpec) -> ProvisionResult: ...
```

**Key constraints:**
- ADPT-01: All three methods are abstract — omitting any one raises `TypeError` at instantiation
- TypeError fires at `BrokenAdapter()` (instantiation), not at `import BrokenAdapter` (import) — the test must call the constructor to trigger enforcement
- D-04: Adapters never raise for expected failures; they return `ProvisionResult(status=FAILED, error="...")`
- All three methods are `async` — Phase 2 mock adapters use `asyncio.sleep()` for simulated latency

---

### `src/pecp/api/dependencies.py` (middleware, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Architecture Patterns / Pattern 3: RequestContext FastAPI Dependency" and "Code Examples / RequestContext Dependency"

**Pattern:**
```python
# src/pecp/api/dependencies.py
from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel


class RequestContext(BaseModel):
    user_id: str
    team_memberships: list[str]
    is_pe_admin: bool


async def get_request_context() -> RequestContext:
    """
    Auth stub. Hardcoded for PoC.
    To add JWT: replace this function body only.
    Route signatures (ContextDep parameter) do not change.
    """
    return RequestContext(
        user_id="stub-user",
        team_memberships=["platform"],
        is_pe_admin=False,
    )


ContextDep = Annotated[RequestContext, Depends(get_request_context)]
```

**Key constraints:**
- ARCH-02: Every route handler accepts `ctx: ContextDep` — the `Annotated` alias means `Depends()` in the route param list is not needed
- Stub returns hardcoded values; replacing `get_request_context` body is the only change required to add real JWT auth — route signatures stay identical
- `get_request_context` takes no arguments — it reads from FastAPI's `Request` object if headers are needed later, not from query params

---

### `src/pecp/api/main.py` (controller, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md open question A3 resolves to `src/pecp/api/main.py`

**Pattern:**
```python
# src/pecp/api/main.py
from fastapi import FastAPI

from pecp.api.routes import resources

app = FastAPI(title="PECP Control Plane", version="0.1.0")

app.include_router(resources.router)
```

**Key constraints:**
- `app` must be importable as `from pecp.api.main import app` for test fixtures
- Phase 1 registers route skeletons only; no middleware, no database lifespan events yet

---

### `src/pecp/api/routes/resources.py` (controller, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Architecture Patterns / Pattern 4: Team Scope Enforcement" and "Code Examples / Route Skeleton"

**Pattern:**
```python
# src/pecp/api/routes/resources.py
from fastapi import APIRouter, HTTPException

from pecp.api.dependencies import ContextDep

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
async def list_resources(
    team: str | None = None,
    ctx: ContextDep,
) -> list[dict]:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    # Phase 3 fills in: query DB, filter by team, return resource records
    return []


@router.post("")
async def create_resource(
    team: str | None = None,
    ctx: ContextDep,
) -> dict:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    # Phase 3 fills in: parse body, dispatch to adapter
    return {"status": "accepted"}
```

**Key constraints:**
- ARCH-01: `team` must be optional (`str | None = None`) with explicit `HTTPException(status_code=400)` — FastAPI's automatic 422 for missing required params does NOT satisfy the success criterion
- ARCH-02: `ctx: ContextDep` on every handler — uses the `Annotated` alias, no `= Depends()` needed in the param list
- Phase 1 route bodies are stubs; return values are placeholder minimal responses

---

### `src/pecp/cli/main.py` (utility, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md standard stack (Typer 0.26.2)

**Pattern:**
```python
# src/pecp/cli/main.py
import typer

app = typer.Typer(name="pecp", help="PECP Platform Engineering Control Plane CLI")


@app.command()
def version() -> None:
    """Print the CLI version."""
    typer.echo("pecp 0.1.0")


if __name__ == "__main__":
    app()
```

**Key constraints:**
- Phase 1 is a stub — no real commands yet; `pecp` entrypoint must be registered in `pyproject.toml` as `pecp = "pecp.cli.main:app"`
- Phase 3 adds `apply`, `get`, `delete`, `status` commands

---

### `tests/conftest.py` (test, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / Async Test Pattern"

**Pattern:**
```python
# tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from pecp.api.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
```

**Key constraints:**
- `@pytest.fixture` (not `@pytest_asyncio.fixture`) works with `asyncio_mode = "auto"` — pytest-asyncio 1.4.0 auto-wraps async fixtures
- `ASGITransport` is the pytest-asyncio 1.x replacement for the deprecated `app=` kwarg pattern — use `AsyncClient(transport=ASGITransport(app=app), ...)`, never `TestClient`
- The `client` fixture is session-scoped only if all tests in the session are async — default function scope is safe

---

### `tests/test_models/test_resource_spec.py` (test, transform)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Validation Architecture / Phase Requirements to Test Map"

**Pattern:**
```python
# tests/test_models/test_resource_spec.py
import yaml
import pytest
from pydantic import ValidationError

from pecp.models.resource_spec import LambdaSpec, ResourceSpec


EXAMPLE_YAML = """
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""


def test_lambda_spec_parses_from_example_yaml() -> None:
    data = yaml.safe_load(EXAMPLE_YAML)
    resource = ResourceSpec.model_validate(data)
    assert resource.kind == "PECPLambda"
    assert isinstance(resource.spec, LambdaSpec)
    assert resource.spec.source_code == "github://myorg/lambda-code"
    assert resource.spec.api_gateway == "/hello"


def test_invalid_kind_raises_validation_error() -> None:
    data = yaml.safe_load(EXAMPLE_YAML)
    data["kind"] = "InvalidKind"
    data["spec"]["kind"] = "InvalidKind"
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)


def test_lambda_spec_missing_required_field_raises_validation_error() -> None:
    data = yaml.safe_load(EXAMPLE_YAML)
    del data["spec"]["source-code"]
    with pytest.raises(ValidationError):
        ResourceSpec.model_validate(data)
```

**Key constraints:**
- Use `yaml.safe_load()` — never `yaml.load()` (CLAUDE.md explicit prohibition)
- Always use `model_validate()` — never `model_construct()` (skips validation)
- Tests must exercise the hyphenated alias round-trip (`api-gateway` in YAML → `api_gateway` on Python model)

---

### `tests/test_models/test_provision_result.py` (test, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md D-01 through D-03 validation requirements

**Pattern:**
```python
# tests/test_models/test_provision_result.py
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult


def test_provision_result_defaults_to_empty_collections() -> None:
    result = ProvisionResult(status=ResourceStatus.pending)
    assert result.provider_metadata == {}
    assert result.activity_log == []
    assert result.error is None


def test_provision_result_failed_status_carries_error() -> None:
    result = ProvisionResult(status=ResourceStatus.failed, error="Quota exceeded")
    assert result.status == ResourceStatus.failed
    assert result.error == "Quota exceeded"


def test_get_status_reuse_allows_empty_log_and_metadata() -> None:
    # D-03: get_status() reuses ProvisionResult; activity_log may be empty
    result = ProvisionResult(status=ResourceStatus.ready)
    assert result.activity_log == []
    assert result.provider_metadata == {}
```

---

### `tests/test_adapters/test_adapter_base.py` (test, event-driven)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / ABC TypeError Test"

**Pattern:**
```python
# tests/test_adapters/test_adapter_base.py
import pytest

from pecp.adapters.base import AdapterBase
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec


def test_adapter_base_raises_type_error_without_provision() -> None:
    """Instantiating an incomplete adapter raises TypeError (ADPT-01)."""

    class IncompleteAdapter(AdapterBase):
        async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:  # type: ignore[override]
            ...

        async def get_status(self, resource: ResourceSpec) -> ProvisionResult:  # type: ignore[override]
            ...
        # provision() intentionally omitted

    with pytest.raises(TypeError, match="provision"):
        IncompleteAdapter()


def test_complete_adapter_instantiates_without_error() -> None:
    """A fully-implemented adapter instantiates successfully (ADPT-01)."""

    class FullAdapter(AdapterBase):
        async def provision(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

        async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

        async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
            return ProvisionResult(status=ResourceStatus.ready)

    adapter = FullAdapter()
    assert adapter is not None
```

**Key constraints:**
- TypeError fires at `IncompleteAdapter()` (instantiation), not at class definition or import
- The success criterion says "at import time" — this is satisfied by the test file's existence: pytest collects the test module, which defines the broken class, and the `with pytest.raises` assertion runs at test execution time. Per RESEARCH.md Pitfall 6, true import-time enforcement is not achievable with ABC alone.

---

### `tests/test_api/test_routes.py` (test, request-response)

**Analog:** None — new project
**Source doc:** RESEARCH.md "Code Examples / Async Test Pattern" and "Pitfall 1: 422 vs 400"

**Pattern:**
```python
# tests/test_api/test_routes.py
from httpx import AsyncClient


async def test_get_resources_without_team_returns_400(client: AsyncClient) -> None:
    response = await client.get("/resources")
    assert response.status_code == 400


async def test_get_resources_with_team_returns_200(client: AsyncClient) -> None:
    response = await client.get("/resources", params={"team": "platform"})
    assert response.status_code == 200


async def test_post_resource_without_team_returns_400(client: AsyncClient) -> None:
    response = await client.post("/resources", json={})
    assert response.status_code == 400


async def test_route_handler_receives_request_context(client: AsyncClient) -> None:
    # ARCH-02: RequestContext stub must be injected without error
    response = await client.get("/resources", params={"team": "platform"})
    assert response.status_code == 200  # 200 confirms dependency injection succeeded
```

**Key constraints:**
- `asyncio_mode = "auto"` in pyproject.toml means no `@pytest.mark.asyncio` decorator is needed on each test
- The `client` fixture from `conftest.py` is injected by pytest name matching
- ARCH-01: Assert `400`, not `422` — the route must use explicit `HTTPException(status_code=400)` not FastAPI's default 422

---

### `docs/DEMO-SCRIPT.md` (documentation)

**Analog:** None — new project
**Source doc:** CONTEXT.md D-13 through D-16

**Structure constraints (not a code pattern):**
- D-13: Mixed audience — leads with narrative, commands are visible but story drives
- D-14: Flowing prose with actual `pecp` commands embedded inline
- D-15: Full story now with `[expected output]` placeholders where terminal output does not exist yet; Phase 5 replaces placeholders with real output
- D-16: Core scenario is new team onboards end-to-end — team creation, Lambda + AWS account request, watch status update with PE notes, account reaches `ready`, open dashboard to see full team inventory
- Document lives at `docs/DEMO-SCRIPT.md`

---

## Shared Patterns

### Import Convention
**Apply to:** All `src/pecp/` Python files

Use absolute imports from the `pecp` package root — never relative imports. This is enforced by the `src/` layout:
```python
from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult
from pecp.models.resource_spec import ResourceSpec
from pecp.api.dependencies import ContextDep
from pecp.adapters.base import AdapterBase
```

### Pydantic v2 Model Convention
**Apply to:** All Pydantic models (`ResourceSpec`, sub-specs, `ProvisionResult`, `RequestContext`)

```python
from pydantic import BaseModel, ConfigDict, Field

class MyModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # when aliases are used
    field: str = Field(alias="hyphenated-key")        # for YAML hyphenated keys
    optional_field: str | None = None                 # Python 3.12 union syntax
    list_field: list[str] = Field(default_factory=list)  # mutable defaults
```

Never use:
- `@validator` (Pydantic v1 — use `@field_validator`)
- `from __future__ import annotations` (not needed in Python 3.12+)
- `Optional[str]` (use `str | None`)

### YAML Loading Convention
**Apply to:** Any file that parses YAML input (tests, API routes)

```python
import yaml

# Always:
data = yaml.safe_load(yaml_text)

# Never:
data = yaml.load(yaml_text)              # unsafe — code execution risk
data = yaml.load(yaml_text, Loader=None) # also unsafe
```

### Error Response Convention
**Apply to:** `src/pecp/api/routes/resources.py` and all future route files

```python
from fastapi import HTTPException

# Team scope enforcement (ARCH-01):
if not team:
    raise HTTPException(status_code=400, detail="team parameter is required")

# Never rely on FastAPI's automatic 422 when the spec requires 400
```

### Async Test Convention
**Apply to:** All `tests/test_api/` files

```python
# No decorator needed — asyncio_mode = "auto" in pyproject.toml handles it
async def test_something(client: AsyncClient) -> None:
    response = await client.get("/endpoint")
    assert response.status_code == 200

# Never use:
# @pytest.mark.asyncio  (not needed with asyncio_mode = "auto")
# TestClient(app)       (sync only; use httpx.AsyncClient instead)
```

---

## No Analog Found

All 21 files in this phase have no existing codebase analog. This is Phase 1 of a new project.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All 21 files listed above | various | various | `src/pecp/` does not exist; project root contains only `example.yaml`, `CLAUDE.md`, and planning artifacts |

---

## Reference: `example.yaml` (the only existing file)

```yaml
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
```

This file is the canonical wire format. All Pydantic alias configurations in `LambdaSpec` must parse this exact structure — hyphenated keys (`api-gateway`, `source-code`) in the `spec` block, `apiVersion` camelCase at the top level.

---

## Metadata

**Analog search scope:** `/Users/punitlad/projects/pecp-poc/` (entire project root)
**Python files scanned:** 0 (no `.py` files exist yet)
**Pattern sources:** RESEARCH.md code examples + official library documentation
**Pattern extraction date:** 2026-05-27

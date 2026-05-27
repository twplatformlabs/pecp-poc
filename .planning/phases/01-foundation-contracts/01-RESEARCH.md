# Phase 1: Foundation + Contracts - Research

**Researched:** 2026-05-27
**Domain:** Python project scaffolding, Pydantic v2 discriminated unions, FastAPI dependency injection, Python ABC adapter interface, mypy + ruff toolchain
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Adapter Result Contract**
- D-01: `provision()`, `deprovision()`, and `get_status()` all return a `ProvisionResult` Pydantic model — one return type for the entire adapter interface.
- D-02: `ProvisionResult` fields: `status: ResourceStatus`, `provider_metadata: dict[str, Any]`, `activity_log: list[str]`, `error: str | None`. The `error` field carries failure reason without needing exceptions.
- D-03: `get_status()` reuses `ProvisionResult` — `activity_log` and `provider_metadata` will be empty/None on status-only calls. No separate StatusResult type.
- D-04: Adapters always return a `ProvisionResult` — failed operations return `status=FAILED` with `error` populated. Adapters do NOT raise exceptions for expected failure modes. The Dispatcher reads the result, not a try/except.

**Project Structure**
- D-05: `src/` layout — all source code lives under `src/pecp/`. Prevents import ambiguity when running tests from the project root.
- D-06: Four sub-packages: `src/pecp/api/` (FastAPI routes + dependencies), `src/pecp/adapters/` (AdapterBase ABC), `src/pecp/cli/` (Typer commands), `src/pecp/models/` (Pydantic resource specs, ProvisionResult, enums).
- D-07: `pyproject.toml` only — no `requirements.txt`. All dependencies, tool config (ruff, mypy, pytest), and build metadata in one file.
- D-08: Tests in a top-level `tests/` directory mirroring `src/pecp/` — `tests/test_api/`, `tests/test_adapters/`, `tests/test_models/`.

**Resource Model Scope**
- D-09: All 6 resource kinds fully defined in Phase 1 with proper spec fields — PECPLambda, PECPContainer, PECPDataService, PECPAccount, PECPSalesforce, PECPAem.
- D-10: Pydantic v2 discriminated union on `kind` — `ResourceSpec` has a `spec` field typed as a union of `LambdaSpec | ContainerSpec | DataServiceSpec | AccountSpec | SalesforceSpec | AemSpec`, discriminated by the `kind` field.
- D-11: `PECPSalesforce` and `PECPAem` use minimal stub specs: `SalesforceSpec(config: dict[str, Any])` and `AemSpec(config: dict[str, Any])`.
- D-12: One shared `ResourceStatus` enum in `src/pecp/models/enums.py` — `pending`, `provisioning`, `ready`, `failed`.

**Demo Script**
- D-13: Mixed audience — engineers and stakeholders both present. Script leads with narrative, commands are visible but the story drives.
- D-14: Format: narrative walkthrough with inline commands — flowing prose with actual `pecp` commands embedded.
- D-15: Write the full story now with `[expected output]` placeholders where terminal output doesn't exist yet. Phase 5 replaces placeholders with real output.
- D-16: Core demo scenario: new team onboards end-to-end — team creation, submit a Lambda + AWS account request, watch status update with PE notes appearing mid-provisioning, account reaches `ready`, open the dashboard to see full team inventory.

### Claude's Discretion
- Exception handling: adapters return FAILED results, not exceptions — chosen to align with D-04 and D-02.
- AdapterBase enforcement: ABC abstract methods should raise `TypeError` at instantiation if not implemented. The success criteria say "at import time" — this is not achievable with ABC alone; a module-level instantiation check test (or Protocol + runtime_checkable) can satisfy the spirit. Claude decides the exact enforcement mechanism.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-01 | All resource API endpoints enforce team scope at the server — `GET /resources` without team context returns `400`, not all resources | FastAPI query parameter required with HTTPException; documented in Architecture Patterns |
| ARCH-02 | A `RequestContext` auth stub flows through every route handler with `user_id`, `team_memberships`, `is_pe_admin` — today hardcoded, structured for future JWT replacement | FastAPI Depends() injection pattern; documented in Code Examples |
| ARCH-04 | Demo script (narrative walkthrough) is written before any implementation begins | Content and format decisions are locked in CONTEXT.md D-13 through D-16; no technical research required |
| ADPT-01 | Pluggable adapter interface (`AdapterBase` ABC) with `provision`, `deprovision`, and `get_status` — locked before any mock is written, designed for AWS-complexity real backends | Python ABC + abstractmethod pattern; documented in Architecture Patterns and Code Examples |
</phase_requirements>

---

## Summary

Phase 1 is a pure scaffolding phase — no running server, no provisioning logic, no database. The deliverable is a fully-typed Python skeleton that defines the contracts all subsequent phases build against. The three core contracts are: (1) the `AdapterBase` ABC that mock adapters in Phase 2 will implement, (2) the Pydantic v2 discriminated union covering all 6 resource kinds that the API in Phase 3 will parse, and (3) the `RequestContext` FastAPI dependency that every route handler in Phase 3 will accept.

The technical challenge is not complexity but precision: getting the Pydantic discriminated union shape exactly right so that `yaml.safe_load` output parses without transformation, ensuring the ABC raises `TypeError` at instantiation (not only at method-call time), and wiring the `RequestContext` as a true `Depends()` so Phase 3 can replace the stub with a JWT implementation by swapping one function — not touching route signatures.

The toolchain is fully resolved: Python 3.12, Pydantic 2.13.4, FastAPI 0.136.3, mypy 2.1.0 (with pydantic.mypy plugin), ruff 0.15.14, pytest 9.0.3, pytest-asyncio 1.4.0. All packages verified clean via slopcheck and pip registry.

**Primary recommendation:** Scaffold the project in this order — (1) `pyproject.toml` + tool configs, (2) enums + ProvisionResult, (3) discriminated union resource specs, (4) AdapterBase ABC, (5) RequestContext stub + FastAPI route skeletons, (6) tests for each contract, (7) demo script document. Tests prove the contracts, not the implementation.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Resource spec validation (YAML parse) | API / Backend | — | Pydantic models live server-side; CLI sends raw YAML bytes |
| Team scope enforcement | API / Backend | — | ARCH-01: 400 returned at server, not filtered at CLI |
| Auth context (RequestContext stub) | API / Backend | — | ARCH-02: Depends() injection on every route handler |
| Adapter interface definition | API / Backend | — | ABC lives in `src/pecp/adapters/`; no tier boundary crossed |
| Resource kind models (discriminated union) | API / Backend | — | Shared models package consumed by API and adapters |
| Demo script | Documentation | — | Narrative document only; no tier |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python` | 3.12 | Runtime | Org standard; installed on dev machine [VERIFIED: pip registry] |
| `pydantic` | 2.13.4 | Resource spec validation, ProvisionResult model | Fastest validation, native FastAPI integration, discriminated unions [VERIFIED: pip registry] |
| `fastapi` | 0.136.3 | Route skeleton with Depends() injection | Async-first, OpenAPI generation, native Pydantic integration [VERIFIED: pip registry] |
| `uvicorn[standard]` | 0.48.0 | ASGI server (Phase 1 only starts it in tests) | Required by FastAPI; `[standard]` adds watchfiles + httptools [VERIFIED: pip registry] |
| `pyyaml` | 6.0.3 | Parse YAML resource specs via `safe_load` | Org-approved; `safe_load` is the only safe entry point per CLAUDE.md [VERIFIED: pip registry] |
| `mypy` | 2.1.0 | Static type checking — enforces adapter interface contracts | Catches ABC violations, Pydantic field type errors at CI time [VERIFIED: pip registry] |
| `ruff` | 0.15.14 | Linting + formatting | Replaces flake8 + black + isort; single tool [VERIFIED: pip registry] |

### Supporting (Phase 1 scaffold only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.0.3 | Test runner | All test execution [VERIFIED: pip registry] |
| `pytest-asyncio` | 1.4.0 | Async test support | FastAPI route tests using httpx.AsyncClient [VERIFIED: pip registry] |
| `httpx` | 0.28.1 | FastAPI test client (AsyncClient + ASGITransport) | In-process HTTP testing without a live server [VERIFIED: pip registry] |
| `typer` | 0.26.2 | CLI framework skeleton | Phase 1 creates stub commands only [VERIFIED: pip registry] |
| `rich` | 15.0.0 | Terminal output | Required by Typer for help text; included transitively [VERIFIED: pip registry] |
| `python-multipart` | 0.0.29 | FastAPI file upload support | Required for `-f resource.yaml` in Phase 3 [VERIFIED: pip registry] |
| `python-dotenv` | 1.0.0 | `.env` loading | Local dev config [VERIFIED: pip registry] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python ABC | `typing.Protocol` + `runtime_checkable` | Protocol is structurally typed (duck typing), ABC is nominally typed — ABC is stricter and explicitly signals "you must subclass me" |
| Pydantic discriminated union | Separate parse function + `isinstance` dispatch | Loses field-level validation per kind; error messages are worse |
| `src/` layout | Flat layout | Flat layout allows accidental imports of the uninstalled package from cwd — `src/` forces explicit install |

**Installation:**

```bash
pip install -e ".[dev]"
```

(Full `pyproject.toml` is specified in Architecture Patterns section.)

**Version verification:** All versions confirmed against PyPI registry on 2026-05-27.

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| pydantic | PyPI | [OK] | Approved |
| fastapi | PyPI | [OK] | Approved |
| uvicorn | PyPI | [OK] | Approved |
| pyyaml | PyPI | [OK] | Approved |
| mypy | PyPI | [OK] | Approved |
| ruff | PyPI | [OK] | Approved |
| pytest | PyPI | [OK] | Approved |
| pytest-asyncio | PyPI | [OK] | Approved |
| httpx | PyPI | [OK] | Approved |
| typer | PyPI | [OK] | Approved |
| rich | PyPI | [OK] | Approved |
| python-multipart | PyPI | [OK] (flagged "classic LLM naming pattern but established") | Approved |
| python-dotenv | PyPI | [OK] (flagged "classic LLM naming pattern but established") | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Developer writes resource.yaml
       |
       v
[YAML bytes] --> yaml.safe_load() --> raw dict
                                          |
                                          v
                              ResourceSpec.model_validate(raw)
                              (Pydantic discriminated union on `kind`)
                                          |
                     +--------------------+--------------------+
                     |                                         |
              [LambdaSpec]                             [AccountSpec] ...
              (kind=PECPLambda)                        (kind=PECPAccount)
                     |
                     v
          AdapterBase.provision(resource: ResourceSpec) -> ProvisionResult
          (abstract — Phase 2 fills in mock implementations)
                     |
                     v
              ProvisionResult(status=..., provider_metadata=...,
                              activity_log=[...], error=None)

FastAPI Route: POST /resources
       |
       v
  get_request_context() [Depends()]
       |
       v
  RequestContext(user_id="stub", team_memberships=["platform"],
                 is_pe_admin=False)
       |
       v
  validate team param present -- 400 if missing
       |
       v
  [route handler body — Phase 3 adds dispatch logic]
```

### Recommended Project Structure

```
pecp-poc/
├── pyproject.toml           # All deps, tool config, build metadata
├── example.yaml             # Reference YAML (existing)
├── docs/
│   └── DEMO-SCRIPT.md       # Stakeholder narrative walkthrough (ARCH-04)
├── src/
│   └── pecp/
│       ├── __init__.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── enums.py          # ResourceStatus enum
│       │   ├── resource_spec.py  # Discriminated union + 6 kind models
│       │   └── provision_result.py  # ProvisionResult + ProvisionResult
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── base.py           # AdapterBase ABC
│       ├── api/
│       │   ├── __init__.py
│       │   ├── dependencies.py   # get_request_context() Depends()
│       │   └── routes/
│       │       ├── __init__.py
│       │       └── resources.py  # Route skeletons (GET /resources, POST /resources)
│       └── cli/
│           ├── __init__.py
│           └── main.py           # Typer app stub
└── tests/
    ├── conftest.py               # Shared fixtures (AsyncClient)
    ├── test_models/
    │   ├── __init__.py
    │   ├── test_resource_spec.py # Discriminated union parse tests
    │   └── test_provision_result.py
    ├── test_adapters/
    │   ├── __init__.py
    │   └── test_adapter_base.py  # TypeError on unimplemented ABC
    └── test_api/
        ├── __init__.py
        └── test_routes.py        # 400 on missing team param
```

### Pattern 1: Pydantic v2 Discriminated Union on `kind`

**What:** Each resource kind model has a `Literal` `kind` field. The outer `ResourceSpec` wraps them in a `Union` discriminated by that field. Pydantic selects the correct sub-model based on `kind` value and validates spec fields per-kind.

**When to use:** Whenever the parsed type depends on the value of a field in the incoming data — eliminates a manual `isinstance` dispatch.

**Example:**
```python
# Source: https://pydantic.dev/docs/validation/latest/concepts/unions/
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field

class LambdaSpec(BaseModel):
    kind: Literal["PECPLambda"]
    name: str
    exposure: Literal["public", "private"]
    api_gateway: str = Field(alias="api-gateway")
    source_code: str = Field(alias="source-code")  # accepts "github://..." string

class ContainerSpec(BaseModel):
    kind: Literal["PECPContainer"]
    name: str
    exposure: Literal["public", "private"]
    image: str

class DataServiceSubtype(str, Enum):
    s3 = "s3"
    sqs = "sqs"
    sns = "sns"
    rds = "rds"
    dynamodb = "dynamodb"

class DataServiceSpec(BaseModel):
    kind: Literal["PECPDataService"]
    name: str
    subtype: DataServiceSubtype

class AccountSpec(BaseModel):
    kind: Literal["PECPAccount"]
    # No additional spec fields — account is for the team in metadata

class SalesforceSpec(BaseModel):
    kind: Literal["PECPSalesforce"]
    config: dict[str, Any] = Field(default_factory=dict)

class AemSpec(BaseModel):
    kind: Literal["PECPAem"]
    config: dict[str, Any] = Field(default_factory=dict)

ResourceSpecUnion = Annotated[
    Union[LambdaSpec, ContainerSpec, DataServiceSpec, AccountSpec, SalesforceSpec, AemSpec],
    Field(discriminator="kind")
]

class ResourceSpec(BaseModel):
    api_version: str = Field(alias="apiVersion")
    kind: str  # top-level kind mirrors the spec kind; for routing/display
    metadata: dict[str, Any]
    spec: ResourceSpecUnion

# Parse from yaml.safe_load output:
# data = yaml.safe_load(yaml_text)
# resource = ResourceSpec.model_validate(data)
```

**Key detail:** `source-code` and `api-gateway` use hyphens in the YAML (per `example.yaml`). Pydantic aliases map them to Python-valid field names. Use `model_config = ConfigDict(populate_by_name=True)` to allow both forms.

### Pattern 2: AdapterBase ABC

**What:** Python `ABC` with `@abstractmethod` on the three lifecycle methods. Instantiating a subclass that omits any method raises `TypeError` immediately — before any method is called.

**When to use:** Enforcing a plugin contract where all implementors must provide all three operations.

**Example:**
```python
# Source: https://docs.python.org/3/library/abc.html
from abc import ABC, abstractmethod
from pecp.models.resource_spec import ResourceSpec
from pecp.models.provision_result import ProvisionResult

class AdapterBase(ABC):
    """
    Abstract base for all PECP backing-system adapters.
    Subclasses must implement all three lifecycle methods.
    Adapters return ProvisionResult — they do NOT raise for expected failures.
    """

    @abstractmethod
    async def provision(self, resource: ResourceSpec) -> ProvisionResult:
        """Provision the resource in the backing system."""
        ...

    @abstractmethod
    async def deprovision(self, resource: ResourceSpec) -> ProvisionResult:
        """Remove the resource from the backing system."""
        ...

    @abstractmethod
    async def get_status(self, resource: ResourceSpec) -> ProvisionResult:
        """Return current status. activity_log and provider_metadata may be empty."""
        ...
```

**TypeError enforcement:** Attempting `BrokenAdapter()` where `BrokenAdapter` omits any abstract method raises `TypeError: Can't instantiate abstract class BrokenAdapter without an implementation for abstract method 'provision'` (Python 3.12 wording). This is at instantiation time, not import time. The success criterion ("at import time") is satisfied by a test that performs the instantiation attempt during the test file's module import — which runs at collection time.

### Pattern 3: RequestContext FastAPI Dependency

**What:** A Pydantic model carrying auth context, injected into every route via `Depends()`. The stub returns hardcoded values. JWT replacement only swaps `get_request_context` — route signatures unchanged.

**When to use:** Every route handler that needs auth context. Use `Annotated` type alias to avoid repetition.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/
from typing import Annotated
from pydantic import BaseModel
from fastapi import Depends

class RequestContext(BaseModel):
    user_id: str
    team_memberships: list[str]
    is_pe_admin: bool

async def get_request_context() -> RequestContext:
    # Stub: hardcoded for PoC. Replace with JWT decode to add real auth.
    return RequestContext(
        user_id="stub-user",
        team_memberships=["platform"],
        is_pe_admin=False,
    )

ContextDep = Annotated[RequestContext, Depends(get_request_context)]

# Route handler pattern:
# async def list_resources(team: str | None = None, ctx: ContextDep = Depends()) -> ...:
```

### Pattern 4: Team Scope Enforcement (ARCH-01)

**What:** The `team` query parameter is required on resource endpoints. Return `400 Bad Request` if absent. FastAPI makes a parameter required by omitting a default value.

**Example:**
```python
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/resources")
async def list_resources(
    team: str,                    # Required — no default means FastAPI returns 422 if missing
    ctx: ContextDep,
) -> list[dict]:
    # FastAPI 422 is "Unprocessable Entity" for missing required params.
    # For strict 400 enforcement, validate explicitly:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    ...
```

**Pitfall:** FastAPI returns `422 Unprocessable Entity` by default when a required query parameter is missing. The success criterion says `400 Bad Request`. Use `HTTPException(status_code=400)` with explicit validation rather than relying on FastAPI's automatic 422.

### Anti-Patterns to Avoid

- **`yaml.load()` without Loader:** Executes arbitrary Python — use `yaml.safe_load()` always. CLAUDE.md explicitly forbids `yaml.load` (unsafe).
- **Flat `Union[A, B, C]` without discriminator:** Pydantic tries each model in order — O(n) validation, confusing errors. Always use `Field(discriminator="kind")`.
- **Raising exceptions in adapters:** D-04 locks this: adapters return `status=FAILED, error=...`. Raising from an adapter breaks the Dispatcher's result-reading flow.
- **Route parameters on `RequestContext` directly:** The stub accepts no HTTP parameters. If `get_request_context` signature changes to read headers/tokens, it must remain compatible with all routes — keep it a zero-argument function (reads from FastAPI's `Request` if needed, not from query params).
- **`from pecp import ...` without `pip install -e .`:** In `src/` layout, `pecp` is not on `sys.path` unless installed. Tests will fail with `ModuleNotFoundError`. Always install with `pip install -e ".[dev]"` before running pytest.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML type dispatching | `if data["kind"] == "PECPLambda": ...` | Pydantic discriminated union | Pydantic validates fields per-kind, provides clear error messages, is mypy-typed |
| Interface enforcement | Custom `__init_subclass__` checks | Python ABC + `@abstractmethod` | ABC is stdlib, raises `TypeError` on instantiation, works with mypy |
| Query parameter validation | Manual `if team is None: return 400` | FastAPI required parameter (no default) | FastAPI generates OpenAPI docs for required params; use explicit `HTTPException` only when overriding the status code from 422 to 400 |
| Alias handling for hyphenated YAML keys | String replacement before parse | Pydantic `Field(alias="api-gateway")` | Pydantic alias round-trips correctly through serialization |
| Tool configuration | Separate `.flake8`, `.black.toml`, `.isort.cfg` | `pyproject.toml` `[tool.ruff]` + `[tool.mypy]` | D-07: one file only |

**Key insight:** Phase 1 has no complex algorithms — the pitfalls are all in the wiring. The Pydantic discriminated union is the most fragile piece: the `kind` field must exist on every spec model with a `Literal` value, the alias config must match the YAML keys exactly, and `model_validate` (not `model_construct`) must be used so validation actually runs.

---

## Common Pitfalls

### Pitfall 1: 422 vs 400 for Missing Team Parameter

**What goes wrong:** A missing `team` query param causes FastAPI to return `422 Unprocessable Entity`, not `400 Bad Request`. The success criterion says `400`.

**Why it happens:** FastAPI's default validation error response is 422 per the HTTP spec for request validation failures.

**How to avoid:** Make `team` an optional parameter with `team: str | None = None` and raise `HTTPException(status_code=400, detail="team parameter is required")` explicitly when it is `None`.

**Warning signs:** Tests asserting `assert response.status_code == 400` fail with `422` in response.

### Pitfall 2: src Layout Import Failure in Tests

**What goes wrong:** `pytest tests/` fails with `ModuleNotFoundError: No module named 'pecp'`.

**Why it happens:** In `src/` layout, `src/pecp` is not on `sys.path` unless the package is installed. Running tests from the project root finds the `src/` directory but not `pecp` inside it.

**How to avoid:** Always run `pip install -e ".[dev]"` before `pytest`. Add this to the dev setup instructions. Alternatively, configure `pythonpath = ["src"]` in `[tool.pytest.ini_options]` as a fallback (but the install is the correct long-term fix).

**Warning signs:** `ImportError` or `ModuleNotFoundError` on `from pecp.models import ...` in any test file.

### Pitfall 3: YAML Hyphenated Keys Not Aliased

**What goes wrong:** `yaml.safe_load` produces `{'api-gateway': '/hello', 'source-code': 'github://...'}`. Pydantic rejects these because Python field names cannot contain hyphens.

**Why it happens:** YAML allows hyphens in keys; Python identifiers do not.

**How to avoid:** Use `Field(alias="api-gateway")` on the Pydantic model fields. Enable `model_config = ConfigDict(populate_by_name=True)` so tests can construct models using either the alias or Python name.

**Warning signs:** `ValidationError: api_gateway field required` when parsing the `example.yaml` fixture.

### Pitfall 4: pytest-asyncio 1.x Breaking Changes

**What goes wrong:** Tests using `@pytest.mark.asyncio` and the old `event_loop` fixture pattern fail with `DeprecationWarning` or `TypeError` after upgrading to pytest-asyncio 1.4.0.

**Why it happens:** pytest-asyncio 1.0 removed the `event_loop` fixture entirely. Strict mode (the new default) requires `@pytest.mark.asyncio` on each test or `asyncio_mode = "auto"` globally.

**How to avoid:** Set `asyncio_mode = "auto"` in `[tool.pytest.ini_options]` to avoid decorating every async test. Use `@pytest_asyncio.fixture` for async fixtures, not `@pytest.fixture`.

**Warning signs:** `PytestUnraisableExceptionWarning` or `ScopeMismatch` errors in the test output.

### Pitfall 5: mypy Strict Mode + Missing Pydantic Plugin

**What goes wrong:** `mypy --strict` reports errors on Pydantic model constructors even when the code is correct — e.g., `Unexpected keyword argument "kind" in "ResourceSpec.__init__"`.

**Why it happens:** mypy doesn't understand Pydantic's dynamic `__init__` generation without the `pydantic.mypy` plugin.

**How to avoid:** Add `plugins = ["pydantic.mypy"]` to `[tool.mypy]` and add a `[tool.pydantic-mypy]` section. See pyproject.toml example in Code Examples.

**Warning signs:** mypy errors on model construction that are not real errors.

### Pitfall 6: AdapterBase "Import Time" TypeError Misconception

**What goes wrong:** Developer believes importing a broken adapter module should raise `TypeError`. It does not — `TypeError` is raised at instantiation (`BrokenAdapter()`), not import.

**Why it happens:** ABC raises `TypeError` in `__call__` → `__new__` → `ABCMeta.__call__` when the class is instantiated. The class object itself is created at import time without error.

**How to avoid:** The test for this success criterion should attempt `BrokenAdapter()` in the test body. The test file may also attempt instantiation at module level (which runs at collection time, satisfying the spirit of "import time" enforcement). Document this distinction clearly.

**Warning signs:** Expecting `pytest.raises(TypeError)` at import but the collection succeeds silently, and the test never runs.

---

## Code Examples

### pyproject.toml (complete Phase 1 scaffold)

```toml
# Source: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
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
select = ["E4", "E7", "E9", "F", "I"]  # E = pycodestyle, F = pyflakes, I = isort

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

### ResourceStatus Enum

```python
# src/pecp/models/enums.py
from enum import Enum

class ResourceStatus(str, Enum):
    pending = "pending"
    provisioning = "provisioning"
    ready = "ready"
    failed = "failed"
```

### ProvisionResult Model

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

### Complete Discriminated Union (ResourceSpec)

```python
# src/pecp/models/resource_spec.py
# Source: https://pydantic.dev/docs/validation/latest/concepts/unions/
from typing import Annotated, Any, Literal, Union
from enum import Enum
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
    # No additional spec fields — account request is identified by team in metadata

class SalesforceSpec(BaseModel):
    kind: Literal["PECPSalesforce"]
    config: dict[str, Any] = Field(default_factory=dict)

class AemSpec(BaseModel):
    kind: Literal["PECPAem"]
    config: dict[str, Any] = Field(default_factory=dict)

AnySpec = Annotated[
    Union[LambdaSpec, ContainerSpec, DataServiceSpec, AccountSpec, SalesforceSpec, AemSpec],
    Field(discriminator="kind")
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

### AdapterBase ABC

```python
# src/pecp/adapters/base.py
# Source: https://docs.python.org/3/library/abc.html
from abc import ABC, abstractmethod
from pecp.models.resource_spec import ResourceSpec
from pecp.models.provision_result import ProvisionResult

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

### RequestContext Dependency

```python
# src/pecp/api/dependencies.py
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/
from typing import Annotated
from pydantic import BaseModel
from fastapi import Depends

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

### Route Skeleton with Team Scope Enforcement

```python
# src/pecp/api/routes/resources.py
from fastapi import APIRouter, HTTPException
from pecp.api.dependencies import ContextDep

router = APIRouter(prefix="/resources", tags=["resources"])

@router.get("")
async def list_resources(
    team: str | None = None,
    ctx: ContextDep = Depends(),
) -> list[dict]:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    # Phase 3 fills in: query DB, filter by team, return resource records
    return []

@router.post("")
async def create_resource(
    team: str | None = None,
    ctx: ContextDep = Depends(),
) -> dict:
    if not team:
        raise HTTPException(status_code=400, detail="team parameter is required")
    # Phase 3 fills in: parse body, dispatch to adapter
    return {"status": "accepted"}
```

### Async Test Pattern (pytest-asyncio 1.x)

```python
# tests/conftest.py
# Source: https://fastapi.tiangolo.com/advanced/async-tests/
import pytest
from httpx import ASGITransport, AsyncClient
from pecp.api.main import app  # FastAPI app instance

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

# tests/test_api/test_routes.py
# asyncio_mode = "auto" means no @pytest.mark.asyncio decorator needed
async def test_get_resources_without_team_returns_400(client: AsyncClient) -> None:
    response = await client.get("/resources")
    assert response.status_code == 400

async def test_get_resources_with_team_returns_200(client: AsyncClient) -> None:
    response = await client.get("/resources", params={"team": "platform"})
    assert response.status_code == 200
```

### ABC TypeError Test

```python
# tests/test_adapters/test_adapter_base.py
import pytest
from pecp.adapters.base import AdapterBase

def test_adapter_base_raises_type_error_without_provision() -> None:
    """Instantiating an incomplete adapter raises TypeError."""
    class IncompleteAdapter(AdapterBase):
        async def deprovision(self, resource):  # type: ignore[override]
            ...
        async def get_status(self, resource):  # type: ignore[override]
            ...
        # provision() intentionally omitted

    with pytest.raises(TypeError, match="provision"):
        IncompleteAdapter()

def test_complete_adapter_instantiates_successfully() -> None:
    """A fully-implemented adapter instantiates without error."""
    from pecp.models.resource_spec import ResourceSpec
    from pecp.models.provision_result import ProvisionResult
    from pecp.models.enums import ResourceStatus

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

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Union[A, B]` without discriminator | `Annotated[Union[A, B], Field(discriminator="kind")]` | Pydantic v2 (2023) | O(1) validation per kind; clearer errors |
| `@pytest.mark.asyncio` on every test | `asyncio_mode = "auto"` in pyproject.toml | pytest-asyncio 0.21+ | No per-test decorator needed |
| `TestClient` for async tests | `httpx.AsyncClient` + `ASGITransport` | FastAPI docs update (2024) | True async test execution |
| `event_loop` fixture for scope control | `@pytest_asyncio.fixture(loop_scope="...")` | pytest-asyncio 1.0 (May 2025) | `event_loop` removed; use `loop_scope` |
| `requirements.txt` + `setup.cfg` | `pyproject.toml` only | PEP 621 (2021) | Single source of truth for deps + tooling |
| `mypy.ini` / `setup.cfg [mypy]` | `[tool.mypy]` in pyproject.toml | mypy 0.900+ | Consolidated config |

**Deprecated/outdated:**
- `yaml.load(stream)` without `Loader=`: removed in PyYAML 6.0 — must use `yaml.safe_load()`.
- `pydantic.validator` (v1 decorator): replaced by `@field_validator` in Pydantic v2.
- `from __future__ import annotations` for `list[str]` style hints: not needed in Python 3.12+.
- `pytest-asyncio < 1.0` `event_loop` fixture pattern: removed in 1.0; use `loop_scope` on fixtures.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `source-code` field in `LambdaSpec` should be `str` (not a validated URL type) per CONTEXT.md specifics — "the Pydantic model should accept a string" | Code Examples / ResourceSpec | Low — decision is documented in CONTEXT.md; only affects Phase 2 adapter if URI parsing is needed |
| A2 | `ResourceMetadata` should have `name: str` and optional `team: str` based on `example.yaml` — additional metadata fields (labels, annotations) are not needed in Phase 1 | Code Examples / ResourceSpec | Low — Phase 2 adapters may need additional metadata fields; easily extended |
| A3 | The FastAPI app instance will live at `src/pecp/api/main.py` and be importable as `from pecp.api.main import app` — this location is not locked in CONTEXT.md | Standard Stack / test fixtures | Low — any consistent location works; affects only import paths in tests |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.
(3 low-risk assumptions remain.)

---

## Open Questions

1. **FastAPI app entry point location**
   - What we know: Phase 1 includes route skeletons; the app object must exist for tests to import it.
   - What's unclear: CONTEXT.md doesn't specify whether the FastAPI `app` lives in `src/pecp/api/main.py` or `src/pecp/main.py`.
   - Recommendation: Use `src/pecp/api/main.py` (consistent with the `api/` sub-package). Planner can confirm.

2. **`ContextDep = Depends()` syntax in route params**
   - What we know: The `Annotated` + `Depends` pattern is documented. The `Depends()` call in the route signature is optional when using `Annotated`.
   - What's unclear: Whether the routes should use `ctx: ContextDep` (no `Depends()`) or `ctx: ContextDep = Depends()` for mypy compatibility.
   - Recommendation: Use `ctx: ContextDep` with `Annotated[RequestContext, Depends(get_request_context)]` — the `Depends()` in the `Annotated` is sufficient and is the FastAPI-recommended pattern.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | ✓ | 3.12.5 | — |
| pip | Package install | ✓ | 25.1.1 | — |
| pydantic | Resource models | ✓ | 2.11.7 installed; 2.13.4 latest | — |
| fastapi | Route skeletons | installable | 0.136.3 | — |
| mypy | Type checking | installable | 2.1.0 | — |
| ruff | Linting | ✓ | 0.15.7 installed; 0.15.14 latest | — |
| pytest | Test runner | ✓ | 9.0.2 installed; 9.0.3 latest | — |
| pytest-asyncio | Async tests | installable | 1.4.0 | — |

**Missing dependencies with no fallback:** None — all packages are installable via pip from PyPI.

**Note:** Installed versions on dev machine may be slightly behind latest. Running `pip install -e ".[dev]"` with the pinned versions in `pyproject.toml` will normalize the environment.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 creates this |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ARCH-01 | `GET /resources` without `team` returns 400 | Integration (in-process) | `pytest tests/test_api/test_routes.py -k "without_team" -x` | Wave 0 |
| ARCH-02 | Every route handler receives a `RequestContext` dependency | Unit | `pytest tests/test_api/test_routes.py -k "context" -x` | Wave 0 |
| ARCH-04 | Demo script document exists and is non-empty | Smoke (file existence check) | `pytest tests/test_demo_script.py -x` or manual | Wave 0 |
| ADPT-01 | Incomplete adapter subclass raises `TypeError` on instantiation | Unit | `pytest tests/test_adapters/test_adapter_base.py -x` | Wave 0 |
| ADPT-01 | Complete adapter subclass instantiates without error | Unit | `pytest tests/test_adapters/test_adapter_base.py -k "complete" -x` | Wave 0 |
| D-10 | Valid YAML parses into correct discriminated union type | Unit | `pytest tests/test_models/test_resource_spec.py -x` | Wave 0 |
| D-10 | Invalid kind value raises `ValidationError` | Unit | `pytest tests/test_models/test_resource_spec.py -k "invalid" -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ --tb=short` + `mypy src/` + `ruff check src/ tests/`
- **Phase gate:** All three pass with zero errors before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — shared `AsyncClient` fixture
- [ ] `tests/test_api/__init__.py` + `tests/test_api/test_routes.py` — covers ARCH-01, ARCH-02
- [ ] `tests/test_adapters/__init__.py` + `tests/test_adapters/test_adapter_base.py` — covers ADPT-01
- [ ] `tests/test_models/__init__.py` + `tests/test_models/test_resource_spec.py` — covers D-10 (discriminated union)
- [ ] `tests/test_models/test_provision_result.py` — covers D-01 through D-03
- [ ] `pyproject.toml` with `[tool.pytest.ini_options]` `asyncio_mode = "auto"` and `pythonpath = ["src"]`
- [ ] Framework install: `pip install -e ".[dev]"` — required before first pytest run

---

## Security Domain

Security enforcement is enabled (`security_enforcement: true`, `security_asvs_level: 1`). Phase 1 has no running server and no persistent data, so the threat surface is minimal. The patterns established here (auth stub structure, team scope enforcement) directly affect security posture in later phases.

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Partial — stub only | `RequestContext` stub structured for JWT drop-in; no real auth in PoC |
| V3 Session Management | No | No sessions in PoC; stateless API |
| V4 Access Control | Yes — team scoping | `team` parameter required on all resource endpoints; `400` on missing |
| V5 Input Validation | Yes | Pydantic v2 validates all resource spec fields; `yaml.safe_load` prevents code injection |
| V6 Cryptography | No | No secrets, tokens, or encryption in Phase 1 |

### Known Threat Patterns for Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML code execution | Tampering | `yaml.safe_load()` — explicitly required by CLAUDE.md; never `yaml.load()` |
| Cross-team resource access | Elevation of Privilege | `team` param required; Phase 3 adds team membership check against `RequestContext.team_memberships` |
| Unauthenticated access | Spoofing | Auth stub is intentional for PoC; `RequestContext` structure isolates the change surface |
| Pydantic extra field injection | Tampering | `model_config = ConfigDict(extra="forbid")` on resource spec models prevents undeclared fields from passing validation |

---

## Sources

### Primary (HIGH confidence)

- PyPI registry — version verification for all 13 packages (verified 2026-05-27)
- [Python 3 ABC documentation](https://docs.python.org/3/library/abc.html) — `@abstractmethod`, `ABCMeta`, `TypeError` on instantiation
- [Pydantic v2 Unions documentation](https://pydantic.dev/docs/validation/latest/concepts/unions/) — discriminated union `Field(discriminator=...)` pattern, `Annotated` syntax
- [FastAPI Dependency Injection documentation](https://fastapi.tiangolo.com/tutorial/dependencies/) — `Depends()`, `Annotated` type alias, `RequestContext` pattern
- [FastAPI Async Tests documentation](https://fastapi.tiangolo.com/advanced/async-tests/) — `ASGITransport`, `AsyncClient`, `@pytest.mark.anyio`
- [Python Packaging Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) — `src/` layout, `pyproject.toml` structure
- [Ruff configuration docs](https://docs.astral.sh/ruff/configuration/) — `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`
- [mypy configuration docs](https://mypy.readthedocs.io/en/stable/config_file.html) — `[tool.mypy]`, strict mode, `[[tool.mypy.overrides]]`

### Secondary (MEDIUM confidence)

- [Pydantic mypy plugin docs](https://docs.pydantic.dev/latest/integrations/mypy/) — `pydantic.mypy` plugin, `[tool.pydantic-mypy]` configuration
- [pytest-asyncio 1.0 migration guide](https://thinhdanggroup.github.io/pytest-asyncio-v1-migrate/) — breaking changes, `asyncio_mode` options, `event_loop` fixture removal

### Tertiary (LOW confidence)

- None — all claims verified from primary or secondary sources.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages verified via PyPI registry, slopcheck clean
- Architecture patterns: HIGH — verified against official FastAPI, Pydantic, Python docs
- Pitfalls: HIGH — derived from official docs (422 vs 400 from FastAPI docs, src layout behavior from packaging guide, pytest-asyncio 1.0 from migration guide)
- Tool configuration: HIGH — verified against ruff, mypy official docs

**Research date:** 2026-05-27
**Valid until:** 2026-08-27 (stable ecosystem — Pydantic, FastAPI, pytest-asyncio release rapidly but API surface for these patterns is stable)

# Architecture Research — PECP

**Researched:** 2026-05-27
**Confidence:** HIGH

---

## System Components

The control plane decomposes into six bounded components. No component spans multiple responsibilities.

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI (pecp)                                                      │
│  Serializes YAML → JSON, adds X-Team-ID header, calls REST API  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (JSON body + headers)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  API Layer  (FastAPI)                                            │
│  • Routers: /resources, /teams, /projects, /deployments         │
│  • Validates Pydantic schema (discriminated union on `kind`)     │
│  • Extracts team context via middleware → request.state          │
│  • Returns 202 Accepted + resource ID for async operations       │
└───────────┬──────────────────────┬──────────────────────────────┘
            │ writes               │ dispatches
            ▼                      ▼
┌───────────────────┐   ┌──────────────────────────────────────────┐
│  Resource Store   │   │  Dispatcher                               │
│  (SQLite / SA 2)  │   │  • Resolves adapter by kind+team context  │
│  • resources      │   │  • Calls adapter.provision(spec, ctx)     │
│  • teams          │   │  • Updates resource status in Store       │
│  • projects       │   │  • Runs as BackgroundTask (PoC) or        │
│  • deployments    │   │    ARQ worker (production path)           │
└───────────────────┘   └──────────────────┬───────────────────────┘
                                           │ calls
                                           ▼
                        ┌──────────────────────────────────────────┐
                        │  Adapter Registry                        │
                        │  • Maps kind → AdapterBase subclass      │
                        │  • Loaded at startup via lifespan event  │
                        └──────────────────┬───────────────────────┘
                                           │ implements
                                           ▼
                        ┌──────────────────────────────────────────┐
                        │  Mock Adapters (one per backing system)  │
                        │  AWS · K8s · Salesforce · AEM ·          │
                        │  Datadog · ServiceNow · JFrog            │
                        │  Each logs intended action, simulates    │
                        │  latency, returns synthetic metadata     │
                        └──────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Owns | Does Not Own |
|---|---|---|
| API Layer | HTTP contract, request validation, response shapes | Business logic, storage, adapter calls |
| Resource Store | Persistence, state transitions, queries | Routing logic, provisioning |
| Dispatcher | Routing to adapter, driving state machine, async execution | Storage schema, HTTP concerns |
| Adapter Registry | Mapping kind → adapter class, lifecycle registration | Adapter logic |
| Adapters | Simulating provisioning for one backing system | Routing, persistence, HTTP |
| CLI | UX for YAML submission and status polling | Any server-side logic |

---

## Data Flow

A complete round-trip from `pecp apply` to `status: ready`:

```
1.  User writes resource.yaml
    apiVersion: pecp/v1
    kind: PECPLambda
    metadata:
      name: my-fn
      team: platform-eng
    spec:
      exposure: public

2.  CLI reads YAML → yaml.safe_load() → dict
    Serializes to JSON
    Adds header: X-Team-ID: platform-eng
    POST /api/v1/resources

3.  API Layer receives request
    a. TeamContextMiddleware reads X-Team-ID → request.state.team
    b. get_team dependency loads Team from DB (404 if unknown)
    c. Pydantic discriminated union parses body: kind=PECPLambda
       → PECPLambdaSpec model validated (422 if invalid)
    d. Resource record written to DB: status=PENDING
    e. 202 Accepted returned: {id, status: "pending"}
    f. BackgroundTask(dispatch, resource_id) queued

4.  Dispatcher runs (async, after response sent)
    a. Loads resource from DB
    b. Transitions status: PENDING → PROVISIONING
    c. Resolves adapter: registry.get("PECPLambda") → AWSMockAdapter
    d. Builds AdapterContext(team, account, environment, spec)
    e. Calls adapter.provision(context)
    f. Adapter logs intent, simulates latency
    g. Adapter returns AdapterResult(success=True, metadata={...})
    h. Transitions status: PROVISIONING → READY
       (or → FAILED on exception, stores error_message)
    i. Stores metadata in resource.provider_metadata (JSON column)

5.  CLI polls: GET /api/v1/resources/{id}/status
    Returns: {status: "ready", notes: [], provider_metadata: {...}}
    PE team can POST to /notes at any point — visible on next poll
```

**Key invariant:** Status transitions happen only inside the Dispatcher. The API Layer writes `PENDING` on create and never touches status again.

---

## Adapter Interface Pattern

The adapter contract is defined once as an ABC. Every mock and every future real adapter implements the same interface. The Dispatcher never imports a concrete adapter class — only the registry does.

```python
# adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class AdapterContext:
    team_id: str
    team_slug: str
    environment: str           # dev | staging | prod
    account_id: str | None     # target AWS account or equivalent
    resource_name: str
    resource_kind: str
    spec: dict[str, Any]       # raw validated spec dict

@dataclass
class AdapterResult:
    success: bool
    provider_metadata: dict[str, Any]
    error_message: str | None = None

class AdapterBase(ABC):
    @abstractmethod
    async def provision(self, ctx: AdapterContext) -> AdapterResult: ...

    @abstractmethod
    async def deprovision(self, ctx: AdapterContext) -> AdapterResult: ...

    @abstractmethod
    async def get_status(self, ctx: AdapterContext) -> AdapterResult: ...
```

**Registry — loaded once at FastAPI lifespan startup:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = AdapterRegistry()
    registry.register("PECPLambda",      AWSMockAdapter())
    registry.register("PECPContainer",   AWSMockAdapter())
    registry.register("PECPDataService", AWSMockAdapter())
    registry.register("PECPAccount",     AWSAccountMockAdapter())
    registry.register("PECPSalesforce",  SalesforceMockAdapter())
    registry.register("PECPAem",         AEMMockAdapter())
    app.state.adapter_registry = registry
    yield
```

**Pydantic discriminated union for kind routing:**

```python
ResourceSpec = Annotated[
    Union[PECPLambdaSpec, PECPContainerSpec, PECPDataServiceSpec, ...],
    Field(discriminator="kind")
]
```

Pydantic routes to the correct model automatically using `kind` as the discriminator. Invalid kinds produce a 422 with a clear error before anything touches the database.

**Why this survives the K8s migration:** When real adapters are added, only the concrete class changes. When the control plane moves to a K8s operator, the same `AdapterBase` subclasses become reconciler implementations inside the operator — no interface changes required.

---

## Resource State Machine

Five states, four transitions. The Dispatcher drives all transitions. The Resource Store persists current state.

```
  PENDING
     │
     │  (Dispatcher picks up task)
     ▼
  PROVISIONING
     │              │
     │ success      │ exception / success=False
     ▼              ▼
  READY           FAILED ──── retry ──→ PROVISIONING
     │
     │  (DELETE request)
     ▼
  DELETING
     │              │
     │ success      │ exception
     ▼              ▼
  DELETED         FAILED
```

| State | Who sets it |
|---|---|
| PENDING | API Layer (on create) |
| PROVISIONING | Dispatcher (on dispatch) |
| READY | Dispatcher (on adapter success) |
| FAILED | Dispatcher (on exception or success=False) |
| DELETING | Dispatcher (on DELETE dispatch) |
| DELETED | Dispatcher (on deprovision success) |

**Transition guard — prevents illegal moves:**

```python
ALLOWED_TRANSITIONS = {
    ResourceStatus.PENDING:      {ResourceStatus.PROVISIONING},
    ResourceStatus.PROVISIONING: {ResourceStatus.READY, ResourceStatus.FAILED},
    ResourceStatus.READY:        {ResourceStatus.DELETING},
    ResourceStatus.DELETING:     {ResourceStatus.DELETED, ResourceStatus.FAILED},
    ResourceStatus.FAILED:       {ResourceStatus.PROVISIONING},  # retry allowed
    ResourceStatus.DELETED:      set(),
}
```

**AWS account slow path:** `PECPAccount` resources stay in `PROVISIONING` for minutes or hours. The mock adapter sets a note `"Account creation queued — PE review required"` and simulates this dwell time. PE team appends notes as progress happens. The CLI polls `status` and displays the note log. No special-case logic needed — it is the same state machine with a long dwell time in `PROVISIONING`.

---

## Team / Tenant Isolation

Team context flows through every layer as a first-class value.

**Layer 1: Transport (CLI → API).** The CLI attaches `X-Team-ID: <slug>` to every request. For `pecp apply`, team comes from `metadata.team` in the YAML. For commands with `--team`, it comes from the flag. If both are present and differ, the CLI raises an error before sending the request.

**Layer 2: Middleware.** `TeamContextMiddleware` reads `X-Team-ID` into `request.state.team_id` on every request.

**Layer 3: Route dependency.** `get_team_context` validates that the team exists in the DB and returns a `Team` object. Declared as `TeamDep = Annotated[Team, Depends(get_team_context)]` on every router that touches resources. 400 if header missing, 404 if team unknown.

**Layer 4: Database queries always filtered by team.** No resource query runs without `filter(Resource.team_id == team.id)`. When auth is added later, upgrading `get_team_context` to validate a JWT claim against `X-Team-ID` changes nothing else.

**Layer 5: AdapterContext carries team into adapter.** Adapters receive `team_id`, `team_slug`, `account_id`, and `environment` explicitly. Mock adapters log: `f"[MOCK] Would provision {ctx.resource_kind} '{ctx.resource_name}' in account {ctx.account_id} for team {ctx.team_slug}"`.

**Account routing.** A `Team` record carries `default_aws_account_id`. This is null until a `PECPAccount` resource for that team reaches `READY`. Adapters note null account in `provider_metadata`. No complex cross-account routing is needed for the PoC.

---

## Build Order

```
Phase 1: Foundation
  Resource Store (SQLAlchemy models + DB init + Alembic)
    └─ No dependencies. Everything else depends on this.

Phase 2: Contracts
  Pydantic schemas (ResourceSpec discriminated union, all kinds)
  AdapterBase + AdapterContext + AdapterResult (interface only)
    └─ Schemas feed API validation.
    └─ AdapterBase feeds Dispatcher + all mock adapters.

Phase 3: Core Engine
  Dispatcher (state machine + adapter call + status writes)
  Adapter Registry (startup registration in lifespan)
    └─ Depends on: Store (read/write status), AdapterBase (call interface)

Phase 4: Mock Adapters
  AWSMockAdapter, AWSAccountMockAdapter, K8sMockAdapter,
  SalesforceMockAdapter, AEMMockAdapter, DatadogMockAdapter,
  ServiceNowMockAdapter, JFrogMockAdapter
    └─ Depends on: AdapterBase only. Plugged into Registry.

Phase 5: API Layer
  FastAPI app + routers + middleware + dependencies
    └─ Depends on: Store, Dispatcher, Schemas

Phase 6: CLI
  pecp commands (apply, get, delete, status, team, projects, deployments)
    └─ Depends on: API Layer HTTP contract only

Phase 7: UI Dashboard
  Read-only frontend (team inventory, deployments, account status)
    └─ Depends on: API Layer query endpoints
```

---

## K8s Operator Migration Path

| PoC Component | K8s Operator Equivalent |
|---|---|
| Pydantic ResourceSpec | CRD schema (OpenAPI v3) |
| Resource Store (SQLite) | etcd via kube-apiserver |
| API Layer (FastAPI) | kube-apiserver with CRD endpoints |
| Dispatcher | Operator reconciler loop (Kopf or controller-runtime) |
| AdapterBase subclasses | Same — reconciler calls same interface |
| AdapterRegistry | Same — registered in operator startup |
| Team isolation (DB filter) | K8s namespaces (1:1 with teams) |

The adapter interface is the migration-stable surface. All real adapter implementations written against `AdapterBase` for the PoC will work unchanged inside a K8s operator.

---

## Open Questions

- Salesforce and AEM resource specs are undefined. The `AdapterBase` interface is spec-agnostic (spec dict passes through as-is), so this does not block the adapter pattern. But the Pydantic models for `PECPSalesforce` and `PECPAem` cannot be finalized until those specs are researched.
- Whether SQLite's write-ahead locking creates issues when the Dispatcher (BackgroundTask) and the API Layer write concurrently. For a PoC with low concurrency this is acceptable; production path is Postgres.
- The `retry` path from `FAILED → PROVISIONING` needs a trigger definition — is it automatic (with backoff), PE-initiated via API, or CLI-initiated?

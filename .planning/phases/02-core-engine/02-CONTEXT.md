# Phase 2: Core Engine - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the async engine: 7 mock adapters + a Dispatcher that drives resources through the `PENDING → PROVISIONING → READY/FAILED` lifecycle — all testable without a running HTTP server.

**What's in:** `AwsLambdaMockAdapter`, `AwsContainerMockAdapter`, `AwsDataMockAdapter`, `AwsAccountMockAdapter`, `KubernetesMockAdapter`, `SalesforceMockAdapter`, `AemMockAdapter` — each implementing `AdapterBase`. A `dispatch()` async function that reads a `ResourceRecord`, runs the correct adapter, and writes all status transitions back to SQLite. Alembic migration adding `provider_metadata` and `activity_log` columns. Tests for all adapters and the Dispatcher using in-memory SQLite.

**What's not in:** Running HTTP server, `BackgroundTasks` integration, CLI commands, REST endpoints for triggering dispatch — those are Phase 3. Datadog/ServiceNow/JFrog adapters are listed in REQUIREMENTS.md under ADPT-02 but are Phase 2 deliverables too — they are simple "would provision" stubs in the same file structure.

</domain>

<decisions>
## Implementation Decisions

### Salesforce + AEM Mock Strategy
- **D-01:** `SalesforceMockAdapter` and `AemMockAdapter` use generic team-scoped placeholder log messages. No Salesforce Connected App or AEM site provisioning domain research needed — the goal is proving adapter wiring, not domain fidelity. Specs stay `config: dict[str, Any]`. Example log: `"Would provision Salesforce resource for team toxins-research"`.
- **D-02:** `SalesforceMockAdapter` and `AemMockAdapter` are separate classes — no shared `GenericMockAdapter` base. When real specs arrive, they diverge cleanly without refactoring. Matches the pattern of all other adapters.

### Dispatcher Design
- **D-03:** The Dispatcher writes resource status to SQLite in Phase 2. Signature: `async def dispatch(resource_id: str, session: AsyncSession) -> None`. It reads the `ResourceRecord`, routes to the correct adapter, and writes all status transitions (`PENDING → PROVISIONING → READY/FAILED`) plus `provider_metadata` and `activity_log` back to the record. Phase 3 calls this function from `BackgroundTasks` with no changes to the Dispatcher itself.
- **D-04:** `ResourceRecord` gains two new columns: `provider_metadata` (Text, JSON-serialized dict) and `activity_log` (Text, JSON-serialized list[str]). An Alembic migration is generated for these additions. Schema evolution via Alembic from Phase 2 onward.
- **D-05:** Dispatcher lives at `src/pecp/dispatcher.py` — a top-level module, not inside `api/`. This keeps it callable from tests, BackgroundTasks, and future CLI commands without importing the API layer.
- **D-06:** Adapter routing via a dict registry defined at the top of `dispatcher.py`: `ADAPTER_REGISTRY: dict[str, AdapterBase] = {"PECPLambda": AwsLambdaMockAdapter(), "PECPContainer": AwsContainerMockAdapter(), ...}`. The Dispatcher does `adapter = ADAPTER_REGISTRY[resource.kind]`. Missing kinds raise a clear `KeyError`-derived error.

### Claude's Discretion
- **PECPAccount slow-path:** The `AwsAccountMockAdapter.provision()` uses `await asyncio.sleep(3)` internally to simulate slow account creation. Tests mock this sleep. The Dispatcher does not poll `get_status()` — the adapter handles the dwell inline and transitions to `READY` when done. This matches the Phase 2 goal of standalone testing without a polling loop.
- **Activity log format:** Keep `activity_log: list[str]` with a consistent prefix format — `"Would call: aws lambda create-function --function-name my-fn ..."`. Structured dicts would add deserialization complexity in Phase 5; the prefix convention is parseable without committing to a structured schema now.
- **Mock adapter file layout:** Each backing system gets its own file under `src/pecp/adapters/mock/` (e.g., `aws_lambda.py`, `aws_container.py`, `aws_data.py`, `aws_account.py`, `kubernetes.py`, `salesforce.py`, `aem.py`, `datadog.py`, `servicenow.py`, `jfrog.py`). The `__init__.py` re-exports all adapter classes.
- **Test strategy:** `asyncio.sleep` is patched via `unittest.mock.patch("asyncio.sleep")` for all tests — no real latency in the test suite. One integration-style test per adapter calls `provision()` and asserts `ProvisionResult.status == READY` and `activity_log` is non-empty.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contracts (Phase 1 outputs — the stable interfaces Phase 2 builds against)
- `src/pecp/adapters/base.py` — `AdapterBase` ABC. All mock adapters MUST subclass this. Rules: always return `ProvisionResult`, never raise for expected failures.
- `src/pecp/models/provision_result.py` — `ProvisionResult` model. Fields: `status`, `provider_metadata`, `activity_log`, `error`.
- `src/pecp/models/resource_spec.py` — `ResourceSpec` discriminated union. All 6 kinds already defined. Adapters receive a `ResourceSpec` and pattern-match on `spec.kind` for kind-specific logic.
- `src/pecp/models/enums.py` — `ResourceStatus` enum. Single source of truth for `pending/provisioning/ready/failed`.
- `src/pecp/persistence/models.py` — `ResourceRecord` ORM model. Phase 2 adds `provider_metadata` and `activity_log` columns via Alembic migration.
- `src/pecp/persistence/database.py` — `AsyncSession` setup. Dispatcher and tests use the same session factory.

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — Phase 2 delivers ADPT-02, ADPT-03, KINDS-01 through KINDS-06. Read the full requirement text for each before planning.
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 items). Treat as the acceptance test checklist.
- `.planning/PROJECT.md` — Constraints (all backends mocked, Python only, no auth). Out-of-scope list.

### Phase 1 Decisions (carrying forward)
- `.planning/phases/01-foundation-contracts/01-CONTEXT.md` — D-04 (adapters return, never raise), D-11 (SalesforceSpec and AemSpec use `config: dict[str, Any]`), D-12 (single `ResourceStatus` enum).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AdapterBase` at `src/pecp/adapters/base.py` — subclass this for every mock adapter. Abstract methods enforce the interface at class definition time.
- `ProvisionResult` at `src/pecp/models/provision_result.py` — return type for all three adapter methods.
- `ResourceSpec` at `src/pecp/models/resource_spec.py` — the discriminated union dispatchers and adapters receive. Use `isinstance(spec.spec, LambdaSpec)` for kind-specific branches within an adapter.
- `ResourceStatus` at `src/pecp/models/enums.py` — import directly; do not define local status strings.
- `AsyncSession` from `src/pecp/persistence/database.py` — use the same session factory for tests (in-memory SQLite) and production.

### Established Patterns
- Async-first: all methods are `async def`. `await asyncio.sleep(...)` for simulated latency.
- Return, don't raise: set `status=FAILED` and `error="..."` on `ProvisionResult` for failures.
- `src/` layout: new files go under `src/pecp/`. Tests go under `tests/` mirroring the source layout.

### Integration Points
- `ResourceRecord.status` is the shared state between Dispatcher and API. Only the Dispatcher writes this column after Phase 2 — the API route handler sets initial `status="pending"` on creation only.
- Phase 3 will call `dispatch(resource_id, session)` from a `BackgroundTasks` callback. Dispatcher signature must remain stable.

</code_context>

<specifics>
## Specific Ideas

- `ADAPTER_REGISTRY` dict in `dispatcher.py` maps kind strings to adapter instances. This is the switching mechanism — real adapters replace mock instances here without changing any other code.
- `AwsAccountMockAdapter.provision()` does `await asyncio.sleep(3)` before transitioning to READY. Success criteria require ≥3 seconds dwell in PROVISIONING.
- Activity log strings use prefix `"Would call: ..."` for all adapter log lines, e.g. `"Would call: aws lambda create-function --function-name my-fn --runtime python3.12"`.
- Alembic migration adds two nullable Text columns to `resource_records`: `provider_metadata` and `activity_log`. Both default to empty JSON (`"{}"` / `"[]"`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Core Engine*
*Context gathered: 2026-05-28*

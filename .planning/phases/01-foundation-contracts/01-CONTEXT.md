# Phase 1: Foundation + Contracts - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the contracts — adapter interface, Pydantic resource models, auth stub, and demo script — so Phase 2 can build 7 mock adapters against stable types without design ambiguity. No provisioning logic. No running server. Just types, interfaces, and a written stakeholder narrative.

**What's in:** AdapterBase ABC, ProvisionResult model, all 6 ResourceSpec kinds (Pydantic discriminated union), RequestContext auth stub, FastAPI route skeletons enforcing team scope, demo script, project scaffold (src layout, pyproject.toml, ruff + mypy configs).

**What's not in:** Any mock adapter implementations, any Dispatcher logic, SQLite/SQLAlchemy setup, CLI commands, running HTTP server — all of that starts in Phase 2 or later.

</domain>

<decisions>
## Implementation Decisions

### Adapter Result Contract
- **D-01:** `provision()`, `deprovision()`, and `get_status()` all return a `ProvisionResult` Pydantic model — one return type for the entire adapter interface.
- **D-02:** `ProvisionResult` fields: `status: ResourceStatus`, `provider_metadata: dict[str, Any]`, `activity_log: list[str]`, `error: str | None`. The `error` field carries failure reason without needing exceptions.
- **D-03:** `get_status()` reuses `ProvisionResult` — `activity_log` and `provider_metadata` will be empty/None on status-only calls. No separate StatusResult type.
- **D-04:** Adapters always return a `ProvisionResult` — failed operations return `status=FAILED` with `error` populated. Adapters do NOT raise exceptions for expected failure modes. The Dispatcher reads the result, not a try/except.

### Project Structure
- **D-05:** `src/` layout — all source code lives under `src/pecp/`. Prevents import ambiguity when running tests from the project root.
- **D-06:** Four sub-packages: `src/pecp/api/` (FastAPI routes + dependencies), `src/pecp/adapters/` (AdapterBase ABC), `src/pecp/cli/` (Typer commands), `src/pecp/models/` (Pydantic resource specs, ProvisionResult, enums).
- **D-07:** `pyproject.toml` only — no `requirements.txt`. All dependencies, tool config (ruff, mypy, pytest), and build metadata in one file.
- **D-08:** Tests in a top-level `tests/` directory mirroring `src/pecp/` — `tests/test_api/`, `tests/test_adapters/`, `tests/test_models/`.

### Resource Model Scope
- **D-09:** All 6 resource kinds fully defined in Phase 1 with proper spec fields — PECPLambda, PECPContainer, PECPDataService, PECPAccount, PECPSalesforce, PECPAem. Phase 2 adapter authors have complete models to build against.
- **D-10:** Pydantic v2 discriminated union on `kind` — `ResourceSpec` has a `spec` field typed as a union of `LambdaSpec | ContainerSpec | DataServiceSpec | AccountSpec | SalesforceSpec | AemSpec`, discriminated by the `kind` field. Pydantic validates spec fields per-kind at parse time.
- **D-11:** `PECPSalesforce` and `PECPAem` use minimal stub specs: `SalesforceSpec(config: dict[str, Any])` and `AemSpec(config: dict[str, Any])`. Catches-all without blocking Phase 2. Phase 2 researcher fills real fields once specs are confirmed.
- **D-12:** One shared `ResourceStatus` enum in `src/pecp/models/enums.py` — `pending`, `provisioning`, `ready`, `failed`. Imported by adapters, Dispatcher, and API. Single source of truth.

### Demo Script
- **D-13:** Mixed audience — engineers and stakeholders both present. Script leads with narrative, commands are visible but the story drives.
- **D-14:** Format: narrative walkthrough with inline commands — flowing prose with actual `pecp` commands embedded. Readable as a story, runnable as a script.
- **D-15:** Write the full story now with `[expected output]` placeholders where terminal output doesn't exist yet. Phase 5 replaces placeholders with real output from the running system.
- **D-16:** Core demo scenario: **new team onboards end-to-end** — team creation, submit a Lambda + AWS account request, watch status update with PE notes appearing mid-provisioning, account reaches `ready`, open the dashboard to see full team inventory. Covers the complete lifecycle in one session.

### Claude's Discretion
- Exception handling: adapters return FAILED results, not exceptions — chosen to align with D-04 and D-02 (error field on ProvisionResult makes exceptions redundant).
- AdapterBase enforcement: ABC abstract methods should raise `TypeError` at instantiation if not implemented. The success criteria say "at import time" — this is not achievable with ABC alone; a module-level instantiation check test (or Protocol + runtime_checkable) can satisfy the spirit. Claude decides the exact enforcement mechanism.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Scope
- `.planning/PROJECT.md` — Core value, constraints, key decisions table, out-of-scope list. Read before making any structural decisions.
- `.planning/REQUIREMENTS.md` — All 33 v1 requirements with IDs and traceability. Phase 1 delivers ARCH-01, ARCH-02, ARCH-04, ADPT-01.
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 items). Treat as the acceptance test checklist.

### Resource Spec Format
- `example.yaml` — The one existing file. Shows the expected YAML format: `apiVersion: pecp/v1`, `kind: PECPLambda`, `metadata.name`, `spec.exposure`, `spec.api-gateway`, `spec.source-code` (URI scheme: `github://myorg/repo`). Pydantic models must parse this exactly.

### No external specs
No ADRs, design docs, or external specs exist yet — requirements are fully captured in decisions above and in `.planning/REQUIREMENTS.md`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — project is a blank slate. `src/pecp/` does not exist yet.

### Established Patterns
- YAML spec format is fixed: `apiVersion: pecp/v1`, `kind: PECP<Type>` — see `example.yaml`. The Pydantic model must parse this exact structure.
- Python is the org standard — no alternative language consideration.

### Integration Points
- Phase 2 builds mock adapters against `AdapterBase` and `ProvisionResult` — these are the primary Phase 1 outputs consumed by Phase 2.
- Phase 3 builds the FastAPI server against `ResourceSpec` models and `RequestContext` stub — those are the secondary outputs.
- The `RequestContext` stub must be a FastAPI `Depends()` injection — route signatures `async def handler(ctx: RequestContext = Depends(get_request_context))` — structured so a real JWT implementation replaces `get_request_context` with no signature changes.

</code_context>

<specifics>
## Specific Ideas

- `source-code` field in `PECPLambda` uses a URI scheme: `github://myorg/repo` — the Pydantic model should accept a string (not a URL type) since this is a proprietary URI scheme.
- `PECPDataService` needs a `subtype` field (s3, sqs, sns, rds, dynamodb) — this is a discriminator within the DataService kind. Use a `DataServiceSubtype` enum.
- `PECPAccount` is async — the spec model should accept `team` in metadata; no additional spec fields required for requesting an account (the account is for the team, not parameterized further).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Foundation + Contracts*
*Context gathered: 2026-05-27*

# Phase 2: Core Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 2-Core Engine
**Areas discussed:** Salesforce + AEM mock depth, Dispatcher + DB scope

---

## Salesforce + AEM Mock Depth

### Q1: Placeholder vs real concept research

| Option | Description | Selected |
|--------|-------------|----------|
| Generic placeholders now | Adapters log generic team-scoped messages; no domain research needed | ✓ |
| Research minimal real concepts | Phase 2 researcher defines 2-3 real SF/AEM fields and realistic log lines | |
| You decide | Claude picks the approach | |

**User's choice:** Generic placeholders now
**Notes:** The point is proving the adapter wiring, not Salesforce or AEM domain knowledge.

---

### Q2: Shared base vs separate classes

| Option | Description | Selected |
|--------|-------------|----------|
| Each gets its own class | SalesforceMockAdapter and AemMockAdapter are separate classes | ✓ |
| Shared GenericMockAdapter base | One base handles generic behavior; SF and AEM subclass it | |

**User's choice:** Each gets its own class (Recommended)
**Notes:** Matches the pattern of all other adapters; diverges cleanly when real specs arrive.

---

## Dispatcher + DB Scope

### Q1: Writes to SQLite vs stateless

| Option | Description | Selected |
|--------|-------------|----------|
| Writes to SQLite in Phase 2 | Dispatcher takes resource_id + session, writes all status transitions | ✓ |
| Stateless in Phase 2, DB writes deferred | Dispatcher returns ProvisionResult; Phase 3 does the DB write | |

**User's choice:** Writes to SQLite in Phase 2 (Recommended)
**Notes:** State machine proven end-to-end from day one; Phase 3 just calls dispatch() from BackgroundTasks.

---

### Q2: Schema evolution strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Add columns + Alembic migration | Add provider_metadata and activity_log columns; generate migration | ✓ |
| Add columns, recreate table | Drop-and-recreate in dev; no Alembic | |
| Separate activity log table | ActivityLogEntry table with FK to ResourceRecord | |

**User's choice:** Add columns + Alembic migration (Recommended)
**Notes:** Sets up the proper migration workflow for future schema changes.

---

### Q3: Dispatcher location and form

| Option | Description | Selected |
|--------|-------------|----------|
| src/pecp/dispatcher.py — async function | `async def dispatch(resource_id, session)`, top-level module | ✓ |
| src/pecp/dispatcher.py — Dispatcher class | Class with run() method; DI of adapter registry | |
| src/pecp/engine/ subpackage | Subpackage with dispatcher.py, registry.py, etc. | |

**User's choice:** src/pecp/dispatcher.py — async function (Recommended)
**Notes:** Callable directly from tests, BackgroundTasks, and future CLI without importing the API layer.

---

### Q4: Adapter routing mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Dict registry in dispatcher.py | `ADAPTER_REGISTRY: dict[str, AdapterBase]` — simple, explicit | ✓ |
| Adapter self-registers via class attribute | Each adapter declares `handles = "PECPLambda"`; registry built by scanning subclasses | |
| You decide | Claude picks the simplest approach | |

**User's choice:** Dict registry in dispatcher.py (Recommended)
**Notes:** Simple and explicit; real adapters swap in by replacing mock instances in the dict.

---

## Claude's Discretion

- **PECPAccount slow-path:** `await asyncio.sleep(3)` inside provision() — adapter handles the dwell inline. Tests mock sleep.
- **Activity log format:** `list[str]` with "Would call: ..." prefix convention. Structured dicts deferred to Phase 5.
- **Mock adapter file layout:** `src/pecp/adapters/mock/` with one file per backing system.
- **Test strategy:** `asyncio.sleep` patched for all tests; one integration-style test per adapter.

## Deferred Ideas

None — discussion stayed within phase scope.

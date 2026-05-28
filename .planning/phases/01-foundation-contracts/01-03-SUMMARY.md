---
phase: 01-foundation-contracts
plan: "03"
subsystem: api
tags:
  - python
  - fastapi
  - sqlalchemy
  - typer
  - walking-skeleton
  - end-to-end
  - sqlite

dependency_graph:
  requires:
    - phase: 01-foundation-contracts
      plan: "01"
      provides:
        - pecp.models.resource_spec.ResourceSpec
        - pecp.api.dependencies.ContextDep
        - pecp.adapters.base.AdapterBase
  provides:
    - pecp.persistence.database (engine, AsyncSessionLocal, init_schema, get_session, SessionDep)
    - pecp.persistence.models.ResourceRecord
    - pecp.api.main.app (FastAPI app with lifespan)
    - pecp.api.routes.resources (GET /resources, POST /resources — ARCH-01)
    - pecp.cli.main.app (Typer pecp apply + pecp version)
    - README.md (dev run command, quickstart)
    - .planning/phases/01-foundation-contracts/SKELETON.md (all architectural decisions)
  affects:
    - Phase 2 (Dispatcher + mock adapters build on this live API and persistence layer)
    - Phase 3 (adds idempotency, pecp status/delete, team membership enforcement)
    - Phase 5 (UI dashboard reads GET /resources)

tech-stack:
  added:
    - sqlalchemy>=2.0 (SQLAlchemy 2.x async, Mapped[] typed ORM)
    - aiosqlite>=0.20 (async SQLite DBAPI for SQLAlchemy)
  patterns:
    - FastAPI lifespan event for schema initialization (init_schema on startup)
    - SQLAlchemy 2.x Mapped[] typed columns with async_sessionmaker
    - SessionDep = Annotated[AsyncSession, Depends(get_session)] FastAPI injection pattern
    - ARCH-01: explicit HTTPException(400) on missing team param (not implicit 422)
    - ARCH-02: ctx:ContextDep present on every route handler
    - yaml.safe_load() exclusively — no yaml.load() anywhere (T-01-01)
    - Typer CLI wrapping httpx.post() — sync httpx for CLI simplicity
    - In-memory SQLite via PECP_DATABASE_URL env var for test isolation

key-files:
  created:
    - src/pecp/persistence/__init__.py
    - src/pecp/persistence/database.py
    - src/pecp/persistence/models.py
    - src/pecp/api/main.py
    - src/pecp/api/routes/__init__.py
    - src/pecp/api/routes/resources.py
    - src/pecp/cli/__init__.py
    - src/pecp/cli/main.py
    - tests/test_persistence/__init__.py
    - tests/test_persistence/test_database.py
    - tests/test_api/test_walking_skeleton.py
    - tests/test_api/test_cli.py
    - README.md
    - .planning/phases/01-foundation-contracts/SKELETON.md
  modified:
    - pyproject.toml (added sqlalchemy>=2.0 and aiosqlite>=0.20 to dependencies)
    - tests/test_api/test_routes.py (un-skipped 3 Plan 01 placeholder tests)

key-decisions:
  - "SQLAlchemy 2.x Mapped[] typed columns used throughout — SQLModel explicitly avoided per CLAUDE.md rough-edges warning"
  - "spec_json TEXT column stores full validated ResourceSpec as model_dump_json() — avoids 6-table schema for PoC"
  - "Test isolation via PECP_DATABASE_URL=sqlite+aiosqlite:///:memory: set before module import — avoids pecp.db pollution in test runs"
  - "CLI uses synchronous httpx.post() — async not needed for a one-shot CLI command, keeps implementation simple"
  - "ARCH-01 enforced with explicit HTTPException(status_code=400) — not relying on implicit Pydantic 422 (Pitfall 1 from RESEARCH.md)"
  - "Team name toxins-research used in all tests and README (revised from initial payments per user feedback before plan approval)"

patterns-established:
  - "ARCH-01 pattern: if not team: raise HTTPException(status_code=400, detail='team parameter is required') on every route"
  - "ARCH-02 pattern: ctx: ContextDep always present in every route handler signature"
  - "Persistence injection: session: SessionDep = ... in route signatures (not global state)"
  - "TDD RED/GREEN per task: test commit then implementation commit"

requirements-completed:
  - ARCH-01

duration: "~77min"
completed: "2026-05-28"
---

# Phase 1 Plan 03: Walking Skeleton Summary

**SQLite-backed PECP control plane — `pecp apply -f example.yaml --team toxins-research` persists via SQLAlchemy 2.x async, serves via FastAPI GET/POST /resources with ARCH-01 team-scope enforcement, and prints Rich-formatted confirmation via Typer CLI; 25 tests passing, 0 skipped.**

## Performance

- **Duration:** ~77 min
- **Started:** 2026-05-27T23:11:43-04:00
- **Completed:** 2026-05-28T00:29:14-04:00
- **Tasks:** 5 (Task 1: human package verify, Tasks 2-4: auto TDD, Task 5: human live demo)
- **Files modified:** 14 created, 2 modified

## Accomplishments

- SQLAlchemy 2.x async persistence layer: `ResourceRecord` ORM model with `Mapped[]` typed columns, `AsyncSession` + `async_sessionmaker`, `init_schema()` idempotent schema creation, `get_session` FastAPI dependency
- FastAPI app with lifespan (`init_schema` on startup), `GET /resources?team=<team>` and `POST /resources?team=<team>` with ARCH-01 enforcement (400 on missing team), ARCH-02 (ctx: ContextDep on all handlers), yaml.safe_load exclusively (T-01-01)
- Typer `pecp apply` CLI posting YAML bytes to API via httpx, honoring `--api-url` flag and `PECP_API_URL` env var, Rich-formatted success output
- All 3 Plan 01 SKIPPED placeholder tests un-skipped and passing for real
- End-to-end walking skeleton test proves POST→persist→GET round trip via in-memory SQLite
- Live demo verified by human: uvicorn boots, /docs renders, ARCH-01 400 on curl /resources, `pecp apply` returns 202 with id, GET lists the resource
- README.md with dev run command and quickstart; SKELETON.md capturing all architectural decisions for Phase 2

## Task Commits

Each task was committed atomically with TDD RED/GREEN pairs:

1. **Task 2: SQLAlchemy persistence layer (RED)** — `b3edd81` (test)
2. **Task 2: SQLAlchemy persistence layer (GREEN)** — `eb5fb9c` (feat)
3. **Task 3: FastAPI routes + walking skeleton (RED)** — `5d445c6` (test)
4. **Task 3: FastAPI routes + walking skeleton (GREEN)** — `c378928` (feat)
5. **Task 4: Typer CLI + README + SKELETON.md (RED)** — `7f0d335` (test)
6. **Task 4: Typer CLI + README + SKELETON.md (GREEN)** — `5ee4925` (feat)
7. **Post-Task 5: Rename payments→toxins-research** — `b8c816d` (refactor)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/pecp/persistence/database.py` | Async engine, AsyncSessionLocal, init_schema(), get_session(), SessionDep |
| `src/pecp/persistence/models.py` | ResourceRecord ORM model with Mapped[] typed columns, created_at UTC |
| `src/pecp/api/main.py` | FastAPI app instance, lifespan (init_schema on startup), /resources router |
| `src/pecp/api/routes/resources.py` | GET /resources (team-scoped list) + POST /resources (YAML parse, persist, 202) |
| `src/pecp/cli/main.py` | Typer app — `pecp apply` + `pecp version`; httpx.post, PECP_API_URL env var |
| `tests/test_persistence/test_database.py` | Schema creation test + ResourceRecord round-trip test |
| `tests/test_api/test_walking_skeleton.py` | End-to-end POST→GET round trip via isolated in-memory SQLite |
| `tests/test_api/test_cli.py` | CLI tests via CliRunner + unittest.mock patching httpx.post |
| `README.md` | Dev setup, run server, apply resource, run tests, project structure |
| `.planning/phases/01-foundation-contracts/SKELETON.md` | Architectural decisions table + stack checklist + out-of-scope + Phase 2-5 goals |
| `pyproject.toml` | Added sqlalchemy>=2.0 and aiosqlite>=0.20 to [project].dependencies |
| `tests/test_api/test_routes.py` | Removed 3 pytest.skip() calls — ARCH-01 tests now active and passing |

## Decisions Made

- **SQLAlchemy 2.x Mapped[] exclusively**: SQLModel has documented Pydantic v2 rough edges (CLAUDE.md explicit warning). Typed `Mapped[str]` columns give mypy strict compliance without SQLModel.
- **spec_json TEXT column**: Stores `ResourceSpec.model_dump_json()` rather than normalized columns per kind. Avoids a 6-table schema for PoC; Phase 3 can add columns if querying on spec fields becomes necessary.
- **Test isolation via env var**: `PECP_DATABASE_URL=sqlite+aiosqlite:///:memory:` set before module import in walking-skeleton fixture — simpler than tmp_path file, avoids engine reload complications.
- **Synchronous httpx.post in CLI**: One-shot CLI commands don't benefit from async; sync httpx keeps the CLI implementation straightforward.
- **Explicit 400, not implicit 422**: RESEARCH.md Pitfall 1 explicitly warned that missing query params return 422 by default. ARCH-01 requires 400. Used `if not team: raise HTTPException(status_code=400)` on both routes.
- **Team name toxins-research**: All tests and README use `toxins-research` throughout (revised from initial `payments` per user feedback — same decision recorded in Plan 02 SUMMARY).

## Deviations from Plan

### Auto-fixed Issues

None — the user-requested rename of `payments` → `toxins-research` was applied before the previous checkpoint was signed off (committed as `b8c816d`). Tests and README were already using `toxins-research` by the time this SUMMARY was written. No unexpected deviations occurred during task execution.

**Total deviations:** 0 auto-fixed
**Impact on plan:** Plan executed exactly as specified. All TDD RED/GREEN commits follow plan order. ARCH-01, ARCH-02, T-01-01, T-01-02, T-01-08 all applied as specified.

## Issues Encountered

None during task execution. The user's post-approval request to rename `payments` → `toxins-research` in tests and README was handled immediately; inspection confirmed all four target files were already clean (the rename was done in commit `b8c816d` before this SUMMARY was written).

## Manual Verification Results (Task 5)

The user ran the full live demo and typed "approved":

| Step | Command | Expected | Result |
|------|---------|----------|--------|
| 1 | `uvicorn pecp.api.main:app --reload --port 8000` | Server starts, schema init logged | PASSED |
| 2 | `http://localhost:8000/docs` | Swagger UI with GET/POST /resources | PASSED |
| 3 | `curl -i "http://localhost:8000/resources"` | 400 Bad Request, "team parameter is required" | PASSED |
| 4 | `pecp apply -f example.yaml --team toxins-research` | Green "Applied PECPLambda hello-world → id=... status=pending" | PASSED |
| 5 | `curl -s "http://localhost:8000/resources?team=toxins-research"` | JSON array with hello-world resource | PASSED |
| 6 | Second apply with `--api-url http://localhost:8000` | Second resource appears (idempotency deferred Phase 3) | PASSED |

## What Phase 2 Inherits

- **Live API**: FastAPI app boots with `uvicorn pecp.api.main:app`, /resources endpoint live
- **Persistence**: SQLAlchemy 2.x async session, ResourceRecord ORM, SQLite file at `pecp.db`
- **AdapterBase ABC**: From Plan 01 — 3 abstract async methods `provision`, `deprovision`, `get_status` — ready for mock adapter implementations
- **ResourceSpec discriminated union**: All 6 kinds (PECPLambda, PECPContainer, PECPDataService, PECPAccount, PECPSalesforce, PECPAem) validated at POST time
- **ContextDep stub**: RequestContext hardcoded, signature stable for JWT drop-in (Phase post-PoC)
- **CLI entrypoint**: `pecp apply` live — Phase 3 adds `pecp status`, `pecp delete`, `pecp get`
- **SKELETON.md**: All architectural decisions captured for Phase 2 adapter work

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `get_request_context()` hardcoded stub | `src/pecp/api/dependencies.py` | ARCH-02: intentional PoC stub; JWT replacement swaps function body only (from Plan 01) |
| `SalesforceSpec.config: dict` / `AemSpec.config: dict` | `src/pecp/models/resource_spec.py` | D-11: real specs undefined pending PE team input (from Plan 01) |
| No Dispatcher wired | `src/pecp/api/routes/resources.py` | Provisioning is Phase 2 scope; POST creates record with status=pending, no adapter called |

## Threat Surface Scan

All threats from the plan's `<threat_model>` were mitigated as specified:

| Threat | Status | Evidence |
|--------|--------|----------|
| T-01-01: yaml.safe_load only | Mitigated | `grep -nE "yaml\.load\(" src/ tests/` returns 0 matches outside `safe_load` |
| T-01-02: extra=forbid on LambdaSpec/ContainerSpec | Mitigated | Carried from Plan 01, ValidationError wrapped in HTTPException(422) |
| T-01-05: team-scope param only (no membership check) | Accepted | Documented in SKELETON.md "Out of Scope"; Phase 3 closes |
| T-01-08: SQLAlchemy ORM parameterization | Mitigated | All queries use `select(ResourceRecord).where(ResourceRecord.team == team)` — no raw SQL |

No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond the plan's threat model.

## User Setup Required

None — SQLite file is auto-created by `init_schema()` on server startup. No external services, no environment variables required for local dev.

## Next Phase Readiness

Phase 2 (Core Engine) can begin immediately:
- API live: `uvicorn pecp.api.main:app` works
- AdapterBase ABC locked: Phase 2 implements 7 mock adapters
- ResourceRecord persisted: Phase 2 adds status updates as provisioning progresses
- No blockers: PECPSalesforce/PECPAem stubs remain pending PE team input (tracked from Phase 1)

---
*Phase: 01-foundation-contracts*
*Completed: 2026-05-28*

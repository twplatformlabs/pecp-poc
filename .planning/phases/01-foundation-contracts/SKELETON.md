# Walking Skeleton — Phase 1

## Capability Proven End-to-End

A team member runs `pecp apply -f resource.yaml --team toxins-research` and the platform persists the YAML and returns a resource id and status=pending — listable via `GET /resources?team=toxins-research`.

This is the thinnest vertical slice that proves the entire PECP stack: CLI → HTTP → FastAPI → SQLAlchemy async → SQLite → JSON response. No provisioning logic runs yet — Phase 2 wires the Dispatcher and mock adapters.

---

## Architectural Decisions

| Decision | Choice | Alternative Considered | Reason |
|----------|--------|------------------------|--------|
| API Framework | FastAPI + Uvicorn | Flask, Django | Async-first, Pydantic native, auto OpenAPI. CLAUDE.md HIGH confidence. |
| Data Layer | SQLite + SQLAlchemy 2.x async | PostgreSQL, MongoDB | Zero-infra for PoC. `aiosqlite` driver. SQLAlchemy 2.x typed `Mapped[]` columns. |
| Database migrations | Alembic (planned Phase 3) | manual DDL | `init_schema()` via `Base.metadata.create_all` for Phase 1; Alembic added when schema evolves. |
| Auth | RequestContext stub | JWT, OAuth2 | PoC explicitly defers auth. Function body swap only — route signatures unchanged. ARCH-02. |
| CLI Framework | Typer + Rich | Click, argparse | Typer wraps Click with type annotations; Rich for formatted output. CLAUDE.md HIGH. |
| HTTP Client (CLI→API) | httpx.post() | requests, aiohttp | httpx is already a dependency (FastAPI test client). Sync for CLI simplicity. |
| ORM style | SQLAlchemy 2.x `Mapped[...]` | SQLModel, legacy Column() | SQLModel has documented Pydantic v2 rough edges. `Mapped[]` is fully typed. CLAUDE.md. |
| Resource spec storage | JSON in `spec_json` TEXT column | normalized columns per kind | Pydantic `model_dump_json()` serializes the full validated spec. Avoids 6-table schema for PoC. |
| Directory layout | `src/` layout, 5 sub-packages | flat layout | D-05, D-06. Sub-packages: models/, adapters/, api/, cli/, persistence/. |
| Test isolation | In-memory SQLite via `PECP_DATABASE_URL` | tmp_path SQLite file | Set env var before module import so engine URL is correct without reload. |
| YAML parsing | `yaml.safe_load()` exclusively | `yaml.load()` | CLAUDE.md explicit prohibition on `yaml.load` (code execution risk). T-01-01. |
| Extra-field injection | `extra="forbid"` on LambdaSpec/ContainerSpec | permissive | T-01-02: Pydantic rejects undeclared fields. Salesforce/AEM stubs use `config: dict` by design (D-11). |

---

## Stack Touched in Phase 1

- [x] FastAPI + Uvicorn — HTTP server with OpenAPI docs at /docs
- [x] SQLAlchemy 2.x async + aiosqlite — ResourceRecord ORM model, AsyncSession, init_schema()
- [x] Pydantic v2 — ResourceSpec discriminated union (6 kinds), ProvisionResult, RequestContext
- [x] AdapterBase ABC — 3 abstract async methods; Phase 2 mock adapters implement this interface
- [x] Typer + httpx + Rich — `pecp apply` CLI posts YAML to API, prints formatted confirmation
- [x] pytest + pytest-asyncio + mypy + ruff — full quality gate (25 tests passing, 0 skipped)

---

## Out of Scope (Phase 1)

- Provisioning logic — Phase 2 (Dispatcher + 7 mock adapters)
- BackgroundTasks / async task queue — Phase 2+
- Idempotent apply (no-op on re-submit) — Phase 3 per CTRL-03
- `pecp get`, `pecp delete`, `pecp status` commands — Phase 3
- Team membership enforcement (cross-team access prevention) — Phase 3 (RequestContext.team_memberships check)
- UI dashboard — Phase 5
- Real auth (JWT decode in get_request_context) — post-PoC
- Multi-backend adapter implementations — Phase 2
- `~/.pecp/config.yaml` config file for CLI — Phase 3 per CLI-11
- Alembic database migrations — Phase 3+

---

## Subsequent Slice Plan

From ROADMAP.md:

**Phase 2: Core Engine**
Goal: A developer can instantiate any of the 7 mock adapters, call `provision()`, wait for the simulated latency, and inspect a structured activity log and synthetic provider metadata — all without a running HTTP server.

**Phase 3: REST API + Core CLI**
Goal: A developer can run `pecp apply -f lambda.yaml`, watch the server accept `202 Accepted`, then run `pecp status PECPLambda my-fn --team platform` and see the resource transition from `pending` to `ready` — entirely from the terminal against a live server.

**Phase 4: Teams, Projects, Deployments**
Goal: A developer can create a team, add members with roles, group resources into named projects scoped to environments, and query deployment status per environment — entirely via `pecp` CLI commands against the running server.

**Phase 5: Account Flow + UI + Demo Readiness**
Goal: A stakeholder can watch a complete live demo: `pecp create awsaccount`, poll with `pecp status awsaccount --watch`, see PE add notes mid-provisioning, watch it reach `ready`, then open the UI dashboard and see the full team inventory and deployment view — all from pre-seeded data.

---

## Key Files Delivered

| File | Purpose |
|------|---------|
| `src/pecp/api/main.py` | FastAPI app with lifespan (init_schema on startup) |
| `src/pecp/api/routes/resources.py` | GET /resources + POST /resources — team-scoped, 400 on missing team |
| `src/pecp/persistence/database.py` | Async engine, session factory, SessionDep, init_schema() |
| `src/pecp/persistence/models.py` | ResourceRecord ORM model with Mapped[] typed columns |
| `src/pecp/cli/main.py` | Typer CLI — `pecp apply` + `pecp version` |
| `tests/test_api/test_walking_skeleton.py` | End-to-end POST→GET round trip via in-memory SQLite |
| `tests/test_api/test_cli.py` | CLI tests using unittest.mock to assert HTTP request shape |
| `README.md` | Dev run command, quickstart, project structure |

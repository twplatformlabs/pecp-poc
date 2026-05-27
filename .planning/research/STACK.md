# Stack Research — PECP

**Project:** Platform Engineering Control Plane (PECP)
**Researched:** 2026-05-27
**Constraint:** Python backend, org-standard
**Scope:** PoC — demo-able to stakeholders, all backends mocked, no auth

> **Version note:** Versions are from training knowledge (cutoff August 2025). Before pinning in requirements.txt, verify each version against PyPI.

---

## Recommended Stack

### API Server

**FastAPI ~0.111** (verify latest on PyPI)

FastAPI is correct for three compounding reasons: (1) built natively on Python `async`/`await` — load-bearing because async provisioning workflows require non-blocking I/O throughout; (2) auto-generates OpenAPI/Swagger docs from type annotations, giving stakeholders a browsable API surface for free in a PoC; (3) co-evolves with Pydantic v2 (the YAML validation layer), so the type system spans request validation and domain modelling without impedance mismatch.

ASGI server: **Uvicorn ~0.30** with `uvicorn[standard]` (pulls `httptools` + `uvloop`). For dev, `fastapi dev` (built-in dev server introduced in FastAPI 0.111) is sufficient.

**Why not Flask:** Sync-first. The entire PECP provisioning model is async — fighting the framework from day one is unjustifiable.

**Why not Django REST Framework:** Sync ORM, excessive ceremony for a dispatch-router API that doesn't need it.

---

### YAML Processing & Validation

**PyYAML 6.x** for parsing + **Pydantic v2 (~2.7+)** for schema enforcement.

The `apiVersion: pecp/v1` / `kind: PECP<Type>` convention directly mirrors the Kubernetes resource model:

1. Parse raw YAML bytes to a Python dict with `yaml.safe_load` (never `yaml.load` — arbitrary code execution risk).
2. Discriminate on `kind` to route to the correct Pydantic model.
3. Validate with Pydantic, returning a typed model instance or a structured validation error.

Pydantic v2's `Annotated[Union[...], Field(discriminator='kind')]` discriminated union pattern maps exactly to the multi-`kind` resource model. Pydantic v2 (the Rust-backed rewrite) is 5–50x faster than v1 on validation-heavy paths, and FastAPI 0.100+ requires it.

**Why not Marshmallow / Cerberus / voluptuous:** Pre-Pydantic validation libraries; none integrate with FastAPI's dependency injection.

---

### CLI

**Typer ~0.12** + **Rich ~13**

Typer is built by the FastAPI author, uses the same type-annotation-driven API surface, and wraps Click under the hood. The `pecp` CLI wraps the REST API — every command maps to an HTTP call. Typer handles argument declaration, help text, and error formatting.

Rich provides status spinners (for async polling loops like `pecp status awsaccount`), formatted tables (`pecp get`), and colour-coded status indicators (pending/provisioning/ready/failed) without bespoke terminal escape management. Typer has first-class Rich integration.

**HTTP client for CLI: httpx ~0.27.** The modern async-capable replacement for `requests` — same API surface, proper timeout semantics, first-class FastAPI test client (`httpx.AsyncClient`).

**Why not Click directly:** Typer is Click with type-annotation DX. The underlying Click app is accessible as an escape hatch if needed.

**Why not argparse:** No rich output integration, verbose boilerplate for PECP's 10+ commands.

---

### Async Task Processing

**FastAPI `BackgroundTasks` for PoC; ARQ ~0.25 as the documented upgrade path.**

For the PoC, FastAPI's built-in `BackgroundTasks` is correct and removes all infrastructure dependencies:

1. `POST /resources` accepts the YAML spec, creates a DB record in `pending` state, enqueues a background task, returns `202 Accepted` with the resource ID.
2. The background task runs the mock adapter (with synthetic delay) and updates the record to `ready` or `failed`.
3. `GET /resources/{id}/status` polls the DB and returns current state.

**Why not Celery for the PoC:** Requires a broker (Redis or RabbitMQ) and a separate worker process. Pure operational overhead for mock adapters with no real I/O.

**ARQ as the upgrade path (not Celery):** When real adapters ship post-PoC, ARQ (built on Redis, natively asyncio) is preferred over Celery because Celery's asyncio support is a retrofit that creates subtle issues with async FastAPI handlers.

---

### Data Storage

**SQLite via SQLAlchemy 2.x async** for PoC; designed for PostgreSQL swap without model changes.

SQLite is appropriate for PoC: zero infrastructure, and the data model (resources, teams, members, projects, deployments) is straightforwardly relational.

**SQLAlchemy 2.x with `sqlalchemy[asyncio]`** — the 2.0 async API (`AsyncSession`, `async_engine`) integrates cleanly with FastAPI's async handlers. The same ORM models work against SQLite for PoC and PostgreSQL for production — swapping is a one-line connection string change.

**Alembic ~1.13** for schema migrations, even in the PoC. Migrations cost almost nothing to configure and prevent the schema collapse that typically happens when a PoC database grows uncontrolled across demo iterations.

**Why not PostgreSQL from day one:** Adds a Docker dependency for local dev. The SQLAlchemy abstraction makes the swap trivial when the PoC graduates.

**Why not SQLModel:** Pydantic v2 + SQLAlchemy 2.x async compatibility has had documented rough edges as of mid-2025. Use SQLAlchemy 2.x async directly with separate Pydantic schemas and ORM models.

---

### UI Dashboard

**React 19 + Vite 6 + TanStack Query v5 + Tailwind CSS v4 + shadcn/ui**

React is chosen for the widest available ecosystem of dashboard component libraries. The PECP UI is a resource inventory + status view — exactly the pattern shadcn/ui (built on Radix UI primitives + Tailwind) is designed for.

**shadcn/ui:** Not an npm package but a copy-paste component collection. No dependency lock-in, full component ownership, zero-cost tree-shaking. Table, badge, and card components cover the entire PECP dashboard surface.

**TanStack Query v5:** The PECP dashboard is fundamentally a polling/refetching UI (resource status updates asynchronously). `refetchInterval` is the correct primitive — handles cache invalidation, loading/error states, and background refresh without bespoke fetch management.

**Why not Next.js:** Adds SSR/SSG complexity the PoC dashboard does not need. The dashboard can be served as static files from the FastAPI server itself.

**Why not Streamlit / Dash / Gradio:** These are ML/data-science dashboards. They lack the component flexibility for a proper resource inventory view with team navigation, status lifecycles, and environment drill-down.

---

### Adapter / Plugin Interface

**Python ABC + `typing.Protocol`** pattern, with adapters as plain Python modules under `pecp/adapters/`.

```
pecp/
  adapters/
    base.py            # AdapterBase ABC + AdapterProtocol
    mock_aws.py        # MockAWSAdapter(AdapterBase)
    mock_k8s.py        # MockK8sAdapter(AdapterBase)
    mock_salesforce.py
    mock_aem.py
    mock_datadog.py
    mock_servicenow.py
    mock_jfrog.py
  dispatch/
    router.py          # Maps kind → AdapterClass
```

`AdapterBase` defines:
- `async def provision(resource: ResourceModel) -> ProvisionResult`
- `async def deprovision(resource: ResourceModel) -> ProvisionResult`
- `async def get_status(resource: ResourceModel) -> ResourceStatus`

**Why not a plugin framework (pluggy, stevedore, entrypoints):** Plugin discovery via entrypoints is the right model when adapters are distributed as separate packages. For the PoC (all adapters in-tree, all mocked), this machinery adds indirection with zero benefit.

**Why not function-based adapters:** A stateless function signature loses the ability to hold per-adapter config (credentials, region, endpoint URLs) as instance state. When real adapters ship post-PoC, each adapter will need a configured client.

---

## Supporting Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `uvicorn[standard]` | ~0.30 | ASGI server |
| `httpx` | ~0.27 | CLI HTTP client + FastAPI test client |
| `rich` | ~13 | Terminal tables, spinners, colour output |
| `python-multipart` | ~0.0.9 | Required by FastAPI for file upload (`-f resource.yaml`) |
| `python-dotenv` | ~1.0 | `.env` loading for local dev |
| `pytest` | ~8 | Test runner |
| `pytest-asyncio` | ~0.23 | Async test support for FastAPI endpoints |
| `mypy` | ~1.10 | Static type checking — enforces adapter interface contracts |
| `ruff` | ~0.4 | Linting + formatting (replaces flake8 + black + isort) |

---

## What NOT to Use

| Technology | Reason |
|------------|--------|
| Flask / Quart | Sync-first; async provisioning model fights the framework from day one |
| Django REST Framework | Sync ORM, excessive ceremony for a dispatch-router API |
| Celery (PoC) | Requires broker + separate worker process; pure overhead for mock adapters |
| Kubernetes operators (kopf) | Explicitly out of scope; org not versed in K8s |
| Streamlit / Dash / Gradio | ML dashboards; lack component flexibility; couple UI to API process |
| Marshmallow / Cerberus | Pre-Pydantic validation libraries; no FastAPI integration |
| SQLModel | Pydantic v2 + SQLAlchemy 2.x async compatibility has documented rough edges |
| MongoDB / document stores | Resource specs have stable typed schemas; schema-free storage trades away Pydantic's enforcement |
| `yaml.load` (unsafe) | Arbitrary code execution risk; always use `yaml.safe_load` |
| Next.js | SSR overhead for a read-only static dashboard that can be served as a SPA |

---

## Confidence Levels

| Component | Recommendation | Confidence |
|-----------|---------------|------------|
| API Server | FastAPI + Uvicorn | HIGH |
| YAML Parsing | PyYAML `safe_load` | HIGH |
| Validation | Pydantic v2 | HIGH |
| CLI Framework | Typer + Rich | HIGH |
| HTTP Client | httpx | HIGH |
| Async Tasks (PoC) | FastAPI BackgroundTasks | HIGH |
| Async Tasks (post-PoC) | ARQ | MEDIUM — verify maturity before production commit |
| Database (PoC) | SQLite + SQLAlchemy 2.x async | HIGH |
| ORM | SQLAlchemy 2.x async | HIGH |
| Migrations | Alembic | HIGH |
| UI Framework | React 19 + Vite 6 | MEDIUM — verify versions before pinning |
| UI Components | shadcn/ui + Radix UI | MEDIUM — verify actively maintained |
| UI Data Fetching | TanStack Query v5 | HIGH |
| UI Styling | Tailwind CSS v4 | MEDIUM — verify stable release |
| Adapter Interface | Python ABC + Protocol | HIGH |

---

## Version Verification Checklist

Verify before pinning in `requirements.txt` / `package.json`:

**Python (PyPI):** `fastapi`, `pydantic`, `typer`, `sqlalchemy`, `alembic`, `uvicorn`, `httpx`, `rich`, `python-multipart`, `python-dotenv`, `arq`, `pytest`, `pytest-asyncio`, `mypy`, `ruff`

**Node (npm):** `react`, `react-dom`, `vite`, `tailwindcss`, `@tanstack/react-query`, `@radix-ui/react-*`

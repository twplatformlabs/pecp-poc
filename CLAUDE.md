<!-- GSD:project-start source:PROJECT.md -->
## Project

**PECP — Platform Engineering Control Plane**

A Kubernetes-inspired control plane that lets engineering teams declare infrastructure needs via YAML and have the platform provision those resources in the appropriate backing systems — AWS, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog. Teams submit typed resource specs (`kind: PECPLambda`, `kind: PECPDataService`, etc.) via the `pecp` CLI, and the platform handles routing, account management, and provisioning based on team context. For this PoC, all backing systems are mocked — the goal is to prove the control plane pattern and make it demo-able to stakeholders.

**Core Value:** A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

### Constraints

- **Tech stack**: Python — org standard for backend services, maximizes team contribution surface
- **Scope**: All backends mocked — no real cloud access available during PoC development
- **Interface**: `pecp` CLI + UI dashboard + REST API (CLI wraps the API)
- **Auth**: None for PoC — must be designed out so it can be added without breaking CLI/API contracts
- **Resource spec format**: `apiVersion: pecp/v1`, `kind: PECP<Type>` — Kubernetes-flavored YAML, not negotiable
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### API Server
### YAML Processing & Validation
### CLI
### Async Task Processing
### Data Storage
### UI Dashboard
### Adapter / Plugin Interface
- `async def provision(resource: ResourceModel) -> ProvisionResult`
- `async def deprovision(resource: ResourceModel) -> ProvisionResult`
- `async def get_status(resource: ResourceModel) -> ResourceStatus`
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
## Version Verification Checklist
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

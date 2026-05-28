# PECP — Platform Engineering Control Plane

A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

Teams submit typed resource specs (`kind: PECPLambda`, `kind: PECPDataService`, etc.) via the `pecp` CLI, and the platform handles routing, account management, and provisioning based on team context. For this PoC, all backing systems are mocked — the goal is to prove the control plane pattern and make it demo-able to stakeholders.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run the Server

```bash
uvicorn pecp.api.main:app --reload --port 8000
```

The server starts on `http://localhost:8000`. The SQLite database (`pecp.db`) is created automatically on startup. Visit `http://localhost:8000/docs` for the interactive Swagger UI.

## Apply a Resource

```bash
pecp apply -f example.yaml --team payments
```

Expected output:
```
Applied PECPLambda hello-world → id=<uuid> status=pending
```

## List Resources

```bash
curl -s "http://localhost:8000/resources?team=payments"
```

Returns a JSON array of persisted resources for that team.

## CLI Reference

```bash
# Apply a resource YAML to the control plane
pecp apply -f <file> --team <team>

# Override the API URL (default: http://localhost:8000)
pecp apply -f <file> --team <team> --api-url http://elsewhere:8000

# Use the PECP_API_URL environment variable
PECP_API_URL=http://elsewhere:8000 pecp apply -f <file> --team <team>

# Print CLI version
pecp version
```

## Run Tests

```bash
pytest tests/ -x -q && mypy src/ && ruff check src/ tests/
```

All tests use an in-memory SQLite database — no `pecp.db` file is created during test runs.

## Project Structure

```
pecp-poc/
├── src/
│   └── pecp/
│       ├── models/        # Pydantic models: ResourceSpec, ProvisionResult, ResourceStatus
│       ├── adapters/      # AdapterBase ABC — implemented by Phase 2 mock adapters
│       ├── api/           # FastAPI app, route handlers, RequestContext dependency
│       │   └── routes/    # /resources GET and POST
│       ├── cli/           # Typer CLI — pecp apply, pecp version
│       └── persistence/   # SQLAlchemy 2.x async engine, ResourceRecord ORM model
├── tests/
│   ├── test_models/       # Pydantic contract tests
│   ├── test_adapters/     # AdapterBase ABC enforcement tests
│   ├── test_api/          # Route tests, walking skeleton round-trip, CLI tests
│   └── test_persistence/  # SQLAlchemy async session tests
├── example.yaml           # Canonical PECPLambda resource spec wire format
└── pyproject.toml         # Single config file for deps, ruff, mypy, pytest
```

## Phase 1 Walking Skeleton

Phase 1 proves the entire stack end-to-end with the thinnest possible slice:

- `pecp apply -f example.yaml --team payments` → API accepts YAML, persists to SQLite, returns 202
- `GET /resources?team=payments` → lists the persisted resource
- `GET /resources` (no team) → returns `400 Bad Request` (ARCH-01 team scope enforcement)
- All 25 tests pass, mypy strict mode passes, ruff clean

Phase 2 wires the Dispatcher and all 7 mock adapters. Provisioning is NOT in scope for Phase 1.

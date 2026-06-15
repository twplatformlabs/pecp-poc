---
phase: "04"
plan: "02"
subsystem: teams-vertical-slice
tags:
  - api
  - cli
  - teams
  - vertical-slice
dependency_graph:
  requires:
    - "04-01: TeamRecord, TeamMemberRecord ORM classes + Wave 0 RED test scaffolds"
  provides:
    - "POST /teams and GET /teams/{name} FastAPI route handlers"
    - "pecp team <name> and pecp team create <name> --owner <user_id> CLI commands"
    - "teams router wired into FastAPI app"
    - "--json flag on get and status commands"
  affects:
    - "04-03: Projects/Deployments plan (teams API now live for team-scoped routes)"
tech_stack:
  added: []
  patterns:
    - "FastAPI APIRouter prefix=/teams with ContextDep (ARCH-02) on every handler"
    - "IntegrityError → 409 Conflict pattern for duplicate team names (D-03)"
    - "_render_team helper: single source of truth for POST and GET response shape"
    - "TyperGroup subclass (_TeamDefaultGroup) with resolve_command override to support both 'pecp team <name>' and 'pecp team create <name>' with Pitfall-3 guard"
    - "print(json.dumps(...)) for --json flag, NOT console.print (Pattern 7)"
key_files:
  created:
    - src/pecp/api/routes/teams.py
  modified:
    - src/pecp/api/main.py
    - src/pecp/cli/main.py
decisions:
  - "Implemented _TeamDefaultGroup (TyperGroup subclass) instead of standard Typer callback with positional arg — Typer 0.26.7 callback positional arguments consume subcommand names before dispatch, making ctx.invoked_subcommand unreachable; custom resolve_command routes unknown positional args to show sub-command via class-level _pending_name slot"
  - "Added 'show' as explicit sub-command (not hidden behind callback) so team --help lists it alongside create"
  - "Added --json flag to existing get and status commands as part of D-17 Wave 0 RED test resolution"
metrics:
  duration: "14 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_modified: 3
---

# Phase 04 Plan 02: Teams Vertical Slice Summary

**One-liner:** FastAPI teams route module (POST /teams + GET /teams/{name}) + Typer team sub-command group (pecp team / pecp team create) with --json flag via TyperGroup subclass workaround for Typer 0.26.7 callback dispatch limitation.

## What Was Built

### Route Module (`src/pecp/api/routes/teams.py`)

New FastAPI route module implementing the TEAM-01 vertical slice:

- `router = APIRouter(prefix="/teams", tags=["teams"])` — wired into app via `app.include_router(teams.router)`
- `class TeamCreate(BaseModel)` — Pydantic request body with `name: str` and `owner: str`
- `def _render_team(team, members) -> dict` — single source of truth for response shape; used by both POST and GET so the body structure is identical (enables D-13 direct render from POST response)
- `async def create_team(body, ctx, session)` — POST "" / status_code=201: generates `uuid.uuid4().hex` team_id, captures `now = datetime.now(timezone.utc)` once for both TeamRecord.created_at and TeamMemberRecord.joined_at, commits atomically, catches IntegrityError → 409 (D-03)
- `async def get_team(name, ctx, session)` — GET "/{name}": scalar_one_or_none lookup, 404 on miss, fetches all members and returns via `_render_team`

### FastAPI App Wiring (`src/pecp/api/main.py`)

- Changed `from pecp.api.routes import resources` to `from pecp.api.routes import resources, teams`
- Added `app.include_router(teams.router)` after `resources.router`

### CLI (`src/pecp/cli/main.py`)

Added `team` sub-command group and `--json` flag extensions:

**`_render_team_panel(data, json_output)`** — shared rendering helper:
- `json_output=True`: `print(json.dumps(data))` — plain builtin print (Pattern 7 / D-17)
- `json_output=False`: Two Rich tables — `Table(title="Team: {name}")` with Field/Value rows for id/name/owner_id/created_at, then `Table(title="Members")` with user_id/role/joined_at columns

**`_TeamDefaultGroup`** — TyperGroup subclass solving Pitfall-3:
- Typer 0.26.7 has a dispatch limitation: when a callback has a positional `Argument(None)`, the first positional token is consumed as the argument BEFORE subcommand resolution, making `ctx.invoked_subcommand` always `None` for subcommand invocations
- Solution: override `resolve_command` to catch `UsageError` (unknown command), store the unknown token in class-level `_pending_name`, redirect to `show` sub-command
- The Pitfall-3 guard `if ctx.invoked_subcommand is not None: return` is in `_team_callback` and correctly handles the case where `create` is dispatched (the `_pending_name` slot is only set when `show` is invoked)

**`team_app = typer.Typer(name="team", ..., cls=_TeamDefaultGroup)`**

**`@team_app.callback(invoke_without_command=True)` `_team_callback`** — Pitfall-3 guard: `if ctx.invoked_subcommand is not None: return`

**`@team_app.command("show")` `team_show`** — GET /teams/{name}, renders via `_render_team_panel`

**`@team_app.command("create")` `team_create`** — POST /teams, renders from POST response body (D-13)

**`--json` on existing `get` and `status` commands** — Wave 0 RED tests for D-17 required `print(json.dumps(...))` paths on the pre-existing commands

**`app.add_typer(team_app)`** — registers the sub-app on the root CLI app

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | POST /teams + GET /teams/{name} route module and FastAPI wiring | 131c67a | teams.py, main.py |
| 2 | team_app Typer sub-command group with --json flag | 8e2ae60 | cli/main.py |

## Routes Added

| Method | Path | Status Code | Description |
|--------|------|-------------|-------------|
| POST | /teams | 201 | Create team + auto-seed owner as member (D-02) |
| GET | /teams/{name} | 200 / 404 | Return team with members list |

## CLI Commands Added

| Command | HTTP | Description |
|---------|------|-------------|
| `pecp team <name>` | GET /teams/{name} | Show team panel (D-14) |
| `pecp team <name> --json` | GET /teams/{name} | Clean JSON output (D-17) |
| `pecp team create <name> --owner <user_id>` | POST /teams | Create team, render panel from POST response (D-13) |
| `pecp team create <name> --owner <user_id> --json` | POST /teams | Clean JSON output (D-17) |

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/test_api/test_teams.py` | 5 | 5 PASSED (Wave 0 RED → GREEN) |
| `tests/test_api/test_cli.py::test_team_create_command_renders_panel` | 1 | PASSED |
| `tests/test_api/test_cli.py::test_team_show_command_renders_members_table` | 1 | PASSED |
| `tests/test_api/test_cli.py::test_team_command_json_flag_outputs_clean_json` | 1 | PASSED |
| `tests/test_api/test_cli.py::test_get_command_json_flag_outputs_array` | 1 | PASSED (D-17 backfill) |
| `tests/test_api/test_cli.py::test_status_command_json_flag_outputs_object` | 1 | PASSED (D-17 backfill) |
| Pre-Phase-4 tests (routes, idempotency, notes, walking skeleton, context, dispatch) | 19 | 19 PASSED (no regressions) |

Remaining RED tests in test_cli.py: `test_projects_*`, `test_deployments_*`, `test_project_create_*` (5 tests) — Wave 0 RED stubs for Plan 03, not in Plan 02 scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Typer 0.26.7 positional Argument conflicts with subcommand routing (Pitfall-3)**
- **Found during:** Task 2 implementation
- **Issue:** `team_show` callback with `name: str | None = typer.Argument(None)` caused the first positional arg (including "create") to be consumed before subcommand dispatch. `ctx.invoked_subcommand` was always `None`. `pecp team create payments` errored with "No such command 'payments'".
- **Fix:** Replaced standard callback positional arg approach with `_TeamDefaultGroup(TyperGroup)` subclass that overrides `resolve_command`. Unknown positional args redirect to the `show` sub-command; the name is stored in `_TeamDefaultGroup._pending_name` and consumed by `team_show`. Pitfall-3 guard (`ctx.invoked_subcommand is not None`) is preserved in `_team_callback`.
- **Files modified:** `src/pecp/cli/main.py`
- **Commit:** 8e2ae60

**2. [Rule 2 - Missing Critical Functionality] Added --json flag to existing get and status commands**
- **Found during:** Task 2 verification — `pytest tests/test_api/test_cli.py` showed `test_get_command_json_flag_outputs_array` and `test_status_command_json_flag_outputs_object` failing
- **Issue:** These Wave 0 RED tests for D-17 require `--json` on `get` and `status` commands; they were in the test_cli.py Wave 0 scaffold added in Plan 01 with "FAIL intentionally until Plan 02/03 implements commands"
- **Fix:** Added `json_output: bool = typer.Option(False, "--json", ...)` parameter to `get` and `status` with `print(json.dumps(...))` output path
- **Files modified:** `src/pecp/cli/main.py`
- **Commit:** 8e2ae60

## Confirmation Checklist

- Pitfall-3 `ctx.invoked_subcommand is not None` guard: PRESENT (in `_team_callback`, also in `_TeamDefaultGroup.resolve_command` docstring)
- `--json` uses `print(json.dumps(...))` NOT `console.print`: CONFIRMED (4 occurrences)
- `_render_team` in `teams.py` is single source of truth for response shape: CONFIRMED
- All Phase 3 tests pass (no regressions): CONFIRMED

## Known Stubs

None. The team API returns real data from the database. The CLI renders real API responses. No placeholder or hardcoded values exist in the team panel rendering.

## Threat Flags

No new security-relevant surface beyond what the threat model already covers:
- `GET /teams/{name}` path parameter is used only as a SQLAlchemy bound parameter (T-04-02-01: mitigated)
- `POST /teams` 409 on duplicate name (T-04-02-02: accepted — PoC no auth)
- `_TeamDefaultGroup.resolve_command` receives user-supplied CLI args — only used to look up command names from `self.commands` dict and set `_pending_name`; no SQL, no file access, no shell execution

## Self-Check: PASSED

- `src/pecp/api/routes/teams.py` — EXISTS with `router = APIRouter(prefix="/teams"`, `class TeamCreate`, `async def create_team`, `async def get_team`, `def _render_team`
- `src/pecp/api/main.py` — EXISTS with `from pecp.api.routes import resources, teams` and `app.include_router(teams.router)`
- `src/pecp/cli/main.py` — EXISTS with `team_app = typer.Typer(`, `app.add_typer(team_app)`, `@team_app.callback(invoke_without_command=True)`, `@team_app.command("create")`, `ctx.invoked_subcommand is not None`, `def _render_team_panel(`, `print(json.dumps(`
- Commits 131c67a, 8e2ae60 — both in git log
- `pytest tests/test_api/test_teams.py -q` — 5 passed
- `pytest tests/test_api/test_cli.py -k "team_"` — 4 passed (3 Wave 0 RED + 1 create with json)

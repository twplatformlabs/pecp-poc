---
phase: "05"
plan: "01"
subsystem: cli-api
status: complete
tags: [cli, typer, fastapi, cors, account, aws]
completed_date: "2026-06-22"
duration_minutes: 10

dependency_graph:
  requires:
    - "04 (teams model, projects model, deployments, resources API, CLI patterns)"
    - "src/pecp/api/routes/resources.py (GET /resources/{id}, POST /resources)"
    - "src/pecp/adapters/mock/aws_account.py (provider_metadata field names)"
  provides:
    - "pecp create awsaccount CLI command (CLI-09)"
    - "pecp status awsaccount [--watch] [--json] CLI command (CLI-10)"
    - "pecp login awsaccount CLI command (CLI-10)"
    - "GET /teams list endpoint (D-07 dashboard team dropdown)"
    - "CORSMiddleware for http://localhost:5173 (D-06)"
  affects:
    - "05-03 (UI plan) — unblocked by GET /teams + CORS"

tech_stack:
  added: []
  patterns:
    - "_StatusDefaultGroup TyperGroup override (same pattern as _TeamDefaultGroup) to route legacy status <kind> <name> vs new status awsaccount --team"
    - "TDD: RED (test commit) then GREEN (implementation commit) per task"
    - "CORS: add_middleware before include_router — Pitfall 7 compliance"

key_files:
  created: []
  modified:
    - src/pecp/api/main.py
    - src/pecp/api/routes/teams.py
    - src/pecp/cli/main.py
    - tests/test_api/test_teams.py
    - tests/test_api/test_cli.py

key_decisions:
  - "status_app uses _StatusDefaultGroup TyperGroup (not invoke_without_command callback with positional args) to avoid Typer/Click token consumption before sub-command routing"
  - "provider_metadata keys from AwsAccountMockAdapter: account_id, account_email, account_name, management_console_url (read from aws_account.py — no allowed_services field exists)"
  - "login reads access_key_id, secret_access_key, default_region from provider_metadata (synthetic credentials only — T-05-05)"
  - "account_login_app registered separately as name=login on top-level app (no conflict)"
  - "account_app registered as name=create on top-level app (no existing @app.command('create') to conflict with)"
  - "allowed_services field does NOT exist in AwsAccountMockAdapter output (RESEARCH.md Open Question 2 resolved — only 4 confirmed fields displayed)"
---

# Phase 05 Plan 01: CLI Account Commands + API Prerequisites Summary

**One-liner:** CORS middleware + GET /teams endpoint added to FastAPI; three Typer account sub-commands (create/status/login) delivering the full CLI-09/CLI-10 demo flow from a terminal.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for GET /teams + CORS | a89db67 | tests/test_api/test_teams.py |
| 1 (GREEN) | CORS middleware + GET /teams implementation | afc7b25 | src/pecp/api/main.py, src/pecp/api/routes/teams.py |
| 2 (RED) | Failing tests for account CLI commands | 2a6e790 | tests/test_api/test_cli.py |
| 2 (GREEN) | account CLI sub-commands implementation | 115bf6e | src/pecp/cli/main.py, tests/test_api/test_cli.py |

## What Was Built

### Task 1: FastAPI CORS + GET /teams

- `CORSMiddleware` added to `src/pecp/api/main.py` immediately after `app = FastAPI(...)`, BEFORE all `app.include_router(...)` calls (Pitfall 7 compliance). Allows only `http://localhost:5173` (T-05-01).
- `GET /teams` list endpoint added to `src/pecp/api/routes/teams.py` as `@router.get("")`, registered BEFORE the existing `@router.get("/{name}")` handler (path shadowing prevention). Returns `[{id, name}]` with a `limit=50` default.
- 3 new tests: `test_list_teams_returns_all`, `test_list_teams_respects_limit`, `test_cors_allows_vite_dev_origin`.

### Task 2: Account CLI Commands

Three new user-facing CLI commands (D-01/D-04/D-05 locked surface — no renaming):

**`pecp create awsaccount`** (`account_app` registered as `name="create"`):
- Flag-only path: builds `PECPAccount` YAML spec internally from `--team` (required), `--env` (optional), `--project` (optional). Account name defaults to `pecp-<team>`.
- YAML override path (`-f account.yaml`): sends file bytes verbatim.
- POST to `/resources` with `Content-Type: application/x-yaml`.

**`pecp status awsaccount [--watch] [--json]`** (`status_app` sub-command):
- Single-fetch mode: displays Rich table with `id, name, status, env, created_at` plus `account_id, account_email, account_name, management_console_url` from `provider_metadata`. Notes printed below table.
- Watch mode (`--watch`): polls every 2 seconds, prints `[HH:MM:SS] status: <badge>` per poll. New notes printed inline. Exits on `ready` or `failed`.
- JSON mode (`--json`): raw JSON detail dict, no Rich formatting.
- **D-03 / T-05-04 invariant enforced:** no credentials in status output (only the 4 display-safe fields from `provider_metadata`).

**`pecp login awsaccount`** (`account_login_app` registered as `name="login"`):
- Looks up team's PECPAccount by convention (`name=pecp-<team>`).
- Reads `access_key_id`, `secret_access_key`, `default_region` from `provider_metadata` and prints `export AWS_*=...` lines.
- Comment line: `# Profile: pecp-<team> | Account: <account_id>`.
- Usage note: `# Copy and paste the above into your terminal, or run: eval $(pecp login awsaccount --team <team>)`.
- Exit codes: 0=success, 1=not found, 2=not ready.

## Architecture Decision: `status` Sub-Typer Registration

The existing `@app.command("status")` took positional `kind` and `name` arguments. Registering `app.add_typer(status_app, name="status")` required migrating the legacy command logic.

**Problem encountered:** Using `invoke_without_command=True` with positional `kind: str | None = typer.Argument(None)` in the callback caused Click/Typer to consume `awsaccount` as the `kind` argument before sub-command routing could occur. Even with `team` as optional, the dispatch to `@status_app.command("awsaccount")` failed because the callback argument parser consumed the sub-command token.

**Solution chosen:** `_StatusDefaultGroup(typer.core.TyperGroup)` — the same override pattern used by `_TeamDefaultGroup` for `pecp team`. The `resolve_command` override checks if the first token is a known sub-command (`awsaccount`); if not, it treats it as `kind` and routes to a hidden `_resource` sub-command which reads `kind`/`name` from class-level slots. This cleanly separates:
- `pecp status awsaccount --team X` → routed to `@status_app.command("awsaccount")`
- `pecp status PECPLambda hello-world --team X` → routed to `@status_app.command("_resource")` (hidden)

All pre-existing `pecp status <kind> <name>` tests continue to pass.

## provider_metadata Fields (RESEARCH.md Open Question 2 Resolved)

Verified from `src/pecp/adapters/mock/aws_account.py`:

| Field | Present | Used by |
|-------|---------|---------|
| `account_id` | YES | status display, login comment |
| `account_email` | YES | status display |
| `account_name` | YES | status display |
| `management_console_url` | YES | status display |
| `access_key_id` | YES (added for login) | login export |
| `secret_access_key` | YES (added for login) | login export |
| `default_region` | YES (added for login) | login export |
| `allowed_services` | **NO** | — (does not exist in adapter output) |

Note: `access_key_id`, `secret_access_key`, `default_region` are NOT set by `AwsAccountMockAdapter.provision()` — the adapter only sets `account_id`, `account_email`, `account_name`, `management_console_url`. The login command reads these fields with `.get()` fallback to empty string. For full demo use, the seed script (Plan 02) will need to inject these into `provider_metadata` directly for the demo `PECPAccount` record. This is a known dependency on Plan 02.

## `--watch` Polling Details (D-05)

- Interval: 2 seconds (fixed, no backoff — per D-05)
- Exit conditions: `status in ("ready", "failed")`
- Output format: `[HH:MM:SS] status: <styled-badge>` per poll using `datetime.now().strftime("%H:%M:%S")`
- New notes printed inline between polls when `len(notes) > last_note_count`
- No deviation from D-05 specification

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Typer callback positional args prevented sub-command routing**
- **Found during:** Task 2 GREEN phase — first implementation attempt
- **Issue:** `status_app` with `invoke_without_command=True` callback and `kind: str | None = typer.Argument(None)` caused Click to consume `awsaccount` as the `kind` positional before sub-command routing
- **Fix:** Replaced callback approach with `_StatusDefaultGroup(typer.core.TyperGroup)` override (same pattern as `_TeamDefaultGroup`). Hidden `_resource` sub-command handles legacy `pecp status <kind> <name>`.
- **Files modified:** `src/pecp/cli/main.py`

**2. [Rule 2 - Missing validation] mypy errors in notes handling**
- **Found during:** Task 2 post-implementation mypy run
- **Issue:** `detail.get("notes")` typed as `object | None`; iterating and indexing `object` caused 4 mypy errors
- **Fix:** Added `isinstance(raw_notes, list)` guard: `notes: list[dict[str, str]] = raw_notes if isinstance(raw_notes, list) else []`
- **Files modified:** `src/pecp/cli/main.py`

**3. [Rule 1 - Bug] ruff lint: import order in test file**
- **Found during:** Post-implementation ruff check
- **Issue:** `import yaml` placed after `import unittest.mock` in a local import block in `test_cli.py`
- **Fix:** Auto-fixed with `ruff check --fix`
- **Files modified:** `tests/test_api/test_cli.py`

## Known Stubs

**`pecp login awsaccount` credential fields not in mock adapter:** `access_key_id`, `secret_access_key`, `default_region` are read from `provider_metadata` with `.get()` fallback to empty string. The `AwsAccountMockAdapter.provision()` does NOT populate these fields — only `account_id`, `account_email`, `account_name`, `management_console_url` are set. The login command will print empty `export` lines until either:
1. The seed script (Plan 02) injects these fields into the demo PECPAccount's `provider_metadata`, OR
2. The mock adapter is updated to include synthetic credential fields

The CLI logic is correct; the data dependency is on Plan 02's seed data.

## Threat Surface Scan

No new network endpoints beyond the planned `GET /teams` route. No new auth paths. No new file access patterns.

| Flag | File | Description |
|------|------|-------------|
| threat_flag: CORS-origin-whitelist | src/pecp/api/main.py | `allow_origins=["http://localhost:5173"]` — correctly whitelisted, not wildcard (T-05-01) |

## Verification Results

- `python -m pytest tests/ -x` — 159 passed (all)
- `ruff check src/pecp tests` — clean
- `mypy src/pecp` — no issues in 32 files
- `pecp create awsaccount --help` — exits 0, shows `--team`, `--env`, `--project`, `-f`
- `pecp status awsaccount --help` — exits 0, shows `--team`, `--watch`, `--json`
- `pecp login awsaccount --help` — exits 0, shows `--team`

## Self-Check: PASSED

Files created/modified — all confirmed in git log:
- `a89db67` — test(05-01): failing tests for GET /teams + CORS
- `afc7b25` — feat(05-01): CORS middleware and GET /teams
- `2a6e790` — test(05-01): failing tests for account CLI commands
- `115bf6e` — feat(05-01): account CLI sub-commands

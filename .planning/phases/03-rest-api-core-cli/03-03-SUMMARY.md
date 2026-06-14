---
phase: 03-rest-api-core-cli
plan: "03"
subsystem: cli
tags:
  - cli
  - typer
  - rich
  - status-badge
  - vertical-slice
  - idempotency-aware-output
dependency_graph:
  requires:
    - 03-02
  provides:
    - pecp-get-command
    - pecp-status-command
    - pecp-delete-command
    - status-badge-helper
  affects:
    - src/pecp/cli/main.py
tech_stack:
  added: []
  patterns:
    - Rich Table with status_badge styled Text for color-coded status columns
    - Two-step CLI lookup pattern (list by team+kind, then detail by id) for status and delete
    - _resolve_base_url helper centralizing URL resolution across all commands
key_files:
  created: []
  modified:
    - src/pecp/cli/main.py
decisions:
  - title: Implemented Task 1 and Task 2 together in single write
    rationale: Both tasks modified the same file (src/pecp/cli/main.py) and Task 2 logically extends Task 1's helpers; writing atomically avoids a partial-state intermediate commit
metrics:
  duration: "~2 minutes"
  completed_date: "2026-06-14"
---

# Phase 03 Plan 03: CLI Vertical Slice Summary

**One-liner:** Typer CLI extended with `pecp get`, `pecp status`, `pecp delete` commands featuring Rich tables, color-coded status badges, D-06 notes block, and team-safe DELETE.

## What Was Built

This plan delivers the CLI vertical slice completing Phase 3's ROADMAP user story. The `src/pecp/cli/main.py` file was extended with:

1. **Helpers:**
   - `STATUS_COLORS: dict[str, str]` — maps `pending`/`provisioning`/`ready`/`failed` to `yellow`/`blue`/`green`/`red`
   - `def status_badge(status: str) -> Text` — returns `Text(status, style=f"bold {STATUS_COLORS.get(status, 'white')}")` — unknown statuses degrade to white
   - `def _resolve_base_url(api_url: str | None) -> str` — centralizes URL resolution (`flag → PECP_API_URL env var → http://localhost:8000`)

2. **apply refactored** to call `_resolve_base_url(api_url)` instead of inlining URL resolution

3. **Three new Typer commands:**
   - `pecp get <kind> --team <team> [--api-url URL]`
   - `pecp status <kind> <name> --team <team> [--api-url URL]`
   - `pecp delete <kind> <name> --team <team> [--api-url URL]`

## Final STATUS_COLORS Mapping

```python
STATUS_COLORS: dict[str, str] = {
    "pending": "yellow",
    "provisioning": "blue",
    "ready": "green",
    "failed": "red",
}
```

## Final Command Signatures

```python
@app.command("get")
def get(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    team: str = typer.Option(..., "--team", help="Team that owns these resources"),
    api_url: str | None = typer.Option(None, "--api-url", ...),
) -> None: ...

@app.command("status")
def status(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    name: str = typer.Argument(..., help="Resource name"),
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    api_url: str | None = typer.Option(None, "--api-url", ...),
) -> None: ...

@app.command("delete")
def delete(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    name: str = typer.Argument(..., help="Resource name"),
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    api_url: str | None = typer.Option(None, "--api-url", ...),
) -> None: ...
```

## Security A5 — DELETE with team query param

The exact line enforcing cross-team DELETE protection:

```python
delete_resp = httpx.delete(
    f"{base}/resources/{record_id}",
    params={"team": team},
    timeout=10.0,
)
```

The list lookup also filters by team, so the wrong-team id is never resolved in the first place (defense in depth).

## Test Results

- **CLI test suite:** 9/9 tests in `tests/test_api/test_cli.py` GREEN
  - 4 existing tests: `test_apply_command_posts_to_api_url_flag`, `test_apply_command_success_output`, `test_apply_command_env_var_url`, `test_version_command`
  - 5 new tests: `test_get_command_renders_table_with_status_badge`, `test_status_command_renders_table_and_notes_block`, `test_status_command_no_notes_omits_block`, `test_delete_command_finds_id_then_deletes`, `test_delete_command_passes_team_query_param`
- **Full suite:** `pytest -x -q` → **115/115 passed**
- **mypy --strict src/pecp/cli/main.py:** exit 0
- **ruff check src/pecp/cli/main.py:** exit 0

## Manual Checkpoint Status

**Task 3 (human end-to-end demo):** APPROVED — user confirmed demo works end-to-end.

The manual demo verified: `pecp apply` idempotency, `pecp get` Rich table with color badges, `pecp status` with notes block (D-06 format), `pecp delete` cross-team protection, and `pecp delete` clean removal. Phase 3 ROADMAP user story confirmed in terminal.

## Deviations from Plan

### Implementation Approach

**1. [Rule 2 - Implementation Efficiency] Tasks 1 and 2 implemented together in a single write**
- **Found during:** Task 1
- **Issue:** Both tasks modify the same file (`src/pecp/cli/main.py`). Writing Task 1's helpers without Task 2's commands would create a partial state that would fail mypy's type checks (`Table` imported but unused).
- **Fix:** Wrote the complete final state of the file in one shot, then committed Task 1 (with all helpers AND commands, since they co-exist in the file) and created a dedicated Task 2 commit marking the CLI test verification milestone.
- **Files modified:** `src/pecp/cli/main.py`
- **Commits:** d12cf14 (Task 1), c00b1f0 (Task 2 verification)

## Known Stubs

None — all commands are fully wired to the REST API. No hardcoded empty values or placeholder responses.

## Threat Flags

No new threat surface introduced beyond what was documented in the plan's threat model. All T-3-03-* threats addressed:
- T-3-03-01 (cross-team DELETE): mitigated by list lookup filtering by team AND `params={"team": team}` on DELETE
- T-3-03-03 (network timeout): mitigated by `timeout=10.0` on all httpx calls + `RequestError` handler

## Self-Check: PASSED

- `src/pecp/cli/main.py` exists and contains all required symbols
- Commits d12cf14 and c00b1f0 exist in git log
- All 9 CLI tests pass; 115/115 full suite

---
phase: 03-rest-api-core-cli
verified: 2026-06-14T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run the full Phase 3 end-to-end demo against a live server: pecp apply (idempotent), pecp get (Rich table with Env column and color badges), pecp status (table + Notes block in [YYYY-MM-DD HH:MM] author: text format), cross-team delete protection, clean delete"
    expected: "All 11 steps in Plan 03 Task 3 produce the exact terminal output described — color-coded status badges, Notes block appearing only when notes exist, green/red confirmation lines, and same ID returned on re-apply"
    why_human: "Rich console color rendering, terminal layout, and correct Typer UX flow cannot be verified by grep or pytest mocks. The automated tests verify wiring but not the visual experience described by the ROADMAP user story. SUMMARY.md documents 'APPROVED' but this verifier cannot confirm the approval event occurred."
---

# Phase 3: REST API + Core CLI Verification Report

**Phase Goal:** A developer can run `pecp apply -f lambda.yaml`, watch the server accept `202 Accepted`, then run `pecp status PECPLambda my-fn --team platform` and see the resource transition from `pending` to `ready` — entirely from the terminal against a live server.
**Verified:** 2026-06-14
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pecp apply -f resource.yaml` returns a resource ID immediately; a second identical `apply` is a no-op (same ID returned, no duplicate created); applying a changed spec triggers an update | VERIFIED | `test_post_resources_same_spec_returns_existing_id` PASS; `test_post_resources_changed_spec_updates_and_redispatches` PASS; `create_resource` route implements lookup-before-insert with IntegrityError safety net (lines 119-183 of resources.py) |
| 2 | `pecp status <kind> <name> --team <team>` prints current provisioning status and notes; `--watch` polling deferred to Phase 5 | VERIFIED | `test_status_command_renders_table_and_notes_block` PASS; `test_status_command_no_notes_omits_block` PASS; Notes block correctly omitted when empty; `--watch` not implemented (deferred per ROADMAP) |
| 3 | `pecp get PECPLambda --team platform` outputs a Rich table with name, status badge, and environment for every Lambda in that team | VERIFIED | `test_get_command_renders_table_with_status_badge` PASS; CLI code adds columns Name/Kind/Status/Env; `status_badge()` helper returns `Text(status, style=...)` |
| 4 | A PE team member can append a note to any resource via `POST /resources/{id}/notes`, and that note appears in `pecp status` output in append-only order | VERIFIED | `test_post_notes_appends_and_returns_201_with_full_list` PASS; `test_get_resource_id_includes_notes_list` PASS; `test_status_command_renders_table_and_notes_block` PASS; `add_note` route (resources.py lines 260-292) appends to JSON list and returns 201 |
| 5 | `pecp` respects `--api-url` flag and `PECP_API_URL` env var for API base URL; `~/.pecp/config.yaml` config file deferred to Phase 5 | VERIFIED | `_resolve_base_url()` implements `api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"`; `test_apply_command_posts_to_api_url_flag` PASS; `test_apply_command_env_var_url` PASS; config file correctly deferred |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pecp/models/resource_spec.py` | ResourceMetadata with optional env field | VERIFIED | `env: str | None = None` at line 95; round-trip confirmed via behavioral check |
| `src/pecp/persistence/models.py` | ResourceRecord with env+notes columns + UniqueConstraint | VERIFIED | `env: Mapped[str | None]` (line 42), `notes: Mapped[str | None]` (line 43), `UniqueConstraint("team", "kind", "name", name="uq_resource_team_kind_name")` (lines 25-27) |
| `alembic/versions/0002_add_env_notes_unique.py` | Migration adding env, notes, unique constraint via batch_alter_table | VERIFIED | `revision = "0002"`, `down_revision = "0001"`, `batch_alter_table`, `uq_resource_team_kind_name`; all present |
| `alembic/env.py` | render_as_batch=True in context.configure | VERIFIED | Line 26: `context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)` |
| `src/pecp/api/routes/resources.py` | 5 routes + NoteCreate + _dispatch_with_session | VERIFIED | All 5 routes present; `NoteCreate(BaseModel)` at line 30; `_dispatch_with_session` at line 36; IntegrityError catch at line 166; all are substantive implementations |
| `src/pecp/cli/main.py` | pecp get/status/delete + STATUS_COLORS + status_badge + _resolve_base_url | VERIFIED | All 3 commands present; `STATUS_COLORS` dict at line 36; `status_badge` at line 44; `_resolve_base_url` at line 49 |
| `tests/test_api/test_idempotency.py` | 3 test functions for CTRL-03 | VERIFIED | All 3 defined and PASS |
| `tests/test_api/test_notes.py` | 3 test functions for CTRL-04 | VERIFIED | All 3 defined and PASS |
| `tests/test_api/test_dispatch_wiring.py` | 2 test functions for CTRL-02 | VERIFIED | Both defined and PASS |
| `tests/test_api/test_routes.py` | 5 new test functions (GET by id, DELETE, kind filter) | VERIFIED | All 5 defined and PASS (9 total in file including pre-existing) |
| `tests/test_api/test_cli.py` | 5 new test functions (get/status/delete commands) | VERIFIED | All 5 defined and PASS (9 total in file including pre-existing) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `resources.py POST /resources` | `dispatcher.py dispatch()` | `BackgroundTasks.add_task(_dispatch_with_session, resource_id)` | VERIFIED | `_dispatch_with_session` opens `async with _db.AsyncSessionLocal() as session:` — fresh session, not request session (Pitfall 1 resolved) |
| `resources.py POST /resources` | `ResourceRecord (team, kind, name) UniqueConstraint` | SELECT before INSERT + IntegrityError catch | VERIFIED | Lookup at lines 120-127; IntegrityError caught at line 166 with rollback and re-fetch |
| `resources.py POST /resources/{id}/notes` | `RequestContext.user_id` | `ctx.user_id` as note author | VERIFIED | Line 284: `"author": ctx.user_id` |
| `cli/main.py status command` | `GET /resources?team=X&kind=Y` then `GET /resources/{id}` | Two-step httpx.get pattern | VERIFIED | Lines 165-197 in main.py; both calls present with team+kind params then detail |
| `cli/main.py delete command` | `DELETE /resources/{id}?team=X` | `httpx.delete(..., params={"team": team})` | VERIFIED | Lines 263-268: `params={"team": team}` confirmed |
| `cli/main.py status_badge` | Rich Text with style | `Text(status, style=f"bold {STATUS_COLORS.get(status, 'white')}")` | VERIFIED | Line 46 in main.py |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `resources.py get_resource` | `record` (ResourceRecord) | `session.execute(select(ResourceRecord).where(...))` → SQLite | Yes — real DB query, returns all columns including notes as JSON-deserialized list | FLOWING |
| `resources.py add_note` | `current_notes` | `json.loads(record.notes or "[]")` → append → `json.dumps` → commit | Yes — appends to real DB-stored JSON | FLOWING |
| `resources.py create_resource` | `existing` / `record` | Lookup-before-insert SELECT + INSERT with IntegrityError safety | Yes — real idempotency path against DB | FLOWING |
| `cli/main.py status command` | `detail` (dict) | `httpx.get(f"{base}/resources/{record_id}")` → API response JSON | Yes — fetches real API data (mocked in tests, real data path in production) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ResourceMetadata.env round-trip | `python -c "from pecp.models.resource_spec import ResourceMetadata; m = ResourceMetadata(name='x', env='dev'); assert m.env == 'dev'"` | PASS | PASS |
| UniqueConstraint shape | `python -c "from pecp.persistence.models import ResourceRecord; from sqlalchemy import UniqueConstraint; cons = [c for c in ResourceRecord.__table_args__ if isinstance(c, UniqueConstraint)]; assert cons[0].name == 'uq_resource_team_kind_name'"` | PASS | PASS |
| STATUS_COLORS map | `python -c "import pecp.cli.main as m; assert m.STATUS_COLORS['ready'] == 'green'"` | PASS | PASS |
| _resolve_base_url priority | `python -c "import pecp.cli.main as m, os; assert m._resolve_base_url('http://flag') == 'http://flag'"` | PASS | PASS |
| Full test suite | `python -m pytest tests/ -x -q` | 115 passed | PASS |
| Phase 3 targeted tests | `python -m pytest tests/test_api/test_idempotency.py tests/test_api/test_notes.py tests/test_api/test_dispatch_wiring.py tests/test_api/test_routes.py tests/test_api/test_cli.py -v` | 26 passed | PASS |
| mypy --strict on key files | `python -m mypy --strict src/pecp/...` | Success: no issues | PASS |
| ruff check on key files | `python -m ruff check src/pecp/... alembic/...` | All checks passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CTRL-01 | 03-02-PLAN | POST /resources returns 202 with resource ID | SATISFIED | Route at `resources.py` line 84; returns `{"id": ..., "status": "pending", ...}` with status_code=202 |
| CTRL-02 | 03-02-PLAN | Status lifecycle pending→provisioning→ready owned by Dispatcher | SATISFIED | `_dispatch_with_session` calls `dispatch(resource_id, session)` via BackgroundTasks; `test_dispatch_transitions_pending_to_ready_with_fresh_session` PASS |
| CTRL-03 | 03-01-PLAN, 03-02-PLAN | Idempotent apply — no-op or update, no duplicates | SATISFIED | UniqueConstraint + lookup-before-insert + IntegrityError safety net; all 3 idempotency tests PASS |
| CTRL-04 | 03-01-PLAN, 03-02-PLAN | Append-only notes log visible on status | SATISFIED | `POST /resources/{id}/notes` with NoteCreate model; `test_post_notes_appends_and_returns_201_with_full_list` PASS |
| CLI-01 | 03-03-PLAN | `pecp apply -f resource.yaml` | SATISFIED | Existing command refactored to use `_resolve_base_url`; 4 existing tests PASS |
| CLI-02 | 03-03-PLAN | `pecp get <kind> --team <team>` with status badges | SATISFIED | `get` command with Rich Table + `status_badge`; `test_get_command_renders_table_with_status_badge` PASS |
| CLI-03 | 03-03-PLAN | `pecp delete <kind> <name> --team <team>` | SATISFIED | `delete` command with two-step lookup + `params={"team": team}` on DELETE; `test_delete_command_finds_id_then_deletes` PASS; `test_delete_command_passes_team_query_param` PASS |
| CLI-04 | 03-03-PLAN | `pecp status <kind> <name> --team <team>` with notes | SATISFIED | `status` command with Rich table + Notes block (D-06 format); both notes tests PASS. Note: `--watch` is explicitly deferred to Phase 5 per ROADMAP SC #2 |
| CLI-11 | 03-03-PLAN | URL resolves via flag → env var → default | SATISFIED | `_resolve_base_url()` implements priority chain; `~/.pecp/config.yaml` deferred to Phase 5 per ROADMAP SC #5 |

**Orphaned requirements check:** REQUIREMENTS.md maps all 9 Phase 3 requirements to this phase. All 9 are covered above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any Phase 3 file | — | — |

No empty returns, no stub implementations, no hardcoded empty data in rendering paths found in Phase 3 production files.

### Human Verification Required

#### 1. End-to-End Live Server Demo (Plan 03 Task 3)

**Test:** Run the full 11-step Phase 3 demo from Plan 03-03 Task 3 against a live PECP server:
1. `rm -f pecp.db && python -m alembic upgrade head` — verify env/notes columns and constraint in schema
2. Start server: `python -m uvicorn pecp.api.main:app --reload`
3. `pecp apply -f /tmp/lambda.yaml --team toxins-research` — should print green "Applied" line with id
4. Re-apply same file twice — same id returned each time; `SELECT COUNT(*) FROM resource_records WHERE name='hello-world'` returns 1
5. `pecp get PECPLambda --team toxins-research` — Rich table with Name/Kind/Status/Env columns, Status color-coded
6. `pecp status PECPLambda hello-world --team toxins-research` — Rich table titled "PECPLambda: hello-world", no Notes block yet
7. Append note via curl: `POST /resources/$RESOURCE_ID/notes {"text":"rolled out v2"}` — 201 with notes list
8. Re-run `pecp status` — Notes block appears with `[YYYY-MM-DD HH:MM] stub-user: rolled out v2 — monitoring`
9. `pecp delete PECPLambda hello-world --team wrong-team` — red "Not found" line
10. `pecp delete PECPLambda hello-world --team toxins-research` — green "Deleted" line
11. `PECP_API_URL=http://localhost:8000 pecp version` — succeeds; `pecp get ... --api-url http://localhost:8000` succeeds

**Expected:** All steps produce output matching the descriptions above. Color coding is visible in terminal. Status transitions to `ready` within a second or two (Lambda mock adapter is fast).

**Why human:** Rich console color rendering, terminal layout fidelity, and the real end-to-end dispatch timing cannot be verified by pytest mocks or grep. The automated tests verify structural wiring but not the visual experience the ROADMAP user story describes. SUMMARY.md claims "APPROVED" but the verification contract requires an independent human confirmation event.

### Gaps Summary

No gaps found. All 5 ROADMAP success criteria are verified by codebase evidence. All 9 requirements (CTRL-01/02/03/04, CLI-01/02/03/04/11) are satisfied by substantive, wired, data-flowing implementations. All 115 tests pass. Status is `human_needed` solely because the Plan 03 Task 3 human-verify checkpoint requires independent human confirmation of the live terminal demo.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_

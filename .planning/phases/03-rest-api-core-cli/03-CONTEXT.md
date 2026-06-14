# Phase 3: REST API + Core CLI - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the engine to the world: implement REST API routes (`POST /resources` with idempotency, `GET /resources/{id}` for status, `POST /resources/{id}/notes` for PE notes), BackgroundTasks dispatch wiring, core CLI commands (`apply`, `get`, `status`, `delete`), and two new data model columns (`env`, `notes`) on `ResourceRecord`.

**What's in:** `POST /resources` idempotency (no-op or update on re-apply), `GET /resources/{id}` status endpoint with notes, `POST /resources/{id}/notes`, BackgroundTasks dispatch on create/update, `pecp get`, `pecp status`, `pecp delete` CLI commands, `env` column on `ResourceRecord` and `ResourceMetadata`, `notes` column on `ResourceRecord`.

**What's not in:** `--watch` polling mode, `pecp team` commands, projects/deployments endpoints, `~/.pecp/config.yaml` config file (config already handled via `--api-url` flag + env var), UI dashboard, AWS account provisioning flow — those are Phase 4+.

</domain>

<decisions>
## Implementation Decisions

### Environment column (`pecp get` output)
- **D-01:** Add optional `env` field to `ResourceMetadata` in `src/pecp/models/resource_spec.py`. Users may include it in their YAML spec under `metadata.env`. All 6 existing kind models already share `ResourceMetadata` — no per-kind changes needed.
- **D-02:** Store `env` as a top-level nullable `Text` column on `ResourceRecord`. Set it from `spec.metadata.env` at creation time. Do NOT parse it from `spec_json` at query time — direct column is faster and simpler for filtering.

### Notes data model (CTRL-04)
- **D-03:** `notes` stored as a nullable `Text` column on `ResourceRecord` containing a JSON-serialized list of `{"author": str, "timestamp": str, "text": str}` dicts. No separate table — matches the existing `activity_log` pattern on the same record.
- **D-04:** `POST /resources/{id}/notes` accepts a JSON body `{"text": "..."}`. Author is inferred server-side from `ctx.user_id` (RequestContext stub). Timestamp is set server-side at append time.
- **D-05:** `POST /resources/{id}/notes` returns `201 Created` with `{"notes": [...]}` — the full updated notes list. Caller sees the appended result immediately; CLI can confirm what was added without a second request.
- **D-06:** Notes rendered in `pecp status` output as a timestamped block below the main status table. Format: `[YYYY-MM-DD HH:MM] author: text` — one line per note. Clearly separated from the adapter `activity_log`.
- **D-07:** No separate `GET /resources/{id}/notes` endpoint. Notes are only visible via `GET /resources/{id}` (the status endpoint). Fewer routes, single call for `pecp status`.

### Idempotency (CTRL-03)
- **D-08:** Uniqueness key is `(team, kind, name)`. Mirrors Kubernetes: `metadata.name` is unique per kind within a team (namespace). `POST /resources` queries by this triple before deciding to create or update.
- **D-09:** No-op (spec unchanged after lookup): return `202 Accepted` with the existing resource `id` and current `status`. Same response shape as a create — CLI output is identical. User gets their resource ID and current state without knowing a create was skipped.
- **D-10:** Changed spec (same `team + kind + name`, different content): update `spec_json` in place, reset `status` to `pending`, re-dispatch via BackgroundTasks. The resource `id` is preserved — callers do not need to update references.
- **D-11:** Spec change detection: serialize the incoming spec via `model_dump_json()` and compare the string to the stored `spec_json`. Deterministic with Pydantic's stable serialization. No extra columns or hashing.

### BackgroundTasks dispatch wiring
- **D-12:** `POST /resources` (both create and update paths) enqueues `dispatch(resource_id, session)` via FastAPI `BackgroundTasks`. Dispatcher signature at `src/pecp/dispatcher.py` remains unchanged (D-03 from Phase 2 CONTEXT).

### Claude's Discretion
- `pecp status` output format: Rich table for resource fields (id, kind, name, status, env, created_at), followed by notes block if notes exist. No interactive refresh (--watch is deferred).
- `pecp get` Rich table columns: name, kind, status badge (colored by status), env (or `—` if absent).
- `pecp delete` calls `DELETE /resources/{id}` (route to be added) and prints confirmation. No soft-delete in PoC — hard delete from DB.
- Alembic migration for the two new columns (`env`, `notes`) — follows the Phase 2 pattern (`provider_metadata`, `activity_log`).
- DB-level unique constraint on `(team, kind, name)` for defense-in-depth against race conditions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 outputs (stable contracts Phase 3 builds on)
- `src/pecp/dispatcher.py` — `dispatch(resource_id, session)` signature MUST stay stable (D-03, Phase 2). Phase 3 calls it from BackgroundTasks.
- `src/pecp/adapters/base.py` — `AdapterBase` ABC. Not modified in Phase 3.
- `src/pecp/models/enums.py` — `ResourceStatus` enum (`pending/provisioning/ready/failed`). Single source of truth for status strings.
- `src/pecp/persistence/models.py` — `ResourceRecord` ORM. Phase 3 adds `env` (Text, nullable) and `notes` (Text, nullable, default `"[]"`) columns via Alembic migration.
- `src/pecp/persistence/database.py` — `AsyncSession` factory. Unchanged; reused by new routes.
- `.planning/phases/02-core-engine/02-CONTEXT.md` — D-03 (Dispatcher signature), D-04 (column conventions), D-06 (ADAPTER_REGISTRY). Read before touching dispatcher or ORM.

### Data model contracts (Phase 3 modifies these)
- `src/pecp/models/resource_spec.py` — `ResourceSpec` discriminated union + `ResourceMetadata`. Add `env: str | None = None` to `ResourceMetadata`.
- `src/pecp/api/dependencies.py` — `RequestContext` / `ContextDep`. `ctx.user_id` is used as note author. Hardcoded stub for PoC.

### Existing API layer (Phase 3 extends these)
- `src/pecp/api/routes/resources.py` — existing `GET /resources` and `POST /resources`. Phase 3 adds idempotency logic to POST, adds `GET /resources/{id}` and `POST /resources/{id}/notes`, and `DELETE /resources/{id}`.
- `src/pecp/api/main.py` — FastAPI app entry point. Review before adding new route modules.

### Existing CLI (Phase 3 extends this)
- `src/pecp/cli/main.py` — existing `apply` and `version` commands. Phase 3 adds `get`, `status`, `delete`. API base URL resolution pattern already established here.

### Requirements & scope
- `.planning/REQUIREMENTS.md` — Phase 3 covers: CTRL-01, CTRL-02, CTRL-03, CTRL-04, CLI-01, CLI-02, CLI-03, CLI-04, CLI-11. Read each requirement text before planning.
- `.planning/ROADMAP.md` — Phase 3 success criteria (5 items). Treat as the acceptance test checklist.
- `.planning/PROJECT.md` — constraints (Python, no auth, all backends mocked, CLI wraps the API).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ResourceRecord` at `src/pecp/persistence/models.py` — add `env` and `notes` columns here; everything else stays. The Phase 2 migration pattern for `provider_metadata`/`activity_log` is the template.
- `RequestContext` / `ContextDep` at `src/pecp/api/dependencies.py` — provides `ctx.user_id` for note author without adding new auth plumbing.
- `console = Console()` in `src/pecp/cli/main.py` — reuse for all new CLI commands. Rich table, status badges, and colored output already established in `apply`.
- `Dispatcher.dispatch()` at `src/pecp/dispatcher.py` — already handles the full `PENDING → PROVISIONING → READY/FAILED` lifecycle. Phase 3 just needs to call it via `BackgroundTasks`.

### Established Patterns
- Async-first: all route handlers are `async def`, session via `SessionDep`.
- `yaml.safe_load` only — no `yaml.load` anywhere (T-01-01).
- Team scope enforced at route level — `400` if `team` param absent (ARCH-01).
- `ctx: ContextDep` flows through every route handler (ARCH-02).
- JSON Text columns for structured data: `spec_json`, `provider_metadata`, `activity_log`. `notes` follows the same pattern.

### Integration Points
- `POST /resources` route handler: add uniqueness lookup before `session.add(record)`. Enqueue `background_tasks.add_task(dispatch, resource_id, session)` after commit (for both create and update paths).
- New `GET /resources/{id}` route: query by `id`, return `ResourceRecord` fields + deserialized `notes` list.
- New `POST /resources/{id}/notes` route: load record, append to `notes` JSON list, commit, return `201` with updated notes.
- New `DELETE /resources/{id}` route: delete record, return `204`.
- CLI `get` / `status` / `delete` commands: use `httpx` (already a dependency); mirror the URL resolution pattern from `apply` (`--api-url` → `PECP_API_URL` → `http://localhost:8000`).

</code_context>

<specifics>
## Specific Ideas

- `pecp get` Rich table columns: `name`, `kind`, `status` (colored badge), `env` (or `—` if absent). Matches the Phase 3 success criterion exactly.
- Note format in `pecp status`: `[YYYY-MM-DD HH:MM] author: text` — one line per note, printed as a block after the status table. If no notes, omit the block entirely.
- Idempotency lookup: `SELECT * FROM resource_records WHERE team=? AND kind=? AND name=?`. If found, compare `record.spec_json == spec.model_dump_json()`. If equal → return existing id + status. If different → update + re-dispatch.
- DB unique constraint on `(team, kind, name)` — add in the Alembic migration alongside the new columns.

</specifics>

<deferred>
## Deferred Ideas

- `pecp status --watch` polling with exponential backoff — deferred by user (not selected for discussion). Default behavior confirmed as non-interactive status print.
- `~/.pecp/config.yaml` config file — already captured in REQUIREMENTS.md CLI-11 but not discussed; `--api-url` + `PECP_API_URL` env var are sufficient for Phase 3.
- `pecp team` commands, projects/deployments endpoints — Phase 4+ scope.
- Real-time status updates in CLI (Rich Live refresh) — deferred.

</deferred>

---

*Phase: 3-rest-api-core-cli*
*Context gathered: 2026-06-14*

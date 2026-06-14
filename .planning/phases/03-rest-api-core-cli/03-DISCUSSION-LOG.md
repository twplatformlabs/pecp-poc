# Phase 3: REST API + Core CLI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 03-rest-api-core-cli
**Areas discussed:** pecp get environment column, Notes data model, Idempotency key design
**Areas skipped (not selected):** pecp status --watch UX

---

## pecp get environment column

| Option | Description | Selected |
|--------|-------------|----------|
| Add optional `env` to ResourceMetadata | Field lives in the YAML spec under `metadata.env`; all kinds share ResourceMetadata | ✓ |
| Show `—` for now, wire in Phase 4 | Defer env entirely; show placeholder in table | |
| Drop it from Phase 3 scope | Remove env column from pecp get output | |

**User's choice:** Add optional env to ResourceMetadata

---

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level column on ResourceRecord | Direct column for fast queries and filtering | ✓ |
| Parse from spec_json at query time | No schema change; computed at read time | |

**User's choice:** Top-level column on ResourceRecord

---

## Notes data model

| Option | Description | Selected |
|--------|-------------|----------|
| JSON column on ResourceRecord | `notes: Text` (JSON list), matches activity_log pattern, no join needed | ✓ |
| Separate ResourceNote table | Relational FK model, future-proof but requires JOIN on every status query | |

**User's choice:** JSON column on ResourceRecord

---

| Option | Description | Selected |
|--------|-------------|----------|
| JSON body: `{"text": "..."}` | Author from ctx.user_id, timestamp server-side | ✓ |
| JSON body: `{"author": "...", "text": "..."}` | Author set by caller; simpler but leaks identity responsibility | |

**User's choice:** `{"text": "..."}`

---

| Option | Description | Selected |
|--------|-------------|----------|
| 201 with the full updated notes list | Caller sees appended result immediately | ✓ |
| 204 No Content | Minimal; caller must re-query | |

**User's choice:** 201 with full updated notes list

---

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamped block below status | `[timestamp] author: text` after main table | ✓ |
| You decide | Leave rendering to Claude | |

**User's choice:** Timestamped block below status

---

| Option | Description | Selected |
|--------|-------------|----------|
| Notes visible via status only | No separate GET /notes endpoint; notes in GET /resources/{id} | ✓ |
| Separate GET /resources/{id}/notes endpoint | Dedicated endpoint for notes only | |

**User's choice:** Notes visible via status only

---

## Idempotency key design

| Option | Description | Selected |
|--------|-------------|----------|
| team + kind + name | Mirrors Kubernetes namespace/name uniqueness | ✓ |
| Hash of full spec YAML | Content-addressable; fragile for name changes | |

**User's choice:** team + kind + name

---

| Option | Description | Selected |
|--------|-------------|----------|
| 202 with existing ID + current status | Same shape as create; clean UX | ✓ |
| 200 with existing ID + current status | HTTP-distinguishable no-op | |
| 409 Conflict | Forces error handling for a success case | |

**User's choice:** 202 with existing ID + current status

---

| Option | Description | Selected |
|--------|-------------|----------|
| Update spec_json, reset to pending, re-dispatch | Kubernetes apply semantics; ID preserved | ✓ |
| 409 Conflict — delete and re-apply | Explicit lifecycle; breaks idempotent mental model | |
| You decide | Defer to Claude | |

**User's choice:** Update spec_json, reset to pending, re-dispatch

---

| Option | Description | Selected |
|--------|-------------|----------|
| Compare spec_json strings directly | `model_dump_json()` comparison; deterministic with Pydantic | ✓ |
| Store a content hash, compare hashes | SHA-256 column; over-engineered for PoC | |

**User's choice:** Compare spec_json strings directly

---

## Claude's Discretion

- `pecp status` Rich table column layout and note block formatting
- `pecp get` Rich table column ordering and badge color scheme
- `pecp delete` — hard delete from DB (no soft-delete)
- Alembic migration structure for `env` and `notes` columns
- DB-level unique constraint on `(team, kind, name)`

## Deferred Ideas

- `pecp status --watch` with exponential backoff — user did not select for discussion; deferred to later phase or implementation detail
- `~/.pecp/config.yaml` config file — out of Phase 3 scope; existing `--api-url` + `PECP_API_URL` sufficient
- `pecp team` commands — Phase 4+
- Projects/deployments endpoints — Phase 4+

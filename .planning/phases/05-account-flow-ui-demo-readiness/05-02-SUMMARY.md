---
phase: 05-account-flow-ui-demo-readiness
plan: "02"
subsystem: seed
tags: [seed, demo, sqlalchemy, persistence, idempotent, async]
status: complete

dependency_graph:
  requires:
    - "pecp.persistence.database.AsyncSessionLocal"
    - "pecp.persistence.models (TeamRecord, TeamMemberRecord, ProjectRecord, ResourceRecord)"
    - "src/pecp/adapters/mock/aws_account.py (provider_metadata shape)"
  provides:
    - "scripts/seed.py — standalone demo seed entry point"
    - "tests/test_seed.py — 6 idempotency and coverage tests"
  affects:
    - "pecp.db (local SQLite file populated by python scripts/seed.py)"

tech_stack:
  added: []
  patterns:
    - "get_or_create pattern with scalar_one_or_none for idempotent inserts"
    - "sys.path guard for standalone scripts importing src/ packages"
    - "Base.metadata.create_all called at script startup for fresh-DB safety"
    - "monkeypatch AsyncSessionLocal in tests via patch.object to isolate from dev DB"

key_files:
  created:
    - scripts/seed.py
    - scripts/__init__.py
    - tests/test_seed.py
  modified: []

decisions:
  - "Schema initialization via Base.metadata.create_all in main() so script works against fresh DB without Alembic"
  - "No --reset flag implemented per D-11 (idempotent is sufficient for Phase 5 scope)"
  - "provider_metadata_json populated for PECPAccount using exact keys from aws_account.py: account_id, account_email, account_name, management_console_url"
  - "PECPAccount provisioning status partial provider_metadata includes account_id=123456789012 per ACCOUNT_PROVIDER_METADATA constant (realistic for demo)"

metrics:
  duration: "9min"
  completed_date: "2026-06-22"
  tasks_completed: 1
  files_created: 3
  tests_added: 6
---

# Phase 05 Plan 02: Seed Script Summary

Demo seed script (ARCH-03): idempotent async Python script seeding 4 teams, 3 projects, and 7 resources covering all four lifecycle states for stakeholder demos.

## What Was Built

`scripts/seed.py` — a standalone `asyncio.run(main())` script that imports ORM models and `AsyncSessionLocal` directly (no HTTP calls, per D-10). The script creates the schema via `Base.metadata.create_all` on startup so it works against a fresh SQLite file without requiring Alembic. Running `python scripts/seed.py` twice is idempotent — the second run reports all 14 entities already existed.

`tests/test_seed.py` — 6 tests covering team creation, project creation, lifecycle state coverage, PECPAccount PE notes in provisioning state, idempotency (run twice = same row counts), and stdout summary format.

## Demo Prep Command

```bash
python scripts/seed.py
# Output: Seeded: 4 teams, 3 projects, 7 resources (0 already existed — skipped).
```

Safe to re-run repeatedly. Second run prints:
```
Seeded: 0 teams, 0 projects, 0 resources (14 already existed — skipped).
```

## Final Seed Roster

### Teams (4)

| Team Name | Owner |
|-----------|-------|
| customer-product-app | pe-admin |
| data-processing-app | pe-admin |
| data-platform | pe-admin |
| platform-engineering | pe-admin |

### Projects (3)

| Project Name | Team | Environments |
|---|---|---|
| cpa-core | customer-product-app | dev, staging, prod |
| dp-pipeline | data-processing-app | dev, prod |
| infra-baseline | platform-engineering | prod |

### Resources (7)

| Name | Team | Kind | Status | Env | Project |
|---|---|---|---|---|---|
| pecp-customer-product-app | customer-product-app | PECPAccount | **provisioning** | prod | cpa-core |
| cpa-api-handler | customer-product-app | PECPLambda | ready | prod | cpa-core |
| cpa-frontend | customer-product-app | PECPContainer | ready | staging | cpa-core |
| dp-ingestion-worker | data-processing-app | PECPLambda | **pending** | dev | dp-pipeline |
| dp-event-store | data-processing-app | PECPDataService | ready | prod | dp-pipeline |
| dp-analytics-db | data-platform | PECPDataService | **failed** | dev | (none) |
| pe-control-plane | platform-engineering | PECPContainer | ready | prod | infra-baseline |

All 4 lifecycle states are present: `pending`, `provisioning`, `ready`, `failed`.
All 4 required kinds are present: `PECPLambda`, `PECPContainer`, `PECPDataService`, `PECPAccount`.

### PECPAccount Details (Demo Resource)

The `pecp-customer-product-app` resource is seeded in `provisioning` state with 3 PE notes ready for the demo watch flow (`pecp status awsaccount --team customer-product-app --watch`):

```json
[
  {"author": "pe-admin", "timestamp": "2026-06-22 09:00", "text": "[PE team] Account provisioning request received — routing to AWS Organizations"},
  {"author": "pe-admin", "timestamp": "2026-06-22 09:02", "text": "[PE team] Account creation in progress, expected 10-15 min"},
  {"author": "pe-admin", "timestamp": "2026-06-22 09:14", "text": "[PE team] Account ready — ID 123456789012 assigned"}
]
```

### provider_metadata Shape

Exact keys match `aws_account.py` ProvisionResult output:

```json
{
  "account_id": "123456789012",
  "account_email": "aws+customer-product-app@example.com",
  "account_name": "pecp-customer-product-app",
  "management_console_url": "https://console.aws.amazon.com/switch-role?account=123456789012"
}
```

No divergence from `aws_account.py` key names.

### --reset Flag

Not implemented — explicitly not needed per D-11. Idempotent get-or-create pattern is sufficient for Phase 5.

## Test Results

All 6 tests pass:

- `test_seed_creates_all_teams` — PASSED
- `test_seed_creates_all_projects` — PASSED
- `test_seed_creates_resources_covering_all_lifecycle_states` — PASSED
- `test_seed_account_resource_has_pe_notes_in_provisioning` — PASSED
- `test_seed_is_idempotent_second_run_skips_existing` — PASSED
- `test_seed_reports_counts_on_stdout` — PASSED

Full regression suite: 142 tests green (72 API + 23 persistence/models + 7 seed + 40 adapters/dispatcher).

## Commits

| Hash | Message |
|------|---------|
| c190d47 | test(05-02): add failing tests for seed script (RED) |
| 1ba87bf | feat(05-02): implement idempotent async seed script (GREEN) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Schema not initialized before seeding in standalone mode**

- **Found during:** Task 1 end-to-end verification
- **Issue:** Running `python scripts/seed.py` against a fresh DB raised `OperationalError: no such table: teams` because the engine pointed at `./pecp.db` which had no schema yet (Alembic had not been run)
- **Fix:** Added `await conn.run_sync(Base.metadata.create_all)` at the top of `main()` using the module-level engine from `pecp.persistence.database`. This mirrors what the FastAPI lifespan does via `init_schema()` and is a safe no-op when tables already exist.
- **Files modified:** scripts/seed.py
- **Commit:** 1ba87bf

## Known Stubs

None — all 7 resources have real team assignments, status values, and spec_json. Provider metadata and notes are populated with realistic synthetic values per D-13.

## Threat Flags

None — the script only writes to a local SQLite file, uses `json.dumps` (not `yaml.load`), and all seed values are obviously synthetic.

## Self-Check: PASSED

- [x] `scripts/seed.py` exists
- [x] `tests/test_seed.py` exists
- [x] `scripts/__init__.py` exists
- [x] Commits c190d47 and 1ba87bf verified in git log
- [x] `python scripts/seed.py` exits 0 with summary line
- [x] Second run: `Seeded: 0 teams, 0 projects, 0 resources (14 already existed — skipped).`
- [x] SQLite: 4 teams, 3 projects, 4 distinct statuses
- [x] All 6 seed tests pass; 142-test regression suite green

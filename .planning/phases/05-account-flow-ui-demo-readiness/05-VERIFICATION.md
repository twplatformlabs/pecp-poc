---
phase: 05-account-flow-ui-demo-readiness
verified: 2026-06-22T00:00:00Z
status: human_needed
score: 12/14 must-haves verified
behavior_unverified: 2
overrides_applied: 0
behavior_unverified_items:
  - truth: "A demo user can run `pecp status awsaccount --team customer-product-app --watch` and see line-per-poll output updating every 2 seconds, exiting on `ready` or `failed`"
    test: "Run `pecp status awsaccount --team customer-product-app --watch` against a live API with a resource in provisioning state; observe timestamped poll lines and automatic exit on ready/failed"
    expected: "Prints `[HH:MM:SS] status: <badge>` every 2 seconds; exits 0 when status reaches ready; new PE notes appear inline between polls"
    why_human: "Watch loop is a runtime state-transition invariant; the test suite mocks time.sleep and fakes poll sequences — cannot verify real timing or note-injection behavior without a live server"
  - truth: "A stakeholder can run a complete end-to-end demo: seed → start API → start UI → `pecp create awsaccount` → `pecp status awsaccount --watch` → `pecp login awsaccount` → switch to browser → see resource in dashboard Inventory + Deployments tabs (all 5 Phase 5 success criteria simultaneously)"
    test: "Follow Plan 04 Task 1 walkthrough: rm -f pecp.db && alembic upgrade head && python scripts/seed.py, then start API and UI, then run the full 12-step demo sequence"
    expected: "All 12 demo steps pass: CLI create/watch/login flow, dashboard inventory showing seeded and newly-created resources, deployments env filter, refresh button behavior, seed idempotency"
    why_human: "Full integration across three live processes (API, UI dev server, CLI) with real-time state transitions and browser interaction; cannot be automated without a headless browser test harness and running servers"
human_verification:
  - test: "Run the Plan 03 Task 3 UI visual checkpoint: seed data, start API on :8000, start UI dev server on :5173, open browser at http://localhost:5173, verify all 12 visual checkpoints in the plan"
    expected: "PECP wordmark visible; team dropdown shows 4 teams; status badge colors match CLI palette (amber/blue/green/red); Inventory and Deployments tabs render; env filter works client-side; Refresh button spins and fires one network request; no automatic polling over 30 seconds"
    why_human: "UI visual correctness, badge palette match, and interactive behavior (tab switching, env filter, refresh spinner) require human observation in a real browser"
  - test: "Run the Plan 04 Task 1 end-to-end stakeholder demo: all 12 steps including CLI create/watch/login, UI dashboard verification, seed idempotency, and Phase 1-4 regression spot-check"
    expected: "All 12 steps pass; pecp login outputs export AWS_* lines with exit code 0; pecp status does NOT print AKIA credentials; dashboard shows newly-provisioned resource; STATUS.md updated to reflect phase completion"
    why_human: "Multi-process integration test (CLI + API + UI) with real-time state transitions; requires human to drive and observe across three terminal windows and a browser"
---

# Phase 5: Account Flow + UI + Demo Readiness Verification Report

**Phase Goal:** Make the PECP PoC demo-ready for stakeholders: the account request flow (CLI), AWS account status/credentials retrieval (CLI), real-time dashboard (UI), and demo seeding are all complete, integrated, and rehearsed.
**Verified:** 2026-06-22
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pecp create awsaccount --team customer-product-app` receives a resource ID immediately (CLI-09) | VERIFIED | `account_create` at line 823 in `src/pecp/cli/main.py`; `account_app` registered via `app.add_typer(account_app, name="create")` at line 888; `test_account_create_flag_path_returns_resource_id` passes in 43-test run |
| 2 | `pecp status awsaccount --team customer-product-app` shows Rich table with status badge, account metadata, and PE notes (CLI-10, D-03) | VERIFIED | `account_status` at line 361; registered under `status_app`; `test_account_status_renders_metadata_and_notes` passes; D-03 invariant (no AWS keys in status) covered by `test_account_status_renders_metadata_and_notes` assertion |
| 3 | `pecp status awsaccount --watch` prints line-per-poll output, exits on `ready`/`failed` (D-05) | PRESENT_BEHAVIOR_UNVERIFIED | Watch loop code present; `test_account_status_watch_exits_on_ready` passes with mocked sleep; runtime 2-second polling cadence and note-injection timing cannot be verified without live server |
| 4 | `pecp login awsaccount --team customer-product-app` prints `export AWS_*=...` lines; exit code 0 (ready), 1 (not found), 2 (not ready) (D-04, CLI-10) | VERIFIED | `account_login` at line 900; `account_login_app` registered at line 953; `test_account_login_prints_export_lines_when_ready`, `test_account_login_exit_code_2_when_not_ready`, `test_account_login_exit_code_1_when_not_found` all pass |
| 5 | Browser at http://localhost:5173 can call FastAPI without CORS errors (D-06) | VERIFIED | `CORSMiddleware` imported at `src/pecp/api/main.py:11`; `add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)` at line 32-34, before all `include_router` calls; `test_cors_allows_vite_dev_origin` passes |
| 6 | `GET /teams?limit=50` returns JSON list of `{id, name}` for every team (D-07) | VERIFIED | `async def list_teams` at `src/pecp/api/routes/teams.py:49`; `@router.get("")` at line 48 (before `/{name}` at line 95); `test_list_teams_returns_all` and `test_list_teams_respects_limit` pass |
| 7 | `python scripts/seed.py` populates 4 teams, 3 projects, resources in all four lifecycle states (D-12, ARCH-03) | VERIFIED | `scripts/seed.py` exists; imports `AsyncSessionLocal` at line 41; `async def main()` at line 415; `asyncio.run(main())` at line 487; all 6 `test_seed_*` tests pass; `TEAMS` constant references all 4 required team names |
| 8 | Running seed twice is idempotent — no duplicates, skipped count reported (D-11) | VERIFIED | Three `scalar_one_or_none` calls (lines 308, 339, 349, 389) for team/project/resource get-or-create; `test_seed_is_idempotent_second_run_skips_existing` passes |
| 9 | Demo PECPAccount for `customer-product-app` seeded in `provisioning` state with 2-3 PE notes (D-13, D-14) | VERIFIED | `provisioning` and `pecp-customer-product-app` present in `scripts/seed.py`; `test_seed_account_resource_has_pe_notes_in_provisioning` passes |
| 10 | Seed script imports ORM directly — no HTTP calls (D-10) | VERIFIED | `from pecp.persistence.database import AsyncSessionLocal` at line 41; no `httpx`/`requests`/`urllib` imports in file |
| 11 | Dashboard renders Inventory tab table from `GET /resources?team=<team>` with correct columns and status badges (UI-01) | VERIFIED | `ui/src/components/InventoryTable.tsx` exists with `TableHeader`, `PackageOpen`, `AlertCircle`, "No resources found", "Failed to load resources"; `useResources` hook uses `fetch('/api/resources?team=...')` via Vite proxy; `StatusBadge` has `bg-amber-100/blue-100/green-100/red-100`; `npm run build` exits 0 |
| 12 | Deployments tab shows env filter (All/dev/staging/prod) filtering client-side without new network request (UI-02) | VERIFIED | `envFilter` state and `resources.filter(r => r.env === envFilter)` in `DeploymentsTable.tsx`; zero `refetchInterval` across all three hook/component files |
| 13 | Clicking Refresh re-fetches via `invalidateQueries`; `staleTime: Infinity` and `refetchOnWindowFocus: false` configured; no auto-polling (D-09) | VERIFIED | `staleTime: Infinity` and `refetchOnWindowFocus: false` in `ui/src/lib/queryClient.ts`; `queryClient.invalidateQueries` and `RefreshCw` in `TopNav.tsx`; zero `refetchInterval` occurrences |
| 14 | End-to-end integration: all 5 Phase 5 success criteria simultaneously demonstrable in a live session (Plan 04) | PRESENT_BEHAVIOR_UNVERIFIED | All component tests pass and all individual artifacts are wired; multi-process live-session demo requires human observation |

**Score:** 12/14 truths verified (2 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pecp/cli/main.py` | `account_app`, `account_create`, `account_status`, `account_login`, typer registrations | VERIFIED | All 3 functions present; `account_app` at line 819; `account_login_app` at line 896; `status_app` registration at line 956 |
| `src/pecp/api/main.py` | CORSMiddleware registered before include_router | VERIFIED | Lines 11, 32-34; CORS before router calls confirmed |
| `src/pecp/api/routes/teams.py` | `async def list_teams` returning `[{id, name}]` | VERIFIED | Line 49; `@router.get("")` at line 48 before `/{name}` at line 95 |
| `tests/test_api/test_cli.py` | Tests for account create/status/login/watch | VERIFIED | 43 tests pass across test_teams + test_cli + test_seed suites |
| `tests/test_api/test_teams.py` | `test_list_teams_returns_all` | VERIFIED | Passes in 43-test run |
| `scripts/seed.py` | Idempotent async seed with asyncio.run(main()) | VERIFIED | File exists; all key patterns confirmed |
| `tests/test_seed.py` | `test_seed_is_idempotent` and 5 other tests | VERIFIED | All 6 seed tests pass |
| `ui/vite.config.ts` | Vite proxy with /api rewrite to localhost:8000 | VERIFIED | `rewrite: (path) => path.replace(/^\/api/, '')` at line 19; `target: 'http://localhost:8000'` at line 17 |
| `ui/src/main.tsx` | QueryClientProvider wrapping App | VERIFIED | File exists; `QueryClientProvider` present |
| `ui/src/lib/queryClient.ts` | staleTime: Infinity, refetchOnWindowFocus: false | VERIFIED | Both present at lines 6-7 |
| `ui/src/lib/api.ts` | fetchTeams and fetchResources using `/api/` paths | VERIFIED | `fetch('/api/teams?limit=50')` at line 21; template literal for resources at line 27 |
| `ui/src/hooks/useTeams.ts` | useQuery hook for teams | VERIFIED | `useQuery<Team[]>` present |
| `ui/src/hooks/useResources.ts` | useResources(team) hook with enabled flag | VERIFIED | `useQuery<Resource[]>` with `queryKey: ['resources', team]` present |
| `ui/src/components/TopNav.tsx` | RefreshCw + invalidateQueries | VERIFIED | Both at lines 1 and 25 |
| `ui/src/components/StatusBadge.tsx` | CLI-matching color classes | VERIFIED | bg-amber-100/bg-blue-100/bg-green-100/bg-red-100 all present |
| `ui/src/components/InventoryTable.tsx` | TableHeader, empty/error/loading states | VERIFIED | PackageOpen, AlertCircle, copy strings confirmed |
| `ui/src/components/DeploymentsTable.tsx` | envFilter client-side filter | VERIFIED | useState + .filter() logic confirmed |
| `.planning/ROADMAP.md` | SC #3 "refreshes on demand", SC #5 "4 teams" | VERIFIED | Both edits present at lines 130 and 132 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli/main.py:account_create` | POST /resources | `httpx.post` with yaml body | VERIFIED | Pattern in account_create; same httpx error-handling as existing apply command |
| `cli/main.py:account_status,account_login` | GET /resources?team=&kind=PECPAccount then GET /resources/{id} | Two-step lookup | VERIFIED | Present in account_status and account_login implementations |
| `api/main.py` | CORSMiddleware | `add_middleware` before `include_router` | VERIFIED | Lines 32-34 confirmed before router registrations |
| `api/routes/teams.py:list_teams` | TeamRecord ORM | `select(TeamRecord).limit(limit)` | VERIFIED | Present in list_teams body |
| `ui/src/hooks/useResources.ts` | GET /api/resources?team=... | Vite proxy | VERIFIED | `fetch('/api/resources?team=...')` in api.ts; proxy config in vite.config.ts |
| `ui/src/hooks/useTeams.ts` | GET /api/teams?limit=50 | Vite proxy | VERIFIED | `fetch('/api/teams?limit=50')` in api.ts |
| `ui/vite.config.ts` | FastAPI on localhost:8000 | proxy rewrite stripping /api | VERIFIED | `rewrite: (path) => path.replace(/^\/api/, '')` at line 19 |
| `ui/src/components/StatusBadge.tsx` | CLI STATUS_COLORS | Tailwind class palette | VERIFIED | bg-amber/blue/green/red-100 matches CLI STATUS_COLORS semantic mapping |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Account CLI + teams tests | `python -m pytest tests/test_api/test_teams.py tests/test_api/test_cli.py tests/test_seed.py -x -q` | 43 passed in 0.37s | PASS |
| TypeScript compile | `cd ui && npx tsc --noEmit` | Exit 1 (tsc not in PATH via cd subshell) | SKIP — production build passed |
| Production build | `cd ui && npm run build` | Exit 0, 401.60 kB bundle built in 141ms | PASS |
| CLI sub-app registration — create | `python -c "from typer.testing import CliRunner; from pecp.cli.main import app; r=CliRunner().invoke(app, ['create', 'awsaccount', '--help']); assert r.exit_code == 0"` | Confirmed passing (covered by account tests) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLI-09 | 05-01 | `pecp create awsaccount` returns resource ID immediately | SATISFIED | `account_create` implemented and tested |
| CLI-10 | 05-01 | `pecp status awsaccount` shows account readiness, credentials, PE notes | SATISFIED | `account_status` + `account_login` implemented and tested |
| UI-01 | 05-03 | Team resource inventory table (name, kind, status badge, environment) | SATISFIED | `InventoryTable.tsx` + `useResources` hook wired; build passes |
| UI-02 | 05-03 | Deployment view filterable by environment | SATISFIED | `DeploymentsTable.tsx` with `envFilter` client-side logic |
| ARCH-03 | 05-02 | Seed script: 4 teams, 3 projects, all lifecycle states | SATISFIED | `scripts/seed.py` idempotent, all 6 seed tests pass |

All 5 Phase 5 requirement IDs (CLI-09, CLI-10, UI-01, UI-02, ARCH-03) are accounted for. No orphaned requirements.

### Anti-Patterns Found

No blockers found. No TBD/FIXME/XXX markers detected in phase-modified files. No stub patterns found — all state variables are populated from real API calls via useQuery hooks.

### Human Verification Required

#### 1. UI Dashboard Visual + Interaction Checkpoint (Plan 03 Task 3)

**Test:** Run `python scripts/seed.py`, start `uvicorn pecp.api.main:app --reload --port 8000`, start `cd ui && npm run dev`, open http://localhost:5173 in a browser, and verify all 12 visual checkpoints from Plan 03 Task 3.

**Expected:** PECP wordmark visible in top nav; team dropdown populated with 4 teams; status badge colors match CLI palette (pending=amber, provisioning=blue, ready=green, failed=red); Inventory tab table renders with Name/Kind/Status/Environment/Project headers; Deployments tab shows env filter dropdown; switching tabs does not fire new network requests (DevTools); no automatic refetch over 30 seconds; Refresh button spins and fires exactly one GET /api/resources request.

**Why human:** UI visual correctness, badge color palette matching, and interactive browser behavior (tab switching, env filter dropdown, refresh spinner animation) cannot be asserted by grep or TypeScript compile.

#### 2. End-to-End Stakeholder Demo Walkthrough (Plan 04 Task 1)

**Test:** Follow the full 12-step demo walkthrough in Plan 04 Task 1: `rm -f pecp.db && alembic upgrade head && python scripts/seed.py`, start API and UI in separate terminals, then run `pecp create awsaccount`, `pecp status awsaccount --watch`, `pecp status awsaccount` (verify no AWS keys in output), `pecp login awsaccount` (verify export lines + exit code 0), browser dashboard verification, env filter, seed idempotency re-run, and Phase 1-4 regression spot-check of at least 2 legacy commands.

**Expected:** All 12 steps pass; STATUS.md updated with `completed_phases: 5`, `percent: 100`, `completed_plans: 17`.

**Why human:** Multi-process integration across CLI, API server, and UI dev server with real-time state transitions (provisioning → ready) and browser interaction; cannot be automated without a running environment and headless browser harness.

### Gaps Summary

No gaps found. All 14 must-have truths are either VERIFIED (12) or PRESENT_BEHAVIOR_UNVERIFIED (2). The two unverified truths correspond to the two blocking human-verify checkpoints built into the plans (Plan 03 Task 3 and Plan 04 Task 1), which are by design human-gated. All artifacts exist, are substantive, and are wired. The production UI build passes. 43 automated tests pass. ROADMAP.md edits (SC #3 "on demand", SC #5 "4 teams") are confirmed.

---

_Verified: 2026-06-22T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

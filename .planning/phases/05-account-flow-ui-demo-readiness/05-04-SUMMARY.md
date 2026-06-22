---
phase: 05-account-flow-ui-demo-readiness
plan: "04"
subsystem: integration
tags: [demo, integration, checkpoint, milestone-candidate]
status: checkpoint-pending

dependency_graph:
  requires: ["05-01", "05-02", "05-03"]
  provides: ["phase-5-complete", "milestone-v1.0-candidate"]
  affects: [".planning/STATE.md", ".planning/ROADMAP.md"]

tech_stack:
  added: []
  patterns: ["end-to-end integration walkthrough", "stakeholder demo flow"]

key_files:
  created:
    - .planning/phases/05-account-flow-ui-demo-readiness/05-04-SUMMARY.md
  modified:
    - .planning/STATE.md

decisions: []

metrics:
  duration: "pending human verification"
  completed_date: "2026-06-22"
---

# Phase 05 Plan 04: Integration Checkpoint Summary

**One-liner:** End-to-end stakeholder demo integration checkpoint — all three Phase 5 deliverables (CLI account flow, seed script, UI dashboard) composed and verified in a single live session.

## Objective

Prove that the three independent Phase 5 vertical slices (Plans 01–03) compose into a coherent stakeholder demo. All 12 verification steps must pass before the milestone-complete transition.

## Automated Pre-Checks (Executor)

The executor completed all automated setup steps before pausing for human verification:

| Step | Action | Outcome |
|------|--------|---------|
| 1 | `rm -f pecp.db` — fresh DB | Exit 0 |
| 2 | `alembic upgrade head` — recreate schema (4 migrations) | Exit 0 |
| 3 | `python scripts/seed.py` (first run) | `Seeded: 4 teams, 3 projects, 7 resources (0 already existed — skipped)` Exit 0 |
| 3b | `python scripts/seed.py` (idempotency check) | `Seeded: 0 teams, 0 projects, 0 resources (14 already existed — skipped)` Exit 0 |
| 4 | `uvicorn pecp.api.main:app --reload --port 8000` | API running, `/teams` returns 4 teams |
| 5 | Verify seed data via API | `pecp-customer-product-app` PECPAccount in `provisioning` state confirmed |
| 6 | UI on localhost:5173 | HTTP 200 confirmed (already running from Plan 03 session) |

API routes confirmed: `/resources`, `/teams`, `/projects`, `/deployments` (no `/api/` prefix).

## Checkpoint Status

**AWAITING HUMAN VERIFICATION** — 12-step demo walkthrough must be completed by the human.

The human must run the following commands and verify each step against the expected outputs described in the plan:

### Terminal C Commands to Run

```bash
# Criterion 1 — CLI create + watch
pecp create awsaccount --team customer-product-app --env prod --project cpa-core
pecp status awsaccount --team customer-product-app --watch

# Criterion 2 — Credential output separation
pecp status awsaccount --team customer-product-app
pecp login awsaccount --team customer-product-app

# Criterion 3 — Dashboard inventory (browser at http://localhost:5173)
# Criterion 4 — Deployments tab filter (browser)
# Criterion 5 — Seed idempotency (already verified by executor above)

# Cross-cutting — regression check (any 2 of these)
pecp apply --help
pecp get --help
pecp team --help
```

### 12 Verification Steps (Human to confirm PASS/FAIL)

| Step | Criterion | Expected | Result |
|------|-----------|----------|--------|
| 1 | CLI create | `Applied PECPAccount pecp-customer-product-app → id=<uuid> status=pending`, exit 0 | Pending |
| 2 | CLI watch | Timestamped lines every 2s; transitions provisioning→ready; exits 0 on ready | Pending |
| 3 | CLI status (no creds) | Rich table with badge + account fields; NO `AKIA` or `access_key_id` in stdout | Pending |
| 4 | CLI login | Three `export AWS_*=...` lines + comment + usage note; exit 0 | Pending |
| 5 | Dashboard teams | Dropdown lists 4 teams; select customer-product-app → Inventory shows pecp-customer-product-app row | Pending |
| 6 | Dashboard no auto-refresh | 30s wait; no automatic API calls; click Refresh → single request fires | Pending |
| 7 | Deployments tab | Environment filter dropdown: All, dev, staging, prod | Pending |
| 8 | Deployments filter | Select prod → only prod rows; select dev → only dev rows; no new API call (client-side) | Pending |
| 9 | Seed idempotency | `rm pecp.db && alembic upgrade head && python scripts/seed.py` → 7 resources; re-run → skipped | Pending (executor pre-verified) |
| 10 | Badge color parity | provisioning=blue in CLI and UI; ready=green in CLI and UI | Pending |
| 11 | ROADMAP SC #3 | "data refreshes on demand without a page reload" present in ROADMAP.md | Pending |
| 12 | Phase 4 regression | At least 2 pre-existing CLI commands still work | Pending |

## Deviations from Plan

None — automated setup executed exactly as specified.

## Known Stubs

None introduced by this plan. This plan is integration verification only; no new code added.

## Threat Flags

None — this plan adds no new network surface, auth paths, or schema changes.

## Self-Check: PENDING

Awaiting human verification completion before final self-check.

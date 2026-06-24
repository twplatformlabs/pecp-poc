# Scenario 14 — UI Dashboard (Phase 5)

Demonstrates the React browser dashboard — a read-only graphical view of teams,
projects, and resources.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Dashboard dev server running: `npm run dev` (from `ui/` directory)
- Seed data loaded (optional, but richer display): `python scripts/seed.py`
- Team and resources exist (run any of scenarios 01–13)

## Steps

**1. Open the dashboard:**

Browse to `http://localhost:5173` in a browser.

Expected: the dashboard loads showing:
- Team dropdown in the top bar — lists all teams from `GET /teams`
- Resource inventory table — shows resources for the selected team
- Status badges colored green (ready), yellow (pending), blue (provisioning), red (failed)
- Environment filter (dev / staging / prod)

**2. Select a team:**

Click the team dropdown and select `toxins-research` (or any team with resources).

Expected: the resource table populates with all resources owned by that team.

**3. Verify cross-team isolation:**

Switch to a different team in the dropdown.

Expected: only that team's resources appear. No cross-team data leak.

**4. Check the dashboard auto-refreshes:**

With the dashboard open and the terminal alongside, create a new resource:

```bash
pecp apply -f demo/01-apply-idempotency/lambda.yaml --team toxins-research
```

Expected: the dashboard automatically reflects the new resource without
a manual page reload (TanStack Query polling).

**5. (Optional) Apply a resource and watch status:**

Apply a resource with a known slow-path (e.g. PECPAccount via Scenario 13).
The dashboard updates as the status transitions.

## What this proves

The dashboard gives non-CLI users real-time visibility into the team's
infrastructure inventory. It's read-only — resource submission stays in the CLI.
Cross-team isolation is enforced at the API level; the dashboard merely reflects
what the team-scoped endpoints return. The dashboard works without auth for PoC
and is designed to accommodate auth later without API contract changes.

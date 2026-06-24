# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — PECP PoC MVP

**Shipped:** 2026-06-24
**Phases:** 5 | **Plans:** 17 | **Timeline:** 28 days (2026-05-27 → 2026-06-24)
**Tests:** 165 passing | **LOC:** ~3,700 (Python + TypeScript/TSX)

### What Was Built

- Kubernetes-flavored control plane with `pecp apply -f resource.yaml` end-to-end: FastAPI + SQLAlchemy async + Alembic + SQLite, team-scoped, idempotent, dispatching to mock adapters via BackgroundTasks
- All 7 mock adapters (AWS Lambda/Container/DataService/Account, Kubernetes, Salesforce, AEM, Datadog, ServiceNow, JFrog) with structured activity logs, synthetic provider_metadata, and 3s async slow-path for PECPAccount
- Full `pecp` CLI (`apply/get/status/delete/team/projects/deployments/create/login`) with Rich terminal output, color-coded status badges, and `--watch` poll loop
- Multi-team model: teams, projects, environments, DeploymentRecord audit trail, soft-delete
- React 19 SPA (Vite + TanStack Query + Tailwind v4) with Inventory + Deployments tabs and manual refresh — no SSR, fully separate from API process
- Reproducible stakeholder demo: seed script → API → UI → 12-step CLI walkthrough, all verified end-to-end

### What Worked

- **Contracts-first planning** (Phase 1): locking AdapterBase ABC and the demo script before any implementation prevented scope drift and CRUD-only demo risk
- **Wave-based plan execution**: dependencies explicit per wave; parallel plans in the same wave ran without conflicts
- **Red-green test scaffold pattern**: Wave 0 tests written as RED stubs before implementation began — every plan started with a clear failure baseline
- **Pydantic v2 discriminated union** for resource kinds: adding a new kind required only one ORM row and a new Pydantic model, no changes to dispatch logic
- **Vite proxy to FastAPI**: eliminated all CORS complexity in dev, made the React SPA fully independent of API process location

### What Was Inefficient

- **Phase 2 summary noise**: some SUMMARY.md files captured code-review findings as their one-liner (e.g., "1. [Rule 3 - Blocking]...") rather than feature accomplishments — bloated MILESTONES.md auto-generation; required manual curation at close
- **Human-gated verification debt**: Phase 01 and Phase 03 VERIFICATION.md files were marked `human_needed` at verify time but never completed; surfaced as open items at milestone close 4+ weeks later
- **STATE.md phase sync gap**: STATE.md showed "Milestone complete" before VERIFICATION.md was updated to `passed`, causing `/gsd-progress` to keep routing back to `/gsd-verify-work` — required a manual fix at close

### Patterns Established

- Demo script written before any implementation: prevents CRUD-only demo pitfall and anchors all phase goals to a stakeholder-observable outcome
- `conftest.py` drops+recreates schema per test via StaticPool SQLite: prevents UniqueConstraint collisions in parallel test runs
- Module-reference import for `AsyncSessionLocal`: enables test reload pattern without fixture scope issues
- `render_as_batch=True` in Alembic env.py: required for `batch_alter_table` UniqueConstraint operations on SQLite
- STATUS_COLORS map (pending=amber, provisioning=blue, ready=green, failed=red): shared semantic between CLI Rich output and React Tailwind badge classes
- Seed script uses `Base.metadata.create_all` in `main()` for fresh-DB safety — no separate `--reset` flag needed; idempotent via `scalar_one_or_none` get-or-create

### Key Lessons

1. **Lock the adapter interface before any mock is written** — once the ABC is in place, adding adapters is additive with no control-plane changes. Reversing this order requires refactoring all existing mocks.
2. **Write the demo script first** — it anchors what "done" looks like for stakeholders and prevents the PoC from becoming a CRUD API with no demo story.
3. **VERIFICATION.md `human_needed` items age poorly** — flag them at verify time but set a deadline; stale human-needed items block milestone close weeks later.
4. **Vite proxy is the right dev pattern for separate API/UI processes** — avoids CORS configuration entirely and matches prod same-origin serving model.
5. **SUMMARY.md one-liners should describe the feature, not the code-review findings** — the milestone archive auto-generation pulls these verbatim; noise in SUMMARY.md becomes noise in MILESTONES.md.

### Cost Observations

- Model mix: sonnet for execution, opus for planning
- Notable: 28-day PoC from empty repo to demo-ready with 165 tests — wave-based parallelization kept execution efficient

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Pattern |
|-----------|--------|-------|-------------|
| v1.0 | 5 | 17 | Contracts-first, wave parallelization, demo-script anchor |

### Cumulative Quality

| Milestone | Tests | Files Changed | LOC |
|-----------|-------|---------------|-----|
| v1.0 | 165 | 231 | ~3,700 |

### Top Lessons (To Verify Across Milestones)

1. Demo script first — locks stakeholder outcome before implementation
2. Human-needed verification items need explicit deadlines or they become milestone-close debt
3. Adapter interface must be frozen before any adapter is written

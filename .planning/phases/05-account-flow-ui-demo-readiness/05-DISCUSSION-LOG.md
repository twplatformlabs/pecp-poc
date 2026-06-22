# Phase 5: Account Flow + UI + Demo Readiness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 5-account-flow-ui-demo-readiness
**Areas discussed:** Account command UX, Dashboard structure, Seed script design

---

## Account Command UX

| Option | Description | Selected |
|--------|-------------|----------|
| Flag-only, no YAML | `pecp create awsaccount --team <team>` — no YAML needed | |
| Still uses a YAML file | Consistent with `pecp apply -f file.yaml` | |
| Both paths | Flag-only primary, `-f` YAML override for power users | ✓ |

**User's choice:** Both paths
**Notes:** User noted that AWS account deletion is more nuanced than other resources (account tied to team/project, restrictions on what can be created in the account). Wanted both paths to accommodate different user personas. Decided `pecp status awsaccount` shows NO credentials — credential retrieval is a separate `pecp login awsaccount` command.

---

| Option | Description | Selected |
|--------|-------------|----------|
| --team only | Minimal surface, account name defaults to pecp-<team> | |
| --team + --env + --project | Full scoping options | ✓ |

**User's choice:** `--team + --env + --project`

---

| Option | Description | Selected |
|--------|-------------|----------|
| Key-value panel with account metadata | Show account ID, console URL, etc. | Modified |
| Full credential block with copy hints | Show fake creds in status | |

**User's choice:** No credentials in status at all — new `pecp login awsaccount` command
**Notes:** User reframed: `pecp status awsaccount` shows status + metadata only. `pecp login awsaccount` is a separate command that prints synthetic credentials as env-var export lines. No file write to `~/.aws/credentials` for PoC.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Write synthetic creds to ~/.aws/credentials | Configure named profile | |
| Print creds only, no file write | Output as `export` statements | ✓ |
| Defer to Phase 6 | Full credential management is Phase 6 | |

**User's choice:** Print the creds only, no file write

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same output, different syntax | Alias that looks up account by convention | ✓ |
| Different output | Account-specific richer display | |
| You decide | Claude picks simpler implementation | |

**User's choice:** Same output as `pecp status PECPAccount <name>`, just a convenience alias

---

| Option | Description | Selected |
|--------|-------------|----------|
| Rich Live spinner with in-place update | Pulsing live display | |
| Line-per-poll output | Timestamped line per poll | ✓ |
| Progress bar + notes stream | Rich progress bar | |

**User's choice:** Line-per-poll output

---

## Dashboard Structure

| Option | Description | Selected |
|--------|-------------|----------|
| ui/ at repo root, Vite dev server | Port 5173, FastAPI on 8000 | ✓ |
| ui/ at repo root, FastAPI serves built assets | Single process, build step needed | |
| Embedded in docs/ | Simple HTML, no build toolchain | |

**User's choice:** `ui/` at root, Vite dev server on 5173

---

| Option | Description | Selected |
|--------|-------------|----------|
| Single page with tabs: Inventory \| Deployments | One page, two tabs | ✓ |
| Two separate routes: /inventory and /deployments | React Router, sidebar nav | |
| Single table with filter controls | Unified view with filters | |

**User's choice:** Single page with tabs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Team dropdown in the top nav | Fetches available teams | ✓ |
| Team name in the URL | URL-driven, bookmarkable | |
| Hardcoded to seed team during demo | Simple, demo-focused | |

**User's choice:** Team dropdown in top nav

---

| Option | Description | Selected |
|--------|-------------|----------|
| TanStack Query with refetchInterval | Auto every 5 seconds | |
| Manual refresh button only | User-triggered | ✓ |

**User's choice:** Manual refresh button only
**Notes:** This conflicts with ROADMAP.md success criterion #3 ("data refreshes automatically"). User chose to update the success criterion to "refreshes on demand without a page reload."

---

## Seed Script Design

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent: skip existing, add missing | Safe to run repeatedly | ✓ |
| Wipe and recreate | Always clean state, destructive | |
| Fail on conflict | Forces manual DB clear | |

**User's choice:** Idempotent

---

| Option | Description | Selected |
|--------|-------------|----------|
| toxins-research + platform-engineering teams | From demo script | |
| customer-product-app + data-platform teams | Product-domain teams | |
| Let me specify the exact names | Custom | ✓ |

**User's choice:** customer-product-app, data-processing-app, data-platform, platform-engineering (4 teams)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — seed 2-3 realistic PE notes | Pre-populated notes | ✓ |
| No — notes added live during demo | More authentic | |
| Both — 1 pre-seeded, 1 added live | Shows append-only log | |

**User's choice:** Yes — 2-3 realistic PE notes pre-seeded

---

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone Python script: scripts/seed.py | Direct execution | ✓ |
| pecp CLI command: pecp seed | Consistent with CLI-first UX | |

**User's choice:** `scripts/seed.py`

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inject states directly in the DB | Fast, no adapter wait | ✓ |
| Apply resources and let adapters run | Real lifecycle, slower | |

**User's choice:** Inject states directly — write `status` column values directly to DB

---

## Claude's Discretion

- `GET /teams` endpoint for dashboard dropdown — fallback to deriving teams from resource list if endpoint not available
- Exact shadcn/ui component choices (Table, Badge, Tabs, Select)
- `pecp login awsaccount` exit code vs. error message design
- Vite proxy config vs. direct API URL in the dashboard

## Deferred Ideas

- Team onboarding flow + managing users within a team — Phase 6
- Project-repository-pipeline associations — Phase 6
- Full project association walkthrough — Phase 6
- `pecp login awsaccount` writing creds to `~/.aws/credentials` — Phase 6
- Dashboard auto-refresh / TanStack Query polling — deferred by user, easy to add later
- `pecp status awsaccount --watch` exponential backoff — fixed 2s interval for PoC
- Per-resource deployment history in dashboard — Phase 6

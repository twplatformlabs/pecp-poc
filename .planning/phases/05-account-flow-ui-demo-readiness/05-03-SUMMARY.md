---
phase: 05-account-flow-ui-demo-readiness
plan: "03"
subsystem: ui
tags: [ui, react, vite, shadcn, tanstack-query, tailwind]
status: complete

dependency_graph:
  requires:
    - 05-01-PLAN.md (CORS + GET /teams endpoint)
    - 05-02-PLAN.md (seed data for human verification)
  provides:
    - ui/ — React SPA served at localhost:5173
    - StatusBadge color contract matching CLI STATUS_COLORS
    - Inventory + Deployments tab views with shadcn Table
  affects:
    - .planning/ROADMAP.md (SC#5 wording updated)

tech_stack:
  added:
    - react@19.2.7
    - react-dom@19.2.7
    - vite@8.0.16
    - "@vitejs/plugin-react@6.0.2"
    - tailwindcss@4.3.1
    - "@tailwindcss/vite@4.3.1"
    - "@tanstack/react-query@5.101.0"
    - "lucide-react@1.21.0"
    - "shadcn@4.11.0"
    - "@base-ui/react@1.6.0"
    - "tw-animate-css@1.4.0"
    - "typescript@6.0.3"
  patterns:
    - TanStack Query v5 object-form useQuery (staleTime Infinity + refetchOnWindowFocus false)
    - Vite /api proxy with rewrite stripping prefix — Pitfall 2 mitigation
    - shadcn components via Base UI (not Radix UI) — shadcn 4.11 uses @base-ui/react
    - Tailwind v4 CSS-first via @import "tailwindcss" (no tailwind.config.ts)
    - QueryClientProvider singleton pattern via queryClient.ts

key_files:
  created:
    - ui/package.json
    - ui/vite.config.ts
    - ui/components.json
    - ui/tsconfig.json
    - ui/tsconfig.app.json
    - ui/index.html
    - ui/src/index.css
    - ui/src/main.tsx
    - ui/src/App.tsx
    - ui/src/lib/queryClient.ts
    - ui/src/lib/api.ts
    - ui/src/lib/utils.ts
    - ui/src/hooks/useTeams.ts
    - ui/src/hooks/useResources.ts
    - ui/src/components/TopNav.tsx
    - ui/src/components/StatusBadge.tsx
    - ui/src/components/InventoryTable.tsx
    - ui/src/components/DeploymentsTable.tsx
    - ui/src/components/ui/table.tsx
    - ui/src/components/ui/badge.tsx
    - ui/src/components/ui/tabs.tsx
    - ui/src/components/ui/select.tsx
    - ui/src/components/ui/button.tsx
    - ui/src/components/ui/separator.tsx
    - ui/src/components/ui/skeleton.tsx
  modified:
    - .planning/ROADMAP.md (SC#5 wording: "2 teams" -> "4 teams" per D-12)

decisions:
  - "shadcn 4.11 uses @base-ui/react (not Radix UI) for Select and Tabs — onValueChange passes (value: T | null, eventDetails) so null guard required"
  - "Tailwind v4 no config file — shadcn init confirmed absent, @import tailwindcss in CSS only"
  - "TypeScript 6.0 deprecated baseUrl — added ignoreDeprecations: 6.0 to tsconfig.app.json"
  - "shadcn init default style is now neutral (not new-york) — does not affect status badge colors"
  - "ROADMAP SC#3 was already updated to on-demand wording before this plan; SC#5 updated from 2 teams to 4 teams"

metrics:
  duration: "~25 min"
  completed: "2026-06-22"
  tasks: 4
  files: 26
---

# Phase 05 Plan 03: React Dashboard (ui/) Summary

**One-liner:** Read-only React 19 SPA at `ui/` with Vite 8 + Tailwind v4 + shadcn Base UI + TanStack Query v5 — Inventory and Deployments tabs with manual refresh only, status badge palette matching CLI STATUS_COLORS exactly.

---

## What Was Built

### Task 1: Scaffold `ui/` (commit ea0305d)

Created the full Vite + React TypeScript scaffold at `ui/`:

- `npm create vite@latest ui -- --template react-ts` — Vite 8.0.16, React 19.2.7, TypeScript 6.0.3
- Installed Tailwind CSS v4 (`tailwindcss@4.3.1`, `@tailwindcss/vite@4.3.1`) — no `tailwind.config.ts` generated (Pitfall 4 confirmed correct)
- Installed `@tanstack/react-query@5.101.0` and `lucide-react@1.21.0`
- Ran `npx shadcn@latest init --defaults` — used slate base color, CSS variables
- Added 7 shadcn components: `table`, `badge`, `tabs`, `select`, `button`, `separator`, `skeleton`
- Configured `vite.config.ts` with proxy `/api → localhost:8000` with `rewrite` function (Pitfall 2 mitigation)
- Created `queryClient.ts` with `staleTime: Infinity`, `refetchOnWindowFocus: false` (D-09)
- Wrapped App in `QueryClientProvider` in `main.tsx`
- Fixed `tsconfig.app.json` with `ignoreDeprecations: "6.0"` for TypeScript 6 path alias compatibility

### Task 2: Full UI Implementation (commit 1fd323d)

Implemented all 8 hand-authored source files:

- **`ui/src/lib/api.ts`**: `Team` and `Resource` TypeScript interfaces (matching FastAPI response shapes), `fetchTeams()` and `fetchResources(team)` with relative `/api` paths
- **`ui/src/hooks/useTeams.ts`**: `useQuery<Team[]>` with `queryKey: ['teams']`
- **`ui/src/hooks/useResources.ts`**: `useQuery<Resource[]>` with `queryKey: ['resources', team]`, `enabled: !!team`
- **`ui/src/components/StatusBadge.tsx`**: Custom `<span>` with Tailwind classes — `pending=bg-amber-100 text-amber-700`, `provisioning=bg-blue-100 text-blue-700`, `ready=bg-green-100 text-green-700`, `failed=bg-red-100 text-red-700`. No shadcn Badge variant used.
- **`ui/src/components/InventoryTable.tsx`**: shadcn Table with 5 columns (Name/Kind/Status/Environment/Project), 3-row skeleton loading state, centered PackageOpen empty state, centered AlertCircle error state
- **`ui/src/components/DeploymentsTable.tsx`**: Same table + client-side `envFilter` Select (All/dev/staging/prod), no extra API call on filter change
- **`ui/src/components/TopNav.tsx`**: PECP wordmark, team Select from `useTeams()`, Refresh button with `invalidateQueries` + `animate-spin` during fetch
- **`ui/src/App.tsx`**: `useState<'inventory' | 'deployments'>`, auto-selects first team alphabetically on load, no React Router, no `refetchInterval`

### Task 3: Human Verification Checkpoint — APPROVED

Automation pre-steps were completed:
- `npm run build` succeeds (verified in Tasks 1 and 2)
- `npx tsc --noEmit` passes

User verified:
1. `python scripts/seed.py` from repo root
2. `uvicorn pecp.api.main:app --reload --port 8000`
3. `cd ui && npm run dev`
4. Opened http://localhost:5173 and walked through all 12 visual checkpoints

**All 12 checkpoints passed. User response: "approved"**

### Task 4: ROADMAP.md SC#5 Update (commit 841d598)

Updated Phase 5 success criterion #5: "2 teams" → "4 teams" per D-12 decision.
SC#3 was already correct ("on demand" wording set in a prior session).

---

## Npm Package Versions Installed

| Package | Version |
|---------|---------|
| react | 19.2.7 |
| react-dom | 19.2.7 |
| vite | 8.0.16 |
| @vitejs/plugin-react | 6.0.2 |
| tailwindcss | 4.3.1 |
| @tailwindcss/vite | 4.3.1 |
| @tanstack/react-query | 5.101.0 |
| lucide-react | 1.21.0 |
| shadcn | 4.11.0 |
| @base-ui/react | 1.6.0 (shadcn dependency) |
| tw-animate-css | 1.4.0 (shadcn dependency) |
| typescript | 6.0.3 |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] TypeScript 6.0 baseUrl deprecation error**
- **Found during:** Task 1 — TypeScript compilation
- **Issue:** `tsconfig.json` and `tsconfig.app.json` with `baseUrl: "."` raised `TS5101: Option 'baseUrl' is deprecated` in TypeScript 6.0
- **Fix:** Added `"ignoreDeprecations": "6.0"` to both `tsconfig.app.json` and `tsconfig.json`
- **Files modified:** `ui/tsconfig.json`, `ui/tsconfig.app.json`
- **Commit:** ea0305d (included in Task 1 commit)

**2. [Rule 3 - Blocking] Base UI onValueChange null type mismatch**
- **Found during:** Task 2 — `npm run build`
- **Issue:** shadcn 4.11 uses `@base-ui/react` (not Radix UI). `Select.onValueChange` callback type is `(value: T | null, eventDetails) => void`, but plan assumed Radix UI's `(value: string) => void` signature
- **Fix:** Added null guard: `(v) => { if (v !== null) setEnvFilter(v); }` in `DeploymentsTable`; updated `TopNav` prop type `onTeamChange: (team: string | null) => void`
- **Files modified:** `ui/src/components/DeploymentsTable.tsx`, `ui/src/components/TopNav.tsx`
- **Commit:** 1fd323d (included in Task 2 commit)

**3. [Rule 1 - Bug] StatusBadge comment contained `<Badge variant=` literal**
- **Found during:** Task 2 acceptance criteria verification
- **Issue:** A code comment used the exact string `<Badge variant=...>` which caused `grep -cE "<Badge variant="` to return 1 (expected 0)
- **Fix:** Reworded comment to "shadcn Badge with variant prop" — no semantic change
- **Files modified:** `ui/src/components/StatusBadge.tsx`
- **Commit:** 1fd323d (included in Task 2 commit)

**4. [Observation] shadcn init generated neutral default style, not new-york**
- shadcn 4.11 --defaults uses the "new neutral" palette. The previous RESEARCH.md mentioned "new-york" style. This does not affect status badge colors (which use raw Tailwind bg-amber/blue/green/red-100 classes) or functional behavior. Documented as informational deviation only.
- No fix needed.

**5. [Observation] ROADMAP SC#3 already had correct wording**
- The plan's Task 4 described updating SC#3 from "refreshes automatically" to "refreshes on demand" — but SC#3 already read "on demand" at execution time. This was a prior-session fix. Only SC#5 required update ("2 teams" → "4 teams").

---

## shadcn init generated tailwind.config.ts?

**No.** Confirmed absent. Tailwind v4 is CSS-first — `@import "tailwindcss"` in `src/index.css` is the only configuration. Pitfall 4 held correctly.

---

## TypeScript Types Divergence: `ui/src/lib/api.ts:Resource` vs API Response

| Field | TS Type | API Source | Match? |
|-------|---------|------------|--------|
| `id` | `string` | `ResourceRecord.id` (hex UUID) | Yes |
| `team` | `string` | `ResourceRecord.team` | Yes |
| `kind` | `string` | `ResourceRecord.kind` | Yes |
| `name` | `string` | `ResourceRecord.name` | Yes |
| `status` | `string` | `ResourceRecord.status` | Yes |
| `env` | `string \| null` | `ResourceRecord.env` (nullable) | Yes |
| `project` | `string \| null` | `ResourceRecord.project` (nullable) | Yes |
| `created_at` | `string?` | `ResourceRecord.created_at` (datetime) | Yes (optional) |

No divergence found. The `Resource` type is a conservative subset of the full response — additional fields (e.g., `notes`, `provider_metadata`) are present in the API response but not modeled in TypeScript since the read-only dashboard does not display them.

---

## Known Stubs

None. All components render live API data via TanStack Query. No hardcoded arrays or placeholder strings in rendered output (empty state and error state messages are intentional UI copy, not stubs).

---

## Threat Flags

No new threat surface introduced beyond the plan's threat model:
- `dangerouslySetInnerHTML` — confirmed absent (`grep -r dangerouslySetInnerHTML ui/src/` returns 0)
- No new network endpoints (UI is read-only client)
- No file access patterns
- CORS origin locked to `http://localhost:5173` (Plan 01 verified)

---

## Self-Check: PASSED

**Files exist:**
- `ui/vite.config.ts` — FOUND
- `ui/src/lib/queryClient.ts` — FOUND
- `ui/src/lib/api.ts` — FOUND
- `ui/src/hooks/useTeams.ts` — FOUND
- `ui/src/hooks/useResources.ts` — FOUND
- `ui/src/components/TopNav.tsx` — FOUND
- `ui/src/components/StatusBadge.tsx` — FOUND
- `ui/src/components/InventoryTable.tsx` — FOUND
- `ui/src/components/DeploymentsTable.tsx` — FOUND
- `ui/src/App.tsx` — FOUND
- `.planning/ROADMAP.md` (updated) — FOUND

**Commits exist:**
- ea0305d (Task 1: scaffold) — FOUND
- 1fd323d (Task 2: implementation) — FOUND
- 841d598 (Task 4: ROADMAP) — FOUND

**Production build:** `cd ui && npm run build` — PASSED (✓ 2031 modules, 0 errors)
**TypeScript:** `cd ui && npx tsc --noEmit` — PASSED (exit 0)

---

## Checkpoint Status

**Task 3 (human-verify) APPROVED.** All 12 visual checkpoints passed. Plan 05-03 is fully complete. Plan 05-04 (end-to-end stakeholder demo walkthrough) can proceed.

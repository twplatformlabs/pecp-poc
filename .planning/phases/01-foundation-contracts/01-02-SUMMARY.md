---
phase: 01-foundation-contracts
plan: "02"
subsystem: documentation
tags:
  - documentation
  - demo
  - narrative
  - stakeholder
dependency_graph:
  requires: []
  provides:
    - docs/DEMO-SCRIPT.md
  affects:
    - .planning/REQUIREMENTS.md (ARCH-04 fulfilled)
tech_stack:
  added: []
  patterns:
    - Narrative-first stakeholder demo script with [expected output] placeholders per D-15
key_files:
  created:
    - docs/DEMO-SCRIPT.md
  modified: []
decisions:
  - "Demo team name is toxins-research (revised from initial payments per user feedback)"
  - "Script structure: four day-chapters covering team creation, Lambda deploy, async AWS account, and full inventory view"
  - "All [expected output] placeholders have descriptive plain-language descriptions of what Phase 5 will replace them with"
metrics:
  duration: "~30 minutes"
  completed: "2026-05-27"
  tasks_completed: 1
  files_changed: 1
requirements:
  - ARCH-04
---

# Phase 1 Plan 02: Demo Script Narrative Walkthrough Summary

**One-liner:** Stakeholder-ready narrative demo script covering new-team onboarding from `pecp team create` through Lambda deploy, async AWS account provisioning with PE notes, and dashboard inventory — all with `[expected output]` placeholders for Phase 5 replacement.

## What Was Built

`docs/DEMO-SCRIPT.md` — a single flowing markdown narrative at 268 lines that a stakeholder can read top-to-bottom in one sitting. The document follows the D-16 scenario with team `toxins-research` (revised from initial draft team name `payments` per user feedback before plan approval). Every `pecp` command is embedded in fenced `bash` code blocks; every result is represented by a structured `[expected output: ...]` placeholder that Phase 5 will replace with real captured terminal output.

The script covers four narrative chapters:

1. **Setting the scene** — introduces the team and the platform's value proposition
2. **Day one: a team is born** — `pecp team create toxins-research` and `pecp team toxins-research` with team metadata and member table placeholders
3. **Day two: deploying a Lambda** — inline YAML spec (`apiVersion: pecp/v1`, `kind: PECPLambda`, `metadata.name: toxins-research-webhook-handler`) + `pecp apply -f toxins-research-lambda.yaml --team toxins-research` + `pecp status ... --watch` with full status-transition placeholder
4. **Day three: the long-running ask** — `pecp create awsaccount --team toxins-research` returning immediately + `pecp status awsaccount --watch` showing provisioning stays in-flight with PE notes appearing mid-stream before reaching ready with synthetic credentials
5. **Day four: the full inventory** — `pecp get PECPLambda --team toxins-research` and `pecp deployments --team toxins-research --environment prod` rich-table placeholders + browser dashboard reference at `http://localhost:5173`
6. **What we proved** — closing paragraph mapping narrative back to PECP's core value proposition

## Verification

All acceptance criteria confirmed on final document:
- File exists at `docs/DEMO-SCRIPT.md`, 268 lines (>= 80 required)
- 8 `[expected output` occurrences (>= 6 required)
- 9 distinct `pecp <command>` invocations (>= 6 required)
- Literal strings `apiVersion: pecp/v1` and `kind: PECPLambda` present in inline YAML
- One fenced `yaml` code block present
- Zero references to v2-only features (no JWT/OAuth)
- All six required v1 commands present: `pecp team create`, `pecp apply`, `pecp status`, `pecp create awsaccount`, `pecp get`, `pecp deployments`

## Deviations from Plan

### User-directed revision before approval

**Team name rename: payments -> toxins-research**
- **Found during:** Human verification (Task 2 checkpoint)
- **Action:** User requested all occurrences of team name `payments` be replaced with `toxins-research` throughout the document — team name, command arguments, URLs, YAML metadata, narrative prose, derived names (`payments-lambda.yaml` -> `toxins-research-lambda.yaml`, `payments-webhook-handler` -> `toxins-research-webhook-handler`, `payments@example.com` -> `toxins-research@example.com`)
- **Commit:** `95818fc` — `docs(01-02): rename demo team from payments to toxins-research`

This was a deliberate user revision before plan sign-off, not a bug fix or plan deviation. The plan's acceptance criteria did not mandate a specific team name (only that a team name be present), so the rename satisfies all criteria.

## Threat Flags

None — this plan creates a documentation file only. No network endpoints, auth paths, file access patterns, or schema changes introduced.

## Known Stubs

The document is intentionally stub-heavy by design: every `[expected output: ...]` block is a placeholder. These are not accidental stubs — they are the deliberate Phase 5 handoff mechanism per D-15. The Phase 5 success criterion is to replace each placeholder with real captured terminal output from a running system.

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | Write docs/DEMO-SCRIPT.md narrative walkthrough | `23541bc` |
| Revision | Rename demo team from payments to toxins-research | `95818fc` |

## Self-Check: PASSED

- `docs/DEMO-SCRIPT.md` exists: FOUND
- Commit `23541bc` exists: FOUND
- Commit `95818fc` exists: FOUND

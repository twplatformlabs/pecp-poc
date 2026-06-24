# Phase 8: GitHub Integration — Plan Checker Findings

**Checked:** 2026-06-24
**Plans:** 08-01-PLAN.md (Wave 1), 08-02-PLAN.md (Wave 2)
**Verdict:** BLOCK

---

## PLAN CHECK COMPLETE

**Verdict:** BLOCK

### Dimension Scores

| # | Dimension | Score | Rationale |
|---|-----------|-------|-----------|
| 1 | Requirement Coverage | PASS | All 5 requirements (GH-01 through GH-05) appear in both plans' `requirements` fields. Tasks address every requirement. |
| 2 | Decision Fidelity | PASS | All 7 locked decisions (D-01 through D-07) are explicitly referenced with D-NN IDs in task actions and covered by tests. |
| 3 | Task Completeness | PASS | All 4 tasks across both plans have Files + Action + Verify + Done. Actions are specific and concrete. |
| 4 | Dependency Correctness | PASS | 08-01 → 07-02 (Wave 1), 08-02 → 08-01 (Wave 2). No cycles. All referenced plans exist. |
| 5 | Key Links Planned | PASS | All cross-artifact connections mapped: github.py↔base.py, __init__.py↔github.py, main.py↔__init__.py, test↔github.py, test↔models.py. |
| 6 | Scope Sanity | PASS | 2 tasks per plan. 4 files modified in 08-01, 1 file in 08-02. Well within context budget. |
| 7 | Verification Derivation | PASS | Truths are behavioral and user/developer-observable (not implementation-focused). Artifacts map to truths. |
| 8 | Nyquist Compliance | **BLOCK** | **VALIDATION.md not found.** nyquist_validation=true and RESEARCH.md has "Validation Architecture" section, but no 08-VALIDATION.md exists. Gate check 8e fails. |
| 9 | Goal-Backward Coverage | PASS | All 5 success criteria are traceable to task actions. Each SC has both implementation (08-01) and test (08-02) coverage. |
| 10 | Architectural Tier Compliance | PASS | All capabilities correctly assigned to API/Backend tier per Responsibility Map. No tier mismatches. |
| 11 | Research Resolution | FLAG | Open Questions section exists without `(RESOLVED)` suffix. No inline `RESOLVED` markers. (Questions ARE effectively resolved through D-01–D-07, but formal marker missing.) |
| 12 | Pattern Compliance | FLAG | Plans do not explicitly reference analog files from PATTERNS.md (e.g., noop.py) in task action sections. Action content is thorough but breaks pattern traceability chain. |

---

### Issues

#### [BLOCK] Dimension 8 — Nyquist Compliance (Check 8e: VALIDATION.md Gate)

```
issue:
  dimension: nyquist_compliance
  severity: blocker
  description: "VALIDATION.md not found in phase directory. Nyquist validation is enabled (config.json: nyquist_validation=true) and RESEARCH.md has a 'Validation Architecture' section, but no 08-VALIDATION.md exists."
  plan: null
  phase: 08-github-integration
  fix_hint: "Run `/gsd-plan-phase 8 --research` to regenerate, or manually create 08-VALIDATION.md from the existing test map in 08-RESEARCH.md (lines 462-502). The verification commands are already embedded in PLAN.md — VALIDATION.md is a procedural gate artifact."
```

**Context:** The RESEARCH.md already contains a comprehensive "Validation Architecture" section (lines 462-502) with test framework details, requirements-to-test map, sampling rate, and Wave 0 gaps. The PLAN.md files each have `<verification>` blocks with automated commands. The missing VALIDATION.md is a documentation gap, not a validation gap — the content exists but in the wrong file.

**Remediation:** Create 08-VALIDATION.md by extracting the "Validation Architecture" section from RESEARCH.md and cross-referencing the PLAN.md verification commands. Re-run `/gsd-plan-phase 8 --research` or manually generate.

---

#### [WARNING] Dimension 11 — Research Resolution (Open Questions Marker)

```
issue:
  dimension: research_resolution
  severity: warning
  description: "RESEARCH.md Open Questions section (line 565) lacks `(RESOLVED)` suffix and no inline `RESOLVED` markers are present."
  file: "08-RESEARCH.md"
  phase: 08-github-integration
  fix_hint: "Change heading to `## Open Questions (RESOLVED)` and add `**RESOLVED:** D-XX` inline after each question's recommendation."
```

**Context:** All three open questions ARE effectively resolved:
1. Classic PAT requirement → Resolved by plan using classic PAT (D-07 decision chain implemented)
2. DB re-fetch race condition → Resolved by D-05, D-06 (implemented in 08-01 Task 2)
3. aclose() in lifespan → Resolved by D-03, D-04 (implemented in 08-01 Task 1)

The formality of adding `RESOLVED` markers ensures traceability for downstream Phase 9/10 planners.

---

#### [WARNING] Dimension 12 — Pattern Compliance (Analog References)

```
issue:
  dimension: pattern_compliance
  severity: warning
  description: "Plan task actions do not explicitly reference analog files mapped in PATTERNS.md."
  phase: 08-github-integration
  fix_hint: "Add analog references to task actions, e.g., in 08-01 Task 2: 'Analog: src/pecp/integrations/noop.py (same ABC subclass pattern)'. In 08-02 Task 1: 'Analog: tests/test_integrations/test_noop.py (snapshot construction pattern)'."
```

**Files missing analog references in actions:**
- `src/pecp/integrations/github.py` (08-01 Task 2) — analog: `test_noop.py`
- `tests/test_integrations/test_github.py` (08-02 Task 1) — analog: `test_noop.py`, `test_registry.py`
- `src/pecp/integrations/base.py` modification (08-01 Task 1) — analog: self-modification
- `src/pecp/api/main.py` modification (08-01 Task 1) — analog: self-modification

**Impact:** Low — action content is sufficiently detailed. Pattern traceability is broken for future audits but execution is unaffected.

---

### Detailed Analysis

#### Goal-Backward Trace (Success Criteria → Tasks)

| Success Criterion | Implementation (08-01) | Test (08-02) | Status |
|---|---|---|---|
| SC1: Team → GitHub team + slug writeback | Task 2: `on_team_create` POSTs /orgs/{org}/teams, calls `_write_team_slug` | Test 3: `test_on_team_create_creates_team_and_writes_slug` | ✅ |
| SC2: Project → GitHub repo + ProjectRepo writeback | Task 2: `on_project_create` POSTs /orgs/{org}/repos, calls `_write_project_repo` | Test 5: `test_on_project_create_creates_repo_and_writes_url` | ✅ |
| SC3: Member add/remove sync one-way | Task 2: `on_member_add` PUT, `on_member_remove` DELETE, errors caught | Tests 7-11: member add/remove/404/null-slug/user-not-found | ✅ |
| SC4: Errors (rate limit, 422, 404) non-fatal | Task 2: 422 handled inline, all hooks catch/re-raise | Tests 4, 6, 8, 10, 11, 12: 422/404/429 edge cases | ✅ |
| SC5: No real GitHub calls during pytest | N/A (test architecture) | All 13 tests via `httpx_mock` fixture | ✅ |

#### Decision Trace (D-01 through D-07)

| Decision | Plan | Task | Action Reference | Test |
|---|---|---|---|---|
| D-01: 422 skip, no GET-fallback | 08-01 | Task 2 | `on_team_create`, `on_project_create` 422 handlers | 08-02 Tests 4, 6 |
| D-02: DELETE 404 = success | 08-01 | Task 2 | `on_member_remove` D-02 reference | 08-02 Test 10 |
| D-03: aclose() on ABC | 08-01 | Task 1, 2 | `IntegrationBase.aclose()` addition, `GitHubIntegration.aclose()` | 08-02 Test 13 |
| D-04: Lifespan shutdown wiring | 08-01 | Task 1 | `main.py` lifespan iteration | 08-02 imports test |
| D-05: DB re-fetch in member hooks | 08-01 | Task 2 | `_fetch_team_slug` helper, D-05 reference | 08-02 Test 8 |
| D-06: NULL slug → warn + skip | 08-01 | Task 2 | Member hooks NULL check, D-06 reference | 08-02 Test 8 (caplog) |
| D-07: Name sanitization | 08-01 | Task 2 | `_sanitize` helper, D-07 reference | 08-02 Test 2 |

#### Threat Model Coverage

Both plans have `<threat_model>` blocks with:
- Trust boundary tables ✅
- STRIDE threat registers ✅ (T-08-01 through T-08-03 in each)
- All threats have Category, Component, Disposition, Mitigation Plan ✅
- ASVS Level 1 compliance referenced from RESEARCH.md ✅

**Observations:**
- T-08-01 (Information Disclosure) is well-handled — PAT never in log format strings
- T-08-02 (Tampering of repo names) accepted with route-layer Pydantic validation as mitigation
- T-08-03 (Rate limiting) mitigated through fire_integrations exception handling
- No threats identified for aclose() failure during shutdown (low impact — server is stopping)
- No threats identified for race condition between sequential background tasks (medium risk, accepted per D-05/D-06 tradeoff)

#### Cross-Plan Data Contract Analysis

| Data Entity | Plan 08-01 | Plan 08-02 | Compatible? |
|---|---|---|---|
| TeamRecord.github_team_slug | Written via `_write_team_slug` in new session | Read via `db_session.refresh()` | ✅ Same value |
| ProjectRepoRecord | Inserted via `_write_project_repo` in new session | Queried via `db_session` | ✅ Same data |
| TeamSnapshot.id / TeamRecord.id | Used as lookup key | Used as lookup key | ✅ Same key |
| httpx.AsyncClient | Created per GitHubIntegration instance | Not mocked — used via httpx_mock transport | ✅ pytest-httpx transparent |

No conflicting transformations. All shared data paths are read-after-write with isolation. ✅

---

### Recommendations

#### Required Before Execution

1. **Create 08-VALIDATION.md** (BLOCKER) — Extract the Validation Architecture from RESEARCH.md (lines 462-502) into a standalone validation artifact. The test map, sampling rate, and Wave 0 gaps are already documented; they just need to be in the right file.

#### Recommended Before Execution

2. **Add `(RESOLVED)` markers to Open Questions** in RESEARCH.md (WARNING) — Update heading to `## Open Questions (RESOLVED)` and add inline `**RESOLVED:** D-XX` references to each question.

3. **Add analog references** to task actions in both plans (WARNING) — Reference the PATTERNS.md analogs to maintain traceability for future phases and audits.

---

*Phase: 08-github-integration*
*Plan checker completed: 2026-06-24*

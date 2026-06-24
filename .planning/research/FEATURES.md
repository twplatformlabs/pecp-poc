# Feature Research — PECP v1.1 GitHub Onboarding Integration

**Domain:** Platform Engineering Control Plane — GitHub API integration layer
**Researched:** 2026-06-24
**Confidence:** MEDIUM (GitHub REST API — stable, well-documented, trained through Aug 2025)

> This file updates the v1.0 FEATURES.md with GitHub-specific features for the v1.1 milestone.
> Existing v1.0 features (team CRUD, project CRUD, resource provisioning, CLI, dashboard) are already built.
> Focus is exclusively on the NEW GitHub integration features.

---

## GitHub API Categories

### GitHub Org Teams API

**Endpoint:** `POST /orgs/{org}/teams`

| Parameter | Required | Type | Notes |
|-----------|----------|------|-------|
| `name` | Yes | string | Team display name. GitHub auto-derives `slug` (lowercase, spaces → hyphens). |
| `description` | No | string | Optional team description. |
| `privacy` | No | `secret` \| `closed` | Default `secret`. `closed` = visible to all org members. |
| `parent_team_id` | No | int | For nested teams. Not needed for PECP PoC. |

**Response (201 Created):**
- `id` — numeric team ID
- `slug` — URL-safe identifier used in all subsequent API calls (e.g., `platform-team`)
- `html_url` — `https://github.com/orgs/{org}/teams/{slug}`
- `members_url`, `repos_url`

**Idempotency:** NOT idempotent. If team name already exists, returns `422 Unprocessable Entity` with message `"name already exists"`. Pattern: catch 422, then `GET /orgs/{org}/teams` (paginated) to find the existing team by name and retrieve its slug.

**Confidence:** MEDIUM (trained knowledge, GitHub REST API v2022-11-28)

---

### GitHub Org Repos API

**Endpoint:** `POST /orgs/{org}/repos`

| Parameter | Required | Type | Notes |
|-----------|----------|------|-------|
| `name` | Yes | string | Repo name. Max 100 chars. Alphanumeric + hyphens/underscores/dots. No spaces. |
| `description` | No | string | Optional. |
| `private` | No | bool | Default `false`. Private repos require org plan. For PoC demo: public is fine. |
| `auto_init` | No | bool | If `true`, creates initial commit with README. Default `false` = empty repo. |

**Naming for PECP:** `{team-name}-{project-name}` — normalize both parts (lowercase, spaces → hyphens) before sending to GitHub.

**Response (201 Created):**
- `full_name` — `{org}/{repo-name}`
- `html_url` — `https://github.com/{org}/{repo-name}` — store this as `repo_url` in `ProjectRepo`
- `clone_url`, `ssh_url`

**Idempotency:** NOT idempotent. If repo name already exists in org, returns `422` with `"name already exists on this account"`. Pattern: catch 422, then `GET /repos/{org}/{repo-name}` to retrieve the existing repo URL.

**Confidence:** MEDIUM (trained knowledge, GitHub REST API v2022-11-28)

---

### GitHub Team Membership API

**Add member — `PUT /orgs/{org}/teams/{team_slug}/memberships/{username}`**

| Parameter | Notes |
|-----------|-------|
| `role` | Body param: `"member"` (default) or `"maintainer"`. Use `"member"` for all PECP syncs. |

**Response (200 OK):**
- `state`: `"active"` (user is org member) or `"pending"` (invitation sent — not an error)
- `role`: the assigned role

**Idempotency:** IDEMPOTENT. Calling when user is already a member returns 200. Safe to re-run.

**Pending state:** If the GitHub username is not an existing org member, GitHub sends an org invitation and returns `state: "pending"`. This is expected behavior — treat it as success, do not raise an error.

**User not found:** If the GitHub username does not exist on GitHub at all, returns `422`. Log and skip — do not fail the PECP member add operation.

---

**Remove member — `DELETE /orgs/{org}/teams/{team_slug}/memberships/{username}`**

**Response:** `204 No Content`

**Idempotency:** IDEMPOTENT. If user is not in team, still returns 204. Safe to re-run.

---

**Check membership — `GET /orgs/{org}/teams/{team_slug}/memberships/{username}`**

Returns membership object or `404` if not a member. Useful for diagnostics but not needed in the PECP hot path.

**Confidence:** MEDIUM (trained knowledge, GitHub REST API v2022-11-28)

---

## PAT Scope Requirements

| Operation | Classic PAT Scope | Fine-Grained PAT Permission |
|-----------|-------------------|-----------------------------|
| Create org team | `admin:org` | Members: read+write, Administration: read+write |
| Create org repo | `repo` + `admin:org` | Repository: Contents read+write, Administration read+write |
| Add/remove team member | `admin:org` | Members: read+write |
| Read team info | `read:org` | Members: read |

**Recommendation for PECP PoC:** Use a Classic PAT with `admin:org` scope. This single scope covers all three operations. Fine-grained PATs require more permissions combinations to manage — not worth the setup complexity for a PoC demo.

**Token owner requirement:** The PAT owner must be an org owner or have admin org membership. A regular member PAT with `admin:org` will return `403` on team creation.

**Confidence:** MEDIUM

---

## Rate Limit Behavior

| Limit Type | Threshold | Response Code | Header |
|------------|-----------|---------------|--------|
| Primary rate limit | 5,000 requests/hour per PAT | `403` or `429` | `X-RateLimit-Remaining`, `X-RateLimit-Reset` |
| Secondary rate limit | ~100 mutation requests/minute (undocumented, observed) | `403` | `Retry-After` |

**Response headers to read:**
- `X-RateLimit-Limit` — quota ceiling (5000)
- `X-RateLimit-Remaining` — calls remaining in window
- `X-RateLimit-Reset` — Unix timestamp when window resets
- `Retry-After` — seconds to wait after secondary limit hit

**PECP PoC volumes:** A PoC demo creates tens of teams/repos, not thousands. Primary rate limit will never be hit. Secondary limits are only a concern if PECP fires multiple GitHub calls concurrently in a tight loop (e.g., bulk import). Sequential, on-demand calls are safe.

**Error handling policy for PECP:**
- `401 Unauthorized` → PAT is invalid or expired; log CRITICAL, disable GitHub integration for this request
- `403` with rate limit message → log WARNING, skip GitHub sync for this operation; do not retry in PoC
- `422 Unprocessable Entity` → name exists (team/repo) or user not found (membership); handle per operation above
- `404 Not Found` → team slug mismatch or repo gone; log WARNING

**Confidence:** MEDIUM

---

## Idempotency Matrix

| Operation | HTTP Method | Idempotent? | On Conflict | Recovery Pattern |
|-----------|-------------|-------------|-------------|-----------------|
| Create GitHub team | `POST /orgs/{org}/teams` | NO | `422` name exists | Catch 422 → `GET /orgs/{org}/teams` → find by name → use existing slug |
| Create GitHub repo | `POST /orgs/{org}/repos` | NO | `422` name exists | Catch 422 → `GET /repos/{org}/{name}` → use existing `html_url` |
| Add team member | `PUT /orgs/{org}/teams/{slug}/memberships/{user}` | YES | Returns 200 | No special handling needed |
| Remove team member | `DELETE /orgs/{org}/teams/{slug}/memberships/{user}` | YES | Returns 204 | No special handling needed |

**Key insight:** Team and repo creation require explicit create-or-fetch logic. Membership operations are naturally safe to re-run.

---

## Table Stakes (For v1.1 GitHub Integration)

Features that must work for the integration to be considered functional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `IntegrationBase` ABC with lifecycle hooks | Any integration framework needs a defined contract — without it, GitHub becomes hardwired and Jira/Slack become impossible | LOW | Four hooks: `on_team_create`, `on_project_create`, `on_member_add`, `on_member_remove` — all async, all no-op by default |
| `INTEGRATION_REGISTRY` dispatcher | Hooks must be fired after successful DB write, not before — registry pattern is the only safe way to decouple | LOW | Fire in registration order; errors logged but non-fatal |
| GitHub team creation on `pecp team create` | Core v1.1 requirement — PECP team creation without GitHub team is a broken integration | MEDIUM | Store `github_team_slug` on `TeamRecord`; needed for all subsequent membership calls |
| GitHub repo creation on `pecp project create` | Ditto — the onboarding promise is "team + project = GitHub team + repo" | MEDIUM | Repo name = `{team-name}-{project-name}` (normalized); store `repo_url` in `ProjectRepo` |
| Member add/remove syncs to GitHub team | One-way sync is the stated PECP → GitHub pattern; without it, PECP membership and GitHub diverge immediately | MEDIUM | PUT is idempotent; DELETE is idempotent; user-not-found is a logged warning, not an error |
| Graceful degradation when GitHub is unavailable | Integration errors must not break PECP operations — if PAT is missing or GitHub is down, PECP still works | LOW | `INTG-03`: missing env vars → integration disabled with logged warning; GitHub errors → log, skip, continue |
| Store GitHub identifiers on PECP entities | `github_team_slug` on Team, `repo_url` on ProjectRepo — needed for display in CLI and for subsequent API calls to GitHub | LOW | Two Alembic migrations; one for `TeamRecord.github_team_slug`, one for new `ProjectRepo` table |
| CLI shows GitHub links in output | Users onboarding expect to see "your GitHub team is here" after `pecp team create` | LOW | `pecp team create` → GitHub team URL; `pecp team <name>` → GitHub row; `pecp project <name>` → repo list |

---

## Differentiators (For v1.1)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `IntegrationBase` ABC enabling Jira/Slack in same framework | The hook framework proves PECP is an extensible onboarding platform, not a one-off GitHub script | LOW | Blank implementations for Jira/Slack placeholders can be shown in demo even if not wired |
| `pecp project repo add` — multiple repos per project | Acknowledges real-world projects needing multiple repos (frontend, backend, infra) without forcing a new project per repo | MEDIUM | `ProjectRepo` join table supports one-to-many; CLI surfaces `repo add` subcommand |
| Non-blocking GitHub calls via BackgroundTasks | GitHub API latency is 100–500ms per call; making CLI wait blocks UX. Firing async means `pecp team create` returns immediately | MEDIUM | Already using FastAPI BackgroundTasks for adapter dispatch — same pattern applies here |
| Structured error logging per integration call | Ops visibility: when GitHub sync fails, the log shows exactly which call failed, with what error code, for which team/user | LOW | Matters for demo: show that a failure is handled cleanly, not silently |

---

## Anti-Features (Explicitly Exclude from v1.1)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Two-way member sync (GitHub → PECP) | Requires webhook receiver, signature validation, event parsing, idempotent DB writes — 3x the complexity of one-way sync | One-way only; document webhook path as v2 requirement |
| GitHub team permission management (read/write/admin on repos) | Flat permissions sufficient for PoC demo; permission matrix adds significant API surface | Default `push` permission; defer permission tiers to v2 |
| Repo templates | Adding template support requires GitHub template repos to exist, adds conditional API logic | Empty repo (`auto_init: false`); teams add their own initial commit |
| GitHub Actions setup in new repos | Out of scope — PECP provisions repos, not CI/CD config | Document as a future `on_project_create` hook |
| Retry loops for GitHub failures | Adds complexity (exponential backoff, dead-letter queue) with zero demo value | Log failure clearly; mark operation as best-effort; add retry in v2 with ARQ job queue |
| GitLab / Bitbucket support | GitHub first; parallel implementations before the pattern is proven is premature optimization | `IntegrationBase` ABC is the extension point; implement other VCS providers in v2+ |
| GitHub org invitation management | Inviting non-org members is a GitHub concern; PECP should not manage org membership, only team membership | If user is not an org member, GitHub sends invitation automatically (state=pending); PECP treats this as success |
| Webhook receiver for org events | Requires public ingress, signature validation, event routing — out of scope for internal PoC | One-way push only |

---

## Feature Dependencies

```
IntegrationBase ABC + INTEGRATION_REGISTRY
  └── required by: GitHubIntegration
        ├── on_team_create
        │     └── requires: github_team_slug stored on TeamRecord (DATA-01)
        │           └── required by: on_member_add / on_member_remove (need slug for PUT/DELETE calls)
        ├── on_project_create
        │     └── requires: ProjectRepo table (DATA-02)
        │           └── required by: pecp project repo add, pecp project <name> listing
        ├── on_member_add
        │     └── requires: github_team_slug on team (from on_team_create) — if slug absent, skip with warning
        └── on_member_remove
              └── requires: github_team_slug on team (from on_team_create) — if slug absent, skip with warning

Alembic migration (DATA-03)
  └── required by: DATA-01 (github_team_slug column) + DATA-02 (ProjectRepo table)
        └── must land before any GitHub integration code can store identifiers

GITHUB_PAT + GITHUB_ORG env vars
  └── required by: GitHubIntegration instantiation
        └── absent → integration disabled (INTG-03) — no crash, no GitHub calls
```

### Dependency Notes

- `on_member_add` / `on_member_remove` **require the team's `github_team_slug` to be populated.** If a team was created before GitHub integration was enabled, the slug will be null. Handle gracefully: skip sync, log warning, do not error.
- The `ProjectRepo` table must exist before `on_project_create` can persist repo URLs. Alembic migration must run first.
- `pecp project repo add` is a new CLI command — requires both `ProjectRepo` table and a `POST /projects/{id}/repos` API endpoint that were not in v1.0.

---

## MVP Definition for v1.1

### Launch With (v1.1 — required to close milestone)

- [ ] `IntegrationBase` ABC + `INTEGRATION_REGISTRY` — hook framework (INTG-01, INTG-02, INTG-03)
- [ ] `GitHubIntegration` with real httpx calls (GH-01)
- [ ] Team creation → GitHub team + store slug (GH-02, DATA-01, CLI-12, CLI-13, API-01, API-02)
- [ ] Project creation → GitHub repo + store URL in ProjectRepo (GH-03, DATA-02, DATA-03, CLI-14, CLI-15, API-04)
- [ ] Member add/remove → GitHub team membership sync (GH-04, CLI-17, API-03)
- [ ] GitHub API errors handled gracefully (GH-05)
- [ ] `pecp project repo add` CLI subcommand (CLI-16)

### Add After Validation (v2)

- [ ] Two-way sync via GitHub webhook receiver — when teams want GitHub as the authoritative source
- [ ] Retry queue for failed GitHub syncs — ARQ job queue, already planned for v2
- [ ] Jira integration — `on_team_create` → Jira project, `on_project_create` → Jira board
- [ ] Slack integration — `on_team_create` → Slack channel

### Future Consideration (v3+)

- [ ] Repo templates — `on_project_create` uses org template repo
- [ ] GitHub Actions bootstrap — add workflow files to new repos
- [ ] GitLab / Bitbucket `IntegrationBase` implementations

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| IntegrationBase ABC + registry | HIGH — unlocks all integrations | LOW | P1 |
| GitHub team create on team create | HIGH — core demo moment | MEDIUM | P1 |
| GitHub repo create on project create | HIGH — core demo moment | MEDIUM | P1 |
| Member add/remove sync | HIGH — proves one-way sync pattern | MEDIUM | P1 |
| Graceful degradation (no PAT = disabled) | HIGH — prevents regressions | LOW | P1 |
| Alembic migration (github_team_slug + ProjectRepo) | HIGH — all GitHub features depend on it | LOW | P1 |
| `pecp project repo add` | MEDIUM — one-to-many repos per project | MEDIUM | P1 |
| CLI GitHub links in output | MEDIUM — demo UX, stakeholder expectation | LOW | P1 |
| Non-blocking async via BackgroundTasks | MEDIUM — UX responsiveness | LOW | P2 |
| Structured error logging per call | MEDIUM — ops visibility | LOW | P2 |
| Two-way sync (webhook) | LOW for PoC | HIGH | P3 |
| Retry loop for failures | LOW for PoC | MEDIUM | P3 |

---

## One-Way Sync Design Principles

These inform implementation decisions across all GitHub integration features:

1. **PECP is the source of truth** — never read GitHub state to reconcile. Only write. GitHub is a downstream effect, not a co-owner of state.

2. **Fire-and-forget with structured logging** — GitHub calls happen in FastAPI BackgroundTasks. The PECP API response to the CLI is immediate; GitHub sync happens in the background. Errors are logged with full context (operation, team, user, HTTP status, response body).

3. **Store identifiers on PECP entities** — `github_team_slug` on `TeamRecord`, `repo_url` in `ProjectRepo`. This is the only state PECP needs to make subsequent GitHub calls and to display links in CLI/UI.

4. **Create-or-fetch for non-idempotent operations** — Teams and repos: try `POST`, catch `422`, do `GET` to retrieve existing. Membership: `PUT` and `DELETE` are inherently idempotent — no special handling needed.

5. **Error taxonomy for exception handlers:**
   - `401 Unauthorized` → PAT invalid; log CRITICAL; skip all GitHub calls for this request
   - `403` (secondary rate limit or insufficient scope) → log WARNING; skip sync; do not retry
   - `422` on team/repo create → name already exists; run create-or-fetch
   - `422` on member add (user not found on GitHub) → log WARNING; skip membership sync
   - `404` on membership calls → team slug mismatch; log WARNING; skip
   - `state: "pending"` on member add → user received org invitation; treat as success

6. **No retry loops in PoC** — complexity without demo value. Log clearly. When ARQ job queue lands in v2, retries become straightforward.

---

## Sources

- GitHub REST API documentation (v2022-11-28) — training knowledge through Aug 2025 (MEDIUM confidence)
- PECP v1.1 REQUIREMENTS.md — requirements INTG-01 through DATA-03
- PECP PROJECT.md — existing v1.0 architecture (FastAPI BackgroundTasks, httpx already in stack)

---
*Feature research for: PECP v1.1 GitHub Onboarding Integration*
*Researched: 2026-06-24*

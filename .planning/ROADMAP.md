# Roadmap: PECP — Platform Engineering Control Plane

## Milestones

- ✅ **v1.0 PoC MVP** — Phases 1–5 (shipped 2026-06-24) — [Archive](.planning/milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 GitHub Onboarding Integration** — Phases 6–10 (in progress)

## Phases

<details>
<summary>✅ v1.0 PoC MVP (Phases 1–5) — SHIPPED 2026-06-24</summary>

- [x] **Phase 1: Foundation + Contracts** — Lock adapter interface, auth stub, and demo script before any code is written (3/3 plans) — completed 2026-05-28
- [x] **Phase 2: Core Engine** — Dispatcher, state machine, all 7 mock adapters, all 6 resource kinds (4/4 plans) — completed 2026-05-28
- [x] **Phase 3: REST API + Core CLI** — Running FastAPI server, idempotent apply, `pecp apply/get/delete/status` (3/3 plans) — completed 2026-06-14
- [x] **Phase 4: Teams, Projects, Deployments** — Team model, project grouping, environment-scoped deployment queries, team CLI commands (3/3 plans) — completed 2026-06-15
- [x] **Phase 5: Account Flow + UI + Demo Readiness** — PECPAccount async demo, CLI account commands, React dashboard, seed data (4/4 plans) — completed 2026-06-22

</details>

### v1.1 GitHub Onboarding Integration (Phases 6–10)

- [ ] **Phase 6: Data Model + Migration** - Add `github_team_slug` to TeamRecord and create ProjectRepo table via one Alembic migration
- [ ] **Phase 7: Integration Hook Framework** - Define `IntegrationBase` ABC and `INTEGRATION_REGISTRY` dispatcher; lock the contract before any GitHub code
- [ ] **Phase 8: GitHub Integration** - Implement `GitHubIntegration` with real httpx GitHub API calls for team, repo, and member operations
- [ ] **Phase 9: Service Layer + API Updates** - Extract service layer, wire commit-before-hook dispatch, and expose new GitHub-enriched API endpoints
- [ ] **Phase 10: CLI Updates** - Surface GitHub links and member sync in all relevant `pecp` CLI commands

## Phase Details

### Phase 6: Data Model + Migration
**Goal**: The database schema supports GitHub integration fields, unblocking all subsequent phases
**Depends on**: Nothing (unblocks everything; no code dependencies)
**Requirements**: DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. Existing team records in the database are not broken — `github_team_slug` is nullable and existing rows retain their values
  2. A new `ProjectRepo` row can be inserted with a `project_id` FK, `repo_name`, `repo_url`, and `created_at`
  3. The Alembic migration runs cleanly from scratch (`alembic upgrade head`) and rolls back cleanly (`alembic downgrade -1`)
  4. All existing tests pass without modification after the migration is applied
**Plans**: 1 plan
Plans:
- [ ] 06-01-PLAN.md — models.py changes + Alembic migration 0004 + upgrade/downgrade smoke test (DATA-01, DATA-02, DATA-03)

### Phase 7: Integration Hook Framework
**Goal**: A contract-locked `IntegrationBase` ABC and `INTEGRATION_REGISTRY` are in place and safely fire hooks after DB commits — no GitHub code yet
**Depends on**: Phase 6
**Requirements**: INTG-01, INTG-02, INTG-03
**Success Criteria** (what must be TRUE):
  1. A no-op integration implementing `IntegrationBase` can be registered and receives `on_team_create` / `on_project_create` / `on_member_add` / `on_member_remove` calls after a team or project is created
  2. A failing integration (raises exception) does not prevent the PECP team/project creation from succeeding — the error is logged and the primary operation returns success
  3. Starting the server with `GITHUB_PAT` / `GITHUB_ORG` unset logs a warning but does not crash
  4. Hooks are fired after `session.commit()`, not before — verifiable by a test that asserts the DB row exists when the hook runs
**Plans**: TBD

### Phase 8: GitHub Integration
**Goal**: `GitHubIntegration` performs real GitHub API operations for team creation, repo creation, and member sync — all errors are handled gracefully
**Depends on**: Phase 7
**Requirements**: GH-01, GH-02, GH-03, GH-04, GH-05
**Success Criteria** (what must be TRUE):
  1. Creating a PECP team (with `GITHUB_PAT` + `GITHUB_ORG` set) results in a GitHub team being created and `TeamRecord.github_team_slug` being populated
  2. Creating a PECP project results in an empty GitHub repo named `{org}/{team-name}-{project-name}` being created and its URL stored in `ProjectRepo`
  3. Adding and removing a team member syncs one-way to the GitHub team membership — PECP operation succeeds regardless of whether the GitHub username is found
  4. GitHub API errors (rate limit, 422 "already exists", user not found) are caught, logged with context, and do not fail the PECP operation
  5. All GitHub HTTP calls are intercepted in tests via `pytest-httpx` — no real GitHub API calls are made during `pytest`
**Plans**: TBD
**UI hint**: no

### Phase 9: Service Layer + API Updates
**Goal**: API responses include GitHub data (slugs, URLs, repos list) and new endpoints for member management and additional repo linking are live
**Depends on**: Phase 8
**Requirements**: API-01, API-02, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. `POST /teams` response body contains `github_team_slug` and `github_team_url` when GitHub integration is active
  2. `GET /teams/{name}` response includes `github_team_slug`, `github_team_url`, and a `repos` list drawn from the `ProjectRepo` table
  3. `POST /teams/{name}/members` and `DELETE /teams/{name}/members/{username}` endpoints exist, update PECP membership, and trigger GitHub team membership sync
  4. `POST /projects` response includes `github_repo_url`; `POST /projects/{id}/repos` creates and links an additional GitHub repo
**Plans**: TBD

### Phase 10: CLI Updates
**Goal**: Every `pecp` command that touches teams, projects, or members surfaces GitHub links and syncs membership through the updated API
**Depends on**: Phase 9
**Requirements**: CLI-12, CLI-13, CLI-14, CLI-15, CLI-16, CLI-17
**Success Criteria** (what must be TRUE):
  1. `pecp team create <name>` output includes a `GitHub team:` line with the full org team URL after successful creation
  2. `pecp team <name>` panel shows a "GitHub" row with the team URL and PECP member count
  3. `pecp project create <name> --team <team>` output includes a `GitHub repo:` line with the created repo URL
  4. `pecp project <name> --team <team>` lists all linked repos with their GitHub URLs
  5. `pecp project repo add <repo-name> --project <project> --team <team>` creates a new GitHub repo and links it to the project
  6. `pecp team member add <github-username> <team>` and `pecp team member remove <github-username> <team>` update PECP membership and sync to GitHub
**Plans**: TBD
**UI hint**: no

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation + Contracts | v1.0 | 3/3 | Complete | 2026-05-28 |
| 2. Core Engine | v1.0 | 4/4 | Complete | 2026-05-28 |
| 3. REST API + Core CLI | v1.0 | 3/3 | Complete | 2026-06-14 |
| 4. Teams, Projects, Deployments | v1.0 | 3/3 | Complete | 2026-06-15 |
| 5. Account Flow + UI + Demo Readiness | v1.0 | 4/4 | Complete | 2026-06-22 |
| 6. Data Model + Migration | v1.1 | 0/1 | Not started | - |
| 7. Integration Hook Framework | v1.1 | 0/0 | Not started | - |
| 8. GitHub Integration | v1.1 | 0/0 | Not started | - |
| 9. Service Layer + API Updates | v1.1 | 0/0 | Not started | - |
| 10. CLI Updates | v1.1 | 0/0 | Not started | - |

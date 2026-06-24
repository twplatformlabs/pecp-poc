# Requirements: PECP — v1.1 GitHub Onboarding Integration

**Defined:** 2026-06-24
**Core Value:** A team can go from zero to provisioned infrastructure by writing a YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline runs, or which ticket gets filed.

## v1.1 Requirements

### Integration Hook Framework

- [x] **INTG-01**: An `IntegrationBase` ABC defines lifecycle hooks: `on_team_create(team)`, `on_project_create(project, team)`, `on_member_add(user, team)`, `on_member_remove(user, team)` — all async, all optional (default no-op)
- [x] **INTG-02**: An `INTEGRATION_REGISTRY` (list of `IntegrationBase` instances) is consulted by team/project/member service layer after successful DB writes — integrations are fired in registration order, errors logged but non-fatal to the primary operation
- [x] **INTG-03**: Integration configuration is loaded from environment variables at startup — missing config disables the integration with a logged warning, does not crash the server

### GitHub Integration

- [x] **GH-01**: A `GitHubIntegration` class implements `IntegrationBase` using real httpx calls to the GitHub API, authenticated via `GITHUB_PAT` env var, scoped to `GITHUB_ORG` env var
- [x] **GH-02**: `on_team_create` creates a GitHub team in the org with the same name as the PECP team; the resulting GitHub team slug is stored on `TeamRecord.github_team_slug`
- [x] **GH-03**: `on_project_create` creates an empty GitHub repository named `{org}/{team-name}-{project-name}`; the repo URL is stored in a new `ProjectRepo` join table (`project_id`, `repo_url`, `repo_name`)
- [x] **GH-04**: `on_member_add` adds the user (by GitHub username) to the GitHub team; `on_member_remove` removes them — one-way sync, PECP is the source of truth
- [x] **GH-05**: GitHub API errors (rate limit, user not found, team already exists) are caught, logged with context, and return a structured error without failing the PECP operation

### CLI & Display

- [x] **CLI-12**: `pecp team create <name>` output includes a GitHub team link line after successful creation: `GitHub team: https://github.com/orgs/{org}/teams/{slug}`
- [x] **CLI-13**: `pecp team <name>` panel includes a "GitHub" row showing the team URL and current member count (from PECP, not re-fetched from GitHub)
- [x] **CLI-14**: `pecp project create <name> --team <team>` output includes the created repo URL: `GitHub repo: https://github.com/{org}/{team-name}-{project-name}`
- [x] **CLI-15**: `pecp project <name> --team <team>` lists all linked repos with their GitHub URLs
- [x] **CLI-16**: `pecp project repo add <repo-name> --project <project> --team <team>` creates an additional empty GitHub repo `{org}/{team-name}-{repo-name}` and links it to the project
- [x] **CLI-17**: `pecp team member add <github-username> <team>` adds the user to PECP team membership and syncs to GitHub team; `pecp team member remove <github-username> <team>` does the reverse

### API

- [x] **API-01**: `POST /teams` response body includes `github_team_slug` and `github_team_url` fields when GitHub integration is active
- [x] **API-02**: `GET /teams/{name}` response includes `github_team_slug`, `github_team_url`, and `repos` list (from ProjectRepo table)
- [x] **API-03**: `POST /teams/{name}/members` body accepts `{"username": "<github-username>", "role": "owner|contributor"}` and syncs to GitHub; `DELETE /teams/{name}/members/{username}` removes and desyncs
- [x] **API-04**: `POST /projects` response includes `github_repo_url` when GitHub integration is active; `POST /projects/{id}/repos` creates and links additional repos

### Data Model

- [x] **DATA-01**: `TeamRecord` gains `github_team_slug VARCHAR` (nullable) — populated on team creation when GitHub integration is active
- [x] **DATA-02**: New `ProjectRepo` table: `id`, `project_id` (FK), `repo_name`, `repo_url`, `created_at` — one project maps to many repos
- [x] **DATA-03**: Alembic migration adds both schema changes atomically

## Future Requirements (v2+)

- Two-way member sync — GitHub team membership changes reflected back into PECP
- Jira integration: `on_team_create` creates a Jira project; `on_project_create` creates a Jira board
- Slack integration: `on_team_create` creates a Slack channel
- Repo template support: project creation can use a GitHub template repository
- Webhook receiver: GitHub org webhooks update PECP state (member added/removed via GitHub UI)

## Out of Scope (v1.1)

| Feature | Reason |
|---------|--------|
| Two-way member sync | Complexity of webhook receiver; one-way is sufficient to prove the pattern |
| GitLab / Bitbucket support | GitHub first; `IntegrationBase` pattern enables future additions |
| Jira / Slack integrations | Defined as future; architecture supports them via same hook pattern |
| Repo templates | Empty repo sufficient for PoC demo |
| GitHub Actions setup in new repos | Out of scope for onboarding PoC |
| GitHub team permission management (read/write/admin) | Flat permissions sufficient for demo |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 6 | Complete |
| DATA-02 | Phase 6 | Complete |
| DATA-03 | Phase 6 | Complete |
| INTG-01 | Phase 7 | Pending |
| INTG-02 | Phase 7 | Pending |
| INTG-03 | Phase 7 | Pending |
| GH-01 | Phase 8 | Pending |
| GH-02 | Phase 8 | Pending |
| GH-03 | Phase 8 | Pending |
| GH-04 | Phase 8 | Pending |
| GH-05 | Phase 8 | Pending |
| API-01 | Phase 9 | Pending |
| API-02 | Phase 9 | Pending |
| API-03 | Phase 9 | Pending |
| API-04 | Phase 9 | Pending |
| CLI-12 | Phase 10 | Pending |
| CLI-13 | Phase 10 | Pending |
| CLI-14 | Phase 10 | Pending |
| CLI-15 | Phase 10 | Pending |
| CLI-16 | Phase 10 | Pending |
| CLI-17 | Phase 10 | Pending |

**Coverage:**

- v1.1 requirements: 21 total
- Mapped to phases: 21/21
- Unmapped: 0

---
*Requirements defined: 2026-06-24*

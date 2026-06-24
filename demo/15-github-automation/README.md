# Scenario 15 — GitHub Automation via Integration Hooks (Phase 8)

Demonstrates the GitHub integration that automatically provisions GitHub teams,
repositories, and memberships whenever a PECP team or project is created.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- GitHub credentials set as environment variables on the server process:

```bash
export GITHUB_PAT=ghp_yourRealTokenHere
export GITHUB_ORG=your-org-name
python -m uvicorn pecp.api.main:app --reload
```

> **PoC note:** Without real `GITHUB_PAT` and `GITHUB_ORG`, the integration logs
> a warning and skips registration — the rest of PECP continues to work normally.

### What happens behind the scenes

| PECP Action | GitHub Effect |
|-------------|---------------|
| `pecp team create <name>` | `POST /orgs/{org}/teams` → creates a GitHub team with sanitized name |
| `pecp project create <name>` | `POST /orgs/{org}/repos` → creates a GitHub repo named `{team}-{project}` |
| `pecp member add` (future) | `PUT /orgs/{org}/teams/{slug}/memberships/{user}` → adds member to GitHub team |
| `pecp member remove` (future) | `DELETE /orgs/{org}/teams/{slug}/memberships/{user}` → removes from team |

### GitHub API contract

| Hook | Endpoint | Success | Error handling |
|------|----------|---------|----------------|
| `on_team_create` | `POST /orgs/{org}/teams` | 201 → writes `github_team_slug` to DB | 422 → logged, skipped (already exists); other → re-raised |
| `on_project_create` | `POST /orgs/{org}/repos` | 201 → inserts `ProjectRepoRecord` | 422 → logged, skipped (already exists); other → re-raised |
| `on_member_add` | `PUT /orgs/{org}/teams/{slug}/memberships/{user}` | 200/201 → member added | 404 → re-raised (caught by fire_integrations) |
| `on_member_remove` | `DELETE /orgs/{org}/teams/{slug}/memberships/{user}` | 204 → member removed | 404 → idempotent success (already removed) |

### Error isolation

Integration errors never block the primary PECP flow. If GitHub is unreachable,
the team/project/member creation still succeeds — the error is logged and the
integration continues with the next registered adapter.

## Steps (with real GitHub credentials)

**1. Confirm the integration is loaded:**

Start the server with `GITHUB_PAT` and `GITHUB_ORG` set. Check startup logs:

```
INFO:     Application startup complete.
```

No warning about GitHub integration disabled means it registered.

**2. Create a team — a GitHub team is created automatically:**

```bash
pecp team create toxins-research --owner alice
```

Expected: the team is created in PECP, AND a GitHub team with a sanitized name
(`toxins-research`, lowercase + hyphens) appears in your GitHub org.

The `github_team_slug` (e.g. `toxins-research`) is written to the PECP
TeamRecord after the GitHub API call succeeds.

**3. Create a Project — a GitHub repo is created automatically:**

```bash
pecp project create ml-platform --team toxins-research --env dev,staging,prod
```

Expected: the project is created in PECP, AND a GitHub repo named
`toxins-research-ml-platform` is created in your GitHub org, visible at
`https://github.com/{org}/toxins-research-ml-platform`.

A `ProjectRepoRecord` is inserted linking the PECP project to the repo name and URL.

**4. (Future) Add a member — they are added to the GitHub team:**

Once `pecp member add` is implemented:
```bash
pecp member add toxins-research --user bob --role contributor
```

Expected: Bob gets added to the `toxins-research` team in GitHub via
`PUT /orgs/{org}/teams/toxins-research/memberships/bob`.

## Running without real GitHub (mock server)

For demo environments without real GitHub access, use a local mock:

```python
# mock_github.py — run in a separate terminal
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MockGitHubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if '/orgs/' in self.path and '/teams' in self.path:
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(201)
            self.end_headers()
            self.wfile.write(json.dumps({"slug": body["name"], "name": body["name"]}).encode())
        elif '/orgs/' in self.path and '/repos' in self.path:
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            repo_name = body["name"]
            self.send_response(201)
            self.end_headers()
            self.wfile.write(json.dumps({
                "html_url": f"https://github.com/mock-org/{repo_name}",
                "name": repo_name
            }).encode())

HTTPServer(('', 8443), MockGitHubHandler).serve_forever()
```

Then set `PECP_GITHUB_API=http://localhost:8443` and run the server.

## What this proves

The integration hook framework (Phase 7) lets adapters react to PECP lifecycle
events without coupling to the core API logic. The GitHub integration demonstrates
the pattern: team creation provisions a GitHub team, project creation provisions a
repo, and member management syncs team membership — all transparent to the end user.
Failures in GitHub never cascade back to the PECP API.

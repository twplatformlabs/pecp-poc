# Phase 08: GitHub Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 08-github-integration
**Areas discussed:** 422 idempotency pattern, Adding aclose() to IntegrationBase, Member hook slug resolution, Name sanitization for GitHub

---

## 422 Idempotency Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| GET fallback | On 422, do GET /orgs/{org}/teams/{slug} to recover the existing slug and write to DB | |
| Log and skip | Just log the 422 and leave NULL | ✓ |

**User's choice:** Log and skip for both team creation (POST /orgs/{org}/teams) and repo creation (POST /orgs/{org}/repos).
**Notes:** DELETE memberships returning 404 (user already removed) is treated as success — idempotent remove.

---

## Adding aclose() to IntegrationBase

| Option | Description | Selected |
|--------|-------------|----------|
| Add aclose() to ABC | Add async aclose() to IntegrationBase + implement in GitHubIntegration. Wire to lifespan. | ✓ |
| Skip aclose() | Cosmetic warnings in PoC. Don't modify Phase 7 ABC. | |

**User's choice:** Add aclose() to IntegrationBase and wire to lifespan shutdown.
**Notes:** Lifespan shutdown helper iterates INTEGRATION_REGISTRY and awaits each integration's aclose().

---

## Member Hook Slug Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Re-fetch from DB | Open new AsyncSession and query TeamRecord.github_team_slug | ✓ |
| Rely on snapshot | Use TeamSnapshot.github_team_slug directly | |

**User's choice:** Re-fetch from DB inside each member hook.
**Notes:** If slug is still NULL after DB re-fetch, log warning and skip (no retry).

---

## Name Sanitization for GitHub

| Option | Description | Selected |
|--------|-------------|----------|
| Sanitize | Lowercase + replace spaces with hyphens | ✓ |
| Pass as-is | GitHub returns 422 for invalid names, non-fatal per GH-05 | |

**User's choice:** Sanitize team/project names before sending to GitHub API.
**Notes:** Simple transformation: lowercase + spaces to hyphens. No aggressive character stripping.

---

## the agent's Discretion

- Test file organization (existing patterns in tests/test_integrations/)
- httpx.AsyncClient configuration details (timeouts, retries)
- Sanitization helper implementation (inline vs standalone function)
- Test mock registration order and pytest-httpx fixture patterns

## Deferred Ideas

None — discussion stayed within phase scope.

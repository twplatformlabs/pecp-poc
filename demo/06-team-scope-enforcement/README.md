# Scenario 06 — Team Scope Enforcement (Phase 1)

Demonstrates that the PECP API enforces team scoping **server-side** on every resource
query. A `GET /resources` request without a `team` parameter is rejected with
`400 Bad Request` — even if the caller bypasses the CLI entirely.

This is a Phase 1 guarantee (ARCH-01): team context is not optional, not inferred,
and not defaulted. The server refuses to answer without it.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`

## Steps

**1. Attempt a resource list with no team (direct API call — bypasses CLI guard):**

```bash
curl -s -w "\n\nHTTP %{http_code}" http://localhost:8000/resources
```

Expected: `400 Bad Request` with a message like `"team query parameter is required"`.

**2. Confirm the same rejection for kind-filtered queries:**

```bash
curl -s -w "\n\nHTTP %{http_code}" "http://localhost:8000/resources?kind=PECPLambda"
```

Expected: `400 Bad Request` — kind filter alone is not enough, team is still required.

**3. Confirm a properly-scoped query succeeds:**

```bash
curl -s -w "\n\nHTTP %{http_code}" "http://localhost:8000/resources?team=customer-product-app"
```

Expected: `200 OK` with an array (possibly empty if no resources exist yet).

## Why this matters

The CLI always passes `--team`, so this gate is invisible in normal use. But it is the
server-side enforcement that makes team scoping a contract, not a convention. Any
service, script, or API client that calls PECP directly gets the same enforcement.
This is the foundation for future authz — when JWT auth is dropped in, the server
already validates that a team context exists before it touches the database.

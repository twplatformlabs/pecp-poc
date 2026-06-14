# Scenario 02 — List & Filter

Demonstrates applying multiple resource types for a team and then listing them,
with optional kind filtering so teams can see only the resources they care about.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or no existing resources for `platform-eng`)

## Steps

**1. Apply both resources:**

```bash
pecp apply -f demo/02-list-and-filter/lambda.yaml --team platform-eng
pecp apply -f demo/02-list-and-filter/data-service.yaml --team platform-eng
```

**2. List all resources for the team:**

```bash
pecp get PECPLambda --team platform-eng
```

Expected: table showing `auth-service` (PECPLambda, prod).

```bash
pecp get PECPDataService --team platform-eng
```

Expected: table showing `user-events` (PECPDataService, prod).

**3. Confirm cross-team isolation — another team sees nothing:**

```bash
pecp get PECPLambda --team other-team
```

Expected: empty table (or "no resources found").

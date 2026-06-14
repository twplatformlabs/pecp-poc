# Scenario 04 — Cross-Team Delete Protection

Demonstrates that a team cannot delete another team's resources. A delete attempt
with the wrong `--team` flag is silently rejected (404), while the owning team
can delete successfully.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or no existing `payment-processor` for `backend-team`)

## Steps

**1. Apply the resource as `backend-team`:**

```bash
pecp apply -f demo/04-cross-team-protection/lambda.yaml --team backend-team
```

**2. Confirm it exists:**

```bash
pecp get PECPLambda --team backend-team
```

Expected: table showing `payment-processor`.

**3. Attempt to delete as a different team (should fail):**

```bash
pecp delete PECPLambda payment-processor --team wrong-team
```

Expected: error or "not found" — the resource is not deleted.

**4. Confirm the resource is still there:**

```bash
pecp get PECPLambda --team backend-team
```

Expected: `payment-processor` still present.

**5. Delete as the owning team (should succeed):**

```bash
pecp delete PECPLambda payment-processor --team backend-team
```

Expected: success message.

**6. Confirm it's gone:**

```bash
pecp get PECPLambda --team backend-team
```

Expected: empty table.

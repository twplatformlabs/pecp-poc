# Scenario 01 — Apply & Idempotency

Demonstrates that submitting the same resource spec twice returns the same resource ID
rather than creating a duplicate. This is the core "declare and forget" behaviour of PECP.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or no existing `hello-world` for `toxins-research`)

## Steps

**1. Apply the resource:**

```bash
pecp apply -f demo/01-apply-idempotency/lambda.yaml --team toxins-research
```

Expected: prints a resource ID (UUID) and `status: pending`, then transitions to `ready`.

**2. Apply the same spec again:**

```bash
pecp apply -f demo/01-apply-idempotency/lambda.yaml --team toxins-research
```

Expected: prints the **same** resource ID — no duplicate created.

**3. Verify only one resource exists:**

```bash
pecp get PECPLambda --team toxins-research
```

Expected: a single row in the table for `hello-world`.

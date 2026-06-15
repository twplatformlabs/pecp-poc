# Scenario 05 — Schema Validation (Phase 1)

Demonstrates that the PECP control plane validates resource specs against their
Pydantic models **before** any adapter is invoked. A spec missing a required field
is rejected immediately with field-level errors — the adapter never sees invalid data.

This is a Phase 1 guarantee: the schema layer is the first line of defence.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`

## Steps

**1. Apply the invalid spec (missing `source-code`):**

```bash
pecp apply -f demo/05-schema-validation/lambda-invalid.yaml --team customer-product-app
```

Expected: error response with a `422 Unprocessable Entity` status and a message indicating
the `source-code` field is required. The resource is **not** created — no UUID is returned,
no adapter is called.

**2. Fix the spec and apply the valid version:**

```bash
pecp apply -f demo/05-schema-validation/lambda-valid.yaml --team customer-product-app
```

Expected: resource accepted with a UUID, `status: pending`, transitions to `ready`.

**3. Confirm the invalid attempt left no trace:**

```bash
pecp get PECPLambda --team customer-product-app
```

Expected: only the `valid-lambda` resource appears — the rejected spec created nothing.

## What this proves

Pydantic schema enforcement runs at the API boundary. Even if a team submits a
malformed spec (missing field, wrong type, extra field that's forbidden), the server
returns a structured validation error. The adapter registry is never reached, so there
is no risk of partially-provisioned resources from bad input.

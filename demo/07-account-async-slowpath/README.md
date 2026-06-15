# Scenario 07 — PECPAccount Async Slow Path (Phase 2)

Demonstrates the `PECPAccount` mock adapter's deliberate 3-second provisioning dwell.
AWS account creation via Organizations is slow and sometimes manually assisted — the
adapter simulates this with a minimum 3-second `PROVISIONING` hold before transitioning
to `READY`. The caller gets a resource ID immediately; polling reveals the async lifecycle.

This is a Phase 2 guarantee: the Dispatcher correctly drives the state machine through
`PENDING → PROVISIONING → READY` without blocking the request thread.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Team `customer-product-app` must exist (run Scenario 09 first, or apply any resource to
  implicitly use that team name — the team record is not required for resource submission
  in this PoC)

## Steps

**1. Submit the account request:**

```bash
pecp apply -f demo/07-account-async-slowpath/account.yaml --team customer-product-app
```

Expected: returns immediately with a UUID and `status: pending`. The command does **not**
block for provisioning to complete — the server accepted the request and dispatched it
to the `AwsAccountMockAdapter` in a background task.

**2. Poll status immediately (should be provisioning):**

```bash
pecp status PECPAccount aws-account-customer-product-app --team customer-product-app
```

Expected: `status: provisioning` — the adapter is in its simulated 3-second dwell,
logging what it would call in production (AWS Organizations API calls).

**3. Poll status again after a few seconds:**

```bash
pecp status PECPAccount aws-account-customer-product-app --team customer-product-app
```

Expected: `status: ready` — the adapter completed its dwell and wrote synthetic
provider metadata (account ID, access key) to the resource record.

**4. Inspect the activity log via the API:**

```bash
RESOURCE_ID=$(curl -s "http://localhost:8000/resources?team=customer-product-app&kind=PECPAccount" \
  | python -c "import sys,json; records=[r for r in json.load(sys.stdin) if r['name']=='aws-account-customer-product-app']; print(records[0]['id'])")

curl -s "http://localhost:8000/resources/$RESOURCE_ID" | python -m json.tool
```

Expected: `activity_log` contains structured entries like:
```
Would call: aws organizations create-account --email customer-product-app@example.com --account-name customer-product-app
Would call: aws organizations describe-create-account-status --create-account-request-id car-...
Account provisioned — synthetic account ID: 123456789012
```

## What this proves

The `AwsAccountMockAdapter` enforces the Phase 2 contract: it dwells in `PROVISIONING`
for at least 3 seconds before transitioning to `READY`, and it logs every action it
**would** take against real AWS APIs. The Dispatcher's background task model means the
HTTP response returns in milliseconds even when the adapter takes seconds. When real
adapters replace the mocks, this async pattern — immediate acceptance, background
dispatch, status polling — is the production model.

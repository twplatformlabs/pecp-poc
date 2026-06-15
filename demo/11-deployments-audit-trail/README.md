# Scenario 11 — Deployments Audit Trail & Soft Delete (Phase 4)

Demonstrates the deployment audit trail and soft-delete behaviour. Every resource
mutation — create, update (re-apply), delete — writes a `DeploymentRecord`. Deleted
resources disappear from `pecp get` (soft-delete: `deleted_at` is set, not a DB row
removal), but every mutation is preserved in `pecp deployments` as an immutable audit log.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Team `toxins-research` exists (run Scenario 09 first)

## Steps

**1. Apply a resource (creates the first deployment record):**

```bash
pecp apply -f demo/11-deployments-audit-trail/lambda.yaml --team toxins-research
```

Expected: resource created with a UUID, `status: pending → ready`.

**2. Re-apply the same spec (update path — creates a second deployment record):**

```bash
pecp apply -f demo/11-deployments-audit-trail/lambda.yaml --team toxins-research
```

Expected: same UUID returned — idempotent. But because the spec was re-submitted, an
`update` deployment record is written to capture the intent.

**3. Check deployments — two records so far:**

```bash
pecp deployments --team toxins-research
```

Expected: table shows two rows for `audit-trail-lambda`:
- Row 1: `change_type: create`, `status: ready`
- Row 2: `change_type: update`, `status: ready`
Both sorted newest first.

**4. Delete the resource (soft-delete):**

```bash
pecp delete PECPLambda audit-trail-lambda --team toxins-research
```

Expected: "deleted" confirmation. The row is **not** removed from the database —
`deleted_at` is set to now.

**5. Confirm the resource is gone from the active list:**

```bash
pecp get PECPLambda --team toxins-research
```

Expected: `audit-trail-lambda` does **not** appear. Soft-deleted resources are filtered
from all list and get queries — invisible to normal operations.

**6. Confirm the full audit trail is still visible in deployments:**

```bash
pecp deployments --team toxins-research
```

Expected: now three rows for `audit-trail-lambda`:
- Row 1 (newest): `change_type: delete`, `status: ready`
- Row 2: `change_type: update`, `status: ready`
- Row 3: `change_type: create`, `status: ready`

The soft-delete approach means the `deployments` foreign key (`resource_id`) always
resolves to a valid row. The audit trail is complete and permanent.

**7. Filter by environment to scope the view:**

```bash
pecp deployments --team toxins-research --environment staging
```

Expected: only resources in the `staging` environment appear. The `audit-trail-lambda`
(env: staging) shows all three records; resources in other environments are excluded.

## What this proves

Soft-delete (D-11, D-12) keeps the database consistent for audit purposes — the
`deployments` table always has a valid `resource_id` FK. From the operator's perspective,
deletion is final and invisible; from the compliance perspective, every lifecycle event
is recorded. The `pecp deployments` command is the compliance view — sorted newest first,
filterable by environment, showing the full mutation history per team.

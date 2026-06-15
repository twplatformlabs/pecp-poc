# Scenario 09 — Team Lifecycle (Phase 4)

Demonstrates the full team lifecycle: creating a team, inspecting it, and the
uniqueness guard that prevents accidental duplicate creation. Teams are the primary
organizational unit — every resource, project, and deployment in PECP belongs to a team.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or team `customer-product-app` must not already exist)

## Steps

**1. Create the team with an owner:**

```bash
pecp team create customer-product-app --owner alice@example.com
```

Expected: prints the full team panel immediately —
- Team metadata block: ID (UUID), name, owner_id, created_at
- Members table: one row showing `alice@example.com` with role `owner`

No second command needed — `create` returns the full panel from the POST response.

**2. Inspect the team at any time:**

```bash
pecp team customer-product-app
```

Expected: same panel as above. Any team member (or PE admin) can run this to see
the current roster and team metadata.

**3. Attempt to create the same team again:**

```bash
pecp team create customer-product-app --owner bob@example.com
```

Expected: `Error 409` — team name `customer-product-app` already exists. The existing team
is **not** modified. Team creation is a deliberate one-time act, not idempotent.

**4. Confirm the original team is unchanged:**

```bash
pecp team customer-product-app
```

Expected: panel shows `alice@example.com` as owner — the rejected duplicate did not
overwrite the original.

## What this proves

Team names are unique in the platform — the 409 guard prevents accidental overwrites.
`pecp team create` and `pecp team <name>` use the same rendering path, so the output
is identical whether you are creating or inspecting. The owner is auto-added as the
first member with `role=owner`; future member management commands will append rows
to the same `team_members` table.

# Scenario 12 — JSON Output Flag (Phase 4)

Demonstrates the `--json` flag available on all data-returning CLI commands. When
`--json` is passed, the command writes clean JSON to stdout (no Rich formatting,
no ANSI codes) — suitable for piping to `jq`, scripting, or CI integration.

This is a Phase 4 capability (D-17): every command that renders a table or panel
also supports a machine-readable output path.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Team `customer-product-app` exists and has at least one resource (run Scenarios 09 + 10)

## Steps

**1. Team panel as JSON:**

```bash
pecp team customer-product-app --json
```

Expected: a single JSON object with keys `id`, `name`, `owner_id`, `created_at`,
and `members` (array of `{user_id, role, joined_at}`). No Rich formatting.

**2. Projects list as JSON:**

```bash
pecp projects --team customer-product-app --json
```

Expected: JSON array of project objects:
```json
[
  {
    "id": "...",
    "name": "webhook-platform",
    "environments": ["dev", "staging", "prod"],
    "resource_count": 2
  }
]
```

**3. Deployments as JSON:**

```bash
pecp deployments --team customer-product-app --json
```

Expected: JSON array of deployment records, each with `resource_name`, `kind`,
`change_type`, `status`, `environment`, `deployed_at`.

**4. Resource list as JSON:**

```bash
pecp get PECPLambda --team customer-product-app --json
```

Expected: JSON array of resource records with all fields including `project` and
`deleted_at` (null for active resources).

**5. Resource status as JSON:**

```bash
pecp status PECPLambda webhook-handler --team customer-product-app --json
```

Expected: single JSON object with full resource record including `activity_log` array.

**6. Pipe to jq for field extraction:**

```bash
pecp projects --team customer-product-app --json | jq '.[].name'
pecp deployments --team customer-product-app --json | jq '[.[] | {name: .resource_name, type: .change_type}]'
```

Expected: `jq` extracts fields cleanly — proves stdout is valid JSON with no
extraneous output (no spinners, no Rich panels, no ANSI escape codes).

## What this proves

The `--json` flag makes every PECP CLI command scriptable. CI pipelines, monitoring
scripts, and integration tests can consume PECP data without parsing Rich terminal
output. The flag is additive — Rich output remains the default for human operators,
JSON output is opt-in for machines.

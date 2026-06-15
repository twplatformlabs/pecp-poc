# Scenario 10 — Project Grouping (Phase 4)

Demonstrates how resources are grouped into projects with environment scoping.
A project is a named collection of resources that maps to one or more environments
(dev, staging, prod). Resources can be scoped to a project at apply time via
`--project`, and `pecp projects` shows each project with a live resource count.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Team `toxins-research` exists (run Scenario 09 first)

## Steps

**1. Create a project for the team:**

```bash
pecp project create webhook-platform --team toxins-research --env dev,staging,prod
```

Expected: `Project webhook-platform created (id: <uuid>)`.

**2. Apply a resource scoped to that project:**

```bash
pecp apply -f demo/10-project-grouping/lambda.yaml --team toxins-research --project webhook-platform
```

Expected: resource created with `project: webhook-platform` stored on the record.
The `--project` flag overrides any `metadata.project` from the YAML.

**3. Apply a second resource to the same project:**

```bash
pecp apply -f demo/10-project-grouping/data-service.yaml --team toxins-research --project webhook-platform
```

Expected: second resource in the project — resource count will be 2.

**4. Apply a resource without a project (baseline for contrast):**

```bash
pecp apply -f demo/10-project-grouping/standalone-lambda.yaml --team toxins-research
```

Expected: resource created with `project: null` — not associated with any project.

**5. List projects with resource counts:**

```bash
pecp projects --team toxins-research
```

Expected: table showing `webhook-platform` with `resource_count: 2` and
`environments: dev, staging, prod`. The standalone resource (no project) is not
counted here — it appears only in `pecp get`.

**6. Confirm the project field via JSON:**

```bash
pecp get PECPLambda --team toxins-research --json | python -m json.tool
```

Expected: JSON array where the project-scoped Lambdas show `"project": "webhook-platform"`
and the standalone Lambda shows `"project": null`.

## What this proves

Projects are explicit — they must be created before resources can be associated with them.
The `--project` flag on `apply` is the primary grouping mechanism. `pecp projects` gives
a live count of active (non-deleted) resources per project, making it easy to see which
projects are busy and which environments they cover.

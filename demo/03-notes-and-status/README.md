# Scenario 03 — Notes & Status

Demonstrates the PE notes workflow: platform engineers append operational notes
to a resource (via the API), and `pecp status` surfaces them alongside the
resource's current state.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or no existing `data-pipeline` for `data-science`)

## Steps

**1. Apply the resource:**

```bash
pecp apply -f demo/03-notes-and-status/lambda.yaml --team data-science
```

**2. Check status before any notes:**

```bash
pecp status PECPLambda data-pipeline --team data-science
```

Expected: status table with `ready`, no notes block below.

**3. Look up the resource ID:**

```bash
RESOURCE_ID=$(curl -s "http://localhost:8000/resources?team=data-science&kind=PECPLambda" \
  | python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo $RESOURCE_ID
```

**4. Add a PE note via the API:**

```bash
curl -X POST "http://localhost:8000/resources/$RESOURCE_ID/notes" \
  -H "Content-Type: application/json" \
  -d '{"text":"provisioned in us-east-1 — memory bumped to 512MB after load test"}'
```

**5. Add a second note:**

```bash
curl -X POST "http://localhost:8000/resources/$RESOURCE_ID/notes" \
  -H "Content-Type: application/json" \
  -d '{"text":"rolled out v2 — monitoring stable, no errors in 24h"}'
```

**6. Check status again:**

```bash
pecp status PECPLambda data-pipeline --team data-science
```

Expected: status table followed by a **Notes** block listing both notes with timestamps.

# Scenario 08 — Multi-Adapter Routing (Phase 2)

Demonstrates that the PECP Dispatcher routes each resource kind to the correct mock
adapter based on the `kind` field. All 10 adapter kinds are registered in
`ADAPTER_REGISTRY`; this scenario exercises four distinct ones — Container, two
DataService subtypes, and Kubernetes — to show that each produces its own synthetic
activity log without any cross-contamination.

This is a Phase 2 guarantee: the Dispatcher is a pure router. It inspects `kind`, looks
up the adapter, and hands off. No adapter logic leaks into the control plane.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Fresh database (or unique resource names)

## Steps

**1. Submit a container workload:**

```bash
pecp apply -f demo/08-multi-adapter-kinds/container.yaml --team platform-eng
```

Expected: `status: pending → ready` (fast path — Container adapter has no slow dwell).

**2. Submit an S3 data service:**

```bash
pecp apply -f demo/08-multi-adapter-kinds/data-service-s3.yaml --team platform-eng
```

Expected: accepted and dispatched to the `AwsDataMockAdapter`, S3 branch.

**3. Submit a DynamoDB data service (same kind, different subtype):**

```bash
pecp apply -f demo/08-multi-adapter-kinds/data-service-dynamodb.yaml --team platform-eng
```

Expected: same `PECPDataService` kind, `AwsDataMockAdapter` routes on `subtype=dynamodb`.

**4. Submit a Kubernetes workload:**

```bash
pecp apply -f demo/08-multi-adapter-kinds/kubernetes.yaml --team platform-eng
```

Expected: dispatched to `KubernetesMockAdapter`.

**5. List all resource kinds for the team:**

```bash
pecp get PECPContainer --team platform-eng
pecp get PECPDataService --team platform-eng
pecp get PECPKubernetes --team platform-eng
```

Expected: each command shows only the resources of that kind — cross-kind isolation is
enforced at the query layer.

**6. Inspect activity logs to see adapter-specific entries:**

```bash
curl -s "http://localhost:8000/resources?team=platform-eng" | \
  python -c "
import sys, json
for r in json.load(sys.stdin):
    print(f\"--- {r['kind']} / {r['name']} ---\")
    for entry in (r.get('activity_log') or []):
        print(f\"  {entry}\")
"
```

Expected: each resource has activity log entries prefixed with `Would call:` that are
specific to its adapter:
- Container: ECS `register-task-definition`, `create-service`
- DataService/s3: S3 `create-bucket`
- DataService/dynamodb: DynamoDB `create-table`
- Kubernetes: `kubectl apply -f ...`

## What this proves

The `ADAPTER_REGISTRY` maps every `kind` string to its adapter class. Phase 2's
Dispatcher is adapter-agnostic — adding a new adapter requires only registering it
in the registry, no changes to the control plane. The `DataService` case further
proves that a single adapter class can handle multiple subtypes via internal routing.

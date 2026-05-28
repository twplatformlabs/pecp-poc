# PECP Demo: New Team Onboarding End-to-End

**Audience:** Engineers and stakeholders (mixed)
**Duration:** ~20 minutes live
**Phase 5 Note:** Every `[expected output: ...]` placeholder in this document will be replaced
with captured terminal output from the running system before the stakeholder session.

---

## Setting the scene

A new squad has just formed within the engineering organisation. The team is called `toxins-research`,
they own a couple of microservices, and they need a Lambda function deployed to AWS along with a
dedicated AWS account to isolate their production workloads. Historically, this would mean filing
Jira tickets, waiting for the platform team to action them, and chasing status updates across Slack
and email. Today we are going to show a different model: the `toxins-research` team writes a YAML file and
runs a single command, and the Platform Engineering Control Plane — PECP — handles everything else.
A PE team member is presenting at the terminal. The audience sees the full journey from zero to
provisioned infrastructure without the team ever needing to know which AWS account they land in,
which pipeline fires, or which internal ticket gets created.

---

## Day one: a team is born

Every resource in PECP belongs to a team. Before the `toxins-research` squad can submit anything, they
need to exist in the platform. Team creation is a single command.

```bash
pecp team create toxins-research
```

```
[expected output: team created confirmation with team id and metadata — e.g.
  Team created
  ID:      team-a1b2c3d4
  Name:    toxins-research
  Status:  active
  Created: 2025-09-01T09:00:00Z
]
```

With the team created, anyone with the owner or contributor role can be added and queried. The
team object carries the authoritative list of who can act on behalf of `toxins-research` in the control
plane. We can inspect that record at any time.

```bash
pecp team toxins-research
```

```
[expected output: table showing team members and roles — e.g.
  Team: toxins-research
  ┌─────────────────────┬──────────────┬───────────┐
  │ Member              │ Role         │ Since     │
  ├─────────────────────┼──────────────┼───────────┤
  │ alice@example.com   │ owner        │ 2025-09-01│
  │ bob@example.com     │ contributor  │ 2025-09-01│
  └─────────────────────┴──────────────┴───────────┘
]
```

The team now has an identity in the platform. Every resource they create, every deployment they
trigger, and every account they own will be scoped to this team record. That is the foundation.

---

## Day two: deploying a Lambda

The `toxins-research` squad has a small event-handler they want to run as a serverless function — a
Lambda that processes webhook events. They write a resource spec. It looks exactly like a
Kubernetes manifest because the mental model is deliberately familiar: `apiVersion`, `kind`,
`metadata`, `spec`. No AWS console, no Terraform, no pipeline YAML — just this file.

```yaml
apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: toxins-research-webhook-handler
spec:
  name: toxins-research-webhook-handler
  exposure: public
  api-gateway: /toxins-research/webhook
  source-code: github://toxins-research-org/webhook-lambda
```

They save that as `toxins-research-lambda.yaml` and submit it.

```bash
pecp apply -f toxins-research-lambda.yaml --team toxins-research
```

```
[expected output: resource accepted by the control plane — e.g.
  Resource submitted
  ID:      res-f1e2d3c4
  Kind:    PECPLambda
  Name:    toxins-research-webhook-handler
  Team:    toxins-research
  Status:  pending
  Message: Dispatched to AWS Lambda adapter
]
```

The control plane accepted the spec, validated it against the `PECPLambda` schema, persisted it,
and dispatched it to the AWS Lambda mock adapter — all in under a second. The resource is now in
`pending` state. The team does not need to know which AWS account that Lambda will land in; the
platform resolves that from the team record.

They can watch the resource transition in real time by running the status command with the
`--watch` flag. PECP polls with exponential backoff and prints each state change as it happens.

```bash
pecp status PECPLambda toxins-research-webhook-handler --team toxins-research --watch
```

```
[expected output: status transitions from pending through provisioning to ready with synthetic
  activity log lines — e.g.
  Watching PECPLambda/toxins-research-webhook-handler (team: toxins-research) ...
  [09:01:02] status: pending      Waiting for dispatch
  [09:01:03] status: provisioning Would call: aws lambda create-function --function-name toxins-research-webhook-handler
  [09:01:05] status: provisioning Would call: aws apigateway create-resource --path-part webhook
  [09:01:07] status: provisioning Would call: aws lambda add-permission --action lambda:InvokeFunction
  [09:01:09] status: ready        Function ready — arn:aws:lambda:us-east-1:123456789:function:toxins-research-webhook-handler
  Resource reached ready. Exiting watch.
]
```

From spec submission to `ready` in under ten seconds. The `toxins-research` team can now wire their
CI/CD pipeline to push code to the Lambda ARN surfaced in that output. The platform team sees
a structured activity log that maps every mock action to its real-world equivalent — when real
adapters replace the mocks, those same log lines will represent actual AWS API calls.

---

## Day three: the long-running ask — a new AWS account

Deploying a Lambda is fast. Requesting a new AWS account is a different beast: AWS
Organizations takes minutes to provision a new account, the PE team sometimes needs to open a
support ticket, and the caller has no visibility into any of that today. PECP solves this with
an async model: the command returns immediately with a resource ID, and the status endpoint
streams updates — including free-text notes that the PE team appends as they work through
the process.

```bash
pecp create awsaccount --team toxins-research
```

```
[expected output: account request accepted and resource id returned immediately — e.g.
  Account request submitted
  ID:      res-9a8b7c6d
  Kind:    PECPAccount
  Team:    toxins-research
  Status:  pending
  Message: AWS account provisioning queued
]
```

The command returns in under a second. The `toxins-research` team has a resource ID and nothing else to
do. Meanwhile, the PE team is actioning the request: they file an internal approval ticket, they
watch the AWS Organizations API, and they append notes directly to the resource record as the
situation develops. The team can watch all of this unfold without a single Slack message.

```bash
pecp status awsaccount --team toxins-research --watch
```

```
[expected output: resource stays in provisioning for at least 3 seconds with PE notes appearing
  mid-stream before eventually transitioning to ready — e.g.
  Watching PECPAccount (team: toxins-research) ...
  [09:05:00] status: pending       Account request queued
  [09:05:01] status: provisioning  Would call: aws organizations create-account --email toxins-research@example.com
  [09:05:03] status: provisioning  [PE note] Approval ticket filed: CHG-00412
  [09:05:06] status: provisioning  Would call: aws organizations describe-create-account-status
  [09:05:09] status: provisioning  [PE note] AWS support confirmed — account creation in progress
  [09:05:12] status: ready         Account ready
                                   Account ID:  123456789012
                                   Access Key:  AKIAIOSFODNN7EXAMPLE
                                   Secret Key:  wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  Resource reached ready. Exiting watch.
]
```

This is the moment that changes how a platform team presents async infrastructure work. The
`toxins-research` team never filed a ticket. They never chased anyone on Slack. They ran two commands,
watched a terminal, and got credentials. The PE team had full transparency into what the platform
recorded at every step, and they had a channel to surface operational notes — the approval ticket
reference, the AWS support confirmation — directly in the same stream the team is watching.

---

## Day four: the full inventory

The `toxins-research` team has been running for a week. They have their Lambda deployed, their AWS
account provisioned, and they want a clear picture of everything they own in the platform.
`pecp get` gives them a filtered table by resource kind; `pecp deployments` shows the
environment-scoped deployment view.

```bash
pecp get PECPLambda --team toxins-research
```

```
[expected output: rich table with name, kind, status badge, and environment for every Lambda
  owned by the toxins-research team — e.g.
  Resources: PECPLambda (team: toxins-research)
  ┌──────────────────────────────────────┬────────────┬────────┬─────────────┐
  │ Name                                 │ Kind       │ Status │ Environment │
  ├──────────────────────────────────────┼────────────┼────────┼─────────────┤
  │ toxins-research-webhook-handler      │ PECPLambda │ ready  │ prod        │
  └──────────────────────────────────────┴────────────┴────────┴─────────────┘
]
```

```bash
pecp deployments --team toxins-research --environment prod
```

```
[expected output: rich table of all resources deployed to the prod environment for the toxins-research
  team, with per-resource status — e.g.
  Deployments: toxins-research / prod
  ┌──────────────────────────────────────┬──────────────┬────────┬──────────────────────────────────────┐
  │ Name                                 │ Kind         │ Status │ Resource ID                          │
  ├──────────────────────────────────────┼──────────────┼────────┼──────────────────────────────────────┤
  │ toxins-research-webhook-handler      │ PECPLambda   │ ready  │ res-f1e2d3c4                          │
  │ (awsaccount)                         │ PECPAccount  │ ready  │ res-9a8b7c6d                          │
  └──────────────────────────────────────┴──────────────┴────────┴──────────────────────────────────────┘
]
```

For stakeholders who prefer a graphical view, the React dashboard at
`http://localhost:5173` renders the same data.

```
[expected output: browser screenshot showing the team resource inventory as a filterable table —
  same columns as the CLI output (name, kind, status badge, environment) with a dropdown to
  filter by environment (dev / staging / prod) and automatic data refresh without page reload]
```

The dashboard is read-only for this PoC. Resource submission stays in the CLI — that is the
submission contract we are proving today. The dashboard makes the inventory accessible to
stakeholders who are not at a terminal.

---

## What we proved

In four days of narrative time, the `toxins-research` team went from zero to provisioned infrastructure
— a running Lambda function, a dedicated AWS account, and a team inventory visible in both the
CLI and the browser dashboard. They did it by writing a YAML file and running `pecp apply`.
They never knew which AWS account their Lambda landed in. They never filed a ticket for the
account request. They never had to check a pipeline run. The Platform Engineering Control Plane
handled the routing, the dispatch, the async polling, and the credential surfacing — and every
step was auditable from the terminal.

That is PECP's core value: **a team can go from zero to provisioned infrastructure by writing a
YAML and running `pecp apply` — without knowing which AWS account they're in, which pipeline
runs, or which ticket gets filed.**

The mock adapters we demonstrated today are the scaffolding. Phase 5 replaces each placeholder
with real terminal output from a running server. The contracts — the resource spec format, the
CLI commands, the status lifecycle, the PE notes channel — are locked now. Every phase of
development that follows builds toward exactly this session.

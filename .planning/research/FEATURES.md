# Features Research — PECP

**Domain:** Platform Engineering Control Plane / Internal Developer Platform (IDP)
**Researched:** 2026-05-27
**Confidence:** MEDIUM-HIGH (training knowledge of all reference products through Aug 2025)

---

## Reference Products Surveyed

| Product | Model | Key Insight |
|---------|-------|-------------|
| Backstage (Spotify/CNCF) | Software catalog + plugin marketplace + scaffolder | Sets the bar for "software inventory" UX; plugin ecosystem is its moat |
| Crossplane | K8s-native control plane with Compositions and Providers | Gold standard for declarative multi-backend provisioning; steep K8s operator learning curve |
| Port (getport.io) | Blueprint-driven catalog + self-service actions + scorecards | Modern Backstage alternative; scorecards and developer experience metrics are its differentiator |
| Humanitec | Workload-centric deployment orchestrator + resource graph | Separates "workload spec" from "environment config" via Score + resource drivers |
| Kratix | Platform-as-a-product via Promises and Pipelines | Opinionated about PE team workflow: Promises define what teams can request |
| AWS Service Catalog | Portfolio/product governance for AWS resources | Enterprise governance, IAM constraints, tag enforcement; narrow AWS-only scope |
| Score | Workload spec format (platform-agnostic YAML) | Normative reference for "declare workload needs once, deploy anywhere" |

---

## Table Stakes

Features users expect in any IDP/control plane. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Reference Products |
|---------|--------------|------------|-------------------|
| **Declarative resource spec (YAML/GitOps)** | Every modern IDP accepts structured intent, not imperative scripts. Developers expect `apply -f` semantics. | Low (spec parsing) | Crossplane, Score, Kratix, Humanitec |
| **Resource status lifecycle** | Users need to know if their request is pending, provisioning, ready, or failed — without polling a human. | Low-Med | Crossplane (Conditions), Port, Humanitec |
| **CLI for submitting resources** | Developers live in the terminal; CLI is the primary submission path in all developer-facing control planes. | Med | Crossplane CLI, Port CLI, Humanitec |
| **Team/ownership model** | All resources must belong to an organizational unit. Shared resources without ownership create chaos. | Low-Med | Backstage (System/Component owners), Port (blueprints), Humanitec (orgs/teams) |
| **Role-based access (at minimum owner vs. contributor)** | Without it, any team member can delete production resources. | Med | Backstage (RBAC plugin), Port (role model), AWS Service Catalog (IAM constraints) |
| **Resource inventory view (UI)** | Operators and leads need a dashboard: what's provisioned, in what state, for which team. | Med | Backstage catalog, Port catalog, AWS Service Catalog console |
| **Multi-environment support (dev/staging/prod)** | Teams need the same workload spec to resolve to different configs per environment. | Med-High | Humanitec (environments + delta model), Crossplane (Compositions + XRClaims), Port |
| **Pluggable backend adapters** | No org runs a single cloud. Control planes that hardcode one backend get abandoned when the second arrives. | High | Crossplane (Providers), Kratix (Pipeline steps), Humanitec (resource drivers) |
| **Idempotent apply (re-runnable specs)** | Submitting the same spec twice must not create duplicates. Fundamental contract of declarative systems. | Med | Crossplane (reconciliation loop), Kratix (Works CRD) |
| **Async provisioning with status polling** | Real infrastructure takes minutes. Synchronous wait is broken UX; fire-and-poll is the expected model. | Med | Crossplane (Conditions + events), AWS Service Catalog (provisioned product status), Humanitec |
| **Approval / governance gate** | At least one resource class (AWS account creation) requires human sign-off. Without this, enterprises cannot adopt the platform. | Med | AWS Service Catalog (launch constraints), Kratix (Promise pipeline), Backstage (scaffolder approval) |
| **Free-text / notes field on resources** | PE teams need an escape hatch to communicate async status to developers. Without it, users file tickets. | Low | Port (metadata fields), Humanitec (deployment messages) |
| **Project grouping** | Resources need a named container above "team" to represent a coherent workload or product. | Low-Med | Backstage (System), Port (blueprint hierarchy), Humanitec (applications) |
| **Audit trail (who did what, when)** | Enterprises require traceability. "Who requested this Lambda?" must be answerable. | Med | Port (audit log), AWS Service Catalog (CloudTrail), Humanitec |

---

## Differentiators

Features that make PECP distinctive versus existing products.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Multi-backend routing across AWS + K8s + SaaS in one spec** | Crossplane handles multi-cloud but not SaaS. PECP unifying AWS + K8s + Salesforce + AEM + Datadog + ServiceNow + JFrog under one spec format is unusual in the market. | High | The adapter interface design is the critical investment; mocks prove the routing logic in PoC |
| **Account-aware routing hidden behind team context** | Crossplane handles multi-account but requires explicit per-resource config. PECP hides AWS account routing behind `metadata.team` — developers never need to know which account they're in. | Med-High | `metadata.team` → account mapping is the control plane's core routing responsibility |
| **PE-editable notes on async resources** | None of the reference products specifically model "PE team communicates delay status to developer team" on slow/manual resources. This directly encodes the AWS account creation reality into the product. | Low | High demo value: PE team updates notes live during stakeholder walkthrough |
| **SaaS resource types as first-class kinds** | Crossplane Providers for Salesforce and Datadog exist but are community-maintained and immature. Treating `PECPSalesforce` and `PECPAem` as first-class kinds is distinctive for enterprise IDP use cases. | High (spec design) | Salesforce and AEM specs are undefined — need research before those kinds can be designed |
| **K8s mental model without requiring K8s runtime** | Score is platform-agnostic but has no control plane. Crossplane requires K8s. PECP delivers the `apiVersion`/`kind`/`metadata` mental model for orgs not ready to operate K8s. | Low (design constraint) | The `apiVersion: pecp/v1` convention is a deliberate differentiator |
| **PE approval built into team onboarding as a first-class concept** | Backstage scaffolding has approval hooks but they're plugin-configured and generic. PECP models PE-as-gatekeeper explicitly. | Med | Kratix Promises are comparable but PECP's model is simpler and org-specific |
| **Future K8s migration path by design** | PECP's adapter interfaces and YAML conventions are designed to allow future K8s operator migration without app teams rewriting their specs. | Low (architectural constraint) | Key demo talking point: "When your org is K8s-ready, PECP migrates, not your apps" |

---

## Anti-Features (PoC Scope)

Things to deliberately NOT build during the PoC.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real backend connections** | Adds weeks of setup risk; irrelevant to proving the control plane pattern. | Mock adapters that log what they would provision and return synthetic status/metadata. |
| **Authentication / authz enforcement** | Significant engineering with zero demo value. Backstage took 2+ years to get auth right. | Stub auth surfaces: API key header accepted but not validated. Ensure API contract has auth header slots. |
| **Team-configurable RBAC policies** | Requires a policy engine (OPA, Cedar, or custom). Adds 3-4 weeks with no PoC value. | Hardcode owner/contributor roles. Document the extension point. |
| **GitOps / git-backed state** | Reconciliation complexity with no benefit in a mock-adapter world. | Store resource specs in a database. Add git backend as a future milestone. |
| **Kubernetes operator / CRD runtime** | Org not versed in K8s; running a K8s cluster adds infrastructure overhead. | Custom Python API server. Design adapter interfaces to be K8s-operator-compatible for later migration. |
| **Multi-cluster / multi-region account routing** | Architecturally complex, not demonstrable in a stakeholder demo. | Flat account routing: `metadata.team` maps to one account per environment. |
| **Live ServiceNow / change management integration** | Adds synchronous dependency on external system; may not be available in demo environment. | Mock the ServiceNow adapter like all others. |
| **Cost management / chargeback** | Zero PoC value. | Out of scope entirely. |
| **Software catalog (Backstage-style)** | Conflating provisioner + general catalog creates scope creep. | PECP's resource inventory is the catalog for PECP-managed resources only. |
| **Self-service UI for resource submission** | Adds frontend complexity; CLI proves the submission contract. | Read-only dashboard. CLI is the submission interface. |
| **Drift detection / reconciliation loop** | With mock adapters, drift cannot occur; implementing this is pure overhead. | Document as future capability. Adapter interface should structurally accept a "reconcile" call. |

---

## Feature Dependencies

Which features must exist before others can be built.

```
Team model
  └── Role model (owner / contributor)
        └── Team creation with PE approval flow
              └── Team-scoped resource CRUD
                    ├── Resource status lifecycle (pending → provisioning → ready → failed)
                    │     ├── Async status polling (required for slow resources like PECPAccount)
                    │     └── PE-editable notes field
                    ├── Project grouping (projects belong to teams)
                    │     └── Environment mapping (projects → dev / staging / prod)
                    └── Account routing (team → AWS account mapping)

Resource spec parser (YAML → internal model)
  └── Adapter dispatch (control plane → adapter interface)
        └── Mock adapters (Lambda, Container, DataService, Account, Salesforce, AEM)
              └── Synthetic status/metadata returned by mocks

REST API (resource CRUD, query, status endpoints)
  └── CLI (pecp apply / get / delete / status / team / projects / deployments)
        └── UI Dashboard (reads from REST API)
              ├── Team resource inventory view
              ├── Deployment view per environment
              └── Account status view
```

### Critical path to a demo-able PoC

```
Team model
  → Resource spec parser
    → Mock adapter layer (pluggable interface proven)
      → REST API (CRUD + status)
        → CLI (pecp apply + pecp status)
          → UI Dashboard (read-only inventory)
            → PECPAccount with async status + PE-editable notes
                                    ^^^ THIS IS THE DEMO CENTERPIECE
```

`PECPAccount` with async provisioning and PE-editable notes is the highest-value demo moment. It demonstrates the hardest real-world problem (slow, semi-manual provisioning) with the most visible UX payoff.

---

## Open Questions

- What does a `PECPSalesforce` resource spec look like? What Salesforce objects does PE provision for a team?
- What does a `PECPAem` resource spec look like? What AEM assets/configurations does PE own vs. dev teams?
- Does the org have a ServiceNow ITSM pattern that should influence the approval flow design?

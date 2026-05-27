# Pitfalls Research — PECP

**Domain:** Platform Engineering Control Plane (Kubernetes-flavored YAML processor, Python, mock adapters)
**Researched:** 2026-05-27
**Confidence:** HIGH for control-plane-specific and Python async pitfalls. MEDIUM for build-vs-buy strategic recommendations.

---

## Critical Pitfalls

High-severity mistakes that kill demos or require rewrites.

---

### CP-1: Schema Validation Too Late — Accepting Invalid Specs at the API Boundary

**What goes wrong:** The API accepts raw YAML, stores it, hands it to an adapter, and the adapter is where bad input is discovered. Resources get stuck in `provisioning` with no useful error returned to the CLI user.

**Consequences:** Resources stuck in `pending` forever; CLI returns `500` instead of a structured 422; database fills with unparseable specs that block schema migrations; demo breaks when a stakeholder submits an unknown `kind`.

**Warning signs:** `pecp apply` returns 202 with no validation feedback. Adapter code contains `if spec.get('exposure') ==` type-guards instead of a schema class. No test asserts a 422 on malformed input.

**Prevention:** Define Pydantic models for every `kind` before writing any adapter. The API validates incoming YAML against the correct Pydantic model (dispatched by `kind`) and returns structured 422 with field-level errors before touching the database. Schema definition is Phase 1 work.

---

### CP-2: Mutable `status` Written by Adapters, Owned by Nobody

**What goes wrong:** Adapters update `status` directly in the database. The control plane has no authoritative state machine. Status becomes incoherent — a subsequent adapter call silently overwrites PE-entered notes; illegal transitions (e.g. `ready → pending`) are possible.

**Warning signs:** `notes` field gets overwritten by any code path other than a PE-explicit update endpoint. No state transition table enforces illegal transitions. `status` and `spec` are in the same column or object.

**Prevention:** Separate `spec` (immutable after admission), `status` (written only by the Dispatcher via a single service-layer function), and `notes` (written only via the PE update endpoint). Define a state machine with legal transitions enforced in one place. Make `notes` an append-only log: `[{author, content, created_at}]`.

---

### CP-3: Adapter Interface Designed for the Mock, Not for Real Backends

**What goes wrong:** The interface is reverse-engineered from what mocks need (`log_what_would_happen(spec)`) rather than what real backends need (`provision(spec, account_context) → ProvisionResult`). When real adapters are implemented, the interface breaks and everything depending on it must change.

**Consequences:** Real adapter implementation requires a breaking interface change; all mock adapters rewritten; K8s operator migration blocked; `delete` is underdefined.

**Warning signs:** Adapter interface has `mock_provision(spec)` without context; no `teardown` method defined; no idempotency key or external reference returned; adapter returns `bool` instead of a structured result.

**Prevention:** Define the adapter interface from the perspective of the most complex real backend (AWS), not the simplest mock. Interface must include `provision`, `deprovision`, `get_status`, and `health_check`. Mock adapters implement this interface fully — they just return synthetic data. **Adapter interface must be locked in Phase 1 and not change without a formal versioning decision.**

---

### CP-4: Async Provisioning With No Durable State — The "Lost Job" Problem

**What goes wrong:** A provisioning job is kicked off. The process restarts. The job is gone. Resources are stuck in `provisioning` forever with no mechanism to retry or surface the failure. `PECPAccount` is the exact use case — slow, semi-manual, and async — that makes this pitfall high-severity.

**Why it happens:** Python `asyncio.create_task()` or `threading.Thread` are used for async work. Neither survives a process restart.

**Warning signs:** Async work uses `asyncio.create_task` with no persistence backing. No table exists to store in-flight jobs with their state. `pecp status awsaccount` shows `provisioning` for a resource created before the last restart.

**Prevention:** Store every async job as a row in a `provisioning_jobs` table with `status`, `started_at`, `last_updated_at`, and `error`. On startup, scan for jobs in `provisioning` state older than a threshold and mark them `failed` with a note. A real job queue is not required for the PoC — the persistence layer is.

---

### CP-5: Team/Tenant Isolation Enforced Only in the CLI

**What goes wrong:** Team isolation is enforced by the CLI (`pecp get` filters by `--team`) but not at the API layer. Any API call without a team filter returns all resources. Stakeholders ask "how do you prevent Team A from seeing Team B's data?" — "the CLI enforces it" is a red flag.

**Warning signs:** `GET /resources` returns all resources with no team scope. Team is an optional query parameter rather than required. No server-side rejection of requests missing team context.

**Prevention:** Every resource has a non-nullable `team_id` foreign key. Every API endpoint enforces team scope. Design an auth stub placeholder: middleware that today passes all requests but documents where JWT/API key → team mapping will live. Team-scoped API routing must be built in the same phase as team creation.

---

## Common Mistakes

---

### CM-1: `yaml.load()` Instead of `yaml.safe_load()`

PyYAML's `yaml.load()` with the default `Loader` executes arbitrary Python via `!!python/object` tags. A malformed spec crashes the server or executes attacker-controlled code.

**Prevention:** `yaml.safe_load()` everywhere. Enforce with a linting rule in CI. Add a test that submits YAML with `!!python/object` and asserts 422, not 500.

---

### CM-2: `kind` Dispatch Is a Giant `if/elif` Block

Adding a new kind requires editing the dispatch function. It becomes a merge conflict source and a maintenance target.

**Prevention:** Registry pattern — a dict mapping `kind` strings to adapter classes. Dispatch is `REGISTRY[kind]()`. Adding a new kind requires only registering it.

---

### CM-3: CLI Hardcodes `localhost:8000`

The CLI cannot target a deployed demo environment or a teammate's dev instance without editing source.

**Prevention:** CLI reads base URL from (in priority order): `--api-url` flag → `PECP_API_URL` env var → `~/.pecp/config.yaml` → default `http://localhost:8000`. 30-minute implementation.

---

### CM-4: Status Polling Is a Busy Loop

`while True: poll(); sleep(1)` hammers the API server. Multiple terminals during a demo exhaust connection pools.

**Prevention:** Exponential backoff with a cap (2s → 4s → 8s → 16s → 30s max). Default `pecp status` is single-shot. `--watch` wraps the polling loop.

---

### CM-5: `metadata.team` Trusted From the Spec Body

A user submits a spec with `metadata.team: another-team`. The API creates a resource owned by that team because team is read from the spec body rather than request context.

**Prevention:** `team` is always resolved from request context (URL path param or required query param). If spec body's `metadata.team` is present and doesn't match request context, return 403.

---

### CM-6: `pecp apply` Is Not Idempotent

Running `pecp apply -f lambda.yaml` twice creates two resources with the same name. The second apply should be a no-op (spec unchanged) or an update (spec changed).

**Prevention:** Enforce `UNIQUE(team_id, kind, name)` at the database level. The API apply endpoint implements upsert.

---

### CM-7: PE-Editable `notes` Is a Single Mutable String

PE Team member A writes context. PE Team member B updates it. A's note is gone. No audit trail.

**Prevention:** `notes` as an append-only log: `[{author, content, created_at}]`. The PE update endpoint appends a new entry, never replaces. Better demo story — showing the history of PE communications makes the async account flow more compelling.

---

### CM-8: Python Async Mixed With Synchronous Database Calls

Synchronous DB calls block the event loop. Under concurrent load, the server stops handling requests while a DB query runs.

**Prevention:** Make a single consistent choice: fully async stack (SQLAlchemy 2.x async mode + `aiosqlite`). Do not use SQLAlchemy 1.x or direct `sqlite3` in async handlers.

---

## PoC-Specific Risks

---

### PR-1: Mock Adapters Indistinguishable From "It Doesn't Work"

A resource goes from `pending` to `ready` with no visible activity. Stakeholders ask "so it just... changes a status field?"

**Prevention:** Mock adapters should (1) simulate realistic timing (configurable delay, 3–10 seconds), and (2) produce structured activity output surfaced in `pecp status`: `"Would call AWS Organizations CreateAccount API for team acme-corp in region us-east-1"`. This transforms the demo from "it changes a field" to "here's exactly what would happen in production."

---

### PR-2: Demo Environment Has No Seed Data

`pecp get PECPLambda --team acme` returns `No resources found.` Every demo action is performed live. One typo and the demo fails.

**Prevention:** Build a seed script that populates teams, projects, and resources in various states (one `pending`, one `provisioning`, one `ready`, one `failed`) before any stakeholder demo. Seed script lives in the repo and is tested in CI.

---

### PR-3: The PoC Proves Technical Feasibility Instead of Business Value

The PoC demonstrates CRUD operations on YAML files. It does not demonstrate the reduction in cognitive load for developers or the elimination of manual steps. Stakeholders leave impressed but make no funding decision.

**Prevention:** Write the demo script before building anything. It should narrate: "Today, a developer files a ServiceNow ticket, waits two weeks for an AWS account, receives credentials by email. With PECP: `pecp create awsaccount --team acme`, wait for `ready`, run `pecp status awsaccount`." Every feature should trace to a scene in the demo script.

---

### PR-4: Auth Stub Not Designed — Just Absent

Stakeholders ask "how would you add authentication?" — but there is no enforcement point anywhere in the codebase. Retrofitting auth requires changes to every endpoint.

**Prevention:** Design the auth stub explicitly. A `RequestContext` object with `user_id: Optional[str]`, `team_memberships: List[str]`, `is_pe_admin: bool` flows through every route handler. Today it is populated by a hardcoded stub. Tomorrow it is populated by a JWT decoder. Takes 2 hours. Makes "how would you add auth?" answerable with confidence.

---

## Build-vs-Buy Considerations

### Don't Build What Backstage Already Solves

The PoC UI dashboard is describing the Backstage software catalog. If the org later adopts Backstage, PECP's UI is thrown away. **Recommendation:** Build the control plane API as the durable artifact. Build the PoC UI as a thin, disposable demo layer. Document in PROJECT.md Key Decisions that the long-term UI strategy is Backstage or a Backstage plugin wrapping the PECP API.

**Warning signs:** UI dashboard receives more than 20% of PoC engineering time. Pagination, search, and complex state management are implemented in the PoC UI.

### Design Adapter Interface for Crossplane Compatibility

PECP's adapter layer reinvents Crossplane's Composition/Provider model. Crossplane requires K8s (org not ready), but designing the adapter interface so that a Crossplane provider is a valid future adapter implementation preserves the option. Specifically: adapters must have a `get_status` method (not fire-and-forget), which is required for Crossplane reconcile compatibility.

---

## Prevention Strategies Index

| Pitfall | Phase to Address | Effort |
|---------|-----------------|--------|
| CP-1: Spec validation at API boundary | Same phase as control plane API | Medium — Pydantic models per kind |
| CP-2: Status state machine + ownership | Same phase as resource CRUD | Medium — state machine + separated fields |
| CP-3: Adapter interface for real backends | Phase 1 — locked before mock work begins | Medium — interface design |
| CP-4: Async job persistence | Same phase as async provisioning | Medium — jobs table + startup scan |
| CP-5: Team isolation at API layer | Same phase as team creation | Small — team-scoped routes |
| CM-1: yaml.safe_load | Phase 1 — before any YAML parsing | Trivial |
| CM-2: Registry pattern for kind dispatch | When second adapter is added | Small |
| CM-3: CLI configurable API URL | Phase 1 of CLI | Small |
| CM-4: Polling backoff | When PECPAccount async flow is built | Small |
| CM-5: Team from request context, not spec | Same phase as resource CRUD | Small |
| CM-6: Idempotent apply / upsert semantics | Phase that implements resource model | Small — unique constraint + upsert |
| CM-7: Notes as append-only log | When notes/status update endpoint is built | Small |
| CM-8: Consistent sync/async choice | Before any DB code is written | Architecture decision — zero extra code |
| PR-1: Mock adapters with activity log | Mock adapter design phase | Small |
| PR-2: Demo seed script | Same phase as first end-to-end flow | Small |
| PR-3: Demo script before Phase 1 | Project inception | Zero code — write the script |
| PR-4: RequestContext stub | Phase 1 — before any route handler | Small |

**Highest-leverage interventions:** The zero/small-effort items in Phase 1 (yaml.safe_load, RequestContext stub, adapter interface locking, configurable CLI URL, team-scoped routes) prevent expensive retrofits later. The two make-or-break PoC risks are CP-3 (adapter interface) and PR-3 (proving business value, not technical feasibility).

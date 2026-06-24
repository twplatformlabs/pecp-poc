# Pitfalls Research — PECP

**Domain:** Platform Engineering Control Plane (Kubernetes-flavored YAML processor, Python, mock adapters)
**Researched:** 2026-05-27 (v1.0) · Updated: 2026-06-24 (v1.1 GitHub Integration)
**Confidence:** HIGH for control-plane-specific and Python async pitfalls. MEDIUM for GitHub API specifics and FastAPI session timing (cross-checked with official FastAPI docs). LOW confidence findings are excluded.

---

## Critical Pitfalls (v1.0 — control plane foundation)

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

## Critical Pitfalls (v1.1 — GitHub Integration)

---

### GH-1: Integration Hook Fires Before the DB Transaction Commits

**What goes wrong:** The route handler calls `on_team_create(team)` immediately after `session.add(team)` but before `await session.commit()`. GitHub team gets created. Then `commit()` fails (e.g. IntegrityError on a duplicate name). GitHub now has a team that PECP's database does not. Every subsequent `pecp team create` re-triggers `on_team_create` on a name that already exists in GitHub — causing a 422 from the GitHub API — even though the PECP team creation is itself failing.

**Why it happens:** Developers copy the pattern of "do the thing, then save" without considering that the external side effect must be decoupled from the DB transaction.

**Consequences:** Ghost GitHub teams accumulate. PECP reports team creation failure but GitHub has the team. Re-running `pecp team create` fires the hook again and hits GitHub's "Name has already been taken" 422 on a name PECP does not yet own.

**Prevention:** Always fire integration hooks **after** `await session.commit()` succeeds. The correct call order is: `session.add(team)` → `await session.commit()` → `fire_integrations(team)`. If the commit fails, the hook never fires. If the hook fails after a successful commit, PECP owns the record but GitHub provisioning failed — log the error and surface it as a warning in the response (GH-05 requirement).

**Phase to address:** Integration hook framework phase — must be enforced in `IntegrationBase` contract and the service layer that fires the registry.

---

### GH-2: DB Session Closed Before Integration Hook Runs in Background Task

**What goes wrong:** The integration hook is dispatched via `BackgroundTasks.add_task(fire_integrations, session, team)`. By the time the background task executes, FastAPI has already closed the session provided by the `get_session` yield dependency. Accessing `team.members` or any un-loaded relationship inside the hook raises `MissingGreenlet` or `DetachedInstanceError`.

**Why it happens:** FastAPI's documented execution order is: (1) path operation runs, (2) response is sent, (3) yield dependency cleanup (session close) runs, (4) background tasks execute. This is counterintuitive — developers assume the session stays open "until the background task is done."

**Consequences:** Integration hooks silently fail with `DetachedInstanceError` on first relationship access. Team is created in PECP but GitHub team is never created. No error surfaced in the CLI response because it happened in a background task after the 201 was already sent.

**Prevention:** Two options, choose one:
- **Option A (recommended for PECP):** Fire integration hooks synchronously inside the route handler, after `commit()`, before returning the response. This blocks the response by the duration of the GitHub API call (~200ms) but keeps error handling simple. GH-05 already requires errors to be caught and non-fatal — a timeout on the GitHub call prevents unacceptable delays.
- **Option B:** If hooks must run async, pass only scalar values (`team_id: str`, `team_name: str`) to the background task, not the ORM object. Inside the background task, open a fresh session: `async with AsyncSessionLocal() as session:`.

**Warning signs:** Background task function signature includes `session: AsyncSession` as a parameter passed from the route handler. ORM object attributes are accessed inside background task functions.

**Phase to address:** Integration hook framework phase — session handling pattern must be established before any hook is implemented.

---

### GH-3: GitHub API Returns 422 for "Already Exists" — Not 409

**What goes wrong:** Developer writes `if response.status_code == 409: treat_as_success()`. GitHub does not return 409 for duplicate names — it returns 422 (Unprocessable Entity) with a `errors` array containing `{"message": "Name has already been taken"}` for teams and `{"message": "name already exists on this account"}` for repos. The idempotency guard never fires. Every re-run of `pecp team create` that hits an existing GitHub team raises an exception that propagates as a 500 or an unhandled error log.

**Why it happens:** Developers assume REST convention where 409 means conflict. GitHub chose 422 for validation failures including uniqueness violations.

**Consequences:** `pecp team create` is not idempotent against GitHub — running it twice causes an unhandled error on the second run even though the correct behavior is "GitHub team already exists, treat as success."

**Prevention:** Two-pattern approach:
- **Pattern A (check-then-create):** `GET /orgs/{org}/teams/{slug}` before `POST /orgs/{org}/teams`. If 200, team exists — store the slug and skip creation. If 404, create.
- **Pattern B (create-and-handle):** Attempt creation, catch 422, inspect `response.json()["errors"][0]["message"]`, and if it contains `"already"`, treat as idempotent success and fetch the existing slug via GET.

Pattern A costs one extra API call but is cleaner. Pattern B is one call in the happy path. For PECP, Pattern A is recommended because it gives a deterministic slug even if the team was created externally.

**Phase to address:** GitHubIntegration implementation phase — must be covered in the `on_team_create` and `on_project_create` implementations.

---

### GH-4: Real GitHub API Calls in Unit Tests Break CI

**What goes wrong:** Tests for `GitHubIntegration.on_team_create()` make real HTTP calls to `api.github.com`. In CI: (a) the `GITHUB_PAT` may not be set — tests fail with `401 Unauthorized`; (b) if `GITHUB_PAT` is set, tests create real GitHub teams on every run, accumulate test data, and hit secondary rate limits after ~20 concurrent mutations; (c) test order matters because earlier tests' GitHub side effects can cause later tests to see "already exists" 422s.

**Why it happens:** The `GitHubIntegration` is instantiated directly in tests without a mock layer. The httpx calls are not intercepted.

**Consequences:** CI is flaky — fails when `GITHUB_PAT` is missing, flaky when rate-limited, leaves garbage data in the GitHub org. The existing test suite (165 tests) runs cleanly in <30s with in-memory SQLite; adding GitHub calls breaks that contract.

**Prevention:** Use `respx` to mock httpx at the transport level in all unit and integration tests. `respx.mock` intercepts calls before they leave the process — no network, no auth, no side effects. Install as a dev dependency: `pip install respx`. The pattern:

```python
import respx, httpx

@respx.mock
async def test_on_team_create_success():
    respx.post("https://api.github.com/orgs/my-org/teams").mock(
        return_value=httpx.Response(201, json={"slug": "my-team"})
    )
    integration = GitHubIntegration(pat="fake", org="my-org")
    result = await integration.on_team_create(team_name="my-team")
    assert result.slug == "my-team"
```

CI guard: add `GITHUB_PAT=test-fake-token` to CI env and ensure `respx.mock` is active for all GitHub tests. If respx is not active on a test and a real call would be made, httpx raises `respx.MockTransportError` — this surfaces uncovered tests immediately.

**Phase to address:** GitHubIntegration implementation phase — respx must be the test pattern before any real httpx calls are written.

---

### GH-5: httpx AsyncClient Created at Module Level Without Lifecycle Management

**What goes wrong:** `GitHubIntegration.__init__` creates `self.client = httpx.AsyncClient(...)`. This client is created when the integration is instantiated (at app startup) and never explicitly closed. On app shutdown, asyncio logs "Unclosed client session" or "Event loop is closed" warnings. In some configurations, this causes connection pool leaks or `RuntimeError: Event loop is closed` errors during test teardown.

**Why it happens:** httpx's `AsyncClient` is designed to be used as an async context manager (`async with`). Creating it as a long-lived object without closing it inside the lifespan is a resource leak.

**Consequences:** Test teardown noise; potential connection pool exhaustion under load; cryptic event loop errors when running pytest with `asyncio_mode = "auto"`.

**Prevention:** Two safe patterns — choose one:
- **Per-call client (recommended for PoC):** Each `GitHubIntegration` method creates its own `async with httpx.AsyncClient(...) as client:`. Simple, zero lifecycle management, no resource leaks.
- **Lifespan-managed client:** Create the client in FastAPI lifespan startup: `state.github_client = httpx.AsyncClient(...)`, close it in lifespan shutdown: `await state.github_client.aclose()`. Pass the client to `GitHubIntegration` via constructor.

For PECP v1.1, use per-call client. The overhead is negligible (GitHub API is called on team/project creation, not in hot paths).

**Warning signs:** `self.client = httpx.AsyncClient()` in `__init__` with no corresponding `aclose()` call. `pytest` output contains `ResourceWarning: Unclosed transport`.

**Phase to address:** GitHubIntegration implementation phase.

---

### GH-6: Partial Failure — PECP Record Written, GitHub Call Failed, No Recovery Path

**What goes wrong:** `create_team` succeeds: TeamRecord committed to DB. `on_team_create` fires: GitHub API call fails (network timeout, 500, rate limit). The PECP team exists with `github_team_slug = NULL`. The CLI shows the team but no GitHub team link. On the next `pecp team show`, the missing slug is ambiguous — was it intentional (integration disabled) or a failure?

**Why it happens:** Side-effecting operations cannot be atomically bundled with a DB commit. External API failure after commit creates state inconsistency with no natural retry point.

**Consequences:** Teams accumulate with `github_team_slug = NULL`. There's no built-in way to "retry the GitHub provisioning for this team." PE team has to manually create the GitHub team and update the slug. The CLI output looks incomplete.

**Prevention:**
1. Log GitHub failures with enough context to retry: `logger.error("GitHubIntegration.on_team_create failed for team_id=%s name=%s: %s", team.id, team.name, err)`.
2. Distinguish "integration disabled" (no `GITHUB_PAT` in env) from "integration failed" in the `github_team_slug` field or a separate `github_sync_status` column — `NULL` means disabled, a non-null error string means failed.
3. Future v2 work: a retry endpoint `POST /teams/{name}/sync-github` that re-fires the integration hook for teams where provisioning failed.

**Warning signs:** `github_team_slug IS NULL` for teams created while the integration is active. No error logged when GitHub call fails. CLI `pecp team show` silently omits the GitHub row.

**Phase to address:** GitHubIntegration implementation phase — logging and NULL disambiguation must be in scope.

---

### GH-7: PAT Scope Creep — Requesting More GitHub Permissions Than Needed

**What goes wrong:** Developer sets up a classic PAT with `admin:org` + `repo` + `user` + `admin:repo_hook` scopes "to be safe." The token is stored in `.env`, checked into a dev branch, or logged accidentally. When it leaks, the blast radius is all org repositories, all org members, and all webhooks — not just team management.

**Why it happens:** GitHub's classic PAT scope model is coarse-grained. `admin:org` sounds right for "manage the org" but includes `admin:org_hook` (create/delete org webhooks) and `write:org` (sync org membership). Developers don't read the scope breakdown carefully.

**Prevention:**
- Use a **fine-grained PAT** (GitHub recommends these since 2022) scoped to the specific org with only: `Organization members: Read and write` (required for team management) and `Organization administration: Read and write` (required for repo creation). Do not add `Contents: Read and write` — empty repo creation does not require it.
- Classic PAT minimum: `admin:org` + `repo` — no `user`, no `delete_repo`, no hook scopes.
- Never log the PAT value. httpx client auth header should be constructed as `Authorization: Bearer {token}` — ensure logging middleware strips `Authorization` headers.
- Add `GITHUB_PAT` to `.env.example` with a placeholder value; ensure `.env` is in `.gitignore` (it should already be).

**Phase to address:** GitHubIntegration implementation phase — PAT configuration documented in README and `.env.example`.

---

### GH-8: GitHub Secondary Rate Limit Triggered by Concurrent Test Runs

**What goes wrong:** If real GitHub API calls leak into the test suite (see GH-4), concurrent pytest-asyncio tests fire multiple `POST /orgs/{org}/teams` requests in parallel. GitHub's secondary rate limit is triggered by "too many concurrent requests to resource-mutating endpoints" — not just total requests per hour. A CI run with 10 tests creating teams in parallel can hit the secondary limit within seconds, receiving HTTP 403 with `"You have exceeded a secondary rate limit."` The test run fails non-deterministically.

**Why it happens:** `pytest-asyncio` with `asyncio_mode = "auto"` runs async tests concurrently within a session. Each test creates a GitHub resource. No backoff is in place.

**Prevention:** The primary prevention is GH-4 (use respx, never make real calls in unit tests). Secondary prevention if real calls are ever needed in a dedicated e2e job: serialize GitHub-touching tests with `@pytest.mark.serial` and add a 1-second sleep between mutations.

**Phase to address:** Same phase as GH-4 — test isolation must be established first.

---

### GH-9: Alembic Migration Adds Column With NOT NULL and No DEFAULT — Breaks Existing Data

**What goes wrong:** The migration for DATA-01 adds `github_team_slug` to the `teams` table. If the developer writes `op.add_column('teams', sa.Column('github_team_slug', sa.String(), nullable=False))` without a `server_default`, Alembic generates `ALTER TABLE teams ADD COLUMN github_team_slug VARCHAR NOT NULL`. SQLite raises `Cannot add a NOT NULL column with default value NULL` if any rows exist in the table.

**Why it happens:** The developer sees that `github_team_slug` will always be populated in production and writes `nullable=False` to enforce the invariant. But existing rows have no value to fill.

**Consequences:** Migration fails on any database that has existing team rows (including the demo seed database). The migration must be rolled back and rewritten. If the broken migration was already run against a staging or demo DB, manual schema repair is needed.

**Prevention:** `github_team_slug` must be `nullable=True` in the migration — it is null until GitHub integration runs. ORM model enforces this: `Mapped[str | None] = mapped_column(String, nullable=True)`. SQLite supports `ADD COLUMN` natively for nullable columns without table rebuild. The existing migration pattern (`0003_add_teams_projects_deployments.py`) uses `nullable=True` correctly — follow that pattern.

**Alembic safety checklist for v1.1 migration:**
- `op.add_column('teams', sa.Column('github_team_slug', sa.VARCHAR(), nullable=True))` — safe in SQLite and PostgreSQL.
- `op.create_table('project_repos', ...)` — always safe.
- Do NOT use `batch_alter_table` unless changing column types or adding NOT NULL constraints to existing data.
- Test by running `alembic upgrade head` against a copy of the production DB file before deploying.

**Phase to address:** Migration phase — must be validated before any tests run against the upgraded schema.

---

## Common Mistakes (v1.0)

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

**Prevention:** `notes` as an append-only log: `[{author, content, created_at}]`. The PE update endpoint appends a new entry, never replaces.

---

### CM-8: Python Async Mixed With Synchronous Database Calls

Synchronous DB calls block the event loop. Under concurrent load, the server stops handling requests while a DB query runs.

**Prevention:** Make a single consistent choice: fully async stack (SQLAlchemy 2.x async mode + `aiosqlite`). Do not use SQLAlchemy 1.x or direct `sqlite3` in async handlers.

---

## PoC-Specific Risks

---

### PR-1: Mock Adapters Indistinguishable From "It Doesn't Work"

A resource goes from `pending` to `ready` with no visible activity. Stakeholders ask "so it just... changes a status field?"

**Prevention:** Mock adapters should (1) simulate realistic timing (configurable delay, 3–10 seconds), and (2) produce structured activity output surfaced in `pecp status`.

---

### PR-2: Demo Environment Has No Seed Data

`pecp get PECPLambda --team acme` returns `No resources found.` Every demo action is performed live. One typo and the demo fails.

**Prevention:** Build a seed script that populates teams, projects, and resources in various states before any stakeholder demo. Seed script lives in the repo and is tested in CI.

---

### PR-3: The PoC Proves Technical Feasibility Instead of Business Value

The PoC demonstrates CRUD operations on YAML files but does not show reduction in cognitive load. Stakeholders leave impressed but make no funding decision.

**Prevention:** Write the demo script before building anything. Every feature should trace to a scene in the demo script.

---

### PR-4: Auth Stub Not Designed — Just Absent

Stakeholders ask "how would you add authentication?" but there is no enforcement point in the codebase. Retrofitting auth requires changes to every endpoint.

**Prevention:** Design the auth stub explicitly. A `RequestContext` object flows through every route handler. Today it is a hardcoded stub. Tomorrow it is populated by a JWT decoder.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fire integration hooks in background task using route session | Avoids blocking the response | Session closed before task runs — DetachedInstanceError | Never |
| Skip respx, use real GitHub API in tests | No mock setup | Flaky CI, rate limits, ghost GitHub data | Never |
| `nullable=False` on `github_team_slug` | Enforces invariant | Migration breaks on any DB with existing rows | Never — use nullable, add constraint later |
| Module-level `httpx.AsyncClient` without lifespan | Shared connection pool | Event loop errors on test teardown | Only if using FastAPI lifespan properly |
| Catch all `Exception` in integration hook | Prevents crashes | Swallows useful error context | Acceptable if every caught exception is logged with team_id and full traceback |
| PAT with `admin:org` + `repo` scopes | Gets everything working fast | Over-privileged token — blast radius if leaked | Acceptable for local dev only, not CI or demo env |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub teams API | Checking for 409 on duplicate team creation | GitHub returns 422 for all validation failures including "already exists" — parse `errors[0].message` |
| GitHub repos API | Using `repo` scope to create org repos | Org repo creation requires `admin:org` (classic PAT) or `Organization administration: write` (fine-grained PAT) |
| GitHub members API | Expecting instant membership after PUT | GitHub team membership can be `pending` (requires user to accept invite for private orgs) — treat `pending` as success |
| httpx + respx | Applying `@respx.mock` after `AsyncClient` is created | `AsyncClient` must be created inside the mock context — per-call client pattern solves this automatically |
| FastAPI + SQLAlchemy | Passing `session` to `BackgroundTasks.add_task` | Session is closed before the task runs — pass scalar IDs and open a fresh session inside the task |
| Alembic + SQLite | Using `batch_alter_table` for simple nullable ADD COLUMN | `batch_alter_table` is only needed for type changes and NOT NULL additions — simple nullable ADD COLUMN works without it |

---

## "Looks Done But Isn't" Checklist (v1.1)

- [ ] **GitHubIntegration.on_team_create:** Verify hook fires after `commit()`, not before. Check by inserting a deliberate IntegrityError and asserting no GitHub team was created.
- [ ] **Test suite:** Verify no test makes a real call to `api.github.com` — check with `respx.mock(assert_all_mocked=True)` or `GITHUB_PAT=` (empty) in CI env.
- [ ] **Migration:** Run `alembic upgrade head` against a database file with existing team rows — confirm no error. Run `alembic downgrade -1` — confirm clean rollback.
- [ ] **Idempotency:** Run `pecp team create <name>` twice with GitHub integration active — second run should succeed (or return 409 PECP-side) without creating a duplicate GitHub team.
- [ ] **PAT scopes:** Document in `.env.example` the exact PAT scopes required. Verify the PAT is not logged in any log output (check uvicorn access logs + integration error logs).
- [ ] **NULL disambiguation:** With `GITHUB_PAT` unset, `pecp team show` should show "GitHub integration disabled" rather than a blank row or error.
- [ ] **Partial failure surface:** With a bad PAT, `pecp team create` should succeed (201) with a warning line in the output, not fail (500).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| GH-1: Hook fires before commit, ghost GitHub teams | MEDIUM | Manually delete ghost GitHub teams via GitHub UI or API; add uniqueness check (GH-3) to prevent re-creation |
| GH-2: DetachedInstanceError in background task | LOW | Fix hook to use per-call session; re-run failed provisions via manual `POST /teams/{name}/sync-github` endpoint (v2) |
| GH-3: 422 not handled as idempotent | LOW | Add check-then-create or 422 error parsing; existing GitHub resources are untouched |
| GH-4: Real API calls in CI accumulated test data | MEDIUM | Delete test GitHub teams/repos via API cleanup script; add respx to test suite |
| GH-9: Migration fails on NOT NULL | LOW | Roll back migration (`alembic downgrade -1`), rewrite with `nullable=True`, re-apply |
| GH-6: Teams with NULL github_team_slug | LOW | Add `POST /teams/{name}/sync-github` in v2; for PoC, document manual recovery |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| CP-1 through CP-5 (v1.0) | Phases 1–4 (shipped) | 165 passing tests |
| GH-1: Hook fires before commit | Integration framework phase | Test: IntegrityError on create → no GitHub team created |
| GH-2: Session closed before background task | Integration framework phase | Test: hook accesses ORM attributes → no DetachedInstanceError |
| GH-3: GitHub 422 not idempotent | GitHubIntegration phase | Test: create same team name twice → second call succeeds |
| GH-4: Real API calls in tests | GitHubIntegration phase | CI passes with `GITHUB_PAT=fake` and no network access |
| GH-5: httpx AsyncClient lifecycle | GitHubIntegration phase | pytest output: no ResourceWarning or event loop errors |
| GH-6: Partial failure state | GitHubIntegration phase | Test: bad PAT → team created in PECP, warning returned, no 500 |
| GH-7: PAT scope creep | GitHubIntegration phase | .env.example documents exact required scopes |
| GH-8: Secondary rate limit in CI | GitHubIntegration phase | CI uses respx — no real GitHub calls, no rate limit exposure |
| GH-9: Migration NOT NULL failure | Migration phase | `alembic upgrade head` against DB with existing rows → success |

---

## Prevention Strategies Index

| Pitfall | Phase to Address | Effort |
|---------|-----------------|--------|
| CP-1: Spec validation at API boundary | Phases 1–2 (shipped) | Done |
| CP-2: Status state machine + ownership | Phase 2 (shipped) | Done |
| CP-3: Adapter interface for real backends | Phase 1 (shipped) | Done |
| CP-4: Async job persistence | Phase 5 (shipped) | Done |
| CP-5: Team isolation at API layer | Phases 3–4 (shipped) | Done |
| CM-1 through CM-8 (shipped) | Phases 1–5 | Done |
| GH-1: Hook fires after commit only | Integration framework phase | Small — code review checklist |
| GH-2: Fresh session in background tasks | Integration framework phase | Small — pattern established once, applied everywhere |
| GH-3: GitHub 422 idempotency | GitHubIntegration phase | Small — check-then-create pattern |
| GH-4: respx for all GitHub tests | GitHubIntegration phase | Small — one fixture, applied to all GH tests |
| GH-5: Per-call httpx client | GitHubIntegration phase | Trivial — pattern choice at implementation time |
| GH-6: Log failures, NULL disambiguation | GitHubIntegration phase | Small — two additional log statements and NULL check |
| GH-7: PAT scope documentation | GitHubIntegration phase | Trivial — .env.example update |
| GH-8: CI isolation via respx | Same as GH-4 | No extra work if GH-4 done |
| GH-9: Nullable column migration | Migration phase | Trivial — `nullable=True` in migration |

**Highest-leverage v1.1 interventions:** GH-1 (hook timing) and GH-2 (session scope) are the two pitfalls most likely to cause silent data inconsistency that is hard to debug. GH-4 (real API calls in tests) is the pitfall most likely to break CI permanently. All three must be addressed in the first phase that touches integration code.

---

*Pitfalls research for: PECP v1.0 control plane + v1.1 GitHub integration*
*Researched: 2026-05-27 (v1.0) · Updated: 2026-06-24 (v1.1)*

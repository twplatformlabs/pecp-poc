# Phase 1: Foundation + Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 1-Foundation + Contracts
**Areas discussed:** Adapter result contract, Project structure, Resource model scope, Demo script format

---

## Adapter result contract

### Q1: What should `provision()` return when it succeeds?

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic model (ProvisionResult) | Typed Pydantic model, validated, serializable | ✓ |
| Simple dataclass | Lighter, no validation overhead | |
| You decide | Claude picks | |

**User's choice:** Pydantic model (ProvisionResult)

---

### Q2: What fields should ProvisionResult carry?

| Option | Description | Selected |
|--------|-------------|----------|
| status + provider_metadata + activity_log | Core fields covering Phase 2 success criteria | |
| Add an error field too | Same + error: str \| None for failure reason | ✓ |
| You decide | Claude picks | |

**User's choice:** Add an error field too (status, provider_metadata, activity_log, error)

---

### Q3: Should `get_status()` return the same ProvisionResult, or a separate lighter type?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate StatusResult (status + notes) | Minimal type for status-only calls | |
| Reuse ProvisionResult | One return type everywhere | ✓ |
| You decide | Claude picks | |

**User's choice:** Reuse ProvisionResult

---

### Q4: Should adapters raise exceptions on failure, or return a ProvisionResult with status=FAILED?

| Option | Description | Selected |
|--------|-------------|----------|
| Return FAILED result (no exceptions) | Always return ProvisionResult; failures use error field | |
| Raise AdapterException | Typed exception caught by Dispatcher | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide — Claude chose: return FAILED result (no exceptions), consistent with error field on ProvisionResult

---

## Project structure

### Q1: src layout vs flat?

| Option | Description | Selected |
|--------|-------------|----------|
| Flat layout (pecp/ at root) | Simpler, standard for PoCs | |
| src layout (src/pecp/) | Prevents import ambiguity | ✓ |
| You decide | Claude picks | |

**User's choice:** src layout

---

### Q2: How to split sub-packages?

| Option | Description | Selected |
|--------|-------------|----------|
| api / adapters / cli / models | Four clear layers | ✓ |
| api / adapters / cli (models inline) | Fewer directories, models co-located | |
| You decide | Claude picks | |

**User's choice:** api / adapters / cli / models

---

### Q3: Dependency / project config format?

| Option | Description | Selected |
|--------|-------------|----------|
| pyproject.toml only (PEP 517/518) | Modern standard, single file | ✓ |
| pyproject.toml + requirements.txt | Familiar for pip users | |
| You decide | Claude picks | |

**User's choice:** pyproject.toml only

---

### Q4: Where should tests live?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level tests/ mirroring src/pecp/ | Standard pytest convention | ✓ |
| Alongside source | Co-located tests | |
| You decide | Claude picks | |

**User's choice:** Top-level tests/ mirroring src/pecp/

---

## Resource model scope

### Q1: How complete should the Pydantic discriminated union be in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| All 6 kinds with full spec fields | Complete models for all resource types | ✓ |
| Discriminator structure + 2 example kinds | Skeleton only, fill in Phase 2 | |
| You decide | Claude picks | |

**User's choice:** All 6 kinds with full spec fields

---

### Q2: How should `spec` vary by kind?

| Option | Description | Selected |
|--------|-------------|----------|
| Nested typed spec per kind | Discriminated union on `kind`, separate spec models | ✓ |
| Flat spec with kind-level validators | spec: dict with @model_validator | |
| You decide | Claude picks | |

**User's choice:** Nested typed spec per kind

---

### Q3: What should PECPSalesforce and PECPAem contain in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal stubs with a config: dict field | catch-all, lets Phase 2 fill real fields | ✓ |
| Placeholder models (no fields) | Empty models, strict but blocks any spec data | |
| You decide | Claude picks | |

**User's choice:** Minimal stubs with a config: dict field

---

### Q4: Shared ResourceStatus enum or separate per layer?

| Option | Description | Selected |
|--------|-------------|----------|
| One shared ResourceStatus enum in models/ | Single source of truth | ✓ |
| Separate enums per layer | More isolation, more mapping code | |
| You decide | Claude picks | |

**User's choice:** Yes, one shared ResourceStatus enum in models/

---

## Demo script format

### Q1: Primary audience?

| Option | Description | Selected |
|--------|-------------|----------|
| Stakeholders (non-technical) | Narrative-first | |
| Mixed (engineers + stakeholders) | Narrative + commands side by side | ✓ |
| You decide | Claude picks | |

**User's choice:** Mixed (engineers + stakeholders)

---

### Q2: Format?

| Option | Description | Selected |
|--------|-------------|----------|
| Narrative walkthrough with inline commands | Story with embedded pecp commands | ✓ |
| Structured runbook (sections + commands + expected output) | Step-by-step with exact output | |
| You decide | Claude picks | |

**User's choice:** Narrative walkthrough with inline commands

---

### Q3: How complete in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Full story now, fill in exact output later | Complete narrative with [expected output] placeholders | ✓ |
| Skeleton now, full detail in Phase 5 | Story arc only; Phase 5 fills details | |
| You decide | Claude picks | |

**User's choice:** Full story now, fill in exact output later

---

### Q4: Core demo scenario?

| Option | Description | Selected |
|--------|-------------|----------|
| New team onboards end-to-end | Team creation → Lambda + AWS account → PE notes → dashboard | ✓ |
| The slow path made easy (account provisioning focus) | Focus on PECPAccount async flow | |
| You decide | Claude picks | |

**User's choice:** New team onboards end-to-end

---

## Claude's Discretion

- **Exception handling:** Adapters return FAILED results rather than raising exceptions — chosen because error field on ProvisionResult makes exceptions redundant and simplifies Dispatcher code.
- **AdapterBase enforcement mechanism:** Success criteria say "TypeError at import time" — ABC raises at instantiation, not import. Claude to decide whether to use a module-level check, Protocol + runtime_checkable, or document the distinction.

## Deferred Ideas

None — discussion stayed within phase scope.

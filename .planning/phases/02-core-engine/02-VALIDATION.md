---
phase: 02
slug: core-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.4.0 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_adapters/mock/ tests/test_dispatcher/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (asyncio.sleep patched; no real latency) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_adapters/mock/ tests/test_dispatcher/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | ADPT-02, ADPT-03 | — | `yaml.safe_load` only in test fixtures | unit | `python -m pytest tests/test_adapters/mock/ -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | KINDS-04, D-04 | — | ResourceRecord ORM matches Alembic migration | integration | `python -m pytest tests/test_dispatcher/ -x -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | ADPT-02, ADPT-03, KINDS-01 | T-yaml-safe | `yaml.safe_load` in all test YAML fixtures | unit | `python -m pytest tests/test_adapters/mock/test_aws_lambda.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | ADPT-02, ADPT-03, KINDS-02 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_aws_container.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | ADPT-02, ADPT-03, KINDS-03 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_aws_data.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 1 | ADPT-02, ADPT-03, KINDS-04 | — | asyncio.sleep patched; no real 3s dwell | unit | `python -m pytest tests/test_adapters/mock/test_aws_account.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-05 | 02 | 1 | ADPT-02, ADPT-03 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_kubernetes.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-06 | 02 | 1 | ADPT-02, ADPT-03, KINDS-05 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_salesforce.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-07 | 02 | 1 | ADPT-02, ADPT-03, KINDS-06 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_aem.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-08 | 02 | 1 | ADPT-02, ADPT-03 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_datadog.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-09 | 02 | 1 | ADPT-02, ADPT-03 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_servicenow.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-10 | 02 | 1 | ADPT-02, ADPT-03 | — | N/A | unit | `python -m pytest tests/test_adapters/mock/test_jfrog.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | D-03, D-04, KINDS-04 | T-dispatch | Dispatcher is sole status writer; kind checked before registry lookup | integration | `python -m pytest tests/test_dispatcher/test_dispatch.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_adapters/mock/__init__.py` — empty, needed for pytest collection
- [ ] `tests/test_dispatcher/__init__.py` — empty, needed for pytest collection
- [ ] `tests/test_adapters/mock/test_aws_lambda.py` — stubs for ADPT-02, ADPT-03, KINDS-01
- [ ] `tests/test_adapters/mock/test_aws_account.py` — stubs for KINDS-04 sleep assertion
- [ ] `tests/test_adapters/mock/test_aws_container.py` — stubs for ADPT-02, ADPT-03, KINDS-02
- [ ] `tests/test_adapters/mock/test_aws_data.py` — stubs for ADPT-02, ADPT-03, KINDS-03
- [ ] `tests/test_adapters/mock/test_kubernetes.py` — stubs for ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_salesforce.py` — stubs for ADPT-02, ADPT-03, KINDS-05
- [ ] `tests/test_adapters/mock/test_aem.py` — stubs for ADPT-02, ADPT-03, KINDS-06
- [ ] `tests/test_adapters/mock/test_datadog.py` — stubs for ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_servicenow.py` — stubs for ADPT-02, ADPT-03
- [ ] `tests/test_adapters/mock/test_jfrog.py` — stubs for ADPT-02, ADPT-03
- [ ] `tests/test_dispatcher/test_dispatch.py` — stubs for D-03, D-04, KINDS-04 (Dispatcher flow)
- [ ] `db_session` fixture added to `tests/conftest.py` — shared async in-memory session for Dispatcher tests
- [ ] `src/pecp/adapters/mock/__init__.py` — re-exports all 10 adapter classes

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `AwsAccountMockAdapter.provision()` dwells ≥3s in PROVISIONING under real conditions (no sleep patch) | KINDS-04 | Real sleep is always patched in CI; confirming 3s dwell requires running without patch | `python -c "import asyncio; from pecp.adapters.mock.aws_account import AwsAccountMockAdapter; from pecp.models.resource_spec import ResourceSpec; import yaml; spec = ResourceSpec.model_validate(yaml.safe_load(open('example.yaml'))); asyncio.run(AwsAccountMockAdapter().provision(spec))"` and verify elapsed time ≥ 3s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

# Scenario 13 — Account Async Provisioning (Phase 5)

Demonstrates the async AWS account provisioning flow: requesting an account,
watching it transition through provisioning states, and retrieving credentials.

## Prerequisites

- Server running: `python -m uvicorn pecp.api.main:app --reload`
- Team `toxins-research` exists (run Scenario 09 or `pecp team create toxins-research --owner alice`)

## Steps

**1. Request a new AWS account:**

```bash
pecp create awsaccount --team toxins-research
```

Expected: request accepted immediately with status `pending`:
```
Applied PECPAccount pecp-toxins-research → id=res-<uuid> status=pending
```

The account provisioning is asynchronous. The PECP mock adapter simulates
AWS Organizations and transitions the resource through `pending` → `provisioning` → `ready`.

**2. Check account status:**

```bash
pecp status awsaccount --team toxins-research
```

Expected: status table showing `pending` or `provisioning` with synthetic metadata:
- `account_id`, `account_email`, `account_name`, `management_console_url`

No credential fields are shown (D-03 security constraint).

**3. Watch the account provision in real time:**

```bash
pecp status awsaccount --team toxins-research --watch
```

Expected: polls every 2 seconds, shows each transition:
```
[09:05:00] status: pending
[09:05:01] status: provisioning
[09:05:03] status: provisioning  [PE note] Approval ticket filed: CHG-00412
[09:05:12] status: ready
```

The account mock adapter dwells ~3 seconds in `provisioning` before reaching `ready`.
PE notes may appear mid-stream — appended via the API by simulator or demo orchestrator.

**4. Retrieve account credentials once ready:**

```bash
pecp login awsaccount --team toxins-research
```

Expected: shell-exportable credential lines:
```
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
# Profile: pecp-toxins-research | Account: 123456789012
# Copy and paste the above into your terminal, or run: eval $(pecp login awsaccount --team toxins-research)
```

If the account is not yet `ready`, exits with code 2 and a helpful message.

## What this proves

The async provisioning pattern lets teams request infrastructure that takes seconds
or minutes (AWS account creation) without blocking the CLI. The `--watch` flag gives
real-time visibility into the provisioning pipeline. PE notes provide a human channel
overlaying the process. Credentials are only surfaced after the resource reaches `ready`.

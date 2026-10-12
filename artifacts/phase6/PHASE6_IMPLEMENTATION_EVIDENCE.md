# FRACTAL-FLOW — Phase 6 Implementation Evidence

Date: 2026-10-07

## Scope

This evidence covers the current non-live Phase 6 implementation slices only:

- 6A protocol/framing foundation
- 6B durable application command ledger
- 6C normalized broker-truth model
- authentication/session derivation foundation
- protective-policy foundation

It does **not** establish live MT5 execution authorization.

## Source changes

- `src/fractal_flow/execution/ffbp_protocol.py`
- `src/fractal_flow/execution/command_ledger.py`
- `src/fractal_flow/execution/broker_truth.py`
- `src/fractal_flow/execution/ffbp_session.py`
- `src/fractal_flow/execution/protective_authority.py`
- focused Phase 6 tests for each module
- `docs/DECISION_LOG.md`
- `artifacts/phase6/PHASE6_IMPLEMENTATION_HPL.md`

## Focused verification

Command:

```text
python -m pytest --no-cov -q tests/test_ffbp_protocol.py tests/test_command_ledger.py tests/test_broker_truth.py tests/test_ffbp_session.py tests/test_protective_authority.py
```

Result:

```text
22 passed in the current focused gate
```

The focused campaign covers canonical bytes, HMAC tamper rejection, framing limits, sequence gaps/replays, account/session fencing, bounded queues, durable restart, duplicate/conflict command identity, UNKNOWN no-blind-resend, broker truth normalization, authoritative vs non-authoritative absence, partial fills, HKDF RFC5869 vector, nonce/session binding, protection gating, dead-man behavior, and TTL expiry.

## Compile verification

```text
python -m compileall -q src tests tools
```

Result: PASS.

## Regression verification

The repository-wide ordinary regression was run with the two explicit Phase 5 stress/regression modules excluded because they are separately governed by their own workload-aware campaigns:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS='' python -m pytest -q -o addopts= --ignore=tests/regression/test_phase5_r5_real_campaign.py --ignore=tests/regression/test_phase5_r5_real_campaign.py --ignore=tests/regression/test_phase5_state_machine_hardening.py
```

Result:

```text
767 passed, 6 xfailed in 10.41s
```

This is **not** a replacement for the Phase 5 R5 campaign. The previously verified R5 artifact remains the historical Phase 5 verification authority.

## Tool availability

`ruff` and `mypy` executables were not available in this environment. They remain **UNVERIFIED / ENVIRONMENTAL EXCEPTION** and are not claimed green.

Git provenance is also not established from this archive/tree because `.git` metadata is absent. It remains **UNVERIFIED / ENVIRONMENTAL EXCEPTION**.

## Current Phase 6 gate

**🔴 PHASE 6 FINAL GATE BLOCKED — DO NOT GENERATE FINAL PHASE 6 ARTIFACT.**

Remaining blockers include Python↔MQL5 authenticated-session interoperability, effectful command path, MT5 broker reconciliation runtime evidence, event/snapshot/history synchronization, complete protection continuity, crash/restart matrix, netting/hedging/partial-fill runtime campaigns, cross-language vectors, MetaEditor compile evidence, and final artifact/reproducibility closure.

The current implementation is authorized for continued non-live development only.

## Supplied MQL5 vector reproduction

The supplied `FFBP_INTEROP_VECTOR.json` was independently reproduced in Python.

Result: HMAC, canonical wire body, 337-byte wire length, and `00000151` frame prefix all matched exactly. This proves deterministic compatibility with the supplied vector, not MetaEditor compilation or live MT5 interoperability.

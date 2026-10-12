# FRACTAL-FLOW — Phase 6 Local WSL + MT5 Verification Package Evidence

Date: 2026-10-07

## Scope

This package extends the verified non-live Phase 6 implementation slice with the supplied MQL5 Phase6Bridge sources and a reproducible local WSL/MT5 verification harness.

It does **not** establish live trading authorization or real MT5 broker-effect verification.

## Python focused gate

```text
python -m pytest -q -o addopts= tests/test_ffbp_protocol.py tests/test_ffbp_session.py tests/test_ffbp_interop_vector.py tests/test_command_ledger.py tests/test_broker_truth.py tests/test_protective_authority.py
```

Result:

```text
22 passed
```

## Ordinary regression gate

The two workload-heavy Phase 5 modules are separately governed by the Phase 5 verification lifecycle and are intentionally not folded into this short local regression command:

```text
python -m pytest -q -o addopts= --ignore=tests/regression/test_phase5_r5_real_campaign.py --ignore=tests/regression/test_phase5_state_machine_hardening.py
```

Result:

```text
767 passed, 6 xfailed in 10.41s
```

This does not replace the separately verified R5 campaign.

## Compilation

```text
python -m compileall -q src tests tools
```

Result: PASS.

## Cross-language vector

The supplied MQL5 interoperability vector reproduces exactly on the Python side:

- canonical wire body: matched;
- HMAC: matched;
- payload length: 337 bytes;
- frame prefix: `00000151`.

This is deterministic vector evidence, not MetaEditor or terminal runtime evidence.

## MQL5 package

Included:

- `FractalFlowBridgeEA.mq5`
- `FFBP_Json.mqh`
- `FFBP_Persistence.mqh`
- `FFBP_Crypto.mqh`
- `FFBP_Broker.mqh`
- `FFBP_CryptoSelfTest.mq5`
- supplied bridge documentation and interoperability vector.

The files are preserved from the separately supplied verified Phase6Bridge snapshot; no claim of successful local MetaEditor compilation is made by this package.

## Required local MT5 verification

Run in this order on a controlled **demo/test account only**:

1. MetaEditor compile of EA and crypto self-test.
2. Crypto self-test.
3. HELLO/CHALLENGE/AUTH/SESSION_ESTABLISHED.
4. Account/session mismatch rejection.
5. Replay and sequence-gap rejection.
6. Observation-only transport.
7. Snapshot/history synchronization.
8. Python restart.
9. MT5 restart.
10. Simultaneous restart.
11. Only after prerequisite HPL rows are green: effectful demo command campaign.

Preserve terminal logs, compile reports, protocol traces, and broker evidence.

## Current gate

**🔴 PHASE 6 FINAL GATE BLOCKED — DO NOT GENERATE FINAL PHASE 6 ARTIFACT.**

Remaining mandatory evidence includes authenticated MT5 session completion, MT5 observation/synchronization, MetaEditor compile evidence, real terminal interoperability, broker reconciliation, effectful demo path, protection continuity, crash/restart matrix, netting/hedging/partial-fill runtime campaigns, and final artifact re-verification.

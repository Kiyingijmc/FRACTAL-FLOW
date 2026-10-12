# FRACTAL-FLOW FFBP/1 — MQL5 adapter candidate

This directory contains the Phase 6 MQL5-side implementation candidate.
It is intentionally **fail-closed** and is not live-trading authorization.

## Files

- `FractalFlowBridgeEA.mq5` — EA entry point and protocol pump.
- `Include/FFBP_Crypto.mqh` — SHA-256 and explicit HMAC-SHA256.
- `Include/FFBP_Json.mqh` — bounded fixed-envelope JSON helpers.
- `Include/FFBP_Persistence.mqh` — durable session-fence and command evidence files.
- `Include/FFBP_Broker.mqh` — broker/protective boundary.

## Compile procedure

1. Copy `Experts/FractalFlowBridge` into `<terminal data>/MQL5/Experts/FractalFlowBridge`.
2. Open `FractalFlowBridgeEA.mq5` in MetaEditor.
3. Compile with warnings visible.
4. Record the exact compiler output, including warnings and line numbers.
5. Do not attach it to a live/real account.
6. For first runtime testing use a demo account and localhost only.
7. Add `127.0.0.1` to the MT5 terminal's allowed WebRequest/socket address list as required by the terminal's network permissions.

## Current verification boundary

The files have been statically reviewed against the MQL5 API documentation but have **not** been compiled in MetaEditor in this environment.

The adapter intentionally refuses effectful COMMAND processing until the following are fully implemented and runtime-verified:

- challenge/auth state transition;
- session-derived key installation;
- durable command deduplication before broker effect;
- broker order/deal/position reconciliation;
- command result persistence;
- protective command authorization;
- restart equivalence.

A successful MetaEditor compile is therefore necessary evidence, but is not sufficient for Phase 6 closure.

## Important security note

`InpSharedSecret` is an EA input and must not be logged or committed to source control. For production use, replace plaintext input handling with the approved secret provisioning mechanism after the trust boundary has been validated.

# FRACTAL-FLOW Phase 6 — Local WSL + MT5 Verification Plan

## Purpose

This package is a development/test boundary package. It does not authorize live trading.

## WSL

From the repository root:

```bash
./tools/run_phase6_local_gate.sh
```

The script compiles Python sources, runs the Phase 6 focused campaign, then runs the complete Python regression with pytest plugin autoload disabled for deterministic subprocess behavior.

## MT5 / MetaEditor

Copy `mql5/Phase6Bridge/FractalFlowBridge/` into the terminal's `MQL5/Experts/FractalFlowBridge/` source tree and `FractalFlowBridgeTests/` into a test location under `MQL5/Experts/`.

Compile `FractalFlowBridgeEA.mq5` and `FFBP_CryptoSelfTest.mq5` in MetaEditor. Record:

- MetaEditor build/version
- compile success/failure
- warnings/errors
- terminal build
- account login (redacted in published evidence)
- broker/server name
- margin mode (netting/hedging)
- demo/test account status

## Runtime campaign order

1. Crypto self-test.
2. HELLO/CHALLENGE/AUTH/session establishment.
3. Account/session mismatch rejection.
4. Replay/sequence-gap rejection.
5. Observation-only socket campaign.
6. Snapshot/history synchronization.
7. Restart/reconnect campaign.
8. Only after prerequisite HPL rows are green: effectful command campaign on a controlled demo account.

## Safety

Do not use a live account. Do not treat `OrderSend` return success as broker-effect confirmation. Do not blindly resend an UNKNOWN command. Preserve terminal logs and protocol evidence for every campaign.

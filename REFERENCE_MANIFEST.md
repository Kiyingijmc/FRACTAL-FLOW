# Phase 6 Fresh Session Handoff — Provenance Manifest

## Included current base

The project tree was based on:

`FRACTAL-FLOW-PHASE6-LOCAL-WSL-MT5-SESSION-GATE-20261007-HKDF-FIX.zip`

Known SHA256:

`77f82d4541d919b0bd1378cf49114021a095e8bda7ac50eebe8317a1148e0ffd` (see source package if exact historical hash is required)

## Earlier authoritative references

- Phase 5 verified-green package: `FRACTAL-FLOW-R5-VERIFIED-GREEN-20261007.zip`
- Phase 6 design specifications: `reference/FRACTAL-FLOW-PHASE6-DESIGN-SPECIFICATIONS/`
- Phase 6 canonical research HPL: `reference/FRACTAL-FLOW-PHASE6-CANONICAL-RESEARCH-HPL.md`
- Prior implementation HPL: `reference/PHASE6_IMPLEMENTATION_HPL-PRIOR.md`

## Current-session overlays

- `mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5` — exact diagnostic source recovered from the current conversation attachment; use this as the current runtime source for forensic comparison.
- `mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA-PACKAGED-HKDF-FIX.mq5` — packaged pre-diagnostic source preserved for comparison.
- `mql5/Phase6Bridge/FractalFlowBridgeTests/FFBP_SocketSelfTest.mq5` — minimal native socket probe.
- `artifacts/phase6/evidence/MT5_RUNTIME_LOG_20261007-171016.txt` — owner-observed MT5 runtime log showing TCP connection and HELLO send, followed by repeated quarantine.
- `artifacts/phase6/evidence/WIRE_JSON_DECODE_FAILURE_20261007.txt` — Python decoder traceback.

## Important provenance limitation

The exact local WSL Git metadata is not included in this handoff ZIP. Git provenance must be independently checked in the fresh session and classified according to the governing environmental-exception rule.

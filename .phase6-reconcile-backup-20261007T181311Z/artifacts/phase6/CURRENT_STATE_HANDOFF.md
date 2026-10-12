# FRACTAL-FLOW Phase 6 — Current State Handoff

## Snapshot scope

This snapshot combines the authoritative Phase 5 Part-B baseline ZIP supplied for the Phase 6 effort with the current manually verified MQL5 bridge artifact set v1.1.2.

The Phase 5 baseline is the source-of-truth Python repository snapshot supplied by the owner. The MQL5 bridge artifacts are overlaid under `mql5/Phase6Bridge/`.

## MQL5 evidence established by owner-side MetaEditor/MT5 execution

- `FractalFlowBridgeEA.mq5`: compiled with **0 errors, 0 warnings**; code generated.
- `FFBP_CryptoSelfTest.mq5`: compiled with **0 errors, 0 warnings**; code generated.
- `FFBP_CryptoSelfTest` executed in MT5.
- Experts log reported: `PASS: RFC 4231-style HMAC test vector`.
- The HMAC self-test was observed successfully more than once.
- MQL5 include layout was manually validated using `MQL5\\Include\\FFBP_*.mqh`.

## MQL5 status

Closed/verified:
- Include resolution.
- EA source compilation.
- Crypto self-test compilation.
- HMAC-SHA256 known-answer runtime test.

Not yet verified:
- Python <-> MQL5 TCP interoperability.
- FFBP/1 HELLO/CHALLENGE/AUTH handshake.
- Session fencing across the actual MT5 boundary.
- Sequence/replay behavior across the actual socket.
- MT5 persistence/restart recovery.
- Broker reconciliation.
- Protective autonomy under network/process failure.
- End-to-end crash/recovery equivalence.

## Important safety boundary

No live trading authorization is implied by this snapshot. `InpAllowReal=false` remains the fail-closed default. The bridge must remain non-effectful until the end-to-end HPL is independently verified.

## Python Phase 6 status

The prior forensic work established Phase 6A/6B/6C design and implementation units (canonical bridge specification, protocol core, durable command ledger, and session fencing) in the working analysis environment. Those exact working-tree source changes are **not reconstructed into this downloadable snapshot** because the authoritative bytes of that ephemeral working tree are not available here. Do not represent this ZIP as containing those exact Python Phase 6 source modifications.

Therefore Codex must first perform a fresh forensic inventory of the Python tree and reconcile the Phase 6 artifacts/specification against the current source before making further changes.

## Next objective

Create a local Git repository from this snapshot, then use Codex to:

1. inventory and fingerprint the tree;
2. establish the Phase 5 baseline test state;
3. reconcile the Phase 6 specification against source;
4. inspect the MQL5 bridge artifacts under `mql5/Phase6Bridge/`;
5. implement/recover missing Python Phase 6 bridge components only from verified evidence;
6. run targeted tests first, then full regression;
7. keep MQL5 runtime verification as an external evidence stream supplied by the owner.

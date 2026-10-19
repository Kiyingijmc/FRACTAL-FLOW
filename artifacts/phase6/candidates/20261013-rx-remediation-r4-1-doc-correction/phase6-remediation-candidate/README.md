# Phase 6 receive-path remediation candidate (2026-10-13, package revision 4.1 (documentation correction)

**Disposition: review candidate only; not reconciled to the current canonical EA; not deployable.**

This overlay contains a persistent receive-buffer EA candidate inherited from the Oct 11 remediation bundle, plus exact canonical account-ID matching and a signed-64-bit session-fence exhaustion guard. Revision 2 fixes a packaging defect in the earlier candidate bundle: the UTF-8 end-to-end tests depended on `tools/ffbp_adversarial_rx_server.py` and `tools/ffbp_utf8_cases.py`, but the earlier ZIP omitted those compatible test helpers. The helpers are now included from the Oct 11 remediation overlay.

## Candidate behavior
- Retains partial TCP frame bytes across timer callbacks.
- Uses a bounded frame buffer and validates the 4-byte big-endian length before accepting the body.
- Validates UTF-8 on raw frame bytes before string conversion.
- Applies a bounded 2,000 ms frame-assembly deadline.
- Preserves fail-closed quarantine and reason-coded diagnostics.
- Requires exact canonical decimal account identity.
- Refuses to increment a signed-64-bit session fence at exhaustion.
- Rejects configured frame limits above the protocol maximum of 65,536 bytes before signed-int buffer arithmetic.

## Test results in this analysis environment
- Static EA guard/invariant tests after R4: **14 passed in 0.06 s**.
- Full candidate tests after R4: **22 passed in 8.04 s**.
- R4 corrects the R3 test that compared offsets from different coordinate systems. The replacement checks that the frame-limit guard precedes `FFBP_LoadFence()` and `ConnectBridge()` within the same `OnInit()` body, and separately checks the RX capacity/buffer bounds in `ReadFrame()`.
- The three end-to-end Python tests exercise the Python test server and Python protocol peer, **not an MT5 EA runtime**.
- The Python `src/fractal_flow` modules available to this analysis run came from the Oct 9 repository snapshot because the exact Oct 12 working tree is not present in this environment. The result must not be represented as validation against the current Oct 12 Python tree.
- No MetaEditor compile, MT5 terminal runtime, actual EA socket test, current EX5 identity, or broker-state test was performed.

## R4 review correction
R3 had a faulty ordering assertion in `tests/test_ffbp_frame_limit.py`: it compared an offset relative to the extracted `OnInit()` body against an absolute source-file offset. R4 removes that invalid comparison. The corrected assertion uses offsets from the same function body. The first R4 test attempt exposed that `SocketConnect()` is called inside `ConnectBridge()`, not directly inside `OnInit()`; the final test checks that `OnInit()` validates the frame limit before invoking `ConnectBridge()`. Final full and static suites pass. See `docs/R4_CHANGE_NOTE_20261013.md`.

## Files
- `ea/FractalFlowBridgeEA.REMEDIATED.mq5` — candidate EA; build ID remains `UNSTAMPED` until resolved source/includes are hashed and stamped.
- `patches/06_exact_identity_and_epoch_exhaustion.patch` — two additional corrections relative to the inherited Oct 11 candidate.
- `baseline/FractalFlowBridgeEA.REMEDIATED.prepatch.mq5` — immutable inherited candidate copy.
- `tests/` — static and UTF-8 case tests.
- `tools/ffbp_adversarial_rx_server.py`, `tools/ffbp_utf8_cases.py` — matching test-only helpers required by the UTF-8 end-to-end tests.
- `tools/ffbp_log_hygiene_scan.py` — source/log hygiene scanner.
- `docs/PHASE6_HPL_DELTA_20261013.md` — updated HPL delta.
- `docs/PHASE6_RX_REMEDIATION_AUDIT_20261013.md` — audit findings and test scope.
- `evidence/` — test outputs and source identity limitations.

## Explicit limitations / release gates
The only full repository archive available to this analysis environment is dated Oct 9. Oct 12 evidence records canonical WSL EA SHA-256 `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`, which is not represented by this candidate. Therefore this candidate has **not** been patched onto or reconciled with the current canonical EA. Do not copy it over canonical or deployed files.

Missing-fence first-run provisioning, connection error 5272, ACK contract, source/build/deployment identity, current include parity, broker reconciliation, protective continuity, crash recovery, and all release gates remain open. `InpAllowReal=false` remains mandatory. No deployment, Git mutation, or live state-file modification is authorized or performed.


## R4.1 documentation correction
The HPL delta RX-07 count was stale and has been aligned with the final R4 test evidence (14 static, 22 full candidate tests). This revision changes documentation/checksums only. It does not add MT5 compile/runtime evidence or change the blocked release disposition.

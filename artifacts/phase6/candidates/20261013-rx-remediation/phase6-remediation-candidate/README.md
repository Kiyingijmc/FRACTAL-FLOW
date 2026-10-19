# Phase 6 receive-path remediation candidate (2026-10-13)

This is a reviewable candidate overlay, not a deployment package. It contains a persistent receive-buffer EA candidate inherited from the Oct 11 remediation bundle, plus two additional source-level safety corrections: exact canonical account-ID matching and a signed-64-bit session-fence exhaustion guard.

## Why this exists
Historical MT5 logs show successful session establishment followed almost immediately by fatal/incomplete-frame quarantine. The older receive loop reads the header and body with short blocking deadlines and has no durable partial-frame buffer. The candidate preserves partial bytes across timer callbacks, bounds buffering, rejects malformed UTF-8 before decode, attributes receive failures, and retains fail-closed quarantine.

## Files
- `ea/FractalFlowBridgeEA.REMEDIATED.mq5` — candidate EA; build ID remains `UNSTAMPED` until stamped against the actual resolved include set.
- `patches/06_exact_identity_and_epoch_exhaustion.patch` — only the two additional changes made in this run, relative to the inherited Oct 11 candidate.
- `baseline/` — immutable copy of the inherited candidate for comparison.
- `tests/` and `tools/` — static source guards and hygiene scanner.
- `docs/PHASE6_HPL_DELTA_20261013.md` — updated HPL delta and release disposition.
- `evidence/static_test_results.txt` — exact test command and result.

## Verification performed here
11 static tests passed. The receive buffer, strict UTF-8 order, structured quarantine, no-auth-material logging, exact identity comparison, and epoch overflow guard are statically asserted.

## Explicit limits
- No MetaEditor compile or MT5 runtime was available; no MQL5 compilation/runtime claim is made.
- The full repository snapshot available here is dated Oct 9; Oct 12 evidence reports a different current canonical EA hash. Therefore this candidate is **not reconciled to the exact current WSL source** and must not be blindly copied over the canonical or deployed EA.
- Missing-fence first-run provisioning, connection error 5272, ACK contract, live source/EX5/include identity, broker reconciliation, protective continuity, crash recovery and all release gates remain open.
- Do not enable real-account execution. No deployment, Git mutation, or live state-file modification is authorized or performed.

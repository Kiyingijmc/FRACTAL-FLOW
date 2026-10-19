# FRACTAL-FLOW Phase 6 HPL Delta — 2026-10-13

**Disposition: BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL.** `InpAllowReal=false` remains mandatory. This delta supplements, and does not replace, the canonical HPL.

## HPL-FFBP-RX-01 — Receive framing under TCP fragmentation/coalescing
- **Observed:** historical EA logs show authenticated session establishment followed immediately by `fatal/incomplete frame` quarantine; source snapshot used separate 25 ms header and 50 ms body reads.
- **Remediation candidate:** persistent bounded receive buffer, nonblocking frame extraction, 2,000 ms assembly deadline, strict UTF-8 validation before lossy decode, reason-coded rejection and structured quarantine.
- **Status:** source-level candidate + static tests pass. Actual MT5 compile/runtime fragmentation, coalescing, idle and peer-close tests remain **UNVERIFIED**. The 2,000 ms policy value requires runtime validation.
- **Required evidence:** MetaEditor compile identity, then demo-only adversarial cases for fragmented header/body, coalesced frames, idle >=30s, zero/oversize length, partial-frame deadline, peer close, and bounded-buffer faults.

## HPL-FFBP-ID-02 — Canonical account identity
- **Defect:** numeric parsing can accept noncanonical representations such as a configured account ID with leading zeros.
- **Remediation candidate:** require `InpAccountId` to equal `IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))` exactly.
- **Status:** static assertion passes; MQL5 compile/runtime behavior **UNVERIFIED**.

## HPL-FFBP-FENCE-03 — Epoch exhaustion / overflow
- **Defect:** incrementing the durable signed-64-bit fence at its maximum can wrap or fail at persistence after mutation.
- **Remediation candidate:** refuse startup when loaded epoch is at or above `0x7FFFFFFFFFFFFFFF`, before increment.
- **Status:** static assertion passes. Needs MQL5 compile and boundary tests for max-1, max, corrupt and missing fence. **OPEN:** first-run fence provisioning remains unresolved; do not weaken fail-closed behavior.

## HPL-FFBP-RX-07 — Configured frame limit / signed arithmetic
- **Defect:** `InpMaxFrameBytes` was only lower-bounded, then cast to signed `int` for RX buffer arithmetic; the Python protocol maximum is 65,536 bytes.
- **Remediation candidate:** reject values above 65,536 at EA initialization; add static regression checks.
- **Status (R4 candidate):** source-level guard added; **14 static and 22 full candidate tests pass**. MQL5 compile/runtime and protocol config integration **UNVERIFIED**. The 13-static/21-full counts belong to historical R3 evidence only.

## HPL-FFBP-SRC-04 — Source/build/deployment identity
- **Observed:** the Oct 12 evidence reports canonical WSL EA hash `95bc98a0...`; the full repository archive available in this workspace is dated Oct 9, and historical deployed candidates have divergent hashes.
- **Status:** **OPEN**. This bundle is a candidate overlay based on the Oct 11 remediation EA, not a verified patch onto the exact Oct 12 WSL canonical file. Do not deploy or overwrite either source tree on this basis.

## HPL-FFBP-AUTH-05 — Authentication material logging
- **Remediation inherited:** remove proof/transcript/nonce-value logging; static log-hygiene test passes on this candidate.
- **Status:** source-level only. Scan current canonical source and actual runtime logs after build identity is reconciled; rotate any secret that was exposed.

## HPL-FFBP-CONN-06 — SocketConnect failures
- **Observed:** `SocketConnect error=5272` / `INIT FAIL: ConnectBridge` appears in historical logs, separate from post-auth RX failures.
- **Status:** **OPEN**. Do not conflate connection initialization failures with RX framing. Existing terminal allow-list, execution context, listener lifecycle, host/port and terminal build need to be distinguished using build-stamped logs; this candidate does not claim a fix.

## R4 test-quality correction
- R3 source-order test compared an index relative to the `OnInit()` body with an absolute source-file index. This was invalid evidence.
- R4 now compares the frame-limit guard and `FFBP_LoadFence()` / `ConnectBridge()` call offsets within the same `OnInit()` body, and checks receive capacity guards separately inside `ReadFrame()`.
- Status: corrected source-structure tests pass. MQL5 compiler/runtime remains unverified.

## Release gate
No MT5 compiler/runtime is available in this analysis environment. Python static checks cannot establish MQL5 compilation or terminal socket semantics. Broker truth, startup reconciliation, protective continuity, crash/restart recovery, deployed include parity, current EX5 identity, and real-account execution remain **BLOCKED/UNVERIFIED**.


## R4.1 documentation correction
- Corrected the RX-07 status above to match the final R4 evidence: 14 static tests and 22 full candidate tests. R3 counts remain historical and are not the current candidate result.
- This R4.1 package revision changes documentation and package checksums only; it does not change EA candidate source, tests, or test outputs.

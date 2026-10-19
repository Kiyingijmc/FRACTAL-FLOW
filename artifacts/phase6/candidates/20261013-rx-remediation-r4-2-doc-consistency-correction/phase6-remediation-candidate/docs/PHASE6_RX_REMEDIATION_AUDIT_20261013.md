# Phase 6 RX remediation candidate audit — 2026-10-13

## Decision
**BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL.** This is a candidate overlay, not a canonical-source patch or a release build.

## Evidence-led findings

### RX framing
Historical terminal logs show successful authentication followed by fatal/incomplete-frame quarantine. The source snapshot used separate short header/body reads. A persistent bounded receive buffer is a reasonable remediation candidate because it allows fragmented headers and bodies to survive across timer callbacks, while allowing coalesced frames to remain buffered for subsequent extraction. The 2,000 ms assembly deadline is a candidate policy value, not yet a validated MT5 runtime threshold.

### Candidate tests and historical counts
- **Historical R2:** 11 static EA source-guard/invariant tests and 19 full candidate tests passed.
- **Historical R3:** 13 static EA source-guard/invariant tests and 21 full candidate tests passed after the R3 frame-size upper-bound guard was added. These are R3 results, not the final R4 counts.
- **Final R4 candidate evidence:** 14 static EA/invariant/frame-limit tests and 22 full candidate tests passed (details below). R4 corrected a faulty source-order assertion; it did not add MT5 compile or runtime evidence.
- The first full candidate test run failed collection because the candidate ZIP omitted `src.fractal_flow`; adding the repository source path enabled the static tests.
- The next run had three end-to-end tests fail to start because the only server helper in the Oct 9 snapshot supports the older framing case names, not the UTF-8 case names. The correct Oct 11 remediation helper was then included; all 19 R2 tests passed before the R3 addition.
- The 3 end-to-end cases exercise Python protocol/server behavior only. They do not compile or execute the MQL5 candidate.

### R3 review finding corrected in R4: frame-limit test ordering
The EA exposes `InpMaxFrameBytes` as a configurable `uint`, but the RX buffer capacity calculation casts it to signed `int` and adds four bytes. The prior `OnInit` guard only enforced a lower bound, while the Python protocol implementation and test server default to a 65,536-byte maximum. Values above that protocol maximum could create incompatible behavior and potentially overflow signed arithmetic. R3 rejects `InpMaxFrameBytes > 65536` during input validation. Review found that one R3 ordering assertion compared offsets from different coordinate systems and therefore did not prove its intended relationship. R4 replaces it with same-function offsets: the guard must precede `FFBP_LoadFence()` and `ConnectBridge()` within `OnInit()`. A separate assertion checks the capacity guard and maximum new buffer size within `ReadFrame()`. The corrected suite passes 14 static and 22 full candidate tests. This remains source-level candidate evidence only; it is not proof of MQL5 compilation or runtime behavior.

### Canonical source identity
The Oct 12 source capture records canonical WSL EA SHA-256 `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`. The available full repository ZIP is dated Oct 9, and this EA candidate derives from the Oct 11 remediation overlay. There is no verified diff from the Oct 12 canonical EA to this candidate. This is a hard stop against overwriting canonical or deployed EA files.

### Separate unresolved issues
- `SocketConnect error=5272` remains a distinct initialization failure; RX buffering is not a remedy for it.
- Missing/corrupt fence behavior and first-run provisioning remain unresolved. Fail-closed behavior must not be weakened.
- Current EX5 and resolved include identity have not been proven.
- ACK correlation/sequence contract, startup broker reconciliation, protective continuity, and crash/restart recovery remain release blockers.

## R4 test evidence
- Full candidate suite: **22 passed in 8.04 s**.
- Static EA/invariant/frame-limit suite: **14 passed in 0.06 s**.
- These tests use the Oct 9 Python source snapshot for repository imports and the candidate EA for source checks. They do not execute MT5.

## Required next gates
0. Keep the configured maximum at 65,536 bytes or less and verify the candidate input guard compiles in MetaEditor.
1. Reconcile this RX design against the exact Oct 12 canonical EA source and retain all unrelated canonical fixes.
2. Run syntax/build checks in MetaEditor and record compiler build, source hash, resolved include hashes, and output EX5 hash.
3. In demo-only MT5, exercise fragmented header, fragmented body, coalesced frames, idle socket, invalid/oversized length, partial-frame deadline, peer closure, and session ACK behavior.
4. Independently investigate error 5272 with build-stamped logs; do not conflate it with RX failures.
5. Close provisioning, authority, broker truth, protective continuity, recovery, and HPL gates before any release consideration.

## Scope boundary
No WSL canonical source, deployed MT5 source/EX5, Git history, or live state files were changed by this analysis. Do not enable real-account execution.


## R4.2 documentation consistency note
The earlier Candidate tests paragraph had presented the R3 counts (13/21) as though they were the final suite totals, despite the later R4 evidence section reporting 14/22. R4.2 labels 13/21 as historical R3 results and explicitly identifies 14/22 as final R4 candidate evidence. This is a documentation-only correction; test results and EA source are unchanged.

# Phase 6 HPL Delta — G1 RX candidate + frame bound — 2026-10-17

**Disposition: BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL.** `InpAllowReal=false` remains mandatory. This delta supplements, and does not replace, the canonical HPL.

| ID | Threat / invariant | Candidate treatment | Evidence | Status |
|---|---|---|---|---|
| G1-RX-01 | TCP fragmentation/coalescing must not discard bytes | Persistent bounded receive buffer and frame extraction | Candidate source + reference-model tests | Candidate-only; MT5 runtime unverified |
| G1-RX-02 | Zero/oversized frame lengths fail closed | Reject zero and configured-limit violations before signed length arithmetic | Static source guards | Candidate-only |
| G1-RX-03 | Invalid UTF-8/NUL rejected before lossy decode | Strict raw-byte validator reports first bad offset | Static source guards + reference model | Candidate-only; MQL5 compile unverified |
| G1-RX-04 | Frame assembly is bounded and time-limited | Existing 2,000 ms assembly deadline retained | Static source + model | Policy/runtime suitability unverified |
| G1-RX-05 | Fatal receive paths quarantine and clear session material | Existing close/quarantine/clear paths retained | Static source guards | Candidate-only |
| G1-RX-06 | Diagnostics must not disclose secret/session/proof/payload material | Reason-coded diagnostics only | Static log-hygiene guard | Runtime logs still require inspection |
| G1-RX-07 | Configured frame maximum must not overflow signed-int buffer arithmetic | Added `InpMaxFrameBytes > 65536` rejection in `OnInit()` before fence load and connection | New static regression guard | Implemented in isolated candidate; compile/runtime unverified |
| G1-AUTH-01 | Identity isolation and real-trading prohibition remain | No auth-contract change; `InpAllowReal=false` preserved | Source inspection/static guard | Candidate-only |
| G1-BUILD-01 | Exact source/build/deployment identity | Baseline and candidate EA hashes recorded | SHA-256 evidence | Source lineage verified; build/deployment identity open |
| G1-RUNTIME-01 | Actual MT5 behavior must be verified | No MetaEditor/terminal available for this candidate build | None | OPEN / BLOCKING |

## Exact lineage
- Snapshot HEAD: `6d7d1e66d69698d8a8d9029dea628b09442dc779`
- Baseline EA SHA-256: `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`
- Candidate EA SHA-256: `1679139a1c4c5e86d6095bc1bd44d4a65b6d4a6799855703aef92265449d673a`

## Required next gates
1. Verify the canonical EA still matches the baseline hash before applying this patch in a disposable candidate directory.
2. Run static tests and compile in MetaEditor; record compiler build, EA hash, resolved include hashes, and EX5 hash.
3. Run demo-only MT5 framing adversarial cases and authentication interoperability tests.
4. Reconcile deployed MT5 source/EX5 separately; do not assume parity.
5. Preserve unresolved broker-truth, protection, recovery, and full Phase 5 regression gates.

No canonical/deployed source, Git index/history, or live state was modified while preparing this candidate.

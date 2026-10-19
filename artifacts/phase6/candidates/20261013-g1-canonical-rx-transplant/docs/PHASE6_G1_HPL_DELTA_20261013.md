# Phase 6 HPL Delta — G1 RX Transplant Candidate — 2026-10-13

| ID | Threat / invariant | G1 treatment | Evidence | Status |
|---|---|---|---|---|
| G1-RX-01 | Partial TCP reads must not discard bytes | Retains canonical persistent receive buffer and frame deadline | Source guards + Python reference model | Candidate-only; MQL5 runtime open |
| G1-RX-02 | Zero or oversized length prefix must fail closed | Separate zero-length and over-limit reasons before signed length conversion | Static source guard + model tests | Candidate-only |
| G1-RX-03 | Invalid UTF-8 must be rejected before lossy decode | Strict validator rejects malformed sequences and NUL; records first bad byte offset | Static source guard + model tests | Candidate-only; MQL5 compile open |
| G1-RX-04 | Frame assembly must be bounded and time-limited | Preserves max frame arithmetic and 2,000 ms deadline; adds diagnostic detail | Static source guard + model tests | Deadline policy unvalidated in MT5 |
| G1-RX-05 | Fatal receive path must close socket and clear session material | Retains canonical socket-close and `ClearSessionMaterial()` paths | Static lifecycle guards | Candidate-only; runtime open |
| G1-RX-06 | RX diagnostics must not leak secrets/session material/payload | Adds reason/detail only; no session IDs, nonce, key, secret, or body | Static log-hygiene guard | Candidate-only |
| G1-AUTH-01 | Identity boundary and real-trading prohibition must remain | Canonical blank account/lane inputs and `InpAllowReal=false` retained | Static source guard | Preserved in candidate; deployment unverified |
| G1-PROT-01 | Protective broker checks must not be weakened | No broker include or protective function changed | Patch scope review | Source-scope preserved; deployed parity open |
| G1-FENCE-01 | Durable fence must remain fail-closed | No persistence include changed | Patch scope review | Source-scope preserved; runtime open |
| G1-BUILD-01 | Exact source/build/include identity must be proven | No build stamping claimed | G0 identity evidence; no compile | OPEN |
| G1-RUNTIME-01 | Actual MT5 behavior must be verified | No MetaEditor or MT5 execution available in this artifact build | None | OPEN / BLOCKING |

## Release disposition

`BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL`. `InpAllowReal=false` remains mandatory.

# FFBP G1 RX candidate — bounded frame configuration correction

**Status:** isolated review candidate only; not applied to canonical WSL source, deployed MT5 source, EX5, Git index, or live state.

## Exact source lineage
- Snapshot HEAD: `6d7d1e66d69698d8a8d9029dea628b09442dc779`
- Canonical EA path: `mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5`
- Canonical EA SHA-256 before patch: `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`
- Candidate EA SHA-256 after patch: `1679139a1c4c5e86d6095bc1bd44d4a65b6d4a6799855703aef92265449d673a`
- Change: add `InpMaxFrameBytes > 65536` input validation in `OnInit()`.

## Rationale
`InpMaxFrameBytes` is a `uint`, while receive-buffer arithmetic converts it to signed `int` and adds four bytes. An oversized configuration can overflow or violate the FFBP maximum. The candidate rejects values above 65,536 before loading/updating the session fence or connecting to the bridge.

## Scope
- Carries forward the existing G1 persistent receive-buffer, strict UTF-8, and bounded frame assembly candidate.
- Adds the missing protocol-maximum guard and a static regression test.
- Does not change the authentication contract, persistence include, broker/protective logic, or command authority.
- Keeps `InpAllowReal=false`.

## Gates still open
- MetaEditor compilation and compiler/build identity.
- MT5 demo runtime for fragmented/coalesced frames, idle sockets, invalid/oversized lengths, invalid UTF-8/NUL, deadline, and peer close.
- Runtime authentication/interoperability and resolved include hashes.
- Deployed MT5 source/EX5 parity.
- Full Phase 5 regression campaign and complete repository suite.
- Broker truth, protective continuity, recovery, and final HPL closure.

**Release disposition: BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL.**

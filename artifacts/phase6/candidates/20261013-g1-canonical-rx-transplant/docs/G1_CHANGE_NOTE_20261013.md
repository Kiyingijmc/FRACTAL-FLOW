# G1 Canonical RX Transplant — 2026-10-13

## Disposition

Isolated candidate only. No canonical WSL files, deployed MT5 files/EX5, Git history, or live state were modified. This is not MetaEditor-compiled and is not approved for deployment.

## Exact baseline

The EA was copied from the G0 evidence bundle's canonical source. Its SHA-256 was checked before editing:

- Baseline `FractalFlowBridgeEA.mq5`: `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`
- Branch at capture: `phase6-forensic-baseline`
- HEAD at capture: `6d7d1e66d69698d8a8d9029dea628b09442dc779`

## Minimal change scope

1. Extend strict UTF-8 validation to reject NUL bytes and report the first offending byte offset.
2. Keep persistent RX buffering and the existing 65,536-byte bound; distinguish zero-length and over-limit prefixes.
3. Add numeric diagnostic detail while retaining canonical string reasons and error capture at the failure site.
4. Add the detail to the existing RX diagnostic line. No session ID, nonce, key, secret, or payload is logged.
5. Preserve canonical identity defaults, `InpAllowReal=false`, `ClearSessionMaterial()`, socket-close behavior, and existing failure/quarantine control flow.

## Explicitly not transplanted

- Candidate account/lane defaults.
- Candidate `FFBP_BUILD_ID "UNSTAMPED"` identity mechanism.
- Candidate full-file changes to identity/session code.
- Candidate removal of `ClearSessionMaterial()`.
- Candidate extra send-path diagnostic logging.
- Changes to broker/persistence includes.

## Validation

The included tests check source invariants and an independent Python reference model for fragmented/coalesced frames, bounds, malformed UTF-8/NUL, and timeout behavior. These do not execute MQL5 code and do not substitute for MetaEditor compilation or MT5 runtime tests.

## Known policy still unvalidated

The 2,000 ms assembly deadline is inherited from the canonical captured source; its runtime suitability remains unvalidated. This patch does not claim to resolve `SocketConnect` error 5272.

## Release

`BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL`. Keep `InpAllowReal=false`.

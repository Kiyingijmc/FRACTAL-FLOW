# G1 Canonical RX Transplant Candidate

This is an isolated, reviewable patch against the exact canonical EA captured in the G0 evidence bundle. It is not a replacement package and must not be copied into the canonical or deployed MT5 tree.

- Canonical baseline SHA-256: `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`
- Candidate EA: `mql5/FractalFlowBridgeEA.G1_RX_CANDIDATE.mq5`
- Unified patch: `patches/G1_canonical_rx_transplant.patch`
- Tests: `tests/`
- HPL delta: `docs/PHASE6_G1_HPL_DELTA_20261013.md`
- Change note: `docs/G1_CHANGE_NOTE_20261013.md`

Run tests from this directory with `python -m pytest -q tests`. The Python model tests are reference-model tests, not MQL5 execution. MetaEditor compile, resolved include identity, MT5 socket tests, protective continuity, fence/restart, and broker reconciliation remain open.

Release: `BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL`; keep `InpAllowReal=false`.

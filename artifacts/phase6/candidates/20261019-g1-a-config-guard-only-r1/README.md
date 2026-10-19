# G1-A Configuration Guard Only — Isolated Candidate

Status: candidate for review; not approved for integration or release.

## Scope
- Source base: `mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5`
- Candidate: `artifacts/phase6/candidates/20261019-g1-a-config-guard-only-r1/mql5/FractalFlowBridgeEA.G1A_CANDIDATE.mq5`
- Sole source delta: reject `InpMaxFrameBytes > 65536` in `OnInit()`.
- The guard is intended to run before `FFBP_LoadFence()` and `ConnectBridge()`.

## Safety boundary
This preparation copies the canonical source into this new candidate directory and changes only that copy. It does not edit canonical or deployed MT5 source, stage files, commit, or alter Git history. It refuses to overwrite an existing candidate directory.

## Validation limits
Python source-level tests can establish the exact delta and guard ordering only. They do not establish MQL5 compilation, terminal runtime behavior, broker interoperability, or release readiness.

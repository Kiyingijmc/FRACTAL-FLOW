# Phase 4 Authority-Integrity Evidence

## Canonical baseline

`FRACTAL-FLOW-PHASE4-CANONICAL.zip` was the pre-remediation Phase 4 baseline. This report records the post-remediation worktree state.

## Verification

| Gate | Result |
|---|---|
| Account identity strictness | PASS |
| Opportunity identity/lifecycle | PASS |
| Parent lineage | PASS |
| Tradeability authority | PASS |
| Tradeability input integrity | PASS |
| Gate taxonomy/completeness | PASS |
| Entry geometry / post-cost RR | PASS |
| Confidence provenance | PASS |
| Deterministic decision fingerprint | PASS |
| Independent hostile pytest suite | PASS — 9/9 |
| Direct hostile mutation audit | PASS — 11/11 |
| Full regression | PASS — 596/596 |
| Coverage | PASS — 88.84% |
| Compileall | PASS |
| Ruff | OWNER-APPROVED ENVIRONMENTAL EXCEPTION — unavailable |
| Mypy | OWNER-APPROVED ENVIRONMENTAL EXCEPTION — unavailable |

## Explicit non-claims

Dedicated Phase-4 event-sourcing/replay reducers, Hypothesis state-machine coverage, and a mutation-testing framework score are not claimed as complete. The inherited Phase 2/3 persistence substrate remains intact.

## Boundary

Phase 4 produces `PHASE4_READY` for the next protection/allocation layer. It does not authorize broker exposure, sizing, portfolio allocation, or order submission.

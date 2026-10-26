# FRACTAL-FLOW — Stage H.1.1.3 Adversarial Test Evidence

## 1. Test Execution Summary

- **Command:** `npm test`
- **Working Directory:** `/app/applet` (mirrored in `/tmp/repo`)
- **Node Version:** Node v22.14.0 / npm v10.9.2
- **Overall Result:** All test suites executed with **0 FAILED**.

### Test Suite Breakdown
| Test Suite File | Tests Passed | Tests Failed | Exit Code | Invariant Focus |
|---|---|---|---|---|
| `stage_h1_1_production_path.test.ts` | 28 | 0 | 0 | Production authorization boundary, projected risk, test seam |
| `stage_h1_production_behavior.test.ts` | 18 | 0 | 0 | KPI rendering, micro-R scaling, crypto vectors |
| `stage_h_adversarial_invariants.test.ts` | 17 | 0 | 0 | Risk invariants, latency truthfulness, live fence |
| `risk_validator_and_latency.test.ts` | 8 | 0 | 0 | Automated risk validator, latency monitor |
| `gui_expansion_invariants.test.ts` | 9 | 0 | 0 | Cross-field validation, QUANT layer intents |
| `responsive_behavior.test.ts` | 20 | 0 | 0 | Responsive layout, mobile drawers, keyboard routes |
| Component Unit Tests | 49 | 0 | 0 | Header, ContextPanel, PositionsTable, modals |
| **Total Across All Suites** | **149** | **0** | **0** | **100% PASS** |

---

## 2. Stage H.1.1.3 Section 6 Adversarial Test Matrix

```
--- HPL-H1.1.3-PROJECTED-RISK: Projected Risk Authorization & State Consistency ---
  [PASS] H1.1.3-AUTH-01: Core Finding — Current exposure < cap, but projected exposure > cap rejects fail-closed with zero submission
  [PASS] H1.1.3-AUTH-02: Exact cap equality — Projected exposure exactly equal to cap is permitted under inclusive ceiling contract
  [PASS] H1.1.3-AUTH-03: Lane cap enforcement — Satisfies account cap but breaches lane cap is rejected fail-closed
  [PASS] H1.1.3-AUTH-04: Deterministic micro-R boundary & 0.0001R precision enforcement
  [PASS] H1.1.3-AUTH-05: Missing, malformed, or disconnected portfolio inputs fail closed
  [PASS] H1.1.3-AUTH-06: Sequential operations update post-action state and enforce cap on subsequent operation
  [PASS] H1.1.2-SEAM-01: Finding B — Test seam isolation: AppTestControlHandle absent from production bundle
```

---

## 3. Key Invariant Confirmations

1. **Projected Risk Boundary (Finding A):**
   - Proved in `H1.1.3-AUTH-01`: Account cap 3.0R, pre-action exposure 2.9R, proposed addition +0.4R -> projected exposure 3.3R > 3.0R.
   - Result: Rejection observed in UI state (`activeCommand.status === 'REJECTED'`), zero provider submission.
2. **Lane Cap Enforcement:**
   - Proved in `H1.1.3-AUTH-03`: Account cap 5.0R (satisfied at 2.7R), lane cap 2.5R (breached at 2.7R).
   - Result: Rejected with `MAX_LANE_RISK_EXCEEDED`.
3. **Sequential Operation State Freshness:**
   - Proved in `H1.1.3-AUTH-06`: Op 1 increases position risk from 0.8R to 1.2R (authorized). Op 2 attempts another addition on 1.2R position (+0.6R -> 1.8R > 1.5R cap) and is rejected fail-closed with zero mutation.
4. **Inclusive Ceiling Contract:**
   - Proved in `H1.1.3-AUTH-02`: Current 3.0R + 0.4R = exactly 3.4000R == 3.4R cap. Permitted without spurious floating-point error.
5. **Fail-Closed on Corrupted Inputs:**
   - Proved in `H1.1.3-AUTH-05`: Undefined portfolio, empty portfolio, position not found in snapshot, missing `allocatedRiskR`, and negative deltas all reject fail-closed.

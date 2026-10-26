# FRACTAL-FLOW — Stage H.1.1.3 Risk Semantics and Design Decision

## 1. Executive Summary

This document establishes the authoritative domain semantics and architectural design decision for remediating the risk-increasing modification authorization boundary in FRACTAL-FLOW.

In accordance with the Universal Forensic Engineering Protocol (UFEP):
`SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`

Every proposed risk-increasing modification (`add_size`, `scale_in`) must be evaluated against **projected post-action risk** across both the **aggregate account exposure cap** and the **target lane risk cap** before any command intent is created or dispatched to a provider.

---

## 2. Risk Semantics & Invariant Separation

### 2.1 Distinguishing Risk Categories
1. **Actual Allocated Risk (`pos.allocatedRiskR`):**
   - The authoritative initial structural risk allocated to an open position in units of R.
   - Evaluated strictly via `getValidPositionRiskR(pos)`.
   - Never guessed, never defaulted to setup heuristics, never equated to raw lot size.
2. **Incremental Risk Delta (`deltaRiskR`):**
   - The additional risk in R that the proposed modification will introduce to the portfolio.
   - For `add_size` and `scale_in`, the canonical FRACTAL-FLOW specification defines the standard operation as adding +50% size (scaling factor 1.5):
     `deltaRiskR = pos.allocatedRiskR * 0.5`
   - In micro-R: `deltaMicroR = Math.round(posMicroR * 0.5)`.
   - If explicit incremental risk parameters are provided in the command, they must be validated through `toSafeMicroR`. If invalid or indeterminate, the action fails closed.
3. **Projected Post-Action Risk (`projectedRiskR`):**
   - The authoritative state that will exist immediately after the modification:
     - `projectedPositionMicroR = posMicroR + deltaMicroR`
     - `projectedLaneMicroR = currentLaneMicroR + deltaMicroR`
     - `projectedAccountMicroR = currentAccountMicroR + deltaMicroR`
4. **Candidate/Planned Risk:**
   - Hypothetical risk for an unexecuted trade candidate in the setup pipeline.
   - Evaluated via `getCandidatePlannedRiskR`. Strictly isolated to candidate evaluation; never used as actual or projected position risk.

---

## 3. Boundary Semantics & Cap Policy

### 3.1 Inclusive Cap Policy
The established FRACTAL-FLOW risk contract defines exposure limits as **inclusive ceilings**:
- `projected <= cap` is **PERMITTED** (satisfies policy).
- `projected > cap` is **BREACHED** (strictly rejected fail-closed).

### 3.2 Matrix of Conditions
| Condition | Aggregate Account Exposure (`maxAccountExposureR`) | Target Lane Risk (`maxLaneRiskR`) | Authorization Outcome |
|---|---|---|---|
| Projected <= Cap | <= Cap | <= Cap | **ALLOWED** (subject to P&L checks) |
| Projected Account Exceeds | > Cap | <= Cap | **REJECTED** (`MAX_ACCOUNT_EXPOSURE_EXCEEDED`) |
| Projected Lane Exceeds | <= Cap | > Cap | **REJECTED** (`MAX_LANE_RISK_EXCEEDED`) |
| Both Exceed | > Cap | > Cap | **REJECTED** (Both violations logged) |
| Current Already >= Cap | >= Cap | Any | **REJECTED** (Cannot add risk to breached book) |
| Portfolio Status != 'VALID' | Any | Any | **REJECTED** (`PORTFOLIO_RISK_STATUS` invalid/unknown) |
| Target Position Unallocated | Missing / NaN / <= 0 | Any | **REJECTED** (`INVALID_POSITION_PARAM`) |
| Omitted Portfolio Positions | Omitted / undefined | Any | **REJECTED** (Fail-closed; portfolio required) |
| Daily Loss Limit Breached | Any | Any | **REJECTED** (`DAILY_LOSS_LIMIT_EXCEEDED`) |
| De-risking (`close`, `tighten`, `BE`) | Any | Any | **ALLOWED** (Protective actions always permitted) |

---

## 4. Deterministic Arithmetic (Micro-R Units)

All risk comparisons use exact integer micro-R arithmetic:
- Scale factor: `1 R = 1,000,000 micro-R`.
- Allowed input precision: At most 4 decimal places (`0.0001 R = 100 micro-R`), verified by `hasValidRiskPrecision`.
- Precision limits:
  - Max individual position risk: `100.0 R` (`100,000,000 micro-R`).
  - Max portfolio risk: `200.0 R` (`200,000,000 micro-R`).
- Floating-point comparisons (`>`, `<`, `>=`) are forbidden in cap evaluations. All checks compare integer micro-R values:
  `projectedAccountMicroR > maxAccountMicroR`
  `projectedLaneMicroR > maxLaneMicroR`

---

## 5. Authorization and State Consistency Design

### 5.1 Enforcement Point: `validatePositionModification`
The signature and implementation of `validatePositionModification` in `src/utils/riskValidator.ts` is updated:
```typescript
export function validatePositionModification(
  action: ActionType,
  targetPosition: Position,
  riskConfig: OperationalRiskConfig,
  currentDailyPnlUsd: number,
  portfolioPositions?: Position[],
  incrementalRiskR?: number
): { isAllowed: boolean; violations: RiskViolation[] }
```

When `action === 'add_size' || action === 'scale_in'`:
1. Verify `portfolioPositions` is provided and is a valid non-empty array containing `targetPosition`. If missing or target position not found, fail closed immediately.
2. Evaluate target position's `allocatedRiskR` via `getValidPositionRiskR(targetPosition)`. If invalid, fail closed immediately.
3. Compute `deltaMicroR`:
   - If `incrementalRiskR` provided: validate via `toSafeMicroR(incrementalRiskR)`.
   - Default: `Math.round(posMicroR * 0.5)` (+50% addition).
4. Evaluate current portfolio risk across all positions via `evaluatePortfolioRisk(portfolioPositions)`. If status !== 'VALID', fail closed.
5. Evaluate current lane risk for `targetPosition.lane` via `evaluatePortfolioRisk(portfolioPositions, targetPosition.lane)`. If status !== 'VALID', fail closed.
6. Calculate projected values:
   - `projectedAccountMicroR = currentAccountMicroR + deltaMicroR`
   - `projectedLaneMicroR = currentLaneMicroR + deltaMicroR`
7. Check against caps:
   - If `projectedLaneMicroR > maxLaneMicroR`: add `MAX_LANE_RISK_EXCEEDED` violation.
   - If `projectedAccountMicroR > maxAccountMicroR`: add `MAX_ACCOUNT_EXPOSURE_EXCEEDED` violation.
8. If any violations exist, return `{ isAllowed: false, violations }`.

### 5.2 Provider State Synchronization: `SimulationProvider.ts`
When an authorized `ADD_SIZE` or `SCALE_IN` command is executed by `SimulationProvider`:
```typescript
if (intent.actionType === 'ADD_SIZE' || intent.actionType === 'SCALE_IN') {
  if (targetIdx >= 0) {
    this.positions[targetIdx].size = Number((this.positions[targetIdx].size * 1.5).toFixed(2));
    if (typeof this.positions[targetIdx].allocatedRiskR === 'number') {
      this.positions[targetIdx].allocatedRiskR = Number(
        (this.positions[targetIdx].allocatedRiskR * 1.5).toFixed(4)
      );
    }
  }
}
```
This guarantees that after command confirmation:
1. Position lot size and `allocatedRiskR` scale synchronously (+50%).
2. Subsequent evaluations in `App.tsx` and tests reflect exact post-action risk.
3. Prevents understated risk accumulation across sequential operations.

### 5.3 Zero-Side-Effect Rejection Invariant
If `validatePositionModification` rejects an action in `handleConfirmAction`:
1. `setActiveCommand` is set to `status: 'REJECTED'`, `source: 'PRODUCTION_RISK_GATE'`.
2. An audit trail entry is recorded with `outcome: 'REJECTED_FAIL_CLOSED'`.
3. A critical system event is logged.
4. Function exits immediately without creating an intent fingerprint, calling `simulationProvider.submitCommand`, or touching position state.

---

## 6. Smallest Safe Implementation Plan

1. **`src/utils/riskValidator.ts`:**
   - Update `validatePositionModification` to compute `deltaMicroR`, `projectedAccountMicroR`, and `projectedLaneMicroR`.
   - Enforce both `maxLaneRiskR` and `maxAccountExposureR` using inclusive cap comparison.
   - Fail closed if `portfolioPositions` is missing, target position has missing risk, or portfolio evaluation is invalid.
2. **`src/providers/SimulationProvider.ts`:**
   - In `submitCommand`, ensure `ADD_SIZE` and `SCALE_IN` update `allocatedRiskR` proportionally alongside `size`.
3. **`src/tests/stage_h1_1_production_path.test.ts`:**
   - Update Case 1 to use a configuration or position where projected risk satisfies both lane and account caps.
   - Add Section 6 test suite covering all projected-risk boundary conditions, lane caps, multi-operation sequences, and state consistency.
4. **Audit and Verification:**
   - Run `npm test`, `npm run lint`, `npm run build`.
   - Inspect production bundle to guarantee `AppTestControlHandle` is tree-shaken.
   - Reconcile HPL, generate patch and checksum manifest.

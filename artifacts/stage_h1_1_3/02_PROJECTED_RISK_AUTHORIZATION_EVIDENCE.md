# FRACTAL-FLOW — Stage H.1.1.3 Projected Risk Authorization Evidence

## 1. Summary of Evidence

- **Substage:** Stage H.1.1.3 Projected-Risk Authorization and State-Consistency Remediation
- **Core Invariant:** Every risk-increasing action (`add_size`, `scale_in`) must be authorized against authoritative **projected post-action risk** before any command intent or provider mutation can occur.
- **Enforcement Boundary:** `handleConfirmAction` in `src/App.tsx` calling `validatePositionModification` in `src/utils/riskValidator.ts`.

---

## 2. Production Authorization Path

```
User Action: ContextPanel button "Add size (+50%)" / Hotkey '+'
                           │
                           ▼
                  handleTriggerAction()
                           │
                           ▼
                  setConfirmModal(open: true)
                           │
                           ▼
                 Operator clicks Confirm
                           │
                           ▼
                 handleConfirmAction()
                           │
                           ▼
            validatePositionModification(
              action, targetPosition, riskConfig, dailyPnl, portfolioPositions
            )
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
 [Violations Detected]              [All Gaps Satisfied]
         │                                   │
         ▼                                   ▼
 setActiveCommand(REJECTED)          createIntentFingerprint()
 auditTrail.push(REJECTED_FAIL_CLOSED)  setActiveCommand(REQUESTED)
 systemEvents.push(crit, REJECTED)   simulationProvider.setPositions()
 EXIT IMMEDIATELY                    simulationProvider.submitCommand()
 [ZERO PROVIDER SUBMISSION]                 │
 [ZERO POSITION MUTATION]                   ▼
                                     provider mutates size & allocatedRiskR
                                     setPositions(updatedPositions)
                                     setActiveCommand(CONFIRMED)
```

---

## 3. Adversarial Case Evidence

### Case 1: Core Finding — Current Exposure Below Cap, Projected Above Cap (`H1.1.3-AUTH-01`)
- **Setup:**
  - Account exposure cap: `3.0000 R`.
  - Position A: `2.1000 R` (lane: `ACT_PRIMARY`).
  - Position B: `0.8000 R` (lane: `ACT_SECONDARY`).
  - Pre-action total exposure: `2.9000 R` (< `3.0000 R` cap).
  - Proposed action: `add_size` on Position B (+50% size, +0.4000R delta).
  - Projected exposure: `2.9000 R + 0.4000 R = 3.3000 R` (> `3.0000 R` cap).
- **Execution:**
  - Action triggered via `handle.triggerAction('add_size', posB)`.
  - Confirmed via `handle.confirmAction()`.
- **Observed Decision:**
  - `activeCommand.status`: `'REJECTED'`
  - `activeCommand.source`: `'PRODUCTION_RISK_GATE'`
  - `activeCommand.details`: `"[REJECTED FAIL-CLOSED] Action add_size rejected: Projected total account exposure (3.3000R) exceeds account exposure limit (3.0R) by 0.3000R"`
  - `provider.getSimulatedIntents().size`: Unchanged (0 commands dispatched).
  - `positions`: Bit-for-bit unchanged.
- **Outcome:** **PASS** — Rejected fail-closed at gate before provider dispatch.

### Case 2: Exact Cap Equality (`H1.1.3-AUTH-02`)
- **Setup:**
  - Account exposure cap: `3.4000 R`.
  - Position A: `2.2000 R` (lane: `ACT_SECONDARY`).
  - Position B: `0.8000 R` (lane: `ACT_PRIMARY`).
  - Pre-action total exposure: `3.0000 R`.
  - Proposed action: `add_size` on Position B (+0.4000R delta).
  - Projected exposure: `3.0000 R + 0.4000 R = 3.4000 R` (exactly equal to `3.4000 R` cap).
- **Observed Decision:**
  - Action authorized under inclusive ceiling contract (`projected <= cap`).
  - `provider.getSimulatedIntents().size`: Incremented by 1.
  - Post-action exposure in DOM / state: `3.4 R`.
- **Outcome:** **PASS** — Deterministic inclusive cap comparison verified.

### Case 3: Lane-Level Exposure Cap Enforcement (`H1.1.3-AUTH-03`)
- **Setup:**
  - Account exposure cap: `5.0000 R` (ample account headroom).
  - Lane exposure cap: `2.5000 R` for lane `ACT_PRIMARY`.
  - Current lane exposure: `2.3000 R`.
  - Target position in lane: `0.8000 R`. Proposed addition: `+0.4000 R`.
  - Projected lane risk: `2.3000 R + 0.4000 R = 2.7000 R` (> `2.5000 R` lane cap).
  - Projected account exposure: `2.7000 R` (<= `5.0000 R` account cap).
- **Observed Decision:**
  - `activeCommand.status`: `'REJECTED'`
  - `activeCommand.details`: Mentioned `MAX_LANE_RISK_EXCEEDED` (`Projected lane risk (2.7000R) exceeds maximum lane risk limit (2.5R) by 0.2000R`).
  - `provider.getSimulatedIntents().size`: Zero new submissions.
- **Outcome:** **PASS** — Action satisfying account cap cannot breach applicable lane cap.

### Case 4: Micro-R Boundary & 4-Decimal Precision (`H1.1.3-AUTH-04`)
- **Exact Equality (3.0000 R == 3.0000 R):** `validatePositionModification` returned `isAllowed: true`.
- **100 Micro-R Excess (3.0001 R > 3.0000 R):** `validatePositionModification` returned `isAllowed: false` with both `MAX_ACCOUNT_EXPOSURE_EXCEEDED` and `MAX_LANE_RISK_EXCEEDED`.
- **Unsupported 5-Decimal Precision (0.00005 R):** `validatePositionModification` returned `isAllowed: false` with `INVALID_POSITION_PARAM`.
- **Outcome:** **PASS** — Micro-R deterministic integer arithmetic verified.

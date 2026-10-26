# Stage H.1.1.2 — Production Authorization Evidence & Case Analysis

**Timestamp:** 2026-10-26T21:11:00Z  
**Test Suite:** `src/tests/stage_h1_1_production_path.test.ts` (Section 5)  
**Execution Environment:** Node.js v22.23.4 / JSDOM v26.0.0 / React 19.0.1  

---

## 1. Trace of Production Authorization Boundary Cases

### Case 1 — Valid Portfolio Path (Test `H1.1.2-AUTH-01`)
- **Initial State:** Mounted `<App />` with `INITIAL_POSITIONS` (4 nominal positions, total risk 2.3R).
- **Trigger:** Operator selects Position 0 (`EURUSD LONG 1.00 lots`) and triggers `'add_size'`.
- **UI State:** Modal dialog mounts with title `"Increase Position Size — EURUSD LONG"` and command route `"ExecutionGateway.ADD_SIZE"`.
- **Authorization Decision:** `validatePositionModification('add_size', pos, riskConfig, dailyPnl, positions)` evaluates portfolio risk as `VALID` (2.3R < 3.0R cap). Returns `{ isAllowed: true, violations: [] }`.
- **Submission:** Command proceeds to `simulationProvider.submitCommand`.
- **Outcome:** `simulatedIntents` records the intent; position size increases from 1.00 to 1.50 lots.
- **Evidence Assertion:** `provider.getSimulatedIntents().size` increments by 1; `updatedPos.size > initialSize` passes.

### Case 2 — Invalid Portfolio Interception (Test `H1.1.2-AUTH-02`)
- **Trigger:** Corrupted position `pos_unallocated_hostile_01` (`allocatedRiskR: undefined`) injected via `setPositions`.
- **UI State:** Header KPI updates to render `INVALID` badge (`[data-testid="open-risk-invalid"]`).
- **Action:** Operator triggers `'add_size'` and clicks Confirm Execution.
- **Authorization Decision:** `validatePositionModification` evaluates portfolio risk, obtains status `'INVALID'`, and fails closed:
  ```json
  {
    "isAllowed": false,
    "violations": [
      {
        "code": "MAX_ACCOUNT_EXPOSURE_EXCEEDED",
        "severity": "BLOCKING",
        "message": "Cannot execute risk-increasing action 'add_size' while portfolio risk is invalid or unknown (INVALID)",
        "metric": "PORTFOLIO_RISK_STATUS",
        "currentValue": null,
        "limitValue": 3.0
      }
    ]
  }
  ```
- **Boundary Interception:**
  - `activeCommand` set to `{ status: 'REJECTED', source: 'PRODUCTION_RISK_GATE', details: '[REJECTED FAIL-CLOSED] ...' }`.
  - Audit trail prepends `{ action: 'REJECT_ADD_SIZE', outcome: 'REJECTED_FAIL_CLOSED', actor: 'PRODUCTION_AUTHORITY_GATE' }`.
  - Zero dispatch: `handleConfirmAction` returns early before calling `createIntentFingerprint` or provider submission.
- **Evidence Assertion:** Provider `simulatedIntents` count is identical before and after (0 new intents); positions snapshot remains bit-for-bit unchanged.

### Case 3 — Candidate Risk Separation (Test `H1.1.2-AUTH-03`)
- **Condition:** Portfolio has an open position with `allocatedRiskR: NaN`. Valid `GateCandidate` fixtures exist in the candidate pipeline with calculated setup risks (0.8R).
- **Adversarial Vector:** Proves that candidate planning data cannot masquerade as open position risk or override portfolio invalidity.
- **Outcome:** Attempting `'scale_in'` fails closed at the risk gate with `status: 'REJECTED'`, `source: 'PRODUCTION_RISK_GATE'`.

### Case 4 — De-risking Policy Integrity (Test `H1.1.2-AUTH-04`)
- **Condition:** Portfolio remains in `INVALID` state due to `allocatedRiskR: undefined`.
- **Action 1:** Operator triggers de-risking action `'close_position'`.
- **Outcome 1:** `validatePositionModification` recognises `'close_position'` as a protective de-risking action (`isAllowed: true`). Command dispatches to provider, confirms, and removes position.
- **Action 2 (Asymmetry Verification):** Operator immediately triggers `'add_size'`.
- **Outcome 2:** Intercepted at production gate and rejected (`status: 'REJECTED'`). Proves that de-risking permissions do NOT broaden to risk-increasing operations.

### Case 5 — Recovery & Newly Invalid Barrier Re-engagement (Test `H1.1.2-AUTH-05`)
- **Step A:** Introduce negative allocated risk (`-0.5R`). Attempt `add_size` -> Rejected.
- **Step B:** Filter out corrupt position. UI recovers to `2.3R` KPI. Attempt `add_size` -> Successfully authorized and submitted.
- **Step C:** Introduce new corrupt position (`Infinity`). Attempt `add_size` -> Immediately rejected fail-closed.
- **Outcome:** Proves no stale authorization tokens or bypass flags persist across state transitions.

### Case 6 — Alternate Path Convergence (Test `H1.1.2-AUTH-06`)
- **Vector 1 (Keyboard Hotkey):** Dispatched `KeyboardEvent('keydown', { key: '+' })` at `window`. Modal opens. Confirm button clicked. Action rejected fail-closed at gate.
- **Vector 2 (ContextPanel DOM Button):** Clicked `button[data-testid="context-btn-add-size"]`. Modal opens. Confirm button clicked. Action rejected fail-closed at gate.
- **Outcome:** Proves all entry points converge at `handleConfirmAction` and cannot bypass the production authorization barrier.

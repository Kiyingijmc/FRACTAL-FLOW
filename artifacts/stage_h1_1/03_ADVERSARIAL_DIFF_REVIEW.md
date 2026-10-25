# FRACTAL-FLOW Stage H.1.1 — Adversarial Diff Review

**Document ID:** `STAGE-H1-1-DOC-03-DIFF-REVIEW`
**Execution Date:** 2026-10-25 / 2026-10-26
**Baseline Commit:** `28372d0c28919daccb10e421fcd5f90a25e30223`
**Working Branch:** `work/stage-h1-1-corrective-pass-20261026`
**Review Type:** Forensic Source Code & Invariant Audit

---

## 1. Scope of Modifications

| File | Change Type | Purpose / Safety Invariant Preserved |
| :--- | :---: | :--- |
| `control_surface/src/utils/riskValidator.ts` | Source | **Eliminated setup fallback for open positions.** Added `hasValidRiskPrecision` (max 4 decimals) and `toSafeMicroR` (validates finite, positive, $\le 100R$, precision $\le 4$ decimals, safe integer). Decoupled candidate planning via `getCandidatePlannedRiskR`. Authoritative un-rounded numbers stored in results; diagnostics formatted to 4 decimals. |
| `control_surface/src/App.tsx` | Source | Added `AppProps` (`initialPositions`, `initialRiskConfig`, `initialNavTab`, `onPositionsChange`, `testRef`) allowing mounted production component testing in JSDOM while defaulting to canonical mock data in production. |
| `control_surface/src/components/ConfirmDialog.tsx` | Source | Added `role="dialog"`, `aria-modal="true"`, and `data-testid="confirm-dialog"` for W3C accessibility compliance and modal assertions. |
| `control_surface/src/tests/stage_h1_production_behavior.test.ts` | Test | Updated test `H1-RISK-03.2` to assert fail-closed rejection when `allocatedRiskR` is omitted on open positions. |
| `control_surface/src/tests/stage_h1_1_production_path.test.ts` | Test (New) | 15 comprehensive tests covering explicit allocation, 4-decimal precision enforcement, micro-R cap boundaries, and real mounted `<App />` state transitions in JSDOM. |
| `control_surface/package.json` | Config | Updated `npm test` script to run all 9 test suites sequentially. |
| `artifacts/stage_h1_1/*` | Artifacts | Forensic documentation, risk consumer inventory, executable arithmetic contract, and test logs. |

---

## 2. Line-by-Line Code Review

### 2.1 `src/utils/riskValidator.ts`
- **Constants and Precision:** Introduced `RISK_ARITHMETIC_CONSTANTS` (SCALE: 1,000,000, MAX_INPUT_DECIMALS: 4, MAX_POSITION_RISK_R: 100.0, MAX_PORTFOLIO_RISK_R: 200.0).
- **`hasValidRiskPrecision`:** Computes `val * 10_000` and verifies integer delta $< 10^{-7}$. Rejects 5+ decimal places fail-closed.
- **`toSafeMicroR`:** Validates type (`number`), finite (`Number.isFinite`), positive ($> 0$), upper bound ($\le 100.0R$), precision ($\le 4$ decimals), and safe integer representation.
- **`getValidPositionRiskR`:** Strictly requires `allocatedRiskR` to be defined and validates via `toSafeMicroR`. Missing allocation returns `isValid: false`, citing missing allocatedRiskR.
- **`getCandidatePlannedRiskR`:** Isolates candidate pre-trade planning; validates overrides via `toSafeMicroR` and falls back to `DEFAULT_SETUP_RISK_MAP` solely for prospective trade candidates.
- **`evaluatePortfolioRisk`:** Accumulates integer micro-R, checks portfolio safe-integer limit ($200.0R$), and returns exact unrounded `totalMicroR / 1_000_000`.
- **`validateCandidateAgainstRiskConfig`:** Uses exact unrounded numbers for `projectedLaneRiskR` and `projectedAccountExposureR`, and formats violation messages with 4 decimal places so excess is never concealed.

### 2.2 `src/App.tsx`
- **Component Interface:** Exported `AppProps` and `AppTestControlHandle`.
- **State Initialization:** Uses `initialPositions || INITIAL_POSITIONS`, `initialRiskConfig || INITIAL_OPERATIONAL_RISK_CONFIG`, `initialNavTab || 'POS'`.
- **State Handler Exposure:** When `testRef` is provided, attaches handlers to `testRef.current` allowing JSDOM tests to trigger real production state mutations and observe mounted DOM updates.

### 2.3 `src/components/ConfirmDialog.tsx`
- **Accessibility & Testability:** Container element explicitly specifies `role="dialog"`, `aria-modal="true"`, and `data-testid="confirm-dialog"`.

---

## 3. Negative Controls and Failure Injection Verification

1. **Failure Injection 1: Restore Setup Fallback in `getValidPositionRiskR`**
   - Result: Test `H1.1-RISK-01.2` immediately fails because `isValid` returns `true` instead of `false`.
2. **Failure Injection 2: Accept 5-Decimal Precision ($0.00001R$)**
   - Result: Test `H1.1-RISK-02.2` immediately fails because `hasValidRiskPrecision(0.00001)` returns `false`.
3. **Failure Injection 3: Bypass Live Command Barrier**
   - Result: Test `H1.1-PROTECT-01.2` fails because `executeLiveCommand` would attempt execution rather than throwing `LiveExecutionBlockedError`.
4. **Failure Injection 4: Break State Propagation in `<App />`**
   - Result: Test `H1.1-TEST-01.1` fails because Header KPI in mounted DOM does not transition to `INVALID`.

---

## 4. Protected References Verification

- Branch `main` (`74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d`): Untouched.
- PR #29 Branch `feature/gui-control-surface` (`c392c3e95f8e950cf7552d494a97d8821c2dd158`): Untouched.
- Stage H.1 Starting Branch `work/gui-reconciliation-20261024` (`28372d0c28919daccb10e421fcd5f90a25e30223`): Untouched.
- Dedicated Working Branch: `work/stage-h1-1-corrective-pass-20261026` branched from `2c78c84` (preserving Stage H.1.1 history).

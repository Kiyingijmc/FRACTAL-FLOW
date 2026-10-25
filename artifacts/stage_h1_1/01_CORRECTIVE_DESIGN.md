# FRACTAL-FLOW Stage H.1.1 — Corrective Design Specification

**Document ID:** `STAGE-H1-1-DOC-01-DESIGN`
**Execution Date:** 2026-10-25 / 2026-10-26
**Governing Standard:** Universal Forensic Engineering Protocol
**Operational Hierarchy:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY`

---

## 1. Problem Statement & Root Cause Analysis

### 1.1 Defect 1: Setup-Map Fallback Ambiguity
The legacy implementation of `getValidPositionRiskR` used `DEFAULT_SETUP_RISK_MAP[pos.setup]` when `allocatedRiskR` was omitted. This caused unallocated open positions to masquerade as valid exposure, obscuring unquantified structural risk and converting unknown exposure into a plausible-looking numeric value.

### 1.2 Defect 2: Arithmetic Precision Specification Mismatch
The contract stated a 4-decimal-place limit ($0.0001R$, or $100 \mu R$), but the implementation used unconstrained `Math.round(val * 1_000_000)` without input precision validation or individual position bounds. Inputs with 5+ decimals or non-safe integers were silently quantized rather than rejected fail-closed.

### 1.3 Defect 3: Static Props vs Real Mounted State Transitions
Previous tests exercised `renderToString` on isolated child components from manually supplied props. They did not verify that a live, mounted production component tree (`<App />`) dynamically updates its state, recalculates portfolio exposure, and propagates changes across Header KPIs, GateChainStrip candidate gates, and SecondaryViews.

---

## 2. Corrective Architecture

### 2.1 Explicit Allocated Risk vs Candidate Planning Decoupling
1. **Existing Open Positions:** Handled strictly by `getValidPositionRiskR(pos: Position)`. An explicit, finite, positive `allocatedRiskR` is mandatory. Zero fallback to setup estimates.
2. **Prospective Trade Candidates:** Handled strictly by `getCandidatePlannedRiskR(candidate, overrideRiskR?)`. Setup default estimates from `DEFAULT_SETUP_RISK_MAP` are permitted solely for pre-trade planning and never leak into open position accounting.

### 2.2 Executable Micro-R Precision Contract
1. **Precision Boundary:** Valid inputs accept at most 4 decimal places ($0.0001R = 100 \mu R$). Enforced by `hasValidRiskPrecision`.
2. **Fail-Closed Conversion:** `toSafeMicroR` validates:
   - Type is `number` (rejects strings, booleans, objects, null, undefined).
   - Value is finite and positive ($0 < R \le 100.0R$).
   - Precision $\le 4$ decimal places (rejects 5+ decimals fail-closed).
   - Safe integer scaling (`Number.isSafeInteger(microR)`).
3. **Integer Accumulation:** All summations and cap comparisons are computed on integer micro-R ($10^6$).
4. **Cap Equality:** $\text{Projected} \le \text{Cap}$ is `CLEAR`; $\text{Projected} > \text{Cap}$ is `BREACHED`.
5. **Presentation Separation:** Display strings format for readability, but violation messages display 4 decimal places so excess is never concealed.

### 2.3 Real Mounted Production State Harness
1. **Mounted Production Tree:** `<App />` mounted directly into JSDOM using React 19 `ReactDOM.createRoot` and `act`.
2. **State Propagation:** State updates triggered through production handlers; DOM observed in real-time across valid $\to$ invalid $\to$ valid transitions.
3. **Accessibility:** `ConfirmDialog` container updated with `role="dialog"` and `aria-modal="true"`.

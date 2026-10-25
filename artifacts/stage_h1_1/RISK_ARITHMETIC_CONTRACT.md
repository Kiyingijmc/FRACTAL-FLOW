# FRACTAL-FLOW — Stage H.1.1 Risk Arithmetic Contract
**Document:** `artifacts/stage_h1_1/RISK_ARITHMETIC_CONTRACT.md`
**Governing Standard:** Universal Forensic Engineering Protocol
**Priority Order:** `SURVIVAL > CORRECTNESS > DETERMINISM > AUDITABILITY`
**Date:** 2026-10-25 / 2026-10-26
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`
**Corrective Pass:** Executable 4-Decimal Precision Enforcement and Micro-R Scaling

---

## 1. Domain Definition and Units of $R$

1. **$R$ (Risk Multiple):** The canonical normalized unit of capital exposure defined as the monetary loss incurred if a trade exits at its initial stop loss.
2. **Actual Allocated Risk ($allocatedRiskR$):** The authoritative, immutable risk allocation assigned to an executed open position. It must be a positive finite real number ($0 < R \le 100.0$).
3. **Planned Candidate Risk ($plannedRiskR$):** The prospective risk proposed for a trade candidate prior to execution. Evaluated exclusively via `getCandidatePlannedRiskR`.
4. **Setup Default Estimate ($setupDefaultR$):** An unexecuted strategy template parameter (e.g. `FF-01` = 0.8R). **Strict Rule:** Setup default estimates are strictly prohibited as fallbacks for executed open positions.

---

## 2. Authoritative Executable Arithmetic Contract

### 2.1 Accepted Input Types and Value Bounds
- **Accepted Types:** JavaScript `number` only. Strings, objects, booleans, `null`, and `undefined` are rejected immediately.
- **Finite and Positive Requirement:** Value must satisfy `Number.isFinite(v) && v > 0`. `0`, negative numbers, `NaN`, `Infinity`, and `-Infinity` fail closed.
- **Individual Position Upper Bound:** $0 < R \le 100.0R$ (`RISK_ARITHMETIC_CONSTANTS.MAX_POSITION_RISK_R`). Any position risk exceeding $100.0R$ is rejected with `EXCEEDS_MAX_POSITION_RISK`.
- **Maximum Aggregate Portfolio Bound:** $0 \le \text{Total } R \le 200.0R$ (`RISK_ARITHMETIC_CONSTANTS.MAX_PORTFOLIO_RISK_R`).
- **Safe Integer Boundaries:** All scaled values must satisfy `Number.isSafeInteger(microR)`. Intermediate and aggregate values cannot exceed `Number.MAX_SAFE_INTEGER` ($9,007,199,254,740,991$).

### 2.2 Permitted Input Precision & Boundary Enforcement
- **Permitted Precision:** At most 4 decimal places ($0.0001R$, or $100 \mu R$).
- **Strict Validation Rule:** Inputs with unsupported fractional precision ($>4$ decimal places, e.g. $0.00001R$, $0.12345R$, $0.00005R$) are strictly rejected fail-closed at the validation boundary (`UNSUPPORTED_PRECISION`).
- **Zero Silent Quantization:** The system does NOT silently round or truncate unsupported precision inputs to valid-looking numbers.

```ts
export function hasValidRiskPrecision(val: number): boolean {
  if (typeof val !== 'number' || !Number.isFinite(val)) return false;
  const scaled = val * 10_000;
  return Math.abs(scaled - Math.round(scaled)) < 1e-7;
}
```

### 2.3 Micro-R Integer Representation ($10^6$ Scale)
- Canonical scaling factor: $1 \mu R = 10^{-6} R$. $1.0R = 1,000,000 \mu R$.
- Conversion: `const microR = Math.round(val * 1_000_000);`
- Since valid inputs have $\le 4$ decimal places, every valid risk value converts into an exact integer multiple of $100 \mu R$.
- Integer accumulation eliminates binary IEEE-754 floating-point drift:
  $$\text{totalMicroR} = \sum_{i=1}^N \text{microR}_i$$
  $$\text{totalRiskR} = \frac{\text{totalMicroR}}{1,000,000}$$

### 2.4 Separation of Authoritative Metrics and Display Formatting
- **Authoritative Total:** `PortfolioRiskResult.totalRiskR` and `CandidateRiskValidation.projectedLaneRiskR` store the exact un-rounded floating-point number derived from integer micro-R.
- **Cap Comparison:** Comparisons are executed exclusively on un-truncated integer micro-R:
  $$\text{projectedLaneMicroR} \le \text{maxLaneMicroR} \implies \text{CLEAR}$$
  $$\text{projectedLaneMicroR} > \text{maxLaneMicroR} \implies \text{BREACHED}$$
- **Display Formatting:** Presentation layers format numbers for UI readability (e.g. `2.3R` in KPI, `2.30R` in details). Display strings must NEVER conceal a cap violation. Violation messages explicitly display 4 decimal places:
  `Projected lane risk (1.8001R) exceeds maximum lane risk limit (1.8R) by 0.0001R`

---

## 3. Worked Boundary Examples

### 3.1 The $0.005R$ Discriminator Case
- **Input:** Three positions with $allocatedRiskR = 0.005R$ (3 decimal places $\le 4$ decimals):
  - Position 1: $5,000 \mu R$
  - Position 2: $5,000 \mu R$
  - Position 3: $5,000 \mu R$
- **Sum:** $15,000 \mu R = 0.015000R$ exactly.
- **Display Output:** Formats at 2 decimals as `0.02R` (half-up at display).
- **Contrast with Defective Rounding:** If each position were rounded to hundredths first ($0.005 \to 0.01$), the sum would be $0.03R$ (+100% rounding distortion). The micro-R aggregate preserves exact precision.

### 3.2 Boundary Cap Equality
- **Lane Cap:** $1.8R$ ($1,800,000 \mu R$)
- **Current Lane Risk:** $1.0R$ ($1,000,000 \mu R$)
- **Candidate Risk:** $0.8R$ ($800,000 \mu R$)
- **Projected Risk:** $1,800,000 \mu R \le 1,800,000 \mu R \implies$ **`CLEAR` (Inclusive Ceiling)**.
- **Candidate Risk $0.8001R$:** $1,800,100 \mu R > 1,800,000 \mu R \implies$ **`BREACHED` (Excess $0.0001R$)**.

### 3.3 One Digit Beyond Permitted Precision
- **Input:** $allocatedRiskR = 0.00001R$ (5 decimal places).
- **Result:** Fails closed immediately with `UNSUPPORTED_PRECISION`.
- **Reason:** `Risk value (0.00001) exceeds maximum permitted input precision of 4 decimal places (0.0001R)`.

---

## 4. Invalid, Unknown, and Empty Portfolio Semantics

1. **Empty Portfolio ($N = 0$):**
   - Returns `{ status: 'VALID', totalRiskR: 0.0, evaluatedCount: 0 }`.
   - Distinct from invalid state; renders `0.0R` in UI.
2. **Missing `allocatedRiskR` on Open Position:**
   - Returns `{ isValid: false, riskR: null, reason: 'Position ... has missing allocatedRiskR' }`.
   - Ingestion into portfolio causes `evaluatePortfolioRisk` to return `{ status: 'INVALID', totalRiskR: null }`.
   - **Zero Partial Sums:** Valid positions in the same portfolio are never summed partially. The entire KPI renders `INVALID`.

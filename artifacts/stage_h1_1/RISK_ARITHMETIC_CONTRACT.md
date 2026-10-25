# FRACTAL-FLOW — Stage H.1.1 Risk Arithmetic Contract
**Document:** `artifacts/stage_h1_1/RISK_ARITHMETIC_CONTRACT.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > DETERMINISM > AUDITABILITY`  
**Date:** 2026-10-25  
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`  

---

## 1. Domain Definition and Units of $R$

1. **$R$ (Risk Multiple):** The canonical normalized unit of capital exposure defined as the monetary loss incurred if a trade exits at its initial stop loss.
2. **Actual Allocated Risk ($allocatedRiskR$):** The authoritative, immutable risk allocation assigned to an executed open position. It must be a positive finite real number ($0 < R \le 100.0$).
3. **Planned Candidate Risk ($plannedRiskR$):** The prospective risk proposed for a trade candidate prior to execution.
4. **Setup Default Estimate ($setupDefaultR$):** An unexecuted strategy template parameter (e.g. `FF-01` = 0.8R). **Strict Rule:** Setup default estimates are strictly prohibited as fallbacks for executed open positions.

---

## 2. Representation, Scaling, and Aggregation Rules

1. **Internal Representation (Micro-R Scaling):**
   - All internal portfolio summations, lane aggregations, and cap comparisons are performed on a 64-bit integer micro-R basis ($10^6$ scale):
     $$\text{microR} = \text{Math.round}(R \times 1,000,000)$$
   - This integer representation eliminates binary IEEE-754 floating-point drift while allowing sub-basis-point precision down to $0.000001R$.
2. **Permitted Input Precision:**
   - Positions can accept risk inputs with up to 4 decimal places ($0.0001R$, or $100$ micro-R).
   - Non-finite numbers (`NaN`, `Infinity`, `-Infinity`), numbers $\le 0$, and non-numbers are rejected immediately.
3. **Aggregate-Only Rounding:**
   - Positions are summed without any per-position intermediate rounding:
     $$\text{totalMicroR} = \sum_{i=1}^N \text{microR}_i$$
     $$\text{totalRiskR} = \frac{\text{totalMicroR}}{1,000,000}$$
   - Display layers round strictly at the presentation boundary:
     - Header KPI: `.toFixed(1)` (e.g. `1.8R`)
     - Secondary Cards & Detail Tables: `.toFixed(2)` (e.g. `2.30R`, `0.02R`)

---

## 3. Worked Boundary Examples

### 3.1 The $0.005R$ Discriminator Case
- **Input:** Three positions with $allocatedRiskR = 0.005R$:
  - Position 1: $5,000$ micro-R
  - Position 2: $5,000$ micro-R
  - Position 3: $5,000$ micro-R
- **Sum:** $15,000$ micro-R $= 0.015000R$.
- **Display Output:** Formats at 2 decimals as `0.02R` (half-up at display).
- **Contrast with Defective Rounding:** If each position were rounded to hundredths first ($0.005 \to 0.01$), the sum would be $0.03R$ (+100% rounding distortion). The micro-R aggregate preserves exact precision.

### 3.2 Boundary Cap Equality
- **Lane Cap:** $1.8R$ ($1,800,000$ micro-R)
- **Current Lane Risk:** $1.0R$ ($1,000,000$ micro-R)
- **Candidate Risk:** $0.8R$ ($800,000$ micro-R)
- **Projected Risk:** $1,800,000$ micro-R $\le 1,800,000$ micro-R $\implies$ **`CLEAR` (Inclusive Ceiling)**.
- **Candidate Risk $0.8001R$:** $1,800,100$ micro-R $> 1,800,000$ micro-R $\implies$ **`BREACHED` (Excess $0.0001R$)**.

---

## 4. Invalid, Unknown, and Empty Portfolio Semantics

1. **Empty Portfolio ($N = 0$):**
   - Returns `{ status: 'VALID', totalRiskR: 0.0, evaluatedCount: 0 }`.
   - Distinct from invalid state; renders `0.0R` in UI.
2. **Missing `allocatedRiskR` on Open Position:**
   - Returns `{ isValid: false, riskR: null, reason: 'Position ... has missing or invalid allocatedRiskR' }`.
   - Ingestion into portfolio causes `evaluatePortfolioRisk` to return `{ status: 'INVALID', totalRiskR: null }`.
   - **Zero Partial Sums:** Valid positions in the same portfolio are never summed partially. The entire KPI renders `INVALID`.

---

## 5. Verification Test Matrix

- Precision test: `H1-RISK-02.1` ($3 \times 0.005R = 0.015R$)
- Boundary equality test: `H1-RISK-02.3` ($1.0 + 0.8 = 1.8 \implies$ CLEAR, $1.0 + 0.8001 \implies$ BREACHED)
- Permutation determinism: `H1-RISK-02.2` (Sum is invariant under position order)
- Missing allocated risk test: `H1.1-PROV-01` (Unallocated position fails closed, zero fallback to setup map)

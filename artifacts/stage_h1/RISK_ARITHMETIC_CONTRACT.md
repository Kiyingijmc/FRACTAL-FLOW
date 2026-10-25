# FRACTAL-FLOW — Risk Arithmetic Contract
**Document:** `artifacts/stage_h1/RISK_ARITHMETIC_CONTRACT.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > DETERMINISM > AUDITABILITY`  
**Date:** 2026-10-24  

---

## 1. Domain Definition and Meaning of $R$

In the FRACTAL-FLOW systematic trading architecture:
- **$R$ (Risk Multiple):** The canonical, normalized unit of capital risk allocated to a position or candidate setup.
- **$1.0R$:** The total monetary loss that will be realized if an open position is stopped out at its structural stop loss, including commission and estimated slippage.
- **Allocated Risk ($allocatedRiskR$):** The planned initial risk allocation committed to a trade upon gate clearance and order issuance.
- **Unrealized Risk Multiple ($unrealizedR$):** The mark-to-market floating profit or loss expressed as a multiple of initial risk:
  $$\text{unrealizedR} = \frac{\text{Current Price} - \text{Entry Price}}{\text{Entry Price} - \text{Stop Loss Price}}$$

---

## 2. Numeric Representation & Internal Scaling

To guarantee determinism, prevent floating-point accumulation drift, and eliminate premature truncation:

1. **Internal Scaling (Micro-R Basis):**
   - 1 R is represented internally as $1,000,000$ micro-R ($10^6$).
   - Calculations convert input risk $R \in \mathbb{R}$ to micro-R using exact integer conversion:
     $$\text{microR} = \text{Math.round}(R \times 1,000,000)$$
   - Standard JavaScript `Number.MAX_SAFE_INTEGER` ($9 \times 10^{15}$) accommodates up to $9 \times 10^9$ R without overflow, well above the physical portfolio cap ($200.0R$).

2. **Permitted Precision Layers:**
   - **Position Layer:** High-precision input permitted up to 4 decimal places ($0.0001R$, or 100 micro-R). Minimum meaningful risk is $0.001R$.
   - **Aggregation Layer:** Full precision summation in micro-R without intermediate rounding. Summation order is deterministic:
     $$\text{totalMicroR} = \sum_{i=1}^N \text{microR}_i$$
     $$\text{totalRiskR} = \frac{\text{totalMicroR}}{1,000,000}$$
   - **Display Layer:** Formatted to 2 decimal places (`.toFixed(2)`) for tables/cards, and 1 decimal place (`.toFixed(1)`) for compact headers. Rounding occurs *strictly at the presentation boundary*.

---

## 3. The $0.005R$ Discriminator Case

Consider three small position allocations of $0.005R$:
- **Premature Per-Position Rounding (DEFECTIVE):**
  If each position is rounded to hundredths before summing:
  - $0.005R \xrightarrow{\text{round}} 0.01R$
  - Total $= 0.01 + 0.01 + 0.01 = 0.03R$
  - Result: **+100% rounding distortion** ($0.03R$ reported instead of $0.015R$).
- **Canonical Micro-R Aggregation (CORRECT):**
  - Position 1: $5,000$ micro-R
  - Position 2: $5,000$ micro-R
  - Position 3: $5,000$ micro-R
  - Total: $15,000$ micro-R $= 0.0150R$.
  - Exact aggregate: $0.015R$.
  - Display formatting (half-up at 2 decimals): $0.02R$.

The canonical contract mandates **Aggregate-Only Rounding**: intermediate positions are preserved at micro-R precision throughout portfolio summation.

---

## 4. Cap Comparison & Boundary Semantics

1. **Inclusive Ceiling:**
   Operational caps (`maxLaneRiskR`, `maxAccountExposureR`) are inclusive upper bounds:
   - $\text{projectedRisk} \le \text{cap}$: **CLEAR / PERMITTED**
   - $\text{projectedRisk} > \text{cap}$: **BREACHED (BLOCKING)**

2. **Exact Equality:**
   When $\text{projectedRisk} = \text{cap}$, the candidate or portfolio is strictly within limits and must return `CLEAR` (or nominal status). Equality does not breach.

3. **Comparison Precision:**
   Cap comparisons are performed on the unrounded micro-R integer values:
   $$\text{isBreached} = \text{projectedMicroR} > \text{capMicroR}$$

---

## 5. Invalid, Unknown, and Empty Portfolio Propagation

1. **Empty Portfolio ($N = 0$):**
   - An empty portfolio is valid.
   - $\text{status} = \text{'VALID'}$, $\text{totalRiskR} = 0.0$, $\text{evaluatedCount} = 0$.
   - Display: `0.0R` or `0.00R`.

2. **Corrupt or Unallocated Position ($N \ge 1$):**
   - If *any* included position has `allocatedRiskR` that is `null`, `undefined`, $\le 0$, `NaN`, non-finite, or an unknown setup without explicit allocation:
   - Evaluation fails closed immediately:
     $$\text{status} = \text{'INVALID'}$$
     $$\text{totalRiskR} = \text{null}$$
   - **Zero Partial Sums:** The evaluator never returns a partial numeric sum for remaining valid positions. The entire portfolio is marked `INVALID`.
   - **UI Propagation:** Header and secondary views render `INVALID` or `--R`. They must never display a numeric total or substitute `0.0R`.

---

## 6. Daily Loss Currency Semantics

Daily loss limit is evaluated in integer currency cents to prevent IEEE-754 binary floating-point representation artifacts:
$$\text{pnlCents} = \text{Math.round}(\text{dailyPnlUsd} \times 100)$$
$$\text{limitCents} = \text{Math.round}(\text{dailyLossLimitUsd} \times 100)$$
$$\text{isDailyLossBreached} = \text{pnlCents} \le -\text{limitCents}$$
$$\text{isDailyLossWarning} = \text{pnlCents} \le -\text{Math.round}(\text{limitCents} \times 0.80)$$

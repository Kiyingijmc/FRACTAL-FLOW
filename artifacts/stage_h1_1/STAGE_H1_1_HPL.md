# FRACTAL-FLOW — Stage H.1.1 Hostile Proof List (STAGE_H1_1_HPL)
**Document:** `artifacts/stage_h1_1/STAGE_H1_1_HPL.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`  
**Date:** 2026-10-25  
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`  
**Working Branch:** `work/stage-h1-1-risk-provenance-20261026`  

---

## 1. Stage H.1.1 Invariant Matrix

| Invariant ID | Severity | Defect / Vulnerability Surface | Required Production Invariant | Production Test Target | Current Disposition |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **HPL-H1.1-RISK-01** | CRITICAL (P0/P1) | `DEFAULT_SETUP_RISK_MAP` used as fallback for open positions lacking `allocatedRiskR` | Existing open positions *must* have explicit, valid `allocatedRiskR`. Missing or invalid `allocatedRiskR` fails closed as `INVALID` with zero estimate guessing. Setup map is restricted strictly to candidate planning. | `src/utils/riskValidator.ts`, `src/App.tsx`, `src/components/Header.tsx` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1.1-RISK-02** | HIGH (P1) | Arithmetic precision and cap boundaries across lane and account | Micro-R integer scaling ($10^6$) rigorously validated against $3 \times 0.005R$, exact cap equality (CLEAR), strictly greater (BREACHED), and permutation invariance. | `src/utils/riskValidator.ts`, `evaluatePortfolioRisk` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1.1-TEST-01** | HIGH (P1) | Tests relying solely on static `renderToString` without interactive state changes | Production test harness exercising interactive state transitions: valid $\to$ invalid $\to$ valid, position modification, desktop & mobile displays, protective actions with invalid risk. | `src/tests/stage_h1_1_production_path.test.ts` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1.1-PROTECT-01** | HIGH (P1) | Protective de-risking and authority barriers during risk-invalid states | De-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) permitted; position additions / risk expansions blocked; live execution fails closed unconditionally. | `src/App.tsx`, `src/providers/LiveCommandAdapter.ts`, `src/providers/SimulationProvider.ts` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1.1-EVID-01** | HIGH (P1) | Stale artifact checksums, ambiguous manifests, or premature closure claims | Individual row-by-row closure based on actual verified execution logs; self-referential manifest exclusion explicitly documented; SHA-256 computed from disk bytes. | `artifacts/stage_h1_1/`, `public/export/` | **OPEN (IN IMPLEMENTATION)** |

---

## 2. Invariant Specifications & Acceptance Criteria

### HPL-H1.1-RISK-01: Explicit Allocated Risk vs Setup Estimates
- **Defect Scenario:** Position `pos_1` has `allocatedRiskR: undefined` and `setup: 'FF-01'`. The previous code returned `riskR: 0.8` from `DEFAULT_SETUP_RISK_MAP`.
- **Invariant Requirement:**
  1. `getValidPositionRiskR(pos)` must strictly require `typeof pos.allocatedRiskR === 'number'`, finite, and $> 0$.
  2. If `allocatedRiskR` is missing or invalid, `getValidPositionRiskR` returns `{ isValid: false, riskR: null, reason: 'Position ... has missing or invalid allocatedRiskR' }`.
  3. It must NEVER fall back to `DEFAULT_SETUP_RISK_MAP`.
  4. Candidate planning risk uses a separate function `getCandidatePlannedRiskR(candidate, explicitRiskR?)` that explicitly documents candidate planning semantics.
  5. If an existing position is invalid, the entire portfolio evaluates to `status: 'INVALID'`, `totalRiskR: null`. Zero partial sums!

### HPL-H1.1-RISK-02: Micro-R Arithmetic & Unified Cap Boundaries
- **Invariant Requirement:**
  1. Internal aggregation uses exact integer micro-R ($10^6$ scale).
  2. $0.005R + 0.005R + 0.005R = 0.0150R$ (exact). Displayed as `0.02R` (half-up at 2 decimals).
  3. Cap comparison at both lane and account levels uses micro-R integers:
     - `projectedMicroR <= capMicroR`: CLEAR
     - `projectedMicroR > capMicroR`: BREACHED
  4. Exact equality ($1.8000R \le 1.8R$) returns CLEAR.

### HPL-H1.1-TEST-01: Interactive Production State Transitions
- **Invariant Requirement:**
  1. Test exercises real component state transitions:
     - Initial valid state -> user adds/mutates position to invalid -> Header and Secondary views immediately transition from valid numeric R to `INVALID` badge.
     - Invalid state -> user closes/corrects invalid position -> Header immediately recovers to valid numeric R.
  2. Tests desktop and mobile KPI elements.
  3. Negative controls verify that disabling guards causes tests to fail.

### HPL-H1.1-PROTECT-01: Protective Actions & Authority Boundaries
- **Invariant Requirement:**
  1. De-risking actions (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) remain fully executable in simulation even when open risk is `INVALID` or limits are breached.
  2. Risk configuration updates with cross-field violations (`maxLane > maxAccount`) are rejected fail-closed with `MUTATION_BLOCKED` audit record.
  3. Live command submission unconditionally throws `LiveExecutionBlockedError`.
  4. Command rejections preserve protected trading state bit-for-bit (`FF-D-04`).

### HPL-H1.1-EVID-01: Evidence Reconciliation & Artifact Checksums
- **Invariant Requirement:**
  1. Every HPL row updated individually after verified test execution.
  2. `SHA256SUMS_STAGE_H1_1.txt` generated directly from file bytes on disk.
  3. Manifest excludes itself to prevent circular hashing.
  4. Raw stdout/stderr logs and exit codes captured under `artifacts/stage_h1_1/logs/`.

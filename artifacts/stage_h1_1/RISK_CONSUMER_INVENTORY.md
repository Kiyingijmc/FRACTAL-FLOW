# FRACTAL-FLOW Control Surface — Stage H.1.1 Risk Consumer Inventory
**Document:** `artifacts/stage_h1_1/RISK_CONSUMER_INVENTORY.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Date:** 2026-10-25  
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`  

---

## 1. Risk Semantic Categories

To eliminate semantic conflation between actual open risk and prospective estimates, every risk consumer is classified into one of four explicit categories:

1. **Actual Allocated Exposure (`ACTUAL_EXPOSURE`):** Real, committed capital risk of existing open positions. Must be backed by explicit `allocatedRiskR`. If missing or invalid, evaluation fails closed (`INVALID`, `totalRiskR: null`).
2. **Planned Candidate Risk (`PLANNED_CANDIDATE`):** Proposed risk for a candidate setup prior to execution. Evaluated during pre-flight gate clearance against current exposure.
3. **Strategy Setup Default (`SETUP_DEFAULT_ESTIMATE`):** Static baseline parameters associated with a strategy archetype (e.g. `FF-01` = 0.8R). Used *only* for candidate planning defaults when candidate risk is unconfigured; strictly prohibited as a fallback for open positions.
4. **Invalid / Unknown Risk (`INVALID_UNKNOWN`):** Missing, non-finite, negative, or corrupt risk data. Must propagate as non-numeric `INVALID` or `--R`.

---

## 2. Comprehensive Consumer Inventory

| # | File & Symbol / Component | Input Source | Semantic Category | Validation Path | Invalid / Unknown Handling | Operational Impact | Test Evidence | Final Status |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **RC-01** | `src/utils/riskValidator.ts`<br>`getValidPositionRiskR` | `Position.allocatedRiskR` | `ACTUAL_EXPOSURE` | `typeof pos.allocatedRiskR === 'number'`, finite, $> 0$ | Fails closed: `{ isValid: false, riskR: null, reason: '...' }`. Zero fallback to setup map. | Ingestion gate for position risk | `stage_h1_1_production_path.test.ts` | **VERIFIED** |
| **RC-02** | `src/utils/riskValidator.ts`<br>`evaluatePortfolioRisk` | `Position[]`, `laneFilter?: string` | `ACTUAL_EXPOSURE` | Iterates `getValidPositionRiskR`; micro-R integer scaling ($10^6$) | Atomic fail-closed: if any position invalid, returns `status: 'INVALID'`, `totalRiskR: null` (zero partial sums) | Core portfolio risk calculation | `stage_h1_1_production_path.test.ts` | **VERIFIED** |
| **RC-03** | `src/utils/riskValidator.ts`<br>`calculateLaneRiskR` | `Position[]`, `lane: string` | `ACTUAL_EXPOSURE` | Calls `evaluatePortfolioRisk(positions, lane)` | Returns `NaN` if lane evaluation is `INVALID` | Lane risk aggregation | `risk_validator_and_latency.test.ts` | **VERIFIED** |
| **RC-04** | `src/utils/riskValidator.ts`<br>`calculateAccountExposureR` | `Position[]` | `ACTUAL_EXPOSURE` | Calls `evaluatePortfolioRisk(positions)` | Returns `NaN` if account evaluation is `INVALID` | Total account exposure aggregation | `risk_validator_and_latency.test.ts` | **VERIFIED** |
| **RC-05** | `src/utils/riskValidator.ts`<br>`getCandidatePlannedRiskR` | `GateCandidate`, optional override `number` | `PLANNED_CANDIDATE` | Explicit candidate risk $>0$ or `DEFAULT_SETUP_RISK_MAP[candidate.setup]` | Returns `{ isValid: false, plannedRiskR: null }` if setup unknown | Pre-flight candidate risk sizing | `stage_h1_1_production_path.test.ts` | **VERIFIED** |
| **RC-06** | `src/utils/riskValidator.ts`<br>`validateCandidateAgainstRiskConfig` | `GateCandidate`, `Position[]`, `OperationalRiskConfig` | `PLANNED_CANDIDATE` vs `ACTUAL_EXPOSURE` | Combines `getCandidatePlannedRiskR` with `evaluatePortfolioRisk` | Returns `status: 'INVALID'` or `'UNKNOWN'`, never `'CLEAR'` on corrupted inputs | Gate pre-flight assessment (non-authoritative) | `risk_validator_and_latency.test.ts` | **VERIFIED** |
| **RC-07** | `src/utils/riskValidator.ts`<br>`validateOperationalRiskConfig` | `OperationalRiskConfig` draft | Limit Thresholds | Cross-field invariant (`maxLaneRiskR <= maxAccountExposureR`), finite, $> 0$ | Returns `{ isValid: false, errors: [...] }` | Risk setting mutation gate | `stage_h_adversarial_invariants.test.ts` | **VERIFIED** |
| **RC-08** | `src/App.tsx`<br>`portfolioRiskEval` / `openRiskR` | `positions` array | `ACTUAL_EXPOSURE` | Calls `evaluatePortfolioRisk(positions)` | Sets `openRiskR = null` if status is not `VALID` | Passes validated risk to Header and Secondary views | `stage_h1_production_behavior.test.ts` | **VERIFIED** |
| **RC-09** | `src/components/Header.tsx`<br>Desktop Open Risk KPI | `openRiskR: number \| null` | `ACTUAL_EXPOSURE` | `openRiskR !== null && Number.isFinite(openRiskR)` | Renders `<span data-testid="open-risk-invalid">INVALID</span>` in rose font | Operator instrument panel KPI | `stage_h1_production_behavior.test.ts` | **VERIFIED** |
| **RC-10** | `src/components/Header.tsx`<br>Mobile Open Risk KPI | `openRiskR: number \| null` | `ACTUAL_EXPOSURE` | `openRiskR !== null && Number.isFinite(openRiskR)` | Renders `<span data-testid="open-risk-invalid-mobile">INVALID</span>` | Mobile header KPI | `stage_h1_production_behavior.test.ts` | **VERIFIED** |
| **RC-11** | `src/components/SecondaryViews.tsx`<br>RISK Tab Total Open Risk | `positions?: Position[]` | `ACTUAL_EXPOSURE` | Calls `evaluatePortfolioRisk(positions)` | Renders `INVALID` and disables percent capacity | Detailed secondary view | `stage_h1_production_behavior.test.ts` | **VERIFIED** |
| **RC-12** | `src/components/SecondaryViews.tsx`<br>RISK Tab Lane Open Risk | `positions?: Position[]`, `lane: 'ACT_PRIMARY'` | `ACTUAL_EXPOSURE` | Calls `evaluatePortfolioRisk(positions, 'ACT_PRIMARY')` | Renders `INVALID` and disables percent capacity | Detailed secondary view | `stage_h1_production_behavior.test.ts` | **VERIFIED** |
| **RC-13** | `src/components/AutomatedRiskValidator.tsx`<br>Risk Status Badge | `CandidateRiskValidation` | `PLANNED_CANDIDATE` | Consumes `validateCandidateAgainstRiskConfig` | Renders amber `INVALID` or slate `UNKNOWN` badge with diagnostic tooltip | Pre-flight gate inspector | `risk_validator_and_latency.test.ts` | **VERIFIED** |
| **RC-14** | `src/components/ContextPanel.tsx`<br>Allocated Risk Metric | `Position.allocatedRiskR` | `ACTUAL_EXPOSURE` | Direct property access | Formats `${allocatedRiskR.toFixed(2)}R` or `--R` | Position context panel | Real UI rendering | **VERIFIED** |

---

## 3. Strict Boundary Summary

1. **Zero Estimation for Open Positions:** `getValidPositionRiskR` never falls back to `DEFAULT_SETUP_RISK_MAP`. An open position without `allocatedRiskR` is unconditionally invalid.
2. **Separation of Candidate Planning:** Candidate planning uses `getCandidatePlannedRiskR`, which explicitly allows setup baseline defaults for prospective trades.
3. **Atomic Evaluation:** Corrupt risk in any open position poisons the entire portfolio aggregate to `null`/`INVALID`, preventing partial sums from being presented as valid exposure.

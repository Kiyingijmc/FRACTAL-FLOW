# FRACTAL-FLOW Control Surface — Risk Consumer Inventory
**Document:** `artifacts/stage_h1/RISK_CONSUMER_INVENTORY.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Date:** 2026-10-24  
**Starting Checkpoint:** `b0fed19bc3904538f6081b437ee851c459da2915`  

---

## 1. Inventory Summary

This document catalogues every consumer, calculation, and display of risk units across the entire FRACTAL-FLOW control surface codebase (`src/`).

| # | File & Symbol / Component | Input Source | Unit & Semantics | Validation Function Used | Invalid / Unknown Handling | Value Category | Production Test Target | Current Status |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C-01** | `src/App.tsx`<br>`openRiskR` (useMemo) | `positions` array | Account aggregate open risk in `R` | **DEFECT (BEFORE H.1):** None (`positions.length * 0.6`).<br>**CORRECTED:** `evaluatePortfolioRisk(positions)` | Displays `null` / `INVALID` if any position is invalid | Simulated actual portfolio exposure | `src/tests/stage_h1_production_behavior.test.ts` | **REMEDIATING** |
| **C-02** | `src/components/Header.tsx`<br>Desktop open risk KPI | `openRiskR: number \| null` (prop) | Aggregate account risk in `R` | Consumes validated `openRiskR` from `App.tsx` | If `null` / `NaN`: renders `<span data-testid="open-risk-invalid">INVALID</span>` with warning style | Simulated actual portfolio exposure | `src/tests/stage_h1_production_behavior.test.ts` | **REMEDIATING** |
| **C-03** | `src/components/Header.tsx`<br>Mobile open risk KPI | `openRiskR: number \| null` (prop) | Aggregate account risk in `R` | Consumes validated `openRiskR` from `App.tsx` | If `null` / `NaN`: renders `INVALID` | Simulated actual portfolio exposure | `src/tests/stage_h1_production_behavior.test.ts` | **REMEDIATING** |
| **C-04** | `src/utils/riskValidator.ts`<br>`getValidPositionRiskR` | `Position` object | Single position risk in `R` | `getValidPositionRiskR` | Fails closed: returns `{ isValid: false, riskR: null, reason: '...' }` | Allocated actual risk (or mapped setup fallback if valid) | `src/tests/stage_h_adversarial_invariants.test.ts` | **VERIFIED** |
| **C-05** | `src/utils/riskValidator.ts`<br>`evaluatePortfolioRisk` | `Position[]`, `laneFilter?: string` | Aggregate portfolio or lane risk in `R` | `getValidPositionRiskR` per position | Atomic fail-closed: if any position invalid, returns `totalRiskR: null` (zero partial sums) | Simulated actual portfolio exposure | `src/tests/stage_h1_production_behavior.test.ts` | **REMEDIATING (PRECISION)** |
| **C-06** | `src/utils/riskValidator.ts`<br>`calculateLaneRiskR` | `Position[]`, `lane: string` | Total open risk in `R` for specific lane | `evaluatePortfolioRisk(positions, lane)` | Returns `NaN` if lane risk is `INVALID` | Simulated actual lane exposure | `src/tests/risk_validator_and_latency.test.ts` | **VERIFIED** |
| **C-07** | `src/utils/riskValidator.ts`<br>`calculateAccountExposureR` | `Position[]` | Total open risk in `R` across all lanes | `evaluatePortfolioRisk(positions)` | Returns `NaN` if account risk is `INVALID` | Simulated actual account exposure | `src/tests/risk_validator_and_latency.test.ts` | **VERIFIED** |
| **C-08** | `src/utils/riskValidator.ts`<br>`validateOperationalRiskConfig` | `OperationalRiskConfig` draft | Limit caps (`maxLaneRiskR`, `maxAccountExposureR`) | Pure boundary validation | Rejects `NaN`, `<=0`, `>cap`, and `maxLane > maxAccount` | Configured boundary rules | `src/tests/stage_h_adversarial_invariants.test.ts` | **VERIFIED** |
| **C-09** | `src/utils/riskValidator.ts`<br>`validateCandidateAgainstRiskConfig` | `GateCandidate`, `Position[]`, `OperationalRiskConfig` | Candidate setup risk in `R` combined with existing exposure | `evaluatePortfolioRisk`, `validateOperationalRiskConfig` | Returns `status: 'INVALID'` or `'UNKNOWN'`, never `'CLEAR'` on bad inputs | Candidate planned risk vs current exposure | `src/tests/risk_validator_and_latency.test.ts` | **VERIFIED** |
| **C-10** | `src/components/AutomatedRiskValidator.tsx`<br>Candidate Badge | `CandidateRiskValidation` object | Status badge (`CLEAR`, `WARNING`, `BREACHED`, `INVALID`, `UNKNOWN`) | Consumes `validateCandidateAgainstRiskConfig` | Explicit amber badge for `INVALID` and slate for `UNKNOWN` | Pre-flight analytical assessment | `src/tests/risk_validator_and_latency.test.ts` | **VERIFIED** |
| **C-11** | `src/components/SecondaryViews.tsx`<br>RISK Tab Cards | `positions?: Position[]`, `riskConfig?: OperationalRiskConfig` | Account & Lane capacity metrics | **DEFECT (BEFORE H.1):** Static literals `1.80R`, `1.20R`.<br>**CORRECTED:** Dynamically derived via `evaluatePortfolioRisk` | Displays `INVALID` on corrupt data | Simulated actual portfolio exposure | `src/tests/stage_h1_production_behavior.test.ts` | **REMEDIATING** |
| **C-12** | `src/components/SettingsModal.tsx`<br>Operational Risk Form | `OperationalRiskConfig` draft | Configured risk ceilings | `validateOperationalRiskConfig` | Visual error banner, disables Save button | Planned operational thresholds | `src/tests/expansion_invariants.test.ts` | **VERIFIED** |
| **C-13** | `src/components/ContextPanel.tsx`<br>Position Detail R-Metrics | `Position` (`unrealizedR`, `allocatedRiskR`) | Unrealized P&L in R and excursion | Monospace numeric rendering | Formats `allocatedRiskR` directly with `R` suffix | Position-level allocated risk | Real component UI | **VERIFIED** |
| **C-14** | `src/components/PositionsTable.tsx`<br>Unrealized R Column | `Position.unrealizedR` | Unrealized trade performance in `R` | Signed numeric formatting | Formats `+1.62R`, `-0.74R` | Position mark-to-market performance | `src/tests/positions_table_sort.test.ts` | **VERIFIED** |

---

## 2. Invariant Tracing

1. **Elimination of Fallback Proxies:** No component is permitted to derive risk from `position.size * 100`, `position.size * 1.0`, or `positions.length * 0.6`.
2. **Authority Decoupling:** Risk display components are presentation layers only; they never grant trading or order authorization.
3. **Fail-Closed Propagation:** Corrupted or unallocated position risk in any open position propagates `null`/`INVALID` to both the Header KPI and the Secondary RISK view.

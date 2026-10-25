# FRACTAL-FLOW — Stage H.1.1 Corrective Design Specification
**Document:** `artifacts/stage_h1_1/01_CORRECTIVE_DESIGN.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Date:** 2026-10-25  
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`  
**Working Branch:** `work/stage-h1-1-risk-provenance-20261026`  

---

## 1. Executive Summary & Problem Statement

In commit `28372d0`, `getValidPositionRiskR` retained a fallback path:
```ts
if (pos.setup && typeof DEFAULT_SETUP_RISK_MAP[pos.setup] === 'number') {
  return { isValid: true, riskR: DEFAULT_SETUP_RISK_MAP[pos.setup] };
}
```
If an existing open position lacked explicit `allocatedRiskR`, the validator inferred its risk from `DEFAULT_SETUP_RISK_MAP`. This violated the core safety invariant that **actual allocated exposure must not silently masquerade from strategy setup estimates**.

Stage H.1.1 delivers a targeted, surgical correction:
1. **Eliminate Setup Fallback for Existing Positions:** `getValidPositionRiskR` requires explicit, positive, finite `allocatedRiskR`. If absent or invalid, it returns `isValid: false`, causing portfolio aggregation to fail closed (`status: 'INVALID'`, `totalRiskR: null`).
2. **Dedicated Candidate Planned Risk Function:** Create `getCandidatePlannedRiskR(candidate, explicitRiskR?)` for prospective trade candidates, explicitly separating candidate planning semantics from position actual exposure.
3. **Interactive Production State Verification:** Implement `src/tests/stage_h1_1_production_path.test.ts` verifying real interactive state changes (valid $\leftrightarrow$ invalid) and protective behavior.
4. **Evidence & Artifact Integrity:** Update HPL individually with verifiable evidence, capture raw logs with exit codes, and generate independent disk-based checksum manifests.

---

## 2. Surgical Code Modifications

### 2.1 `src/utils/riskValidator.ts`
```ts
// Existing Position Risk Validator: Strictly requires explicit allocatedRiskR
export function getValidPositionRiskR(pos: Position): { isValid: boolean; riskR: number | null; reason?: string } {
  if (!pos || typeof pos !== 'object') {
    return { isValid: false, riskR: null, reason: 'Position is null or non-object' };
  }
  if (typeof pos.allocatedRiskR !== 'number' || !Number.isFinite(pos.allocatedRiskR) || pos.allocatedRiskR <= 0) {
    return { 
      isValid: false, 
      riskR: null, 
      reason: `Position ${pos.id || 'UNKNOWN'} has missing or invalid allocatedRiskR (${pos.allocatedRiskR})` 
    };
  }
  return { isValid: true, riskR: pos.allocatedRiskR };
}

// Dedicated Candidate Planned Risk: Explicitly documented for prospective planning only
export function getCandidatePlannedRiskR(
  candidate: GateCandidate,
  overrideRiskR?: number
): { isValid: boolean; plannedRiskR: number | null; reason?: string } {
  if (typeof overrideRiskR === 'number') {
    if (!Number.isFinite(overrideRiskR) || overrideRiskR <= 0) {
      return { isValid: false, plannedRiskR: null, reason: `Candidate override risk (${overrideRiskR}) is non-finite or non-positive` };
    }
    return { isValid: true, plannedRiskR: overrideRiskR };
  }
  if (candidate.setup && typeof DEFAULT_SETUP_RISK_MAP[candidate.setup] === 'number') {
    return { isValid: true, plannedRiskR: DEFAULT_SETUP_RISK_MAP[candidate.setup] };
  }
  return { isValid: false, plannedRiskR: null, reason: `Candidate setup '${candidate.setup}' has no documented planned risk` };
}
```

### 2.2 Candidate Validation Integration
In `validateCandidateAgainstRiskConfig`:
Call `getCandidatePlannedRiskR(candidate, candidateRiskOverride)` to establish candidate planned risk, while calling `evaluatePortfolioRisk(positions)` to establish actual current portfolio exposure. The two semantics remain completely decoupled.

---

## 3. Interactive Test Strategy (`stage_h1_1_production_path.test.ts`)

1. **State Transition: Valid $\to$ Invalid $\to$ Valid:**
   - Simulate a user session where initial positions are valid (`2.30R`).
   - Ingest an unallocated position (missing `allocatedRiskR`) -> assert Header and Secondary views immediately transition to `INVALID` badge.
   - Close or remove the invalid position -> assert Header immediately recovers to valid numeric aggregate.
2. **Negative Controls:**
   - Verify that calling `getValidPositionRiskR` on a position with known setup `'FF-01'` but missing `allocatedRiskR` returns `isValid: false` (proving the old fallback is completely removed).
3. **Protective Actions:**
   - Prove that de-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) succeed even when open risk is `INVALID`.

---

## 4. Regression Risks & Rollback

- **Risk:** Existing tests in `stage_h_adversarial_invariants.test.ts` or `stage_h1_production_behavior.test.ts` that constructed mock positions without `allocatedRiskR`.
- **Mitigation:** Audit and ensure all valid test fixtures carry explicit `allocatedRiskR`.
- **Rollback:** Isolated on branch `work/stage-h1-1-risk-provenance-20261026`. Reverting to `28372d0` is clean and deterministic.

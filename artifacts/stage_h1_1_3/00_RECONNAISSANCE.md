# FRACTAL-FLOW — Stage H.1.1.3 Forensic Reconnaissance

## 1. Executive Summary & Objective

- **Stage:** H.1.1.3 Projected-Risk Authorization and State-Consistency Remediation
- **Governing Protocol:** Universal Forensic Engineering Protocol (UFEP):
  `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`
- **Objective:** Remediate the risk-increasing authorization path (`ADD_SIZE`, `SCALE_IN`) by enforcing that every proposed risk-increasing modification is evaluated against both the projected post-action aggregate account exposure and the projected lane-level risk cap using authoritative domain semantics and micro-R arithmetic before any command intent or provider mutation can occur.

---

## 2. Baseline and Reference Provenance Verification

- **Repository Root:** `/tmp/repo` (with workspace mirror at `/app/applet`)
- **Verified Baseline Artifact Commit:** `ea8df46022faa7f5aba5ea12ee653bc1376c0dd3`
- **Verified Implementation Commit:** `7d4790bf5573bd49886b00000c87804467ee7d6d`
- **Verified Parent/Base Commit:** `3d29ea886b557439268b41c414848dfeb8c6014a`
- **Ancestry Verification:**
  - `git merge-base --is-ancestor 7d4790bf5573bd49886b00000c87804467ee7d6d ea8df46022faa7f5aba5ea12ee653bc1376c0dd3` -> `EXIT 0` (Confirmed)
  - `git merge-base --is-ancestor 3d29ea886b557439268b41c414848dfeb8c6014a 7d4790bf5573bd49886b00000c87804467ee7d6d` -> `EXIT 0` (Confirmed)
- **Worktree Status:** Clean (`nothing to commit, working tree clean`)
- **Stage H.1.1.2 Checksum Verification:**
  - `sha256sum -c /tmp/repo/artifacts/stage_h1_1_2/SHA256SUMS_STAGE_H1_1_2.txt` executed in `/tmp/repo/artifacts/stage_h1_1_2` -> 13/13 files verified `OK`.
- **Protected Remote References (Zero-Touch Invariant):**
  - `origin/main`: `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` (bit-for-bit verified)
  - `origin/feature/gui-control-surface`: `c392c3e95f8e950cf7552d494a97d8821c2dd158` (bit-for-bit verified)
  - PR #29: Open, untouched, unmerged, unclosed.
- **Dedicated Substage Branch:**
  - Created: `work/stage-h1-1-3-projected-risk-20261027` branching directly from `ea8df46022faa7f5aba5ea12ee653bc1376c0dd3`.

---

## 3. Relevant Files and Call Graph Reconnaissance

### 3.1 Relevant Files
1. `control_surface/src/utils/riskValidator.ts` (and `/src/utils/riskValidator.ts`):
   - Contains `validatePositionModification`, `evaluatePortfolioRisk`, `toSafeMicroR`, `hasValidRiskPrecision`, `validateOperationalRiskConfig`, `validateCandidateAgainstRiskConfig`.
2. `control_surface/src/App.tsx` (and `/src/App.tsx`):
   - Production entry point containing `handleConfirmAction`, `positionsRef`, `riskConfigRef`, `confirmModalRef`, and test seam `AppTestControlHandle`.
3. `control_surface/src/providers/SimulationProvider.ts` (and `/src/providers/SimulationProvider.ts`):
   - Sandbox execution engine executing command intents, mutating `positions`, recording `systemEvents` and `simulatedIntents`.
4. `control_surface/src/components/ConfirmDialog.tsx`:
   - Modal dialog presenting action details and routes (`ExecutionGateway.ADD_SIZE`, `ExecutionGateway.SCALE_IN`).
5. `control_surface/src/components/ContextPanel.tsx`:
   - Side panel containing `Add size (+50%)` button (`data-testid="context-btn-add-size"`).
6. `control_surface/src/types.ts`:
   - Core domain types: `Position`, `ActionType`, `OperationalRiskConfig`, `CommandExecutionRecord`.
7. `control_surface/src/tests/stage_h1_1_production_path.test.ts`:
   - Production path test suite exercising mounted `<App />` lifecycle.

### 3.2 Authorization Call Graph
```
[User Interaction: Button Click / Keyboard Shortcut '+' / ContextPanel]
        │
        ▼
   handleTriggerAction(action, targetPosition)
        │
        ▼
   setConfirmModal({ isOpen: true, action, targetPosition })
        │
        ▼
   [Operator Confirms in ConfirmDialog]
        │
        ▼
   handleConfirmAction()
        │
        ├─► Read fresh state from positionsRef.current & riskConfigRef.current
        │
        ├─► [AUTHORIZATION GATE]: validatePositionModification(
        │       action, targetPosition, riskConfig, dailyPnl, portfolioPositions
        │   )
        │   │
        │   ├─► IF Rejected:
        │   │     - setActiveCommand({ status: 'REJECTED', source: 'PRODUCTION_RISK_GATE', ... })
        │   │     - auditTrail.push({ outcome: 'REJECTED_FAIL_CLOSED', ... })
        │   │     - systemEvents.push({ level: 'crit', status: 'REJECTED', ... })
        │   │     - EXIT WITH ZERO PROVIDER MUTATION / ZERO INTENT DISPATCH
        │   │
        │   └─► IF Authorized:
        │         - createIntentFingerprint(...)
        │         - setActiveCommand({ status: 'REQUESTED', ... })
        │         - simulationProvider.submitCommand(intent)
        │         - provider applies mutation to positions sandbox
        │         - provider updates allocatedRiskR & size consistently
        │         - updatedPositions = await simulationProvider.getPositions()
        │         - setPositions(updatedPositions)
        ▼
```

---

## 4. Current Defects & Material Authorization Gaps Identified

### Defect 1: Current vs Projected Exposure Gap in `validatePositionModification`
In Stage H.1.1.2, `validatePositionModification` checked:
```typescript
if (portEval.totalRiskR !== null && portEval.totalRiskR >= riskConfig.maxAccountExposureR) {
  return { isAllowed: false, ... };
}
```
**Gap:** It compared *current* portfolio risk against `maxAccountExposureR`. If current risk was below the cap (e.g. 2.9R < 3.0R cap), a proposed risk increase (+0.4R) would project to 3.3R, but was authorized because pre-action risk was 2.9R.

### Defect 2: Omission of Lane-Level Cap Enforcement in `validatePositionModification`
The OperationalRiskConfig specifies `maxLaneRiskR` as well as `maxAccountExposureR`. In Stage H.1.1.2, `validatePositionModification` did not evaluate `maxLaneRiskR` for the target position's lane (`targetPosition.lane`), allowing actions that satisfy the account cap to breach their specific lane cap.

### Defect 3: Permissive Fallback if `portfolioPositions` is Omitted
In Stage H.1.1.2, `portfolioPositions` was optional (`portfolioPositions?: Position[]`). If omitted or undefined, `validatePositionModification` silently bypassed the portfolio check and returned `{ isAllowed: true, violations: [] }`.

### Defect 4: Provider State Metadata Inconsistency upon `ADD_SIZE` / `SCALE_IN`
In `SimulationProvider.ts`, when `ADD_SIZE` or `SCALE_IN` was executed:
```typescript
this.positions[targetIdx].size = Number((this.positions[targetIdx].size * 1.5).toFixed(2));
```
`size` was increased by 1.5, but `allocatedRiskR` was left untouched. This resulted in understated risk in subsequent evaluations, violating `HPL-H1.1.3-STATE-01` and `HPL-H1.1.3-RISK-07`.

---

## 5. Existing Guarantees to Preserve

1. **Survival & Authority Integrity:**
   - Unconditional fail-closed behavior for all non-protective mutations.
   - Zero live broker connections; `LiveCommandAdapter` strictly blocks live commands.
2. **De-risking Invariant:**
   - De-risking actions (`close_position`, `tighten_stop`, `move_to_breakeven`) must remain fully authorized and executable even when portfolio risk is `INVALID` or breached.
3. **Micro-R Precision:**
   - Deterministic integer micro-R arithmetic (`1 R = 1,000,000 micro-R`) with 4-decimal input precision contract (`0.0001 R`).
4. **Inclusive Cap Semantics:**
   - Limits are inclusive caps: `projected <= cap` is permitted; strictly greater (`projected > cap`) is breached.
5. **Test Seam Isolation:**
   - Development-only test handle (`AppTestControlHandle`) must remain strictly tree-shaken and absent from production build bundles.

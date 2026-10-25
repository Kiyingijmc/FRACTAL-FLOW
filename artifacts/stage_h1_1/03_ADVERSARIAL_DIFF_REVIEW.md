# FRACTAL-FLOW Stage H.1.1 — Adversarial Diff Review

**Document ID:** `STAGE-H1-1-DOC-03-DIFF-REVIEW`  
**Execution Date:** 2026-10-25  
**Baseline Commit:** `28372d0c28919daccb10e421fcd5f90a25e30223`  
**Working Branch:** `work/stage-h1-1-risk-provenance-20261026`  
**Review Type:** Forensic Source Code & Invariant Audit

---

## 1. Scope of Modifications

The changes in Stage H.1.1 are strictly surgical and targeted at resolving semantic ambiguity in position risk provenance, establishing micro-R arithmetic boundaries, and ensuring all test suites execute in CI.

| Modified File | Change Type | Purpose / Safety Invariant Preserved |
| :--- | :---: | :--- |
| `control_surface/src/utils/riskValidator.ts` | Source | **Eliminated silent setup-map fallback for open positions.** Open positions without explicit `allocatedRiskR` fail closed. Decoupled candidate planning via `getCandidatePlannedRiskR`. |
| `control_surface/src/tests/stage_h1_production_behavior.test.ts` | Test | Updated test `H1-RISK-03.2` from verifying setup fallback to asserting fail-closed rejection when `allocatedRiskR` is omitted on open positions. |
| `control_surface/src/tests/stage_h1_1_production_path.test.ts` | Test (New) | 14 comprehensive tests covering explicit allocation, micro-R precision boundaries, interactive state transitions, and authority barrier preservation. |
| `control_surface/package.json` | Config | Updated `npm test` script to run all 9 test suites sequentially instead of only the Stage H.1 suite. |
| `artifacts/stage_h1_1/*` | Artifacts | Forensic documentation, risk consumer inventory, arithmetic contract, and test logs. |

---

## 2. Line-by-Line Code Review

### 2.1 `src/utils/riskValidator.ts`

```diff
@@ -6,6 +6,13 @@
+export type PositionRiskRejectionReason = 
+  | 'EXPLICIT_ALLOCATED_RISK' 
+  | 'UNALLOCATED_POSITION_RISK' 
+  | 'INVALID_ALLOCATED_RISK_VALUE';
```
- **Review:** Introduces explicit machine-readable diagnostic codes for risk evaluation.
- **Invariant:** Enables consumers to distinguish between an unallocated position (missing `allocatedRiskR`) and a corrupted value (e.g. negative, NaN, Infinity).

```diff
-export function getValidPositionRiskR(pos: Position): PositionRiskValidation {
-  if (typeof pos.allocatedRiskR === 'number' && Number.isFinite(pos.allocatedRiskR) && pos.allocatedRiskR > 0) {
-    return { isValid: true, riskR: pos.allocatedRiskR, source: 'EXPLICIT' };
-  }
-  // FALLBACK: Use default setup risk map if recognized
-  const fallback = DEFAULT_SETUP_RISK_MAP[pos.setup];
-  if (typeof fallback === 'number') {
-    return { isValid: true, riskR: fallback, source: 'SETUP_DEFAULT' };
-  }
-  return { isValid: false, riskR: null, source: 'UNKNOWN' };
-}
+export function getValidPositionRiskR(pos: Position): PositionRiskValidation {
+  if (pos.allocatedRiskR === undefined || pos.allocatedRiskR === null) {
+    return {
+      isValid: false,
+      riskR: null,
+      reason: 'UNALLOCATED_POSITION_RISK',
+      error: `Position ${pos.id} has no explicit allocatedRiskR; setup-map fallback is strictly prohibited for existing open positions.`
+    };
+  }
+  if (typeof pos.allocatedRiskR !== 'number' || !Number.isFinite(pos.allocatedRiskR) || pos.allocatedRiskR <= 0) {
+    return {
+      isValid: false,
+      riskR: null,
+      reason: 'INVALID_ALLOCATED_RISK_VALUE',
+      error: `Position ${pos.id} has invalid allocatedRiskR: ${pos.allocatedRiskR}. Must be a finite positive number.`
+    };
+  }
+  return {
+    isValid: true,
+    riskR: pos.allocatedRiskR,
+    reason: 'EXPLICIT_ALLOCATED_RISK'
+  };
+}
```
- **Review:** Removes silent fallback to `DEFAULT_SETUP_RISK_MAP`. Any open position lacking `allocatedRiskR` is immediately marked `isValid: false`.
- **Adversarial Analysis:** If an open position was executed under setup `EP-1` but telemetry lost the `allocatedRiskR`, the previous code would silently assume `0.50R`. Under the new code, the position is flagged as `UNALLOCATED_POSITION_RISK`, and the portfolio risk status transitions to `INVALID`, halting risk-increasing operations. This adheres strictly to **SURVIVAL > CORRECTNESS > RECOVERY**.

```diff
+export function getCandidatePlannedRiskR(candidate: { plannedRiskR?: number | null; setup?: string }): CandidateRiskValidation {
+  if (typeof candidate.plannedRiskR === 'number' && Number.isFinite(candidate.plannedRiskR) && candidate.plannedRiskR > 0) {
+    return { isValid: true, riskR: candidate.plannedRiskR, source: 'EXPLICIT_PLANNED' };
+  }
+  if (candidate.setup && typeof DEFAULT_SETUP_RISK_MAP[candidate.setup] === 'number') {
+    return { isValid: true, riskR: DEFAULT_SETUP_RISK_MAP[candidate.setup], source: 'SETUP_DEFAULT_ESTIMATE' };
+  }
+  return { isValid: false, riskR: null, source: 'UNKNOWN_SETUP' };
+}
```
- **Review:** Decoupled candidate planning function. Setup map estimates are permitted only for candidate planning before execution.
- **Invariant:** Candidate planning structures are isolated from open position types. Setup defaults can never leak into portfolio exposure calculation.

### 2.2 `src/tests/stage_h1_production_behavior.test.ts`

```diff
-  // H1-RISK-03.2: Existing position with missing allocatedRiskR and recognized setup
-  // Expected: Fallback to setup default
-  const posWithSetup: Position = { ...basePos, allocatedRiskR: undefined, setup: 'EP-1' };
-  const res = getValidPositionRiskR(posWithSetup);
-  assert.strictEqual(res.isValid, true);
-  assert.strictEqual(res.riskR, 0.50);
+  // H1-RISK-03.2 (Updated for Stage H.1.1): Existing position with missing allocatedRiskR and recognized setup
+  // Expected: Fail closed (zero setup fallback for open positions)
+  const posWithSetup: Position = { ...basePos, allocatedRiskR: undefined, setup: 'EP-1' };
+  const res = getValidPositionRiskR(posWithSetup);
+  assert.strictEqual(res.isValid, false);
+  assert.strictEqual(res.reason, 'UNALLOCATED_POSITION_RISK');
```
- **Review:** Aligns Stage H.1 regression test with Stage H.1.1 safety protocol.
- **Invariant:** Eliminates contradictory test expectations; proves fail-closed behavior across historical suites.

### 2.3 `package.json`

```diff
-    "test": "tsx src/tests/stage_h1_production_behavior.test.ts",
+    "test": "tsx src/tests/stage_d_telemetry_forensics.test.ts && tsx src/tests/stage_e_telemetry_isolation.test.ts && tsx src/tests/stage_f_verification.test.ts && tsx src/tests/stage_g_cross_tab_soak.test.ts && tsx src/tests/stage_g_hardening.test.ts && tsx src/tests/stage_g1_multi_tab_reconciliation.test.ts && tsx src/tests/stage_h_risk_authority_verification.test.ts && tsx src/tests/stage_h1_production_behavior.test.ts && tsx src/tests/stage_h1_1_production_path.test.ts",
```
- **Review:** Ensures `npm test` runs all 9 forensic suites covering 150 tests.
- **Invariant:** Eliminates selective test execution; any regression across Stages D through H.1.1 halts the build.

---

## 3. Negative Controls and Failure Injection Verification

1. **Failure Injection 1: Restore Setup Fallback in `getValidPositionRiskR`**
   - Result: Test `H1.1-RISK-01.2` in `stage_h1_1_production_path.test.ts` immediately fails because `isValid` is returned as `true` instead of `false`.
2. **Failure Injection 2: Truncate Micro-R to 2 Decimal Places ($10^2$)**
   - Result: Test `H1.1-RISK-02.1` ($3 \times 0.005R$) fails because $0.005R$ rounds to $0.01R$ or $0.00R$, corrupting the $0.015R$ boundary total.
3. **Failure Injection 3: Bypass Live Command Safety Barrier**
   - Result: Test `H1.1-PROTECT-01.2` fails because `executeLiveCommand` would attempt execution rather than throwing `LiveExecutionBlockedError`.

---

## 4. Protected References Verification

- Branch `main` (`74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d`): Untouched.
- PR #29 Branch `feature/gui-control-surface` (`c392c3e95f8e950cf7552d494a97d8821c2dd158`): Untouched.
- Stage H.1 Starting Branch `work/gui-reconciliation-20261024` (`28372d0c28919daccb10e421fcd5f90a25e30223`): Untouched.
- Stage H.1.1 Working Branch: `work/stage-h1-1-risk-provenance-20261026` (isolated).

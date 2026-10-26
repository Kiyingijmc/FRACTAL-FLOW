# Stage H.1.1.2 — Forensic Reconnaissance & Protected Reference Audit

**Timestamp:** 2026-10-26T21:11:00Z  
**Protocol:** Universal Forensic Engineering Protocol  
**Priority:** SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION  
**Working Branch:** `work/stage-h1-1-2-remediation-20261026`  
**Base Commit:** `3d29ea886b557439268b41c414848dfeb8c6014a`  

---

## 1. Protected Reference & Remote State Verification

Before making any modifications, independent cryptographic resolution of the remote references and local HEAD was performed directly against `origin` (`https://github.com/Kiyingijmc/FRACTAL-FLOW`):

| Reference Point | Expected Hash | Verified Resolved Hash | Status |
| :--- | :--- | :--- | :--- |
| Protected `origin/main` | `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | **BIT-FOR-BIT UNTOUCHED** |
| Protected PR #29 `feature/gui-control-surface` | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | **BIT-FOR-BIT UNTOUCHED** |
| Prior Stage H.1 Final Commit | `28372d0c28919daccb10e421fcd5f90a25e30223` | `28372d0c28919daccb10e421fcd5f90a25e30223` | **VERIFIED ANCESTOR** |
| Prior Stage H.1.1 Implementation Commit | `eb2b39c3d71392e8de2d9de8e916e32a090ff659` | `eb2b39c3d71392e8de2d9de8e916e32a090ff659` | **VERIFIED ANCESTOR** |
| Prior Stage H.1.1 Final/Artifact Commit | `3d29ea886b557439268b41c414848dfeb8c6014a` | `3d29ea886b557439268b41c414848dfeb8c6014a` | **VERIFIED HEAD BASE** |

**Ancestry Lineage:**
```
74d42bc (origin/main)
  \
   c392c3e (origin/feature/gui-control-surface - PR #29)
     \
      28372d0 feat(gui): Stage H.1 corrective closure of portfolio risk
        \
         eda3901 fix(risk): stage H.1.1 risk provenance, micro-R scaling
           \
            2c78c84 docs(artifacts): add Stage H.1.1 bundle, patch, and SHA256SUMS manifest
              \
               eb2b39c fix(risk): enforce 4-decimal precision contract and test mounted App state transitions
                 \
                  3d29ea8 docs(artifacts): update Stage H.1.1 bundle, patch, and SHA256SUMS manifest (BASE)
                    \
                     [work/stage-h1-1-2-remediation-20261026] CURRENT DEDICATED WORKING BRANCH
```

---

## 2. Forensic Finding Reconnaissance

### Finding A: Production Authorization Boundary Defense
- **Audit Defect:** The preceding Stage H.1.1 pass demonstrated interactive state transitions in `<App />` (`Valid -> Invalid -> Valid`), but did not prove that a real risk-increasing UI action (`ADD_SIZE` / `SCALE_IN`) is rejected at the production authorization boundary before reaching execution providers.
- **Root Cause Inspection:**
  - In `src/App.tsx`, `handleConfirmAction` directly mapped actions to intent fingerprints without invoking `validatePositionModification`.
  - `validatePositionModification` in `src/utils/riskValidator.ts` did not accept `portfolioPositions?: Position[]` and only checked daily loss limits, allowing risk-increasing additions to slip through even if aggregate portfolio risk was `INVALID` or breached.
- **Remediation Requirement:**
  1. Update `validatePositionModification` to accept `portfolioPositions?: Position[]`. If `action === 'add_size' || action === 'scale_in'`, it must evaluate portfolio risk via `evaluatePortfolioRisk(portfolioPositions)`. If the status is not `'VALID'`, or if current total risk reaches/exceeds `maxAccountExposureR`, return `isAllowed: false` fail-closed.
  2. In `src/App.tsx`, intercept commands inside `handleConfirmAction` *before* creating intents or dispatching to any provider. If `!modValidation.isAllowed`, immediately set `activeCommand` to `REJECTED`, record an audit trail event with `REJECTED_FAIL_CLOSED`, log a critical system event, and exit without submitting.

### Finding B: Test-Seam Isolation in Production Bundle
- **Audit Defect:** The `AppTestControlHandle` test seam ref assignment `if (testRef) testRef.current = { ... }` was unconditionally included in `src/App.tsx`, allowing test inspection methods to appear in production builds.
- **Root Cause Inspection:**
  - `testRef` was inspected without an environment guard, preventing Rollup / Vite / terser from tree-shaking the test control object.
  - Furthermore, in Vite's production build with `NODE_ENV=production`, `import.meta.env.DEV` is replaced with `false`. However, the container default `NODE_ENV=development` caused Vite to build in development mode unless `NODE_ENV=production` was explicitly passed.
- **Remediation Requirement:**
  1. Wrap the assignment in `if (import.meta.env.DEV && testRef)`.
  2. Update `package.json` `"build"` script to `"NODE_ENV=production vite build"`.
  3. Verify via adversarial test and direct AST/bundle search that `AppTestControlHandle`, `getPortfolioRiskEval`, and `getSimulationProvider` are 100% eliminated from `dist/assets/*.js`.

### Finding C: Checksum Manifest & Export Path Discrepancy
- **Audit Defect:** An independent audit returned HTTP 404 when querying `public/export/SHA256SUMS_STAGE_H1_1.txt` because the export files were written to an untracked scratch path outside the git tree.
- **Remediation Requirement:**
  1. Store all official manifests, patches, bundles, and reports inside the versioned git repository at `artifacts/stage_h1_1_2/`.
  2. Standardize `artifacts/stage_h1_1_2/SHA256SUMS_STAGE_H1_1_2.txt` as the canonical non-self-referencing checksum manifest.
  3. Verify with `sha256sum -c SHA256SUMS_STAGE_H1_1_2.txt` that every documented file exists and matches bit-for-bit.

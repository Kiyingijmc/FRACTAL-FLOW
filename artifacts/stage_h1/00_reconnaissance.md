# FRACTAL-FLOW — Stage H.1 Forensic Reconnaissance Report
**Document:** `artifacts/stage_h1/00_reconnaissance.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`  
**Date:** 2026-10-24T07:23:45Z  
**Status:** `VERIFIED BY DIRECT SYSTEM EXECUTION`  

---

## 1. Provenance & Baseline Pinning Ledger

| Parameter | Observed Value | Verification Command / Source | Classification |
| :--- | :--- | :--- | :--- |
| **Repository Root** | `/tmp/repo` (Git) & `/app/applet` (Workspace) | `pwd`, `git rev-parse --show-toplevel` | `VERIFIED` |
| **Active Working Branch** | `work/gui-reconciliation-20261024` | `git -C /tmp/repo branch --show-current` | `VERIFIED` |
| **Current HEAD SHA** | `b0fed19bc3904538f6081b437ee851c459da2915` | `git -C /tmp/repo rev-parse HEAD` | `VERIFIED` |
| **Parent Commit** | `174344c04962ee737440acf89462f008cc5189fd` | `git -C /tmp/repo rev-parse HEAD~1` | `VERIFIED` |
| **Base PR #29 Checkpoint** | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `git -C /tmp/repo log -n 5 --oneline` | `VERIFIED` |
| **Protected `main` SHA** | `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | `git -C /tmp/repo ls-remote github refs/heads/main` | `VERIFIED` |
| **Protected PR #29 Ref** | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `git -C /tmp/repo ls-remote github refs/pull/29/head` | `VERIFIED` |
| **Remote Working Branch** | `b0fed19bc3904538f6081b437ee851c459da2915` | `git -C /tmp/repo ls-remote github refs/heads/work/gui-reconciliation-20261024` | `VERIFIED` |
| **Git Working Tree Status** | Clean (0 modified, 0 staged, 0 untracked in `/tmp/repo`) | `git -C /tmp/repo status` | `VERIFIED` |

### 1.1 Lineage & Ancestry Verification
Direct ancestry traversal confirms the unbroken commit chain:
```
b0fed19 (HEAD -> work/gui-reconciliation-20261024) feat(gui): Stage H forensic remediation
  ↑
174344c feat(gui): implement automated risk validator and real-time latency monitor
  ↑
bcf8f41 feat(gui): implement GUI expansion, QUANT layer, notifications, settings, lab
  ↑
c392c3e (refs/heads/feature/gui-control-surface, PR #29 HEAD) docs(gui): Stage D.2.3.4 reconcile canonical closure
  ↑ [17 linear commits ahead]
74d42bc (refs/heads/main) Protected baseline
```
The candidate commit `b0fed19` is descended directly and linearly from `174344c` and base PR #29 `c392c3e`.

---

## 2. Toolchain & Runtime Environment

| Subsystem | Version | Executable / Path | Verification Status |
| :--- | :--- | :--- | :--- |
| **Node.js** | v22.23.3 | `/usr/bin/node` | `VERIFIED` |
| **npm** | 10.9.9 | `/usr/bin/npm` | `VERIFIED` |
| **TypeScript (`tsc`)** | Version 7.0.2 | `/app/applet/node_modules/.bin/tsc` | `VERIFIED` |
| **Vite** | Version 8.3.0 | `/app/applet/node_modules/.bin/vite` | `VERIFIED` |
| **TSX Engine** | Version 4.21.0 | `/app/applet/node_modules/.bin/tsx` | `VERIFIED` |
| **Git** | Version 2.43.0 | `/usr/bin/git` | `VERIFIED` |

---

## 3. Confirmed Source-Level Defects & Forensic Discrepancies

### 3.1 Defect 1: Fabricated Open-Risk Calculation in `src/App.tsx` (P0)
Inspection of `src/App.tsx` lines 325–327 confirmed:
```tsx
const openRiskR = useMemo(() => {
  return positions.length * 0.6;
}, [positions]);
```
- **Finding:** Despite claims in previous reports that arbitrary risk fallbacks had been eliminated, `App.tsx` directly multiplied position count by `0.6` and passed this value to `<Header ... openRiskR={openRiskR} />`.
- **Impact:** Any portfolio with 4 positions renders `2.4R` on desktop and mobile headers regardless of whether the actual allocated positions are `0.8R`, `0.6R`, `0.4R`, or corrupt/negative/missing.
- **Root Cause:** The canonical evaluator `evaluatePortfolioRisk` implemented in `src/utils/riskValidator.ts` was not wired to the top-level KPI calculation in `App.tsx`.

### 3.2 Defect 2: Per-Position Intermediate Rounding in `evaluatePortfolioRisk`
Inspection of `src/utils/riskValidator.ts` line 117:
```tsx
totalHundredths += Math.round(evalResult.riskR * 100);
```
- **Finding:** Every position's allocated risk is individually rounded to 2 decimal places before being summed into `totalHundredths`.
- **Impact:** Sub-cent precision (such as three positions with `0.005R`) rounds each item down to `0` or `0.01` prematurely, introducing cumulative precision bias and failing exact precision contracts.

### 3.3 Defect 3: UTF-8 and Standard Known-Answer SHA-256 Defect in `src/utils/crypto.ts`
Inspection of `src/utils/crypto.ts` lines 86–90:
```tsx
for (let i = 0; i < rawString.length; i++) {
  bytes[i] = rawString.charCodeAt(i) & 0xff;
}
```
- **Finding:** Characters are converted using `charCodeAt(i) & 0xff`.
- **Impact:** Any non-ASCII UTF-8 character (e.g., Unicode symbols, accents, multi-byte UTF-8 sequences) has its high-order bytes truncated or corrupted, producing non-standard, invalid SHA-256 digests. Standard known-answer vectors like `""`, `"abc"`, and multi-block Unicode test vectors were not verified.

### 3.4 Defect 4: Fixture-Only and Tautological Test Assertions
Inspection of `src/tests/stage_h_adversarial_invariants.test.ts`:
- Several test assertions asserted properties on manually constructed inline test objects (e.g. asserting that a local string starts with `session:local_operator`) rather than mounting production components (`App.tsx`, `Header.tsx`, `SettingsModal.tsx`) or invoking actual handlers to test state transitions.

---

## 4. Test Commands in `package.json`

`package.json` specifies:
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "tsc --noEmit",
  "preview": "vite preview",
  "test": "tsx src/tests/safety_invariants.test.ts && tsx src/tests/responsive_structural.test.ts && tsx src/tests/positions_table_sort.test.ts && tsx src/tests/modal_focus_behavior.test.ts && tsx src/tests/gui_expansion_invariants.test.ts && tsx src/tests/risk_validator_and_latency.test.ts && tsx src/tests/stage_h_adversarial_invariants.test.ts"
}
```

---

## 5. Reconnaissance Conclusion & Progression Approval

The declared baseline, branches, parent checkpoint, and toolchain have been reconciled and pinned. The identified source-level defects have been observed and verified directly in the codebase.

Stage H.1 proceeds to Phase 1 (Hostile Proof List) and Phase 2 (Corrective Design) before any code is modified.

# FRACTAL-FLOW — Stage H.1.1 Forensic Reconnaissance Report
**Document:** `artifacts/stage_h1_1/00_RECONNAISSANCE.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`  
**Date:** 2026-10-25T14:58:36Z  
**Status:** `VERIFIED BY DIRECT SYSTEM EXECUTION`  

---

## 1. Baseline & Provenance Gate

| Parameter | Required Specification | Observed Value | Verification Source | Classification |
| :--- | :--- | :--- | :--- | :---: |
| **Repository URL** | `https://github.com/Kiyingijmc/FRACTAL-FLOW` | `https://github.com/Kiyingijmc/FRACTAL-FLOW` | `git remote -v` | `VERIFIED` |
| **Starting Candidate SHA** | `28372d0c28919daccb10e421fcd5f90a25e30223` | `28372d0c28919daccb10e421fcd5f90a25e30223` | `git rev-parse HEAD` | `VERIFIED` |
| **Starting Branch** | `work/gui-reconciliation-20261024` | `work/gui-reconciliation-20261024` (at `28372d0`) | `git ls-remote origin` | `VERIFIED` |
| **New Working Branch** | `work/stage-h1-1-risk-provenance-20261026` | `work/stage-h1-1-risk-provenance-20261026` | `git branch --show-current` | `VERIFIED` |
| **Protected `main` Baseline**| `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | `74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d` | `git ls-remote origin refs/heads/main` | `VERIFIED (UNTOUCHED)` |
| **Protected PR #29 Head** | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `c392c3e95f8e950cf7552d494a97d8821c2dd158` | `git ls-remote origin refs/heads/feature/gui-control-surface` | `VERIFIED (UNTOUCHED)` |
| **Working Tree Status** | Clean | Clean (0 modified, 0 untracked in `/tmp/repo`) | `git status` | `VERIFIED` |

### 1.1 Lineage & Ancestry Verification
Direct traversal of the Git history confirms that `work/stage-h1-1-risk-provenance-20261026` begins exactly at `28372d0`:
```
28372d0 (HEAD -> work/stage-h1-1-risk-provenance-20261026, origin/work/gui-reconciliation-20261024)
  ↑ feat(gui): Stage H.1 corrective closure of portfolio risk, standard SHA-256, and production tests
b0fed19 feat(gui): Stage H forensic remediation of risk, latency, audit, and governance invariants
  ↑
174344c feat(gui): implement automated risk validator and real-time latency monitor
  ↑
bcf8f41 feat(gui): implement GUI expansion, QUANT layer, notifications, settings, lab, and expansion invariants
  ↑
c392c3e (refs/heads/feature/gui-control-surface, PR #29 HEAD) docs(gui): Stage D.2.3.4 reconcile canonical closure report
  ↑ [17 linear commits ahead of main]
74d42bc (refs/heads/main) Mainline protected baseline
```

---

## 2. Toolchain & Runtime Environment

| Subsystem | Version | Executable / Path | Verification Status |
| :--- | :--- | :--- | :---: |
| **Node.js** | v22.23.3 | `/usr/bin/node` | `VERIFIED` |
| **npm** | 10.9.9 | `/usr/bin/npm` | `VERIFIED` |
| **TypeScript Compiler (`tsc`)** | Version 7.0.2 | `/app/applet/node_modules/.bin/tsc` | `VERIFIED` |
| **Vite Bundler** | Version 8.3.0 | `/app/applet/node_modules/.bin/vite` | `VERIFIED` |
| **TSX Runner** | Version 4.21.0 | `/app/applet/node_modules/.bin/tsx` | `VERIFIED` |
| **JSDOM** | Version 26.0.0 | `/app/applet/node_modules/jsdom` | `VERIFIED` |
| **Git Tooling** | Version 2.43.0 | `/usr/bin/git` | `VERIFIED` |

---

## 3. Discrepancies & Defect Reconnaissance (Stage H.1 $\to$ Stage H.1.1)

### 3.1 Defect 1: Conflation of Actual Allocated Risk and Setup Estimates (`HPL-H1.1-RISK-01`)
Inspection of `src/utils/riskValidator.ts` lines 71–76:
```ts
// Mapped setup risk fallback if setup is known
if (pos.setup && typeof DEFAULT_SETUP_RISK_MAP[pos.setup] === 'number') {
  const mapped = DEFAULT_SETUP_RISK_MAP[pos.setup];
  if (!Number.isFinite(mapped) || mapped <= 0) {
    return { isValid: false, riskR: null, reason: `Setup '${pos.setup}' risk (${mapped}) is non-finite or non-positive` };
  }
  return { isValid: true, riskR: mapped };
}
```
- **Finding:** If an existing open position is missing its explicit `allocatedRiskR`, the code automatically falls back to `DEFAULT_SETUP_RISK_MAP[pos.setup]`, treating a static setup-class estimate as actual allocated open exposure.
- **Threat:** If an unallocated or corrupted position is ingested, or if a trade executed at a size/stop different from the setup's default assumption, the portfolio evaluator silently treats the setup default as authoritative live exposure.
- **Remediation Mandate:** Existing open positions *must* carry explicit, valid `allocatedRiskR`. Missing or invalid `allocatedRiskR` on an existing position must fail closed with an explicit invalid result (`isValid: false`, `riskR: null`) and diagnostic reason. Candidate planning risk may continue to use setup defaults, but this must be explicitly separated, typed, and named.

### 3.2 Defect 2: Arithmetic Quantization and Cap Comparison Verification (`HPL-H1.1-RISK-02`)
- **Finding:** While integer micro-R scaling ($10^6$) avoids hundredth-R rounding, the quantization policy must be formally audited and justified against domain risk semantics. Cap comparisons at both lane and account levels must be strictly unified.

### 3.3 Defect 3: Interactive Production State Transitions (`HPL-H1.1-TEST-01`)
- **Finding:** Previous tests relied primarily on `renderToString` with static props. Real interactive state transitions (e.g. state moving from valid $\to$ invalid and invalid $\to$ valid through production handlers) must be verified.

### 3.4 Defect 4: Evidence & Manifest Discrepancies (`HPL-H1.1-EVID-01`)
- **Finding:** The previous `STAGE_H1_HPL.md` was left with open labels during turn completion, and previously queried URLs returned 404 from GitHub.
- **Remediation Mandate:** Every HPL item must be updated individually based on verified execution evidence. Manifests must be generated directly from disk bytes with self-referential exclusion explicitly documented.

---

## 4. Reconnaissance Verdict

Baseline pinning is complete. All discrepancies have been identified and traced to specific source lines. Stage H.1.1 proceeds to Phase 3 (HPL) and Phase 4 (Corrective Design).

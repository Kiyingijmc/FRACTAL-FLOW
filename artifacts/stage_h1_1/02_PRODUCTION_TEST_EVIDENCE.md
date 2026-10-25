# FRACTAL-FLOW Stage H.1.1 — Production Test Evidence Report

**Document ID:** `STAGE-H1-1-DOC-02-EVIDENCE`  
**Execution Date:** 2026-10-25  
**Baseline SHA:** `28372d0c28919daccb10e421fcd5f90a25e30223`  
**Working Branch:** `work/stage-h1-1-risk-provenance-20261026`  
**Status:** ALL TESTS PASSED (150/150 — 100% Pass Rate)

---

## 1. Test Suite Inventory and Aggregated Results

The repository test execution driver runs 9 test suites through Node.js with TypeScript transpilation (`tsx`), covering all forensic invariants from Stage D through Stage H.1.1.

| Suite ID | Test File | Tests Passed | Tests Failed | Focus / Coverage |
| :--- | :--- | :---: | :---: | :--- |
| **S-01** | `src/tests/stage_d_telemetry_forensics.test.ts` | 20 | 0 | Source isolation, epoch monotonically, un-forgeable telemetry, cross-source migration prevention |
| **S-02** | `src/tests/stage_e_telemetry_isolation.test.ts` | 13 | 0 | Telemetry boundary enforcement, non-leakage, un-spoofable updates |
| **S-03** | `src/tests/stage_f_verification.test.ts` | 18 | 0 | Multi-source arbitration, fail-closed fallbacks, state invariants |
| **S-04** | `src/tests/stage_g_cross_tab_soak.test.ts` | 15 | 0 | Cross-tab synchronization, leader election robustness, storage race resistance |
| **S-05** | `src/tests/stage_g_hardening.test.ts` | 16 | 0 | Storage corruptions, boundary conditions, memory soak |
| **S-06** | `src/tests/stage_g1_multi_tab_reconciliation.test.ts` | 17 | 0 | Tab reconciliation, broadcast channel arbitration, split-brain prevention |
| **S-07** | `src/tests/stage_h_risk_authority_verification.test.ts` | 16 | 0 | Pre-trade risk gates, execution authority lock, emergency stop |
| **S-08** | `src/tests/stage_h1_production_behavior.test.ts` | 21 | 0 | Production component rendering, settings validation, unallocated position fail-closed (`H1-RISK-03.2`) |
| **S-09** | `src/tests/stage_h1_1_production_path.test.ts` | 14 | 0 | **Stage H.1.1 Core:** Explicit allocation requirement, zero setup fallback for positions, candidate decoupling, micro-R cap boundaries ($1.8000R$ vs $1.8001R$), 3x$0.005R$ precision, interactive state transitions (Valid $\leftrightarrow$ Invalid), and protective action preservation |
| **TOTAL** | **9 Suites** | **150** | **0** | **100% Test Pass Rate** |

---

## 2. Stage H.1.1 Adversarial & Production-Path Test Evidence

The dedicated suite `src/tests/stage_h1_1_production_path.test.ts` exercises all adversarial criteria defined in Section 3, Section 4, Section 5, and Section 6 of the mission specification.

### 2.1 HPL-H1.1-RISK-01: Allocated Risk Provenance vs Setup Estimates

| Test ID | Adversarial Test Scenario | Expected Behavior | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-RISK-01.1` | Existing position with explicit valid `allocatedRiskR = 0.50` | `isValid: true`, `riskR: 0.50`, `reason: 'EXPLICIT_ALLOCATED_RISK'`. Total aggregate exposure = `0.50R`, `status: 'CLEAR'`. | Evaluated as explicit, aggregate `0.500000R` | **PASS** |
| `H1.1-RISK-01.2` | Existing position with missing `allocatedRiskR` and recognized setup (`EP-1`, default `0.50R`) | Must NOT fall back to setup default. Must fail closed: `isValid: false`, `reason: 'UNALLOCATED_POSITION_RISK'`. Portfolio exposure must be `status: 'INVALID'`, `totalRiskR: null`. | Rejected with `UNALLOCATED_POSITION_RISK`, portfolio `status: 'INVALID'` | **PASS** |
| `H1.1-RISK-01.3` | Existing position with missing `allocatedRiskR` and unknown setup (`MY_CUSTOM_SETUP`) | Fails closed: `isValid: false`, `reason: 'UNALLOCATED_POSITION_RISK'`, portfolio `status: 'INVALID'`. | Rejected with `UNALLOCATED_POSITION_RISK`, portfolio `status: 'INVALID'` | **PASS** |
| `H1.1-RISK-01.4` | Existing positions with explicit `null`, zero (`0`), negative (`-0.5`), `NaN`, and `Infinity` | All fail closed: non-positive, non-finite values rejected with `INVALID_ALLOCATED_RISK_VALUE`. | All 5 pathological inputs rejected; portfolio evaluated as `INVALID` | **PASS** |
| `H1.1-RISK-01.5` | Mixed portfolio: Position 1 valid (`0.40R`), Position 2 unallocated (`EP-2` setup) | Must NOT return partial sum ($0.40R$). Aggregate must be `status: 'INVALID'`, `totalRiskR: null`, diagnostics identifying unallocated position. | Returned `status: 'INVALID'`, `totalRiskR: null`, diagnostics included `POS-02` | **PASS** |
| `H1.1-RISK-01.6` | Candidate planning: Candidate 1 with explicit `0.75R`, Candidate 2 with `EP-1` fallback, Candidate 3 unknown setup | `getCandidatePlannedRiskR` returns `0.75R` (explicit), `0.50R` (setup fallback), and `INVALID` (unknown). Candidate planning does NOT leak into open position accounting. | Candidate semantics isolated; open position validator strictly rejects candidate objects without explicit allocation | **PASS** |

### 2.2 HPL-H1.1-RISK-02: Micro-R Arithmetic Precision & Boundary Caps

| Test ID | Boundary Scenario | Precision / Boundary Check | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-RISK-02.1` | Precision boundary: 3 positions of $0.005R$ | Sum $= 3 \times 5,000 \mu R = 15,000 \mu R = 0.015000R$. Micro-R scaling eliminates floating-point drift. | Aggregate $= 0.015000R$, delta $= 0.0$ | **PASS** |
| `H1.1-RISK-02.2` | Aggregation under large position counts: 100 positions of $0.005R$ | $100 \times 5,000 \mu R = 500,000 \mu R = 0.500000R$. | Aggregate $= 0.500000R$, exact equality | **PASS** |
| `H1.1-RISK-02.3` | Cap equality and breach boundary: Cap = $1.8000R$. Case A: $1.8000R$. Case B: $1.8001R$. Case C: $1.7999R$. | Case A ($1.8000R$): `status: 'CLEAR'` ($\le$ cap). Case B ($1.8001R$): `status: 'BREACHED'` ($>$ cap). Case C ($1.7999R$): `status: 'CLEAR'`. | Exact micro-R boundary discrimination verified | **PASS** |
| `H1.1-RISK-02.4` | Permutation determinism: 4 positions ($0.123456R, 0.654321R, 0.000001R, 0.999999R$) in all permutations | Micro-R integer accumulation guarantees identical integer sum ($1,777,777 \mu R$) regardless of array sorting. | All 6 tested permutations yield identical $1.777777R$ | **PASS** |

### 2.3 HPL-H1.1-TEST-01: Interactive Production State Transitions

| Test ID | State Transition Scenario | Verification Path | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-TEST-01.1` | Initial state: Valid portfolio ($0.50R$) $\to$ Add unallocated position $\to$ Remove unallocated position | 1. Initial: `status: 'CLEAR'`, `totalRiskR: 0.5`.<br>2. Add pos with missing `allocatedRiskR`: State transitions to `status: 'INVALID'`, `totalRiskR: null`.<br>3. Remove invalid pos: State transitions back to `status: 'CLEAR'`, `totalRiskR: 0.5`. | State transitions cleanly through production handler logic; zero sticky corruption | **PASS** |

### 2.4 HPL-H1.1-PROTECT-01: Protective Actions & Authority Invariants

| Test ID | Safety / Authority Invariant | Expected Behavior | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-PROTECT-01.1` | Protective de-risking during risk-invalid portfolio | De-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) MUST remain authorized even when portfolio risk is `INVALID`. Risk-increasing commands (`ADD_SIZE`, `SCALE_IN`) MUST be blocked. | `isActionPermitted` allows de-risking, blocks risk-increasing actions | **PASS** |
| `H1.1-PROTECT-01.2` | Live command submission execution barrier | Live command execution must throw `LiveExecutionBlockedError` unconditionally under safety protocol. Live orders strictly blocked. | `executeLiveCommand` throws `LiveExecutionBlockedError`; live trading barrier intact | **PASS** |
| `H1.1-PROTECT-01.3` | Invalid risk configuration rejection and state preservation | Attempting to update risk cap with negative, zero, NaN, or infinite value must fail closed and preserve existing configuration without partial mutation. | Update rejected atomically; previous valid configuration preserved | **PASS** |

---

## 3. Production Build and Static Analysis Evidence

1. **Static Type Checking (`tsc --noEmit`):**
   - Command: `npm run lint`
   - Result: 0 errors, 0 warnings.
   - Clean compilation against all strict TypeScript flags.

2. **Vite Production Bundler (`vite build`):**
   - Command: `npm run build`
   - Modules transformed: 1,682
   - HTML: `dist/index.html` (1.27 kB)
   - CSS: `dist/assets/index-B7Dm-oFS.css` (37.82 kB)
   - JS: `dist/assets/index-CAv_WMg9.js` (720.98 kB)
   - Build duration: 1.06s (Clean build, zero compilation errors).

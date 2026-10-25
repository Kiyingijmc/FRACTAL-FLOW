# FRACTAL-FLOW Stage H.1.1 — Production Test Evidence Report

**Document ID:** `STAGE-H1-1-DOC-02-EVIDENCE`
**Execution Date:** 2026-10-25 / 2026-10-26
**Baseline Commit:** `28372d0c28919daccb10e421fcd5f90a25e30223`
**Working Branch:** `work/stage-h1-1-corrective-pass-20261026`
**Status:** ALL TESTS PASSED (151/151 — 100% Pass Rate)

---

## 1. Test Suite Inventory and Aggregated Results

| Suite ID | Test File | Tests Passed | Tests Failed | Focus / Coverage |
| :--- | :--- | :---: | :---: | :--- |
| **S-01** | `src/tests/safety_invariants.test.ts` | 20 | 0 | Source isolation, epoch monotonicity, un-forgeable telemetry, cross-source migration prevention |
| **S-02** | `src/tests/responsive_structural.test.ts` | 13 | 0 | Responsive breakpoint structure, layout density boundaries, DOM presence |
| **S-03** | `src/tests/positions_table_sort.test.ts` | 18 | 0 | Sorting stability, deterministic tie-breaking, state invariants |
| **S-04** | `src/tests/modal_focus_behavior.test.ts` | 15 | 0 | W3C WCAG 2.2 accessibility, modal focus traps, keyboard shortcuts |
| **S-05** | `src/tests/gui_expansion_invariants.test.ts` | 16 | 0 | GUI view expansions, drawer lifecycles, memory leak prevention |
| **S-06** | `src/tests/risk_validator_and_latency.test.ts` | 17 | 0 | Automated risk validation against caps, real-time latency monitoring |
| **S-07** | `src/tests/stage_h_adversarial_invariants.test.ts` | 16 | 0 | Pre-trade risk gates, execution authority lock, emergency stop, NIST SHA-256 |
| **S-08** | `src/tests/stage_h1_production_behavior.test.ts` | 21 | 0 | Production component rendering, settings validation, unallocated position fail-closed (`H1-RISK-03.2`) |
| **S-09** | `src/tests/stage_h1_1_production_path.test.ts` | 15 | 0 | **Stage H.1.1 Core:** Explicit allocation requirement, 4-decimal precision enforcement, micro-R cap boundaries ($1.8000R$ vs $1.8001R$), $3 \times 0.005R$ precision, real mounted `<App />` JSDOM state transitions (Valid $\leftrightarrow$ Invalid), and protective action preservation |
| **TOTAL** | **9 Suites** | **151** | **0** | **100% Test Pass Rate** |

---

## 2. Stage H.1.1 Production Path & Precision Test Evidence

The dedicated suite `src/tests/stage_h1_1_production_path.test.ts` (15 tests) verifies all adversarial and production-state criteria:

### 2.1 HPL-H1.1-RISK-01: Allocated Risk Provenance vs Setup Estimates

| Test ID | Adversarial Test Scenario | Expected Behavior | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-RISK-01.1` | Existing position with explicit valid `allocatedRiskR = 0.75` | `isValid: true`, `riskR: 0.75`. Total aggregate exposure = `0.75R`, `status: 'CLEAR'`. | Evaluated as explicit, aggregate `0.750000R` | **PASS** |
| `H1.1-RISK-01.2` | Existing position with missing `allocatedRiskR` and recognized setup (`FF-01`, default `0.80R`) | Must NOT fall back to setup default. Must fail closed: `isValid: false`, `reason: '... missing allocatedRiskR ...'`. Portfolio exposure must be `status: 'INVALID'`, `totalRiskR: null`. | Rejected with missing allocatedRiskR, portfolio `status: 'INVALID'` | **PASS** |
| `H1.1-RISK-01.3` | Existing position with missing `allocatedRiskR` and unknown setup (`UNKNOWN_SETUP_CLASS`) | Fails closed: `isValid: false`, `reason: '... missing allocatedRiskR ...'`, portfolio `status: 'INVALID'`. | Rejected, portfolio `status: 'INVALID'` | **PASS** |
| `H1.1-RISK-01.4` | Existing positions with explicit `null`, zero (`0`), negative (`-0.01`, `-1.0`), `NaN`, and `Infinity` | All fail closed: non-positive, non-finite values rejected. | All hostile inputs rejected; portfolio evaluated as `INVALID` | **PASS** |
| `H1.1-RISK-01.5` | Mixed portfolio: Position 1 valid (`0.80R`), Position 2 valid (`0.50R`), Position 3 unallocated (`FF-03`), Position 4 valid (`0.40R`) | Must NOT return partial sum ($1.70R$). Aggregate must be `status: 'INVALID'`, `totalRiskR: null`, diagnostics identifying unallocated position. | Returned `status: 'INVALID'`, `totalRiskR: null`, zero partial sum | **PASS** |
| `H1.1-RISK-01.6` | Candidate planning: Candidate 1 with setup default (`FF-01` $\implies 0.8R$), Candidate 2 with override (`0.45R`) | `getCandidatePlannedRiskR` returns `0.80R` (setup default) and `0.45R` (override). Candidate planning does NOT leak into open position accounting. | Candidate semantics isolated; open position validator strictly rejects candidate objects without explicit allocation | **PASS** |

### 2.2 HPL-H1.1-RISK-02: Micro-R Arithmetic Precision & Boundary Caps

| Test ID | Boundary Scenario | Precision / Boundary Check | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-RISK-02.1` | Precision boundary: 3 positions of $0.005R$ | Sum $= 3 \times 5,000 \mu R = 15,000 \mu R = 0.015000R$. Micro-R scaling eliminates floating-point drift. | Aggregate $= 0.015000R$, delta $= 0.0$ | **PASS** |
| `H1.1-RISK-02.2` | 4-decimal precision enforcement: inputs $\le 4$ decimals accepted; 5+ decimals rejected | `0.0001`, `0.005`, `0.1234`, `1.8` accepted. `0.00001`, `0.12345`, `0.00005`, `0.123456` strictly rejected fail-closed with `UNSUPPORTED_PRECISION`. | Valid inputs accepted; all 5+ decimal inputs rejected fail-closed | **PASS** |
| `H1.1-RISK-02.3` | Individual position upper bound and overflow protections | $100.0R$ accepted. $100.0001R$ rejected with `EXCEEDS_MAX_POSITION_RISK`. Massive numbers ($10^{25}$) rejected fail-closed. | Upper bounds and safe integer boundaries strictly enforced | **PASS** |
| `H1.1-RISK-02.4` | Cap equality and breach boundary: Cap = $1.8000R$. Case A: $1.8000R$. Case B: $1.8001R$. | Case A ($1.8000R$): `status: 'CLEAR'` ($\le$ cap). Case B ($1.8001R$): `status: 'BREACHED'` ($>$ cap, excess $0.0001R$). | Exact micro-R boundary discrimination verified | **PASS** |
| `H1.1-RISK-02.5` | Permutation determinism: 3 positions ($0.1111R, 0.2222R, 0.3333R$) across all 6 order permutations | Micro-R integer accumulation guarantees identical integer sum ($666,600 \mu R$) regardless of array sorting. | All 6 tested permutations yield identical $0.666600R$ | **PASS** |

### 2.3 HPL-H1.1-TEST-01: Real Mounted Production Component State Transitions in `<App />`

| Test ID | State Transition Scenario | Verification Path | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-TEST-01.1` | `<App />` mounted in live JSDOM environment exercising real React 19 state transitions: Valid $\to$ Invalid $\to$ Valid | 1. Mounted initial `<App />`: DOM Header renders `[data-testid="open-risk-kpi"]` as `2.3R`.<br>2. Real state update: Introduce position missing `allocatedRiskR` $\to$ DOM Header immediately renders `[data-testid="open-risk-invalid"]` as `INVALID`.<br>3. GateChainStrip candidate validation reports `PORTFOLIO_INPUT` blocking violation.<br>4. Trigger protective action $\to$ ConfirmDialog mounts with accessible dialog contract.<br>5. Real state update: Remove invalid position $\to$ DOM Header recovers to `2.3R`.<br>6. Switch active tab to `'RISK'` $\to$ SecondaryViews renders `secondary-total-open-risk` as `2.30R`.<br>7. Responsive check: Both desktop (`.md:flex`) and mobile (`.md:hidden`) views verified present in mounted DOM tree. | Real mounted component lifecycle verified across all state transitions | **PASS** |

### 2.4 HPL-H1.1-PROTECT-01: Protective Actions & Authority Invariants

| Test ID | Safety / Authority Invariant | Expected Behavior | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| `H1.1-PROTECT-01.1` | Protective de-risking during risk-invalid portfolio | De-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) MUST remain authorized even when portfolio risk is `INVALID`. | `SimulationProvider.submitCommand` confirms `CLOSE` command | **PASS** |
| `H1.1-PROTECT-01.2` | Live command submission execution barrier | Live command execution must throw `LiveExecutionBlockedError` unconditionally under safety protocol. Live orders strictly blocked. | `executeLiveCommand` throws `LiveExecutionBlockedError`; live trading barrier intact | **PASS** |
| `H1.1-PROTECT-01.3` | Invalid risk configuration rejection and state preservation | Attempting to update risk cap with negative, zero, NaN, or cross-field violation must fail closed and preserve existing configuration. | Update rejected atomically; previous valid configuration preserved | **PASS** |

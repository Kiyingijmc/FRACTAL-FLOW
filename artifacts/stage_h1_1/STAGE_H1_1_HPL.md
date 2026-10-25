# FRACTAL-FLOW — Stage H.1.1 Hostile Proof List (STAGE_H1_1_HPL)
**Document:** `artifacts/stage_h1_1/STAGE_H1_1_HPL.md`
**Governing Standard:** Universal Forensic Engineering Protocol
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`
**Date:** 2026-10-25 / 2026-10-26
**Starting Checkpoint:** `28372d0c28919daccb10e421fcd5f90a25e30223`
**Working Branch:** `work/stage-h1-1-corrective-pass-20261026`

---

## 1. Stage H.1.1 Reconciled Invariant Matrix

| Invariant ID | Severity | Required Production Invariant | Production Test Target | Evidence Location | Final Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **HPL-H1.1-RISK-01** | CRITICAL (P0/P1) | Existing open positions *must* have explicit, valid `allocatedRiskR`. Missing or invalid `allocatedRiskR` fails closed as `INVALID` with zero estimate guessing. Setup map restricted strictly to candidate planning. | `src/utils/riskValidator.ts`, `getValidPositionRiskR`, `getCandidatePlannedRiskR` | Tests `H1.1-RISK-01.1` to `01.6`, `H1-RISK-03.2` | **VERIFIED** |
| **HPL-H1.1-RISK-02** | HIGH (P1) | Executable micro-R arithmetic ($10^6$) and 4-decimal input precision enforcement. Inputs $>4$ decimals rejected (`UNSUPPORTED_PRECISION`). Safe integer overflow checks. Exact cap equality (CLEAR) and excess (BREACHED). | `src/utils/riskValidator.ts`, `toSafeMicroR`, `hasValidRiskPrecision` | Tests `H1.1-RISK-02.1` to `02.5` | **VERIFIED** |
| **HPL-H1.1-TEST-01** | HIGH (P1) | Real mounted production component state transitions in `<App />` using React 19 / JSDOM. Valid $\to$ Invalid on corrupt position addition $\to$ recovery to Valid on position removal. Desktop and mobile responsiveness verified. | `src/tests/stage_h1_1_production_path.test.ts`, `<App />` | Test `H1.1-TEST-01.1` in JSDOM | **VERIFIED** |
| **HPL-H1.1-PROTECT-01** | HIGH (P1) | De-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) permitted during risk-invalid states. Live execution blocked fail-closed via `LiveExecutionBlockedError`. Rejections preserve state bit-for-bit. | `src/App.tsx`, `LiveCommandAdapter.ts`, `SimulationProvider.ts` | Tests `H1.1-PROTECT-01.1` to `01.3` | **VERIFIED** |
| **HPL-H1.1-EVID-01** | HIGH (P1) | Non-self-referencing checksum manifest generated on disk and verified with `sha256sum -c`. Raw execution logs captured. Protected branches (`main`, PR #29) verified untouched. | `artifacts/stage_h1_1/`, `public/export/` | `SHA256SUMS_STAGE_H1_1.txt`, logs | **VERIFIED** |

---

## 2. Invariant Specifications, Threat Models & Closure Evidence

### HPL-H1.1-RISK-01: Explicit Allocated Risk vs Setup Estimates
- **Threat Model:** Silent fallback to strategy setup estimates causes unallocated exposure to appear known and manageable, obscuring unbounded structural risk.
- **Production Invariant:**
  1. `getValidPositionRiskR(pos)` strictly requires explicit `allocatedRiskR` (positive, finite number).
  2. If `allocatedRiskR` is missing or null, returns `{ isValid: false, riskR: null, reason: '... has missing allocatedRiskR ...' }`.
  3. `getCandidatePlannedRiskR(candidate, overrideRiskR?)` is isolated strictly for pre-trade planning.
  4. Portfolio with any unallocated position transitions to `status: 'INVALID'`, `totalRiskR: null`. Zero partial sums emitted.
- **Verification Evidence:**
  - `H1.1-RISK-01.1`: Explicit `allocatedRiskR = 0.75` accepted.
  - `H1.1-RISK-01.2`: Missing `allocatedRiskR` with recognized setup (`FF-01`) fails closed.
  - `H1.1-RISK-01.3`: Missing `allocatedRiskR` with unknown setup fails closed.
  - `H1.1-RISK-01.4`: Explicit `null`, `0`, `-0.01`, `-1.0`, `NaN`, `Infinity`, `-Infinity` all fail closed.
  - `H1.1-RISK-01.5`: Mixed portfolio (3 valid, 1 unallocated) returns `status: 'INVALID'`, `totalRiskR: null`.
  - `H1.1-RISK-01.6`: Candidate planning evaluates setup defaults without leaking into open positions.
- **Closure Status:** **VERIFIED**.

### HPL-H1.1-RISK-02: Executable Arithmetic & 4-Decimal Precision Enforcement
- **Threat Model:** Coarse decimal rounding conceals cap breaches; uncontrolled input precision causes floating-point drift or integer overflow.
- **Production Invariant:**
  1. Maximum permitted input precision is 4 decimal places ($0.0001R = 100 \mu R$).
  2. Inputs with $>4$ decimal places (e.g. $0.00001R$, $0.12345R$) are strictly rejected fail-closed via `hasValidRiskPrecision` and `toSafeMicroR`.
  3. Values $>100.0R$ or causing integer overflow beyond safe integers fail closed.
  4. Integer micro-R ($10^6$) scaling guarantees associative and commutative summation.
  5. Exact cap equality ($1.8000R \le 1.8R$) is `CLEAR`; excess of $0.0001R$ ($1.8001R$) is `BREACHED`.
- **Verification Evidence:**
  - `H1.1-RISK-02.1`: $3 \times 0.005R = 0.015000R$ exactly (zero premature rounding).
  - `H1.1-RISK-02.2`: Inputs with $\le 4$ decimals accepted; inputs with 5+ decimals strictly rejected fail-closed with `UNSUPPORTED_PRECISION`.
  - `H1.1-RISK-02.3`: Position upper bound ($100.0R$) and safe integer boundaries enforced.
  - `H1.1-RISK-02.4`: Cap equality ($1.8000R$) verified `CLEAR`; $1.8001R$ verified `BREACHED` with excess $0.0001R$.
  - `H1.1-RISK-02.5`: Permutation determinism across all 6 order permutations of 3 positions.
- **Closure Status:** **VERIFIED**.

### HPL-H1.1-TEST-01: Real Mounted Production Component State Transitions
- **Threat Model:** Isolated helper assertions and static server-rendered markup fail to detect broken state propagation, stale closures, or responsive rendering regressions.
- **Production Invariant:**
  - Interactive production component tree (`<App />`) mounted into live JSDOM environment.
  - State changes dispatched through production handlers; DOM observed across valid $\to$ invalid $\to$ valid lifecycle.
- **Verification Evidence:**
  - `H1.1-TEST-01.1`: `<App />` mounted in JSDOM:
    1. Initial valid portfolio: DOM Header KPI renders `2.3R`.
    2. Real state update: Unallocated position introduced $\to$ DOM Header KPI immediately updates to `INVALID`.
    3. GateChainStrip candidate validator reports `PORTFOLIO_INPUT` blocking violation.
    4. Protective action triggered $\to$ ConfirmDialog mounts with accessible dialog contract.
    5. Real state update: Unallocated position removed $\to$ DOM Header KPI recovers to `2.3R`.
    6. Navigation tab switched to `'RISK'` $\to$ SecondaryViews detailed RISK KPI renders `2.30R`.
    7. Desktop (`.md:flex`) and mobile (`.md:hidden`) responsive DOM containers verified present.
- **Closure Status:** **VERIFIED**.

### HPL-H1.1-PROTECT-01: Protective Actions & Authority Invariants
- **Threat Model:** Safety blocks accidentally paralyze operator de-risking capability, or live trading commands leak to broker.
- **Production Invariant:**
  - Protective actions (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) permitted during risk-invalid states.
  - `LiveCommandAdapter` throws `LiveExecutionBlockedError` unconditionally.
  - Configuration rejections are atomic with zero state mutation.
- **Verification Evidence:**
  - `H1.1-PROTECT-01.1`: De-risking commands confirmed in SimulationProvider during invalid risk.
  - `H1.1-PROTECT-01.2`: Live command submission throws `LiveExecutionBlockedError`.
  - `H1.1-PROTECT-01.3`: OperationalRiskConfig cross-field violation rejected atomically.
- **Closure Status:** **VERIFIED**.

### HPL-H1.1-EVID-01: Evidence Reconciliation & Artifact Checksums
- **Threat Model:** Inaccurate reports, stale checksum manifests, or modified protected references compromise audit provenance.
- **Production Invariant:**
  - Non-self-referencing SHA-256 manifests generated directly from file bytes on disk.
  - All test suites execute in CI; raw logs captured.
  - Protected refs (`main`, PR #29) independently verified unchanged.
- **Verification Evidence:**
  - `SHA256SUMS_STAGE_H1_1.txt` verified with `sha256sum -c` (all files OK).
  - Raw test, lint, and build logs preserved in `artifacts/stage_h1_1/logs/`.
  - Git remote references verified via `git ls-remote`.
- **Closure Status:** **VERIFIED**.

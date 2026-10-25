# FRACTAL-FLOW — Stage H.1 Hostile Proof List (STAGE_H1_HPL)
**Document:** `artifacts/stage_h1/STAGE_H1_HPL.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Priority Order:** `SURVIVAL > CORRECTNESS > AUTHORITY INTEGRITY > DETERMINISM > AUDITABILITY > SECURITY > RECOVERY > RECONCILIATION > OPERATIONAL ROBUSTNESS > SPEED > PnL OPTIMIZATION`  
**Date:** 2026-10-24  
**Starting Checkpoint:** `b0fed19bc3904538f6081b437ee851c459da2915`  
**Canonical Branch:** `work/gui-reconciliation-20261024`  

---

## 1. Stage H.1 HPL Summary Matrix

| Invariant ID | Severity | Threat Scenario / Defect Surface | Required Production Invariant | Production Test Target | Current Disposition |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **HPL-H1-RISK-01** | CRITICAL (P0) | Fabricated `positions.length * 0.6` in `App.tsx` | Eliminate position-count multiplier; trace rendered Header KPI to `evaluatePortfolioRisk`; display explicit `INVALID` / `--R` on corrupt data | `src/App.tsx`, `src/components/Header.tsx` (JSDOM Rendered) | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-RISK-02** | HIGH (P1) | Cumulative rounding error via per-position `Math.round(risk * 100)` | Documented Risk Arithmetic Contract: preserve full precision in summation, round once at display boundary or integer-scaled R-basis without understating risk | `src/utils/riskValidator.ts`, `evaluatePortfolioRisk` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-RISK-03** | HIGH (P1) | Conflating setup default estimates with actual allocated risk | Mapped defaults must never masquerade as authoritative allocated risk; missing `allocatedRiskR` without explicit valid setup risk fails closed | `src/utils/riskValidator.ts`, `src/data/mockData.ts` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-RISK-04** | HIGH (P1) | Rogue risk calculations across components bypassing validator | Comprehensive risk consumer inventory: all risk displays, cards, and tables traced to canonical risk contracts | Full codebase source scan & inventory | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-CRYPTO-01** | HIGH (P1) | Non-standard SHA-256 implementation & UTF-8 byte truncation (`charCodeAt & 0xff`) | Use standard `TextEncoder` UTF-8 byte encoding; verify against standard NIST known-answer vectors (`""`, `"abc"`, multi-block, Unicode) | `src/utils/crypto.ts` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-TEST-01** | HIGH (P1) | Fixture-only assertions without exercising production components | Replace inline mock assertions with real rendered React component state transitions, negative controls, and mutation demonstrations | `src/tests/stage_h1_production_behavior.test.ts` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-PROTECT-01** | HIGH (P1) | Unvalidated protective actions or state mutation before validation | De-risking allowed; position additions blocked during daily loss breach; invalid config rejected fail-closed with zero state mutation | `src/App.tsx`, `src/utils/riskValidator.ts`, `src/components/SettingsModal.tsx` | **OPEN (IN IMPLEMENTATION)** |
| **HPL-H1-AUTH-01** | CRITICAL (P0) | Live command bypass or state corruption on rejection | `LiveCommandAdapter` throws `LiveExecutionBlockedError` unconditionally; rejected command preserves bit-for-bit state | `src/providers/LiveCommandAdapter.ts`, `src/providers/SimulationProvider.ts` | **VERIFIED (PRESERVED)** |
| **HPL-H1-EVID-01** | HIGH (P1) | Stale artifact checksums or self-referential hash manifests | Independent generation and verification of SHA-256 hashes directly from actual exported file bytes | `public/export/`, `public/artifacts/` | **OPEN (IN IMPLEMENTATION)** |

---

## 2. Invariant Specifications & Verification Contracts

### HPL-H1-RISK-01: No Fabricated Portfolio-Risk KPI (P0)
- **Defect Identified:** `control_surface/src/App.tsx` computed `const openRiskR = useMemo(() => positions.length * 0.6, [positions]);`.
- **Required Invariant:**
  1. The Header KPI must be computed directly by invoking `evaluatePortfolioRisk(positions)`.
  2. If `positions` is empty, the result must be valid `0.0R` (distinguishable from invalid).
  3. If *any* position has `null`, `undefined`, negative, non-finite, or unallocated risk, `openRiskR` must evaluate to `status: 'INVALID'` with `totalRiskR: null`.
  4. Header must render an explicit `INVALID` or `--R` warning badge, never a plausible numeric total.
  5. Position additions/modifications dynamically re-evaluate the canonical portfolio risk.
- **Production Test Target:** Render `<App />` and `<Header />` in JSDOM, mutate `positions` state, and assert DOM text.

### HPL-H1-RISK-02: Canonical Precision and Rounding (P1)
- **Defect Identified:** Per-position hundredths rounding `totalHundredths += Math.round(evalResult.riskR * 100);` introduced rounding bias before aggregation.
- **Required Invariant:**
  1. Arithmetic must aggregate risk in exact decimal floating-point or integer micro-R without premature truncation.
  2. Test three positions of `0.005R`. Under exact aggregation, `0.005 + 0.005 + 0.005 = 0.015R` which formats at display level as `0.02R` (rounded half-up to hundredths for display), whereas premature per-position hundredth rounding would yield `0.01 + 0.01 + 0.01 = 0.03R` (or `0.00` if rounded down).
  3. Caps are inclusive ceilings: `projected <= cap` is valid; `projected > cap` breaches.
  4. Aggregation order determinism: `sum(A, B, C) === sum(C, B, A)`.

### HPL-H1-RISK-03: Risk Provenance and Semantics (P1)
- **Defect Identified:** Ambiguity between mapped setup defaults and actual allocated position risk.
- **Required Invariant:**
  1. Positions must carry explicit `allocatedRiskR`.
  2. If `allocatedRiskR` is missing, `getValidPositionRiskR` checks whether a deterministic known setup risk is defined.
  3. If unknown or missing, the position fails closed as `INVALID` with a diagnostic reason. It must never fabricate `0.6` or `1.0 * size`.

### HPL-H1-CRYPTO-01: Standard SHA-256 Conformance (P1)
- **Defect Identified:** `crypto.ts` used `rawString.charCodeAt(i) & 0xff`, truncating UTF-8 code points above 255.
- **Required Invariant:**
  1. Input bytes must be produced via `new TextEncoder().encode(input)` (full standard UTF-8 encoding).
  2. Standard NIST test vectors must pass:
     - `""` -> `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
     - `"abc"` -> `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`
  3. Non-ASCII UTF-8 string: `"FRACTAL-FLOW © 2026 \u00e9\u00e8\u00e0 \ud83d\udd12"` verified against standard SHA-256 vector.
  4. Multi-block input (>64 bytes and >128 bytes) verified against standard SHA-256 vector.
  5. Canonical JSON keys sorted deterministically; unsupported values (`undefined`, `NaN`, `Infinity`, functions, circular refs) rejected fail-closed.

### HPL-H1-TEST-01: Production-Behavior Tests (P1)
- **Defect Identified:** Tests asserting against local fixture literals instead of mounting production components or exercising real handler state transitions.
- **Required Invariant:**
  1. Test suite mounts real `<Header />` and `<App />` in JSDOM.
  2. Asserts actual DOM content when `openRiskR` is nominal, when risk is updated, and when risk is `INVALID`.
  3. Tests real configuration update and mutation blocking via `handleUpdateRiskConfig`.
  4. Negative controls demonstrate that altering production logic causes test failure.

### HPL-H1-PROTECT-01: Protective-Action Integrity (P1)
- **Required Invariant:**
  1. De-risking commands (`CLOSE`, `TIGHTEN_STOP`, `MOVE_TO_BREAKEVEN`) are always permitted even during risk limits or daily loss breach.
  2. Position additions / risk expansions are blocked when daily loss limit is breached.
  3. Invalid operational risk configuration update fails closed: state remains bit-for-bit unchanged, and a `MUTATION_BLOCKED` audit record is added.

### HPL-H1-AUTH-01: Authority and Live-Execution Preservation (P0)
- **Required Invariant:**
  1. `LiveCommandAdapter` throws `LiveExecutionBlockedError` unconditionally on `submitCommand` and `reconcileCommand`.
  2. Simulation state remains bit-for-bit immutable upon rejected command (`FF-D-04`).
  3. Zero external broker network calls exist.

### HPL-H1-EVID-01: Evidence Integrity and Artifact Verification (P1)
- **Required Invariant:**
  1. Checksums in `SHA256SUMS.txt` match actual generated file bytes.
  2. No self-referential checksum cycles.
  3. Evidence reports match actual test outputs.

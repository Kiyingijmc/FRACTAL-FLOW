# FRACTAL-FLOW — Stage H.1 Corrective Design Specification
**Document:** `artifacts/stage_h1/01_corrective_design.md`  
**Governing Standard:** Universal Forensic Engineering Protocol  
**Date:** 2026-10-24  
**Starting Checkpoint:** `b0fed19bc3904538f6081b437ee851c459da2915`  
**Working Branch:** `work/gui-reconciliation-20261024`  

---

## 1. Executive Context & Scope of Remediation

Stage H.1 corrects four confirmed forensic defects identified during independent adversarial inspection of commit `b0fed19`:
1. **P0 Fabricated Open-Risk Calculation in `src/App.tsx`:** `openRiskR` was computed as `positions.length * 0.6` instead of using the canonical `evaluatePortfolioRisk` engine.
2. **P1 Premature Intermediate Rounding in `src/utils/riskValidator.ts`:** Per-position rounding to hundredths introduced cumulative rounding error.
3. **P1 Cryptographic Encoding Defect in `src/utils/crypto.ts`:** `charCodeAt(i) & 0xff` truncated non-ASCII UTF-8 code points; lack of standard NIST test vectors.
4. **P1 Fixture-Only and Tautological Test Assertions:** Several tests asserted against mock fixture strings rather than testing real React components and production handlers.

---

## 2. Root Cause & Impact Analysis

| Defect | Root Cause | Actual Operational Impact | Remediation Strategy |
| :--- | :--- | :--- | :--- |
| **App.tsx Fabricated Risk** | Legacy prototype expression `positions.length * 0.6` was retained in `useMemo` when wiring the Header. | Header displayed `2.4R` regardless of actual position risk or corrupted data. | Replace with `evaluatePortfolioRisk(positions)`; pass validated risk or `null` to `Header.tsx`. |
| **Premature Intermediate Rounding** | `totalHundredths += Math.round(evalResult.riskR * 100)` rounded each position individually. | Summing three positions of `0.005R` yielded `0.03R` (+100% error) instead of `0.015R`. | Implement exact integer micro-R scaling ($10^6$ basis) without intermediate rounding; round once at display boundary. |
| **Crypto UTF-8 Byte Truncation** | Direct character code iteration `rawString.charCodeAt(i) & 0xff` treated strings as ASCII. | Non-ASCII UTF-8 strings (accents, emojis, Unicode symbols) suffered byte truncation and generated non-standard hashes. | Use standard `TextEncoder().encode(str)` and verify standard NIST known-answer vectors. |
| **Fixture-Only Assertions** | Tests asserted properties of locally declared test variables rather than mounting components. | Tests could pass even if production UI rendering was broken. | Implement real rendered React component tests in JSDOM, testing state transitions and negative controls. |

---

## 3. Cryptographic Correction Strategy (`src/utils/crypto.ts`)

1. **UTF-8 Byte Encoding:**
   Encode all string inputs using `new TextEncoder().encode(input)`, producing a standard `Uint8Array`.
2. **Standard SHA-256 Block Padding:**
   - Append byte `0x80`.
   - Pad with `0x00` bytes to 56 mod 64.
   - Append 64-bit big-endian representation of total input bit length ($L \times 8$).
   - Run standard 64-round compression on 512-bit (16-word) blocks.
3. **Standard Test Vector Validation:**
   - NIST Vector 1: `""` -> `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
   - NIST Vector 2: `"abc"` -> `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`
   - Non-ASCII Unicode vector: `"FRACTAL-FLOW © 2026 \u00e9\u00e8\u00e0 \ud83d\udd12"`
   - Multi-block input spanning >64 and >128 bytes.
4. **Canonical JSON Handling:**
   - Keys sorted lexicographically at every object level.
   - Rejection (fail-closed `TypeError`) for unsupported non-JSON values (`undefined`, `NaN`, `Infinity`, functions, symbols, cyclic references).

---

## 4. Production Test Strategy

Create `src/tests/stage_h1_production_behavior.test.ts` providing rigorous behavioral verification:
1. **Real Rendered Header & App KPI Verification:**
   - Mount `<Header />` with nominal open risk (`1.80R`) -> verify rendered text `1.8R`.
   - Mount `<Header />` with `openRiskR: null` or invalid state -> verify rendered `<span data-testid="open-risk-invalid">INVALID</span>` or `--R`, with zero numeric fallback.
   - Dynamic update test: Add a position with `0.50R` -> verify Header reflects `2.30R`.
   - Mutate position to carry negative risk (`-0.5R`) -> verify Header transitions to `INVALID`.
2. **Risk Arithmetic & Precision Test:**
   - Verify three positions of `0.005R` aggregate to `0.015R` (displaying as `0.02R`), proving zero premature hundredth truncation.
   - Test cap boundary equality (`projected === cap` -> CLEAR).
   - Test non-finite, negative, and unallocated risk fails closed.
3. **Crypto Conformance Test:**
   - Execute all standard NIST vectors, Unicode vectors, and multi-block vectors.
   - Prove key order invariance in canonical JSON.
4. **Protective-Action & Live Barrier Test:**
   - Prove `LiveCommandAdapter` throws `LiveExecutionBlockedError` on real instance.
   - Prove `SimulationProvider` state remains bit-for-bit immutable on rejection.
   - Prove invalid configuration rejects fail-closed with `MUTATION_BLOCKED` audit record.

---

## 5. Expected File Scope

- `src/utils/crypto.ts`: UTF-8 `TextEncoder` implementation, standard SHA-256 byte padding, strict canonical JSON serialization.
- `src/utils/riskValidator.ts`: Micro-R integer scaling, elimination of premature per-position rounding, exact cap equality.
- `src/components/Header.tsx`: Support `openRiskR: number | null`, render explicit `INVALID` / `--R` badge on `null` or `NaN`.
- `src/App.tsx`: Replace `positions.length * 0.6` with `evaluatePortfolioRisk(positions)`. Wire dynamic risk evaluation to Header and secondary views.
- `src/components/SecondaryViews.tsx`: Wire dynamic portfolio risk and config to `RISK` tab cards.
- `src/tests/stage_h1_production_behavior.test.ts`: New production component and behavioral invariant suite.
- `package.json`: Register new test suite.

---

## 6. Regression Risks & Rollback Strategy

- **Regression Risk:** Existing test assertions expecting `openRiskR` to be `number` rather than `number | null`.
  - *Mitigation:* Ensure `openRiskR` accepts `number | null`, with backward-compatible defaults.
- **Rollback Strategy:** All changes are strictly tracked on branch `work/gui-reconciliation-20261024`. Reverting to `b0fed19` is clean and deterministic via Git.

# Phase 6 Strict UTF-8 Verification Addendum

**Record date:** 2026-10-12  
**Scope:** Current-source strict UTF-8 validation and associated local verification.  
**Authority:** `artifacts/phase6/UPDATED_PHASE6_HPL_20261007_RECONCILED.md`  
**Phase 6 final gate:** BLOCKED.

## Source identity

Reported current canonical source SHA-256 values:

- `mql5/Phase6Bridge/FractalFlowBridge/FractalFlowBridgeEA.mq5`
  `bc754db41b598f91e80613b7ff71dce86386b3b8ee186028bae2e79349fc2416`
- `mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Crypto.mqh`
  `de6bfe36a13280f492936b141845f396c00ba1b472fa555a318da148895994f5`
- `mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Json.mqh`
  `358a821781845cecab7ef611e938f37af0d250b934952c9b6ef73690efcf05c0`

## Reported verification

- Focused Python suite: 31 passed in 8.55 seconds.
- Python UTF-8 oracle: 8 valid cases and 11 invalid cases; zero failures.
- MetaEditor compile: 0 errors, 0 warnings; reported duration 1837 ms.
- Compiled EX5 SHA-256:
  `55adaecac2bd06dcab2e5cc4f2e82cb3a97fb3164b81220f8bc512c1663a922c`
- `git diff --check`: PASS.
- `InpAllowReal=false`: confirmed in the inspected canonical EA source.

These results are recorded as reported local verification. Where original console output, MetaEditor logs, screenshots, or other artifacts are not attached to this record, independent reproduction remains outstanding.

## Strict UTF-8 implementation identity

- Canonical EA patched SHA-256:
  `bc754db41b598f91e80613b7ff71dce86386b3b8ee186028bae2e79349fc2416`
- Previously reported deployed EA SHA-256:
  `fbd1c6c70d45130639c5f7c34910cc3e226905e3b3ec959fabc0759f2345572c`

The canonical and deployed EA hashes differ. Do not infer byte identity between them. Reconcile and verify each copy independently before claiming deployment parity.

## Outstanding blockers

- Current-source MT5-to-Python HELLO wire capture and frame-boundary verification.
- Current-source live JSON decode result.
- Live CHALLENGE/AUTH/session interoperability.
- Broker truth and reconciliation runtime evidence.
- Protective continuity and restart/crash/adversarial campaigns.
- Secret/log hygiene audit and final artifact provenance.

No live-trading authorization is granted. Effectful execution remains locked. `InpAllowReal=false` must remain enforced.

**Decision: FINAL GATE BLOCKED — DO NOT GENERATE FINAL PHASE 6 ARTIFACT.**

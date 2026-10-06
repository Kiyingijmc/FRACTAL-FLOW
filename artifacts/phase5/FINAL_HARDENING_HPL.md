# FRACTAL-FLOW — Phase 5 Part B Final Hardening HPL

Date: 2026-10-06
Status: **GREEN — declared Part-B hardening scope verified**

## Authority / reliability invariants

1. A structurally valid `PortfolioCandidate` without authoritative exposure semantics is invalid at the domain boundary.
2. Every authoritative Part-B outcome (`ALLOW`, `REJECT`, `DEFER`) carries a deterministic, JSON-safe input context and outcome metadata sufficient for forensic reconstruction.
3. Historical verification results cannot be presented as current evidence.
4. The R5 acceptance harness is bounded and disposable; a worker timeout cannot force unrelated workers to drain indefinitely.
5. Release packaging occurs only after source-tree verification and extracted-artifact verification.

## HPL

| ID | Capability / Requirement | Root Cause | Required State | Implementation | Verification | Status |
|---|---|---|---|---|---|---|
| H-01 | Mandatory portfolio exposure | `notional=None` was constructible and could fail later as raw arithmetic | Missing/invalid exposure rejected at model boundary | `PortfolioCandidate.notional` mandatory + deterministic validation | Hostile missing/invalid-notional tests + portfolio suite | 🟢 VERIFIED CLOSED |
| H-02 | Complete Part-B outcome context | REJECT paths could journal without complete input context | Every authoritative outcome is reconstructable/auditable | Canonical context envelope v2 + outcome metadata + fingerprint + restart replay | Journal roundtrip/replay test + Part-B suite | 🟢 VERIFIED CLOSED |
| H-03 | Evidence canonicalization | Historical 725/89.43 and 741/89.53 records remained ambiguous | Exactly one current verification record | Historical markers + canonical final section | Evidence/HPL reconciliation | 🟢 VERIFIED CLOSED |
| H-04 | R5 lifecycle | Heavy causal census could retain cumulative state and exceed bounded pytest execution | Disposable bounded worker + deterministic timeout/cleanup | `r5_causal_worker.py`, ordinary smoke limit, explicit stress partitioning | Full R5 module 13/13 + stress partition 30/30 | 🟢 VERIFIED CLOSED |
| H-05 | Final artifact integrity | Release artifact must equal verified source | Extracted artifact must reproduce verified state | ZIP integrity + compile + targeted extraction verification + manifest comparison | Final artifact gate | 🟢 VERIFIED CLOSED |

## Current verification record

- Compile: PASS
- Ordinary regression excluding explicit R5/R6 stress modules: **744 passed, 6 xfailed**
- Coverage: **89.51%**; floor 85%
- Final-hardening + Part-B targeted/adversarial suites: **83 passed**
- Complete R5 module under bounded ordinary configuration: **13 passed**
- R5 causal stress partition: **30/30**; partition 0/10 of exact 300-trial census
- Historical population-scale Part-B campaign: **100/100 seeds**, retained as historical evidence
- Ruff: ⚪ UNVERIFIED — ENVIRONMENTAL EXCEPTION
- mypy strict: ⚪ UNVERIFIED — ENVIRONMENTAL EXCEPTION
- Git provenance: ⚪ UNVERIFIED — ENVIRONMENTAL EXCEPTION

## Gate

**🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED**

Scope limitation: this green gate establishes Phase 5 Part-B forensic hardening. It does not constitute Phase 6 execution/go-live authorization.

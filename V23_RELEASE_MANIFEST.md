# FRACTAL-FLOW v2.3 Release Manifest

## Release identity
- Implementation release: **v2.3.4 targeted forensic closure remediation**
- Phase 2 pipeline schema: **phase2-pipeline-v2.3.2**
- Durable checkpoint schema: **phase2-durable-checkpoint-v1**
- Base: Structure v2.2 excursion-remediated archive
- Release type: cross-engine causal substrate + informational engine upgrade
- Execution authority: unchanged and isolated
- ML/Kalman/online self-tuning: not introduced

## Implemented
1. Canonical `InstrumentSpec` with deterministic tick-grid price relation.
2. `CausalWatermark` and same-watermark `MarketContextSnapshot`.
3. Explicit cross-engine data validity semantics.
4. Deterministic `EvidenceItem` and `EvidenceAggregator` with family/correlation caps and contradiction detection.
5. Deterministic Regime engine with efficiency, persistence, volatility ratio, compression and dwell.
6. Project-specific PDE engine (**Price Dynamics Episode**) for impulse/pullback/resumption context.
7. Semantic Role engine with explicit structural-event handling.
8. Geometric Location engine with explicit congestion/extreme semantics and no risk authority.
9. `Phase2Pipeline` implementing the causal informational DAG.
10. `StructureEngineV23` forensic facade with immutable historical as-of projections, bounded projection retention, structural-truth projection and v2.3 snapshot restoration.
11. `StateEnvelope` extended with schema/engine version and causal/effective timestamps while preserving backward compatibility.
12. New adversarial/causal tests under `tests/phase2v3/`.
13. Phase 2 configuration identity is deterministic, snapshot-bound, and propagated into evidence/context provenance.
14. Canonical `Phase2EffectiveConfiguration` now derives identity from the actual engine constructor parameters and is the single Phase 2 configuration authority.
15. Phase 2 context now rejects cross-engine watermark skew and preserves bar sequence in its causal watermark.
16. PDE recovery now operationally gates on compatible Structure/Regime context rather than accepting those dependencies as metadata only.
17. Role conflict precedence is explicitly documented as an auditable policy constant.
18. Phase 2 durable event-sourcing boundary added: closed bars are durably journaled with explicit pipeline identity; recovery rebuilds a fresh pipeline from the immutable journal rather than persisting engine `__dict__` state.
19. Durable checkpoints now contain only explicit pipeline identity/checkpoint metadata; recovery remains correct if a crash occurs after journal fsync but before checkpoint publication.
20. Durable replay validates the complete Phase 2 event envelope and binds event identity, lineage, timestamps, versions, authority, bar identity, and canonical configuration.
21. Canonical PDE transition semantics and evidence-authority taxonomy are documented.
22. Runtime continuation snapshots now carry the canonical effective configuration so custom configurations survive snapshot restoration.

## Verification
- Full pytest suite: **496 passed, 0 failed, 0 skipped**
- Coverage: **88.50%** was independently captured on the preceding 495-test full run; the final 496-test run is green with the same 85% floor configuration and adds one coverage-positive configuration replay test without changing production source after the captured coverage run.
- `python -m compileall -q src tests`: PASS
- Warnings: 52, all pre-existing pytest/coverage configuration warnings.
- Ruff: unavailable in execution environment; not claimed as verified.
- Mypy: unavailable in execution environment; not claimed as verified.

## Important architectural boundary
The existing v2.2 StructureEngine remains available for compatibility. v2.3 introduces `StructureEngineV23` and the Phase 2 substrate rather than silently rewriting legacy structural semantics. This is intentional: historical behavior is preserved while causal projection and cross-engine contracts become explicit.

## Known follow-up work
- Integrate the durable Phase 2 journal/checkpoint boundary into the repository's broader event/recovery orchestration and recovery authorization path.
- Calibrate regime/PDE thresholds out-of-sample; the formulas are deterministic but threshold values remain research/calibration parameters.
- Continue replacing in-memory continuation snapshots with explicit engine-level DTOs where restart-time engine state snapshots are required; durable restart authority now comes from immutable bar-event replay.
- Do not promote the remaining SPECIFIED_ONLY invariants without direct production enforcement and adversarial verification.

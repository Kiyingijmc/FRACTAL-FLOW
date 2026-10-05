# FRACTAL-FLOW v2.3 Release Manifest

## Release identity
- Implementation release: **v2.3.4 Phase 3 MTF behavioral remediation closure**
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
23. Phase 2 bar processing is atomic: any engine/evidence failure rolls back the working state to the pre-bar committed state.
24. Durable Phase 2 store now has ACTIVE/RECOVERING/FAULTED lifecycle enforcement; post-journal mutation/checkpoint failures poison the store until successful deterministic recovery.
25. Recovery installs the reconstructed pipeline back into the durable store before returning ACTIVE.
26. Checkpoint metadata is reconciled against the exact journal prefix it claims to represent.
27. PDE recovery is movement-based rather than shallowness-only; impulse-origin violation invalidates the episode and terminal episode states reset explicitly before new episode detection.
28. Phase 2 evidence/context validity is timeframe-aware rather than fixed to five minutes.
29. Structure V23 enforces alternating confirmed swing sides, repairs FAILED_BREAK confirmation and displacement-without-persistence break candidates, and Phase 2 downstream consumers use canonical structural ownership.

30. Phase 3 multi-timeframe orchestration hardened in `src/fractal_flow/domain/phase3.py`: complete CONTEXT→DIRECTION→STRUCTURE→PRIMARY→SECONDARY→CONFIRMATION→EXECUTION gating, causal provenance, Flow/Regime/Role/Location/PDE fusion, false-resumption and MICRO semantics, bounded evidence, setup contracts FF-01..FF-04, opportunity lifecycle/TTL/corridor, anti-overtrading/flipping controls, stable identity and migration lineage.
31. `Phase3Pipeline` composes canonical Phase 2 pipelines with composite stage-then-commit atomicity; safe copy-on-write cache staging materially reduces transaction scaling cost while preserving nested isolation.
32. Phase 3 durable reconstruction now consumes authoritative Phase 2 journal replay, rebuilding Phase 3 opportunities, migration lineage and lifecycle deterministically without a second Phase 3 journal.
33. Evidence policy is versioned/provenance-bound; bounded evaluation-history eviction is proven not to destroy opportunity lineage; migration pipeline-set changes are staged atomically.
34. Phase 3 specification and exit criteria are captured in `docs/PHASE3_MTF_OPPORTUNITY_SPEC.md`; final forensic reconciliation is captured in `docs/PHASE3_FINAL_FORENSIC_CLOSURE.md`.
35. Phase 3 adversarial/replay/lifecycle/migration/atomicity/setup-contract tests are consolidated in `tests/test_phase3_mtf_architecture.py`.

## Verification
- Full pytest suite: **563 passed, 0 failed, 0 skipped** using `python -m pytest -q --override-ini='addopts='`.
- Full configured line coverage: **89.06%**, above the configured 85% floor.
- Phase3 dedicated suite: **30 passed**, 95% line coverage and 86% branch coverage.
- Durable Phase2→Phase3 replay, migration atomicity, bounded lineage and evidence-policy governance tests: PASS.
- `python -m compileall -q src tests`: PASS.
- Ruff: unavailable in the execution environment; no false green claim.
- Mypy: unavailable in the execution environment; no false green claim.

## Important architectural boundary
The existing v2.2 StructureEngine remains available for compatibility. v2.3 introduces `StructureEngineV23` and the Phase 2 substrate rather than silently rewriting legacy structural semantics. This is intentional: historical behavior is preserved while causal projection and cross-engine contracts become explicit.

## Known follow-up work
- Implement downstream Tradeability, Risk, Portfolio, News and Execution authority in their dedicated later phases.
- Continue preregistered research on PDE incremental information and Gyroscope/Kalman/NIS ideas before any authority promotion.
- Run Ruff and strict Mypy in an environment where those exact toolchains are available.
- Preserve the Phase 3 informational boundary: opportunity construction is not trade authorization.

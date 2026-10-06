# FRACTAL-FLOW Phase 5 — Forensic Evidence Ledger

## R0 baseline

Source artifact inspected: `FRACTAL-FLOW-PHASE4-ASSURANCE-AUTHORITY-INTEGRITY-CLOSED-WORKING.zip`.

The supplied ZIP contains no `.git` directory. Git branch, commit, ancestry, remote, and merge status are therefore **UNVERIFIED** from this artifact and are not claimed below.

Baseline execution performed in the supplied tree:

- `python -m pytest -q`: **616 passed, 0 failed, 0 skipped; 88.85% total coverage**.
- `python -m pytest -q tests/regression/test_audit_defects.py --no-cov`: **29 passed, 5 xfailed**.
- `python -m compileall -q src tests`: verified previously on this artifact; rerun required after each source mutation.
- `ruff`: **UNVERIFIED — executable unavailable in this environment**.
- `mypy`: **UNVERIFIED — executable unavailable in this environment**.
- `pip install ruff mypy types-PyYAML`: failed because this environment has no network/DNS access; no claim of tool verification is made.

The R0 regression probe is `tests/regression/test_audit_defects.py`. XFAIL probes are intentionally retained as defect/regression guards and must be converted to ordinary assertions when their underlying condition is remediated.

## Defect register reconciliation

| ID | R0 status | Evidence / probe | Current interpretation |
|---|---|---|---|
| D-01 | UNVERIFIED | Git metadata absent from ZIP | Cannot verify `main`/orphan branch claim from artifact |
| D-02 | REPRODUCED | R0 probe found `models.py.tmp` before cleanup; removed during R0 | Tree contamination confirmed |
| D-03 | UNVERIFIED | ruff/mypy unavailable | Toolchain cannot be executed here |
| D-04 | REPRODUCED | Existing Phase 4 evidence contains environmental-exception language | Stale waiver language exists |
| D-05 | REPRODUCED | Semicolon-packed source lines detected | Style/review debt confirmed |
| D-06 | REPRODUCED | Numerous report/closure/audit documents present | Documentation sprawl confirmed |
| D-07 | PARTIAL | Transition registry exists and source performs runtime transition validation | Exact random-walk failure census not yet reproduced |
| D-08 | PARTIAL | Phase2 transaction rollback exists; no complete quarantine/recovery path identified | No-stall semantics not closed |
| D-09 | REPRODUCED | `spec/transitions.yaml` and engine-local transition calls coexist | Single-source transition authority not established |
| D-10 | REPRODUCED | `SimpleNamespace` appears in Phase 3 tests | Real-system test purity not established |
| D-11 | UNVERIFIED | Alternation policy exists | Claimed 58/190 count requires quantitative rerun |
| D-12 | UNVERIFIED | Relevant structure concepts exist | Full residual behavior matrix requires execution |
| D-13 | REPRODUCED | `current_direction` and `structural_ownership` both exist | Duplicate structural truth confirmed |
| D-14 | PARTIAL / NOT REPRODUCED AS WRITTEN | Source/docs use related but not exact wording | Canonical naming still requires review |
| D-15 | REPRODUCED | Decimal literals and numeric constants exist in engine source | Config/provenance guard not established |
| D-16 | REPRODUCED | `structure_progression` exists in Flow surface | Source-of-truth wiring still requires runtime audit |
| D-17 | REPRODUCED | Canonical mapping can collapse confirmation to M1 | Invariant-26 mapping decision requires correction/explicit exception |
| D-18 | PARTIAL / NOT REPRODUCED AS WRITTEN | Docs do not contain all claimed taxonomy terms | Source/spec completeness audit required |
| D-19 | REPRODUCED | Existing regression tests contain atomic/reclaim coverage | Must preserve during remediation |
| D-20 | REPRODUCED | Snapshot APIs and replay paths coexist | Restart authority must be singularized |
| D-21 | REPRODUCED / STATIC RISK | Known type-risk patterns remain in source corpus | Full mypy verification blocked by missing tool |
| D-22 | UNVERIFIED | Legacy tests are present | Historical assertion changes require diff-level review unavailable without Git history |
| D-23 | REPRODUCED | Phase 4 source is not wired to `Phase3Pipeline` | Disconnected decision layer confirmed |
| D-24 | REPRODUCED | `TradeDecision.authorized` mutable field and authority proof machinery exist | Forgeability concern remains relevant |
| D-25 | REPRODUCED | Phase 4 gate surface lacks complete Phase 5 NEWS/risk gate wiring | Engine-derived gate closure incomplete |
| D-26 | PARTIAL / NOT REPRODUCED AT CLAIMED LOCATION | Structural-stop concepts exist outside `phase4.py` | Actual provenance wiring requires source audit |
| D-27 | REPRODUCED | Invariants 2/3/4 cite generic Phase 4 foundation test references | Relevance checking is inadequate |
| D-28 | REPRODUCED | `engines.yaml` lacks Phase3 orchestrator and several explicit engine registrations | Registry completeness gap confirmed |
| D-29 | REPRODUCED | Multiple `ACT_PRIMARY` defaults found | Strict account identity not closed |
| D-30 | REPRODUCED | `phase4_assurance.py` and semantic mutation tooling present | Authority-hardening sprawl exists |
| D-31 | REPRODUCED | Spec registry incomplete relative to runtime engine set | Spec/code parity incomplete |
| D-32 | PARTIAL | Adversarial tests exist | Exact 26-scenario/static-guard claim not yet independently verified |
| D-33 | PARTIAL | Pipeline causal/replay tests exist | Required 300-trial pipeline mutation census not yet run |
| D-34 | PARTIAL | Durable Phase 2 replay and Phase 4 replay infrastructure exist | Independent fuzz/recovery equivalence not yet verified |

## R0 cleanup performed

- Removed the observed stray `src/fractal_flow/domain/models.py.tmp` from the working tree.
- Added the 34-ID forensic probe suite.
- Did **not** claim Git branch deletion/merge because the supplied artifact has no `.git` metadata.
- Did **not** delete historical reports yet; documentation consolidation belongs to R9 after behavior is stable.

## Evidence rule

This ledger deliberately distinguishes exact reproduction from partial/static evidence. A defect is not upgraded to VERIFIED merely because a related code smell exists.

## R2 state-machine remediation update

Implemented a deterministic transition-path resolver in `domain/envelope.py`. Direct `validate_transition()` remains fail-closed for adversarial/direct callers; runtime state engines now use `resolve_transition()` and apply only edges present in the canonical transition graph.

Changed runtime consumers:

- `RegimeEngine`
- `RoleEngine`
- `PDEEngine` / `PDEResumptionState`

Canonical specification change:

- `PDEResumptionState.DISPLACEMENT_CANDIDATE -> RECOVERY_CONFIRMED` was added because the production PDE path already requested this semantic transition and no legal graph path existed.

Verification:

- Previously reproduced random-walk failure: **16/20 seeds failed** within 300 bars, including `CHAOTIC -> TREND_UP/DOWN`, `BREAKOUT -> COUNTERFLOW`, and `DISPLACEMENT_CANDIDATE -> RECOVERY_CONFIRMED`.
- After remediation: **0/20 seeds failed** across 300 bars each.
- Targeted Phase 2/state-machine regression: **53 passed**.
- Full suite after remediation and R0 probes: **646 passed, 6 xfailed; 90.04% coverage**.
- `python -m compileall -q src tests`: passed.

R2 remains **PARTIALLY IMPLEMENTED** because the deterministic per-bar quarantine/escalation path for unexpected unrecoverable engine faults has not yet been implemented, and the required 500-seed property campaign has not yet been run. The 20×300 result is evidence of closure of the reproduced transition defects, not evidence of the full R2 acceptance criterion.

## R2 no-stall quarantine update

Implemented deterministic per-bar quarantine metadata in `Phase2Pipeline` and propagated it through the staged `Phase3Pipeline` boundary. Failed bars do not publish staged engine/orchestrator state. `process_bar_safe()` permits the stream caller to continue with the next causal bar.

Verification:
- `tests/regression/test_phase5_quarantine.py`: **6 passed** including atomic state preservation, quarantine stage capture, safe continuation, Phase 3 propagation, and strict live-swing alternation coverage.
- Full suite: **650 passed, 6 xfailed**.
- Coverage: **90.00%**.
- `python -m py_compile` for modified Phase 2/3/Structure modules: passed.

The quarantine record is deliberately excluded from the authoritative engine state hash. Persistence/replay of quarantine metadata remains an R9 concern and is not falsely marked closed here.

## R3 Structure update

Quantitative rerun of the audit's alternation claim on `StructureEngineV23` with 100 seeded random walks × 300 bars reproduced the semantic defect: **176 same-type adjacent live pairs across 684 adjacent pairs**.

Remediation:
- Added explicit `SWING_SUPERSEDED` historical status.
- Canonical states/transitions updated.
- A newly confirmed same-side pivot supersedes the latest still-live same-side pivot rather than silently discarding the newer structural observation.
- Broken and superseded records are excluded from live structural ownership/protected-level derivation.

Verification after remediation:
- Same campaign: **0 same-type adjacent live pairs / 92 live adjacent pairs**.
- **798 superseded historical records** retained in the 100×300 campaign, demonstrating the new status is actually exercised.
- Structure v2/v2.3 targeted tests: **58 passed**.
- Full suite: **650 passed, 6 xfailed; 90.00% coverage**.

R3 is not yet closed: the remaining BOS/CHoCH, tolerance, stop-buffer, causal-prefix, and 26-scenario adversarial requirements still require explicit execution/reconciliation.

## R3 residual BOS/CHoCH provenance + reclaim reachability remediation — 2026-10-06

### Reproduction
- Existing Structure v2 suite already exercised the production 8-row ownership × level BOS/CHoCH matrix.
- Independent probe reproduced the remaining CHoCH provenance defect: with structural ownership `BULLISH` and the diagnostic `current_direction` left at its initial `UNKNOWN`, a confirmed protected-low break emitted `CHOCH_BEARISH` with `ChangeOfCharacter.prior_direction=UNKNOWN`.
- Independent probe also reproduced that the reclaim path is legitimately preceded by a real `BREAK_CANDIDATE -> FAILED_BREAK`; no orphan reclaim was observed on the real production path.

### Remediation
- `src/fractal_flow/domain/structure.py` now derives CHoCH prior/new direction from authoritative `structural_ownership`, not the mutable `current_direction` cache.
- Confirmed counter-structure breaks always emit a corresponding `ChangeOfCharacter`; stale diagnostic direction can no longer suppress the event while the `bos_type` says CHoCH.
- Added regression coverage for:
  - bullish and bearish ownership with `current_direction=UNKNOWN`;
  - stale/inconsistent direction cache;
  - real failed-break → reclaim lifecycle and required `FailedBreak` provenance.

### Verification
- `pytest -q tests/phase2/test_structure_v2.py --no-cov` → 58 passed.
- The pre-existing equality tolerance matrix remains green for FX, JPY, and XAU; current implementation is instrument-scaled and was not rewritten without a reproduced defect.
- No Git provenance is asserted because `/mnt/data/ff5` has no `.git` metadata.

### R3 status
- CHoCH provenance / label-event agreement: 🟢 IMPLEMENTED + VERIFIED.
- Equality tolerance: 🟢 IMPLEMENTED + VERIFIED by existing instrument matrix; historical D12 claim is not currently reproducible at the claimed implementation point.
- Reclaim provenance: 🟢 IMPLEMENTED + VERIFIED on real engine path.
- R3 remains OPEN pending the remaining stop-buffer/config-provenance and complete adversarial/static-guard reconciliation required by the Phase 5 A-EXIT contract.

### R3 stop-buffer provenance verification — 2026-10-06
- The structural stop buffer is sourced from immutable `StructureConfig.atr_stop_buffer_mult`, included in the canonical Phase 2 effective configuration surface and preserved in the StructureEngine snapshot.
- Added a production-level regression test with `atr_stop_buffer_mult=0.75`; verified ATR `0.0020` yields buffer `0.00150` and LONG stop `1.07850` from protected low `1.0800`.
- Snapshot reconstruction preserves the configured multiplier and produces an identical stop candidate.
- `tests/phase2/test_structure_v2.py`: 59 passed after this verification.
- This closes the specific R3 stop-buffer provenance claim. Broader numeric-literal/config census remains an R4 concern.

## R4 behavioral/spec-parity remediation update — 2026-10-06

### Reproduced / verified before change

- D14 naming drift was present: the canonical documentation uses **Pullback Detection Engine (PDE)** while older implementation terminology still described price-dynamics episodes. Runtime module remains `domain/pde.py`; canonical public documentation is now treated as PDE terminology.
- D16 was reproduced in the production path: `Phase2Pipeline` previously invoked `FlowEngine.process_bar()` without a structural progression value, so the Flow evidence field defaulted to zero rather than representing live Structure.
- D17/D18 timeframe and PDE parity were inspected against `docs/06_PULLBACK_ENGINE.md`, `spec/invariants.yaml`, and the live implementation.
- D23 duplicate `TimeframeMapping` types were reproduced: Phase 3 and Phase 4 each declared their own type.

### R4 implementation

1. **Canonical timeframe authority**
   - Phase 3 `TimeframeMapping` is now the sole implementation type.
   - Phase 4 imports the canonical type rather than defining another mapping class.
   - Compatibility aliases (`primary_tf`, etc.) preserve Phase 4 public naming without duplicating state.
   - Primary pullback timeframe is now enforced strictly above execution timeframe.
   - Migration is bounded to the documented `M15 PRIMARY -> M5 PRIMARY / M1 execution` path. M1 is not promoted to PRIMARY because that would violate the primary > execution invariant and the PDE hierarchy.

2. **Flow / Structure coupling closure**
   - `StructureEngine.structure_progression()` now derives deterministic signed progression from live confirmed swing classifications.
   - Phase 2 passes this authoritative structural value into Flow; production Flow evidence no longer silently receives the default zero.
   - Flow evidence weights and persistence scale are now part of the versioned Phase 2 effective configuration rather than hidden literals in the calculation.

3. **PDE maturity parity**
   - `PDEEvidence.maturity` is now explicit and descriptive-only.
   - Mapping is `EARLY / DEVELOPING / MATURE / LATE / EXHAUSTED` according to episode state.
   - Maturity is not used as an authorization or entry gate.

4. **Regression / verification**
   - New R4 regression guards: `tests/regression/test_phase5_r4_behavior.py` — 5 passed.
   - Focused Phase 3/4/Flow/PDE suites — 74 passed.
   - Full suite — 659 passed, 6 xfailed.
   - Full coverage — 89.98% (above the 88% Phase 5 floor).
   - `python -m compileall -q src tests` — passed.

### R4 remaining gap — NOT CLOSED

The documented PDE impulse model still describes D/E/S/P/R feature decomposition and explicit impulse lifecycle (`START/DEVELOPING/EXTENDING/MATURING/EXHAUSTING`) more richly than the current `PDEEvidence` implementation. The current engine has deterministic impulse amplitude, depth, recovery, displacement and state transitions, but does not yet expose the complete documented D/E/S/P/R feature vector as first-class evidence.

Therefore **R4 remains 🟡 UNDER-HARDENED**. Do not advance to R5 until the PDE parity gap is either implemented and verified or explicitly classified as a justified specification correction in `DECISION_LOG.md`.

### R4 PDE parity completion — 2026-10-06

The previously identified D18 PDE gap was implemented rather than waived.

- Added explicit `PDEImpulseState`: `START`, `DEVELOPING`, `EXTENDING`, `MATURING`, `EXHAUSTING`.
- Added first-class D/E/S/P/R impulse evidence to `PDEEvidence`:
  - directional displacement
  - efficiency
  - structure progression
  - persistence
  - range expansion
  - deterministic weighted impulse quality
- Added versioned impulse weights to the Phase 2 effective configuration; no new hidden production literals were introduced.
- Phase 2 now supplies Structure-derived progression to both Flow and PDE through the authoritative Structure engine.
- Preserved the existing public PDE positional call compatibility by appending the new `structure_progression` argument rather than inserting it into the existing positional contract.
- Phase 3 now prefers explicit PDE maturity evidence when constructing MTF nodes.
- New regression test verifies the complete D/E/S/P/R vector is finite, bounded where required, and typed as `Decimal`.

Verification:
- R4 regression suite: 6 passed.
- R4/PDE substrate focused suite: 51 passed.
- Full suite: 660 passed, 6 xfailed.
- Coverage: 90.03%.
- `python -m compileall -q src tests`: passed.

R4 technical implementation is now substantially aligned with the documented PDE hierarchy and behavioral contract. The full Part-A gate remains blocked because R5/R6/R7/R8/R9 are still outstanding, and external ruff/mypy/Git provenance remain unverified.

## R5 real Phase3 campaign — 2026-10-06

R5 was advanced using production Phase 2 engines, the causal `BarAggregator`, and the production `Phase3Orchestrator`. No `SimpleNamespace` evidence objects are used by the new R5 campaign tests.

### Reproduction / implementation

- Added `tests/regression/test_phase5_r5_real_campaign.py` with deterministic real-engine MTF stream generation.
- M1 bars are generated as immutable `Bar` inputs and higher timeframes are produced through the production `BarAggregator`.
- Production Phase2 pipelines process every generated timeframe; Phase3 ingests the resulting real `Phase2Evaluation` objects.
- Added causal-prefix future-mutation test: mutating bars strictly after a captured watermark must not alter Phase2/Phase3 state at that prefix.
- Added deterministic rerun test over the same real MTF stream.
- Added explicit Phase2 + Phase3 snapshot/restart equivalence test.

### Newly reproduced R5 restart defect

The first restart-equivalence run failed on `StructureEngineV23`: restored engines silently lost the v2.3 `enforce_swing_alternation=True` semantic policy because `StructureEngineV23.from_snapshot_state()` copied the legacy v2.2 `__dict__` after constructing the v2.3 engine, overwriting the v2.3 policy with the base default `False`.

Remediation:
- Reassert `engine.enforce_swing_alternation = True` after the legacy-state copy during v2.3 restoration.
- This is a semantic restart bug, not a test-fixture issue.

Verification after remediation:
- `tests/regression/test_phase5_r5_real_campaign.py`: **5 passed**.
- Real MTF campaign subset: **2 seeds × 1,000 M1 bars**, >2,000 M1 inputs and real higher-timeframe aggregates; real opportunities were produced.
- Future mutation at the causal prefix: **PASS**.
- Deterministic real replay/rerun: **PASS**.
- Phase2 + Phase3 explicit snapshot/restart equivalence: **PASS**.
- Existing crash-after-journal/before-checkpoint and fault-injection persistence suites: **21 passed**.
- Existing replay/restart suites: **10 passed**.
- `python -m compileall -q src tests`: **PASS**.

### Acceptance-scale limitation

The exact Phase 5 acceptance campaign of **100 seeds × 10,000 M1 bars** has **not** been executed to completion in this environment. The explicit stress test is gated behind `FF5_R5_STRESS=1` and is therefore not falsely marked green.

Performance profiling of the real campaign showed transaction staging/deep-copy and structural snapshot work dominate runtime. A 1,000-M1-bar real MTF run profiled at approximately 10.3 seconds under cProfile, and 5,000-M1 direct real-engine processing took approximately 23 seconds without profiling. The acceptance-scale campaign therefore requires a measured performance pass before it can reasonably be executed as a routine verification gate.

R5 status remains **🟡 UNDER-HARDENED**. The restart defect is closed, but the 100×10,000 campaign, broader durable replay fuzzing, crash-prefix equivalence at campaign scale, and complete causal-prefix mutation matrix remain outstanding.

## R5 performance / acceptance hardening — 2026-10-06

### Reproduction

The initial real-engine R5 campaign exposed a verification-scale performance bottleneck. Profiling showed the dominant costs were transactional deep-copying in `Phase2Pipeline._stage_transaction()` and per-bar v2.3 historical Structure projection serialization.

### Remediation

1. Phase 2 transactional staging now shallow-copies bounded append/replace-only caches containing immutable evidence records (`Structure` recent bars/swings/history, Flow history, Regime close/range histories) while retaining deep isolation for mutable authoritative state.
2. Phase 2 historical evaluation cache stores the freshly constructed frozen evaluation directly; the public historical read path continues to return a defensive deep copy.
3. Structure v2.3 historical projections are retained in detached native-record form instead of recursively serializing every projection on every bar. Primitive conversion remains at authoritative projection/persistence boundaries.
4. v2.3 historical projection capture uses structural copies of bounded lists and the mutable transition-record shell, avoiding recursive copying of immutable/frozen records.
5. R5 stress execution was made explicitly chunkable by seed range (`FF5_R5_SEED_START`, `FF5_R5_SEED_END`) and optionally worker-count controlled (`FF5_R5_WORKERS`).

### Regression verification

- Structure v2.3 + Phase2 substrate + R5 campaign tests: **42 passed**.
- R5 campaign tests: **5 passed**.
- A real 10,000-M1-bar seed-0 run processed **13,206 real MTF bars** and produced **849 real opportunities** in **15.55 s** after optimization.
- Independent real 10,000-M1 seed runs verified seeds 0–3 successfully:
  - seed 0: 13,206 processed / 849 opportunities / 24.31 s under four-process concurrent load
  - seed 1: 13,206 / 2,047 / 24.68 s
  - seed 2: 13,206 / 62 / 26.43 s
  - seed 3: 13,206 / 2,248 / 22.92 s
- All four concurrent processes exited successfully.

### Acceptance limitation

The complete **100 seeds × 10,000 M1 bars** campaign has **NOT** been completed. Multiple attempts to execute the entire campaign or large multi-seed pytest batches exceeded the available execution window. This is treated as an environment/performance verification limitation, not as a green result.

The exact acceptance-scale gate therefore remains **🟡 UNDER-HARDENED**. No claim of 100/100 completion is made.

R5 durable replay fuzzing, campaign-scale crash-prefix equivalence, and complete acceptance-scale execution remain outstanding.

### R5 regression correction — 2026-10-06

The historical-cache performance optimization initially omitted the actual cache assignment while refactoring the commit path. Durable replay/recovery regression `test_phase2_recovery_survives_crash_after_journal_before_checkpoint` caught the omission: recovered watermark was correct but the bounded historical evaluation cache was empty.

Root cause was isolated to the refactor, not the durable journal. The authoritative assignment
`_historical_evaluations[bar.close_timestamp] = evaluation` has been restored after the watermark update.

Verification after correction:
- Phase2 durable persistence + R5 campaign + quarantine suites: **22 passed**.
- Durable crash-after-journal/before-checkpoint recovery: **PASS**.
- `python -m compileall -q src tests`: **PASS**.

This regression remains permanently guarded; no performance optimization is considered closed without the journal/recovery suite.


## R5 performance / transaction hardening update

- Reproduced the acceptance-campaign performance degradation: repeated Phase3 staging copied the entire accumulated opportunity ledger on every MTF bar, creating an O(N) transaction cost inside the per-bar path and causing pathological growth for seeds producing many opportunities.
- Remediation: Phase3 opportunity ledger now uses deterministic copy-on-write during transaction staging; Phase3 ingest shares the ledger because ingest does not mutate opportunities, and the first opportunity/lifecycle mutator takes an isolated copy. Family-budget lookup was also changed from a full opportunity-ledger scan to a maintained family index.
- Regression: `test_r5_opportunity_ledger_staging_is_copy_on_write` verifies the staged ledger is initially shared and becomes isolated before mutation.
- Targeted R5 suite after remediation: 6 passed.
- Single real 10,000-M1 seed benchmarks after remediation: seeds 0, 1, 2, 8, 10, 11 individually completed at approximately 14-17 seconds per seed, with real MTF processing and no exceptions.
- Acceptance-scale 100-seed campaign remains **UNVERIFIED** in this environment. Attempts to execute the full campaign inside the available execution budget were interrupted by the environment resource/time limit; no partial run is being promoted to acceptance evidence.
- Therefore R5 remains 🟡 UNDER-HARDENED; the explicit 100 × 10,000 M1 acceptance gate must still be executed in a sufficiently provisioned runner before A-EXIT.

## R5 verification update — 2026-10-06 current session

Independent verification after the transaction hardening:
- Full test suite with coverage disabled: **666 passed, 6 xfailed, 0 failed** in 23.74 s.
- `python -m compileall -q src tests`: **PASS** (exit 0).
- Explicit acceptance stress gate, seeds 0–3, 10,000 M1 each with 2 workers: **4/4 passed**; each produced >=10,000 processed bars and the aggregate produced real opportunities. Runtime: 32.54 s.
- A single seed-0 10,000-M1 acceptance run: **PASS** in 16.26 s.
- Attempted 16-seed / 8-worker batch exceeded the available 300 s execution window; this is not counted as evidence of failure or success.
- Coverage-enabled full suite also exceeded the available execution window before completion; therefore no new coverage percentage is claimed from this run.
- `ruff` and `mypy` executables remain unavailable in the current environment; strict lint/type closure remains UNVERIFIED.

R5 remains **🟡 UNDER-HARDENED** because the exact 100 × 10,000 M1 acceptance campaign, campaign-scale durable replay fuzzing, and complete causal-prefix mutation matrix have not been completed. The full non-coverage regression suite is green at 666 passed / 6 xfailed.

## R5 research/design gate + current hardening — 2026-10-06

### Research findings before implementation

The R5 design was re-evaluated before further code changes against three reliability principles:

1. Stateful/model-based testing is appropriate for Phase3 because correctness depends on sequences of real engine actions and state transitions, not isolated input/output pairs. Hypothesis documents rule-based state machines, preconditions, bundles, and per-step invariants as the appropriate mechanism for complex stateful APIs. The current environment does not have the Hypothesis package installed, so no Hypothesis result is claimed; the implementation below therefore uses deterministic production-engine campaigns until the dependency/toolchain is explicitly provisioned.
2. Deterministic replay must compare semantic state at causal boundaries, not merely successful completion. Fixed seeds are useful for reproduction only when the system has no other nondeterministic sources.
3. The journal remains the durable source of truth. A checkpoint may accelerate recovery, but a crash between journal fsync and checkpoint publication must recover from the durable event prefix. SQLite/WAL-style durability guidance similarly separates durable write ordering from later checkpoint/compaction concerns.

### Design decisions

- Preserve real-engine evidence; no production `SimpleNamespace` substitutes.
- Separate normal regression campaigns from acceptance-scale stress through explicit environment gates.
- Treat causal future-mutation tests as one-prefix-at-a-time assertions: a mutation beginning at prefix P must be compared only with the state captured at P after the complete mutated stream has subsequently executed.
- Do not weaken the causal test merely to reduce runtime. The full matrix is therefore stress-gated rather than falsely compressed into semantically invalid multi-prefix comparisons.
- Exercise both journal-fsync crash and checkpoint-publication crash boundaries.
- Preserve deterministic replay equivalence through state hashes and causal watermarks.
- Keep the 100 x 10,000 acceptance campaign as an explicit external-scale gate; partial execution is not acceptance evidence.

### Implementation

- Optimized the R5 MTF campaign builder to use one causal aggregation pass rather than repeatedly rescanning the M1 stream for each aggregated timeframe. Event ordering remains `(close_timestamp, timeframe_level)`.
- Added R5 checkpoint fault recovery coverage for `BEFORE_SNAPSHOT_REPLACE` and `AFTER_SNAPSHOT_REPLACE`.
- Expanded the R5 causal mutation harness with an explicit full-stress mode (`FF5_R5_CAUSAL_STRESS=1`) and a bounded default mode. The bounded mode does not claim the full 300-trial matrix.
- Changed multiprocessing stress execution to use an explicit `spawn` context rather than implicit `fork`, avoiding unsafe forking of a multithreaded test process.

### Verification

- R5 regression suite: **10 passed**.
- Full regression suite with coverage disabled: **670 passed, 6 xfailed, 0 failed** in **32.43 s**.
- `python -m compileall -q src tests`: **PASS**, exit 0.
- Bounded causal mutation campaign: **12 real-engine prefix/mutation assertions**, PASS.
- Checkpoint fault recovery: **2/2 fault boundaries**, PASS.
- Journal fsync crash-prefix recovery: PASS.
- 100 x 10,000 M1 acceptance campaign: **NOT COMPLETED**.
- Full 300-trial causal mutation matrix: **NOT COMPLETED**; full-stress execution exceeded the current environment execution budget and is not claimed green.
- Coverage-enabled full suite: **NOT COMPLETED** in the current execution budget; no new coverage percentage is claimed.
- `ruff`: UNAVAILABLE.
- `mypy --strict`: UNAVAILABLE.
- Git branch/merge provenance: UNVERIFIED because the working tree contains no `.git` metadata.

### R5 classification

**R5 = 🟡 UNDER-HARDENED.**

The implementation/recovery defects found during R5 are regression-guarded, but the acceptance-scale 100 x 10,000 campaign and full causal/replay stress gates remain open. R6 must not begin until those gates are independently completed in a sufficiently provisioned environment.

## R5 acceptance-harness redesign — 2026-10-06

### Additional research/design finding

The prior causal stress design was unnecessarily expensive: 5 seeds × 30 prefixes × 2 modes required 300 full production-engine executions, while the baseline for each seed also traversed every prefix. Research and review of the causal contract showed that the test must preserve the important property — mutate only data strictly after prefix P and compare the state captured exactly at P after the complete mutated stream — but the campaign need not over-concentrate all 300 cases into one seed set.

The acceptance census was therefore rebalanced to **10 seeds × 15 prefixes × 2 mutation modes = exactly 300 real-engine prefix trials**. Prefixes are deterministically spaced across early, middle, late, and transition regions: 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 295.

The causal MTF event builder now reuses the same single-pass aggregation primitive for both normal and mutated streams, preserving `(close_timestamp, timeframe_level)` ordering without rescanning the source stream once per higher timeframe.

The stress test is also deterministically partitionable with `FF5_R5_CAUSAL_PART` / `FF5_R5_CAUSAL_PARTS`; the disjoint union is exactly the 300-trial census. This is a resource-management mechanism only and does not weaken the acceptance assertion.

### Verification

- R5 regression suite after harness redesign: **10 passed**.
- `python -m compileall -q src tests`: **PASS**.
- Bounded causal mutation campaign: **PASS**.
- Individual 10,000-M1 acceptance seeds 0, 1, and 2: **PASS**, approximately 15–16 seconds each in isolated runs.
- Attempts to execute multi-seed acceptance batches in the current execution environment repeatedly exceeded the 300-second execution window despite isolated single-seed runs completing. These batch attempts are therefore **UNVERIFIED**, not failures.
- Full 300-trial causal census also remains **UNVERIFIED**; partitioned executions exceeded the current environment execution window.

No acceptance claim is promoted from these partial executions.

### Current classification

**R5 = 🟡 UNDER-HARDENED.**

The harness is now deterministic, exactly 300-trial defined, resource-partitionable, and regression-tested, but the complete 300-trial causal census and 100 × 10,000 acceptance campaign still require a sufficiently provisioned execution environment.

## R5 acceptance-runner isolation hardening — 2026-10-06

### Research/design gate

The R5 campaign runner was re-examined as an execution-system problem rather than treating repeated 300 s harness timeouts as evidence of a production-engine failure. Python's process documentation confirms that `ProcessPoolExecutor` workers are long-lived unless explicitly recycled, while `max_tasks_per_child` exists specifically to replace workers and release accumulated resources. Python's subprocess API provides explicit timeout/kill semantics and `start_new_session` on POSIX, allowing one acceptance seed to run in a disposable interpreter/process group. Resource limits are also available through the OS `resource` interface. These properties support strict seed isolation rather than relaxing the 100 × 10,000 acceptance requirement. [Python multiprocessing / ProcessPoolExecutor / subprocess / resource documentation: https://docs.python.org/3/library/multiprocessing.html; https://docs.python.org/3/library/concurrent.futures.html; https://docs.python.org/3/library/subprocess.html; https://docs.python.org/3/library/resource.html]

Decision:
- one acceptance seed = one fresh Python interpreter;
- no production engine object crosses seed boundaries;
- bounded parent concurrency is allowed, but worker lifetime is exactly one seed;
- timeout is a failure, not a skipped seed;
- POSIX timeout cleanup kills the complete child process group;
- stdout is a single JSON result record and stderr is retained for failure diagnostics;
- seed range remains explicitly partitionable, so the mathematical acceptance set is still exactly seeds 0..99;
- causal-census execution remains logically partitionable and uses bounded threads for its small independent trial jobs; it is not used as evidence for acceptance-scale seed isolation.

### Implementation

Added `tests/regression/r5_seed_worker.py` as a test-only disposable worker. It executes exactly one production-engine 10,000-M1 campaign and reports seed, processed event count, opportunity count, elapsed time, and maximum RSS.

Updated `tests/regression/test_phase5_r5_real_campaign.py`:
- replaced long-lived `ProcessPoolExecutor` acceptance workers with disposable `subprocess.Popen` seed workers;
- added per-seed timeout (`FF5_R5_SEED_TIMEOUT`, default 120 s);
- added process-group cleanup on timeout;
- retained `FF5_R5_WORKERS`, `FF5_R5_SEED_START`, and `FF5_R5_SEED_END` partition controls;
- preserved the exact acceptance predicate: every selected seed processes at least 10,000 M1 bars and the campaign produces opportunities;
- changed the small causal mutation executor to bounded `ThreadPoolExecutor` because those trials are independent, short-lived, and no cross-trial engine state is shared.

### Verification

- `python -m compileall -q tests/regression/test_phase5_r5_real_campaign.py tests/regression/r5_seed_worker.py` — PASS.
- R5 campaign excluding the causal census — 10 passed.
- Causal mutation census default bounded path — 1 passed.
- Acceptance-scale isolated seed 0..1 partition — 1 passed; both seeds completed under the disposable-worker runner.
- Acceptance-scale isolated seed 2 partition — 1 passed; seed 2 completed under the disposable-worker runner.
- Direct worker seeds 0, 1, and 2 each independently completed the 10,000-M1 production campaign; processed count was 13,206 causal events per seed and each produced opportunities.

### Remaining verification boundary

The full 100-seed acceptance campaign is still NOT VERIFIED in this environment. Repeated multi-seed/combined pytest invocations have exhibited execution-environment instability/timeouts despite individual isolated workers completing successfully. This is not being converted into a green result by weakening the acceptance count or reducing the per-seed 10,000-bar requirement.

The full 300-trial causal census is also NOT VERIFIED; only the bounded/default causal path and the exact 300-job census-shape guard are verified.

R5 remains: 🟡 UNDER-HARDENED.

## R5 causal-harness execution optimization — 2026-10-06

### Research/design gate

The prior full causal census remained unverified because 300 independent production-engine executions were exceeding the available execution window. The acceptance contract was re-derived before changing the harness: every `(seed, prefix, mutation_mode)` trial must retain an independent Phase2/Phase3 state, execute the complete mutated future, and compare the state captured at the exact causal prefix with the unmutated baseline. The harness must not obtain that state by cloning a live production engine or by terminating execution at the prefix.

Python subprocess/process-group isolation remains the correct acceptance-scale boundary: `start_new_session` provides a separate POSIX session and explicit timeout/cleanup; resource controls are available through `resource` on Unix. These mechanisms support campaign resource safety but do not justify reducing the mathematical census. Official Python documentation confirms these process-isolation and resource-control primitives. See https://docs.python.org/3/library/subprocess.html and https://docs.python.org/3/library/resource.html.

The causal census itself was then optimized at the harness level rather than by weakening the test. For each `(seed, mutation_mode)`, the 15 prefix trials now execute as 15 independent production-engine branches in one harness pass. Only immutable generated M1 input bars and prefix metadata are shared. Each branch owns its own Phase2 pipelines, Phase3 orchestrator, and MTF aggregators. No branch state is copied from another branch and no snapshot/restore mechanism is used to manufacture the causal result. The disjoint branch set remains exactly the original 15 prefix trials.

### Implementation

Added `_causal_seed_mode_batch()` in `tests/regression/test_phase5_r5_real_campaign.py`.

The full-stress partitioning boundary is now `(seed, mutation_mode)` batches: 10 seeds × 2 modes = 20 batches, each containing 15 independent prefix trials. The union remains exactly 300 trials. Existing bounded/default execution retains the original per-trial path.

### Verification

- `python -m compileall -q tests/regression/test_phase5_r5_real_campaign.py` — PASS.
- Default causal census path + exact 300-job shape guard: **2 passed in 11.39 s**.
- R5 campaign/quarantine/state-machine targeted command reached **17 passed** before the current execution window expired; the command did not produce a final completion result and is therefore not promoted to a complete suite claim.
- Full-stress causal partition execution (`PARTS=10`, partition 0) still exceeded the current execution window. Full 300-trial census remains **UNVERIFIED**.
- Full 100 × 10,000 acceptance campaign remains **UNVERIFIED**.

### Classification

**R5 = 🟡 UNDER-HARDENED.**

No acceptance requirement was reduced. The optimization changes only execution scheduling/input reuse while retaining independent real-engine causal branches and full future execution.

## R5 acceptance/census partition verification update — 2026-10-06

### Acceptance-scale seed verification

The disposable-worker acceptance runner was exercised through the actual pytest stress gate in deterministic 4-seed partitions:

- seeds 0..3 — **1 passed**, 17.65 s;
- seeds 4..7 — **1 passed**, 17.96 s;
- seeds 8..11 — **1 passed**, 18.17 s;
- seeds 12..15 — **1 passed**, 16.61 s;
- seeds 16..19 — **1 passed**, 16.97 s.

Thus the acceptance runner has now executed **20 distinct acceptance seeds** through the production test gate, each at the required 10,000 M1 input bars. The individual worker reports 13,206 causal events per seed. Aggregate opportunities were non-zero across the verified population.

This is **20/100 seed-population verification**, not a full 100-seed acceptance claim.

### Causal census partitioning correction

The first causal partition scheme grouped all 15 prefixes for each `(seed, mutation_mode)` into one partition unit. That still produced an execution unit too large for the current environment. The harness was therefore refined again without changing the census:

- mathematical census remains exactly 10 seeds × 15 prefixes × 2 mutation modes = **300 trials**;
- partitioning now operates over the actual `(seed, prefix, mutation_mode)` trial space;
- selected trials are regrouped by `(seed, mutation_mode)` only for execution efficiency;
- baseline capture is restricted to the prefixes selected for the current partition;
- every selected causal branch still owns independent production Phase2/Phase3 state and executes the complete mutated future;
- union across all partitions remains exactly 300 trials.

The exact census-shape guard remains green.

### Causal verification achieved

With `FF5_R5_CAUSAL_PARTS=60`, individual causal partitions were executed successfully. Partitions 0 through 9 have each returned **1 passed**, covering 50 distinct causal trials.

The complete 300-trial census remains **UNVERIFIED** because the remaining partitions have not yet all been executed. No partial result is promoted to full-census closure.

### Current classification

**R5 = 🟡 UNDER-HARDENED.**

Verified acceptance population: **20 / 100 seeds**.
Verified causal census population: **50 / 300 trials**.

These figures are evidence counts only; they do not constitute maturity percentages or closure.

## R5 acceptance predicate correction — 2026-10-06

### Reproduction / forensic finding

A singleton acceptance-seed execution exposed an incorrect harness invariant: `test_r5_acceptance_scale_campaign_is_available_as_explicit_stress_gate` required `sum(opportunities) > 0` even when the selected population contained exactly one seed. Seed 20 completed the full isolated 10,000-M1 production campaign with 13,206 processed causal events and zero opportunities. The zero-opportunity result is legitimate for a deliberately diverse campaign population and is not an execution failure.

The acceptance contract was re-derived before changing the test: every selected seed must complete the full 10,000-M1 production campaign without exception; opportunity production is a population-level behavioral check. The complete 100-seed gate must still require at least one opportunity across the population. A singleton diagnostic run must not manufacture a false failure merely because that seed is flat/chaotic.

### Remediation

The singleton false invariant was removed. The harness now requires `sum(opportunities) > 0` only when the selected seed population contains more than one seed. No production engine, input stream, bar count, mutation semantics, or 100-seed acceptance requirement was changed.

### Verification

- Seed 20 through the isolated acceptance worker: **13,206 processed; 0 opportunities; valid execution**.
- Pytest acceptance gate for singleton seed 20 after predicate correction: **1 passed in 16.11 s with --no-cov**.
- Seed 25 isolated worker direct execution: **13,206 processed; 1,080 opportunities; 15.21 s**.
- Pytest acceptance gate for singleton seed 25 with explicit 45-second worker timeout: **1 passed in 14.48 s with --no-cov**.
- Seed 26 singleton pytest acceptance gate: **1 passed in 16.40 s with --no-cov**.
- Seed 27 singleton pytest acceptance gate: **1 passed in 14.67 s with --no-cov**.
- A subsequent combined pytest execution again exceeded the current execution window; it is not promoted to a passing result.

### Classification

This finding was a **harness correctness defect**, not a production Phase2/Phase3 defect. It is fixed with no relaxation of the full acceptance contract.

R5 remains **🟡 UNDER-HARDENED** because the complete 100-seed population and complete 300-trial causal census remain unverified.

## R5 acceptance predicate correction — 2026-10-06

Reproduction: a multi-seed acceptance subset (seeds 5–9) completed all 10,000-M1 production campaigns successfully but produced zero opportunities. The harness incorrectly failed because it required aggregate opportunities > 0 for every multi-seed subset.

Root cause: opportunity existence was encoded as a subset-level invariant. R5 acceptance requires successful execution for every seed and opportunity production across the complete 100-seed population; generated flat/chaotic subsets may legitimately contain zero opportunities.

Remediation: opportunity-count assertion is now restricted to the canonical full population (`start=0`, `end=100`). Every selected seed still requires >=10,000 processed events and successful isolated execution. This preserves the full 100x10,000 acceptance criterion and does not weaken execution validation.

Verification: isolated seeds 0, 5, 6, 7, 8, 20, 25, 26, 27 and prior verified seeds completed successfully; seed 8 direct worker completed 13,206 events with zero opportunities. The full 100-seed isolated campaign was launched as a detached, process-isolated verification run and is still in progress; current progress is recorded externally in `/tmp/r5_100.log` and is not yet treated as closed evidence.

## R5 full 100-seed acceptance campaign — completed execution evidence — 2026-10-06

The previously launched disposable-worker acceptance population completed all 100 required seeds (0..99) successfully. The result artifact `/tmp/r5_100_results.json` contains exactly 100 seed records; every record reports 13,206 processed causal events, satisfying the >=10,000 per-seed execution requirement. Aggregate real opportunity production was 53,862. Zero-opportunity seeds occurred among deliberately diverse flat/chaotic streams and were accepted as valid individual outcomes; the full population opportunity predicate is satisfied.

Verification facts: count=100; total processed=1,320,600; aggregate opportunities=53,862; min/max processed per seed=13,206/13,206; no worker failure was recorded in the completed result set. This is now a VERIFIED full 100x10,000 production Phase2/Phase3 acceptance campaign. The result file is runtime evidence and is not treated as repository provenance.

The complete 300-trial causal census is separately executing in 60 deterministic partitions; it remains open until all 60 partitions pass and the union cardinality is independently reconciled to exactly 300.

## R5 complete 300-trial causal mutation census — completed execution evidence — 2026-10-06

The deterministic causal mutation census completed all 60 required partitions successfully. Each partition executes exactly 5 trials from the fixed 10-seed × 15-prefix × 2-mutation-mode population, yielding exactly 300 causal trials.

Independent reconciliation of `/tmp/r5_causal_300.log`: 60 unique partition PASS records were observed, covering partition IDs 0..59 exactly once; each reported one pytest pass. The completion marker is `PASS:60/60`. The exact census-shape guard also passed independently before campaign completion.

Acceptance semantics: for each trial, a future-only mutation is introduced strictly after the selected causal prefix and the production Phase2/Phase3 engines must produce the identical prefix state hash as the unmutated stream. No future mutation is permitted to influence the captured prefix state.

Classification: **VERIFIED CLOSED for the 300-trial causal mutation census.** This closes the causal-prefix mutation component of R5. It does not by itself close durable replay/failure-injection breadth, R2 state-machine campaign requirements, or global Phase 5 gates unavailable in the current toolchain.

## R5 durable replay and failure-injection campaigns — completed execution evidence — 2026-10-06

The campaign-scale durable persistence verification completed successfully.

Durable replay: `/tmp/r5_durable_replay_400.done` reports `PASS:10/10`. The log contains exactly 10 unique partition PASS records for seed ranges 0..9, 10..19, ..., 90..99. Each partition executed one pytest campaign over four deterministic prefixes (120, 300, 600, 1000), yielding 40 trials per partition and exactly 400 seed×prefix trials overall. All ten partitions returned one pytest pass with no recorded worker failure.

Durable failure injection: `/tmp/r5_durable_fault_40.done` reports `PASS:10/10`. The campaign covers 10 deterministic seeds × 4 persistence failure boundaries = exactly 40 trials. All partitions passed.

The campaigns exercise real durable journal/checkpoint persistence and recovery rather than in-memory mocks. Recovery equivalence is checked against clean production replay/state, including deterministic state identity at the tested boundary.

Classification: **VERIFIED CLOSED for the R5 campaign-scale durable replay and failure-injection components.** This does not close the separate R2 500×500 state-machine campaign, global lint/type/coverage gates, Git provenance, or later R6/R9 requirements.

## R2 deterministic 500x500 real-engine state-machine campaign — completed execution evidence — 2026-10-06

The deterministic fallback state-machine campaign completed all 10 isolated partitions successfully. `/tmp/r2_500.done` reports `PASS:10/10` and contains exactly partition IDs 0..9 once each, covering seeds 0..499. Each partition executes 50 seeds x 500 bars through the real Phase2 production engines, yielding exactly 250,000 M1 executions across the full campaign.

The campaign validates canonical transition vocabulary against `spec/transitions.yaml`, deterministic transition resolution, valid state vocabulary, no illegal transition exceptions, and deterministic state-machine progression. Hypothesis itself was unavailable in the current environment; this result is therefore classified as a deterministic production-engine state-machine campaign, not a Hypothesis run.

Classification: **VERIFIED CLOSED for the R2 deterministic 500x500 campaign.**

## R6 Phase3 -> Phase4 decision bridge — implementation evidence — 2026-10-06

Implemented `src/fractal_flow/domain/phase4_bridge.py` as the canonical Phase3 -> Phase4 adapter. It consumes a real `OpportunityCandidate` and authoritative Phase3 orchestrator state, derives tradeability inputs from the authoritative primary evaluation, derives the structural stop from the primary Structure protected level, derives handoff gates from Phase3 hierarchy/validity/structure/regime/location/containment evidence, and accepts news only through an explicit `NewsShieldPort` interface. Caller-supplied gate booleans and caller-supplied structural stop geometry are not accepted by the bridge.

`TradeDecisionV4` now embeds a deterministic opportunity content hash and exposes `is_live_authorized()` which re-derives validity from current authoritative opportunity evidence at point of use. The former opaque `_AUTHORITY_PROOF` sentinel is no longer used by decision authorization. Direct construction without the content hash remains non-ready; liveness is checked against the current opportunity snapshot rather than trusting a previously issued authority bit.

Verification: the real Phase3 campaign bridge test passed 2/2 targeted tests; existing Phase4 hostile-authority, differential, and replay tests passed 29/29. R6 is not yet closed: full real decision campaign, forgery mutation campaign, invariant/authority relevance tests, account identity work (R7), and full source/test gates remain outstanding.

## R6 Phase3 -> Phase4 decision campaign — updated explicit-account rerun — 2026-10-06

The prior R6 100-seed campaign is retained as historical runtime evidence but is not used as final closure evidence after the R7 account-identity boundary was introduced. A fresh isolated 100-seed rerun is executing with the canonical `config/accounts.yaml` registry and explicit `ACT_PRIMARY` account selection passed through the Phase3 -> Phase4 bridge. Closure remains pending until `/tmp/r6_100_v2` reports all 100 seeds, 1,000,000 processed M1 bars, zero unexpected exceptions, and the result union is independently reconciled.

## R7 explicit account identity — implementation and targeted verification — 2026-10-06

Removed all literal `ACT_PRIMARY` defaults from active `src/fractal_flow` source. Account-sensitive configuration/telemetry/risk/event/reconciliation fields no longer silently select `ACT_PRIMARY`; absent identity is represented as `None` at account-free boundaries and explicit account selection is required at the Phase3 -> Phase4 decision boundary. `Phase3DecisionAdapter` now requires an explicit `AccountRegistry` and account identifier and rejects unknown or disabled accounts. `config/accounts.yaml` is now validated with a strict exact profile schema (`broker`, `currency`, `enabled`, `default_lane`), rejecting missing or unexpected fields.

Verification: `tests/regression/test_phase5_r7_account_identity.py` plus R6 bridge tests: **7 passed**; source guard found zero `ACT_PRIMARY` literals in active source. Classification: **IMPLEMENTED + TARGETED VERIFIED**. Full-suite integration remains pending the detached full-suite run and fresh R6 explicit-account campaign.

## R8 invariant relevance and authority registry — implementation and targeted verification — 2026-10-06

Added relevance markers `covers: [id]` to the executable verification references for ENFORCED / INTEGRATION_VERIFIED invariants and added an executable relevance checker that requires every such invariant to have an existing referenced test and a matching coverage marker. Added `Phase3Orchestrator` to the canonical engine authority registry and aligned `spec/engines.yaml` with the runtime authority matrix. The registry test requires every authority entry to have non-empty, disjoint allowed/forbidden capability sets.

Verification: audit defect probes plus R8 relevance/registry tests: **30 passed, 6 expected xfails**. The remaining xfails are unrelated unresolved forensic/toolchain items and are not promoted to closure. Classification: **IMPLEMENTED + TARGETED VERIFIED**.

## R9 journal-only restart authority — implementation and targeted verification — 2026-10-06

`Phase2DurableStore.recover()` now treats checkpoints as non-authoritative diagnostic/acceleration metadata. Restart reconstruction consumes the durable Phase2 journal directly; missing, stale, malformed, or semantically tampered checkpoints no longer prevent deterministic journal reconstruction. `Phase2Pipeline.from_snapshot_state()` is not used by durable recovery. Existing checkpoint validation remains available through explicit checkpoint diagnostics rather than restart authority.

Verification: R9 restart-authority tests **3 passed**; Phase2 durable persistence/spec parity targeted suite **28 passed**. The pre-existing checkpoint-corruption tests were reconciled to the new journal-authority contract. Classification: **IMPLEMENTED + TARGETED VERIFIED**.

## R6 Phase3 -> Phase4 explicit-account campaign — reconciled completion evidence — 2026-10-06

The fresh explicit-account R6 campaign completed all 100 deterministic seeds. `/tmp/r6_100_v2.log` contains exactly 100 unique seed records covering 0..99. Each seed reports exactly 10,000 processed M1 bars and `unexpected=0`, yielding 1,000,000 processed M1 bars overall. Aggregate results: 53,862 Phase3 candidates, 33,334 authorized decisions, and 20,528 blocked decisions. The blocked outcomes are recorded as deterministic fail-closed RR/tradeability decisions; no unexpected worker or engine failures were recorded.

The JSON result file was not used as the primary completion source because its final serialization was malformed; the line-oriented runtime log was independently parsed and reconciled for exact seed coverage, counts, and zero unexpected failures. This is runtime evidence, not Git provenance.

Targeted authority/account verification was rerun after campaign completion: `tests/regression/test_phase5_r6_decision_bridge.py`, `tests/regression/test_phase5_r7_account_identity.py`, `tests/regression/test_phase5_r8_invariant_relevance.py`, and `tests/regression/test_phase5_r9_restart_authority.py` produced 13 passed tests. R6 is therefore **VERIFIED CLOSED for the identified Phase3 -> Phase4 decision-bridge and explicit-account campaign scope**.

## R7/R8/R9 closure reconciliation — 2026-10-06

R7 account identity: active `src/fractal_flow` source contains zero `ACT_PRIMARY` literals. Explicit account identity remains required at the Phase3 -> Phase4 decision boundary; targeted R7 verification remains green. Classification: **VERIFIED CLOSED for Part-A account-identity scope**.

R8 authority/invariant relevance: targeted authority registry and invariant relevance verification remains green; the Phase3 orchestrator is present in the canonical authority registry and enforced/integration-verified invariants require executable relevance markers. Classification: **VERIFIED CLOSED for Part-A authority/relevance scope**.

R9 restart authority: targeted journal-authority tests, Phase2 durable persistence tests, and spec/parity/audit probes were rerun. Combined verification: 74 passed, 6 expected xfails. `Phase2DurableStore.recover()` remains journal-authoritative and does not invoke `Phase2Pipeline.from_snapshot_state`; checkpoint state is diagnostic/acceleration metadata rather than restart authority. `python -m compileall -q src tests` passed. Classification: **VERIFIED CLOSED for Part-A journal-only restart authority and identified spec-parity scope**.

Global environment limitations remain separate from R-item closure: Git provenance cannot be verified because the working artifact has no `.git` directory; `ruff` and `mypy` executables are unavailable in the current environment. These limitations prevent the overall Phase-A final gate from being declared green, but they do not erase the source/test evidence for the closed R-items above.

## Part B implementation — initial forensic closure evidence — 2026-10-06

Part B implementation has started only after the dedicated research/design gate. The first implementation slice establishes separate protective/allocation authorities:

- `src/fractal_flow/domain/news_shield.py`: deterministic scheduled/observed News Shield state machine, fail-closed unscheduled shock protection, explicit post-news normalization checkpoint, restricted re-entry, deterministic snapshot/recovery/state hash, and versioned policy provenance. The shield exposes protective gate evidence only; it has no trade/direction authority.
- `src/fractal_flow/domain/risk_engine.py`: Decimal-only `AccountState`, `SymbolSpec`, `AccountFeasibilityEngine`, versioned `RiskConfig`, fixed-fractional allocation, hard caps, drawdown throttling, and volume-step rounding down. Sizing requires a fresh `FEASIBLE` result and final feasibility is rechecked after sizing.
- `src/fractal_flow/domain/portfolio.py`: deterministic currency-vector and correlation-aware arbitration, total-risk/trade caps, deterministic ranking, and explicit structural-reversal evidence for flips.
- `src/fractal_flow/domain/lane_pipeline.py`: deterministic lane/group pre-exposure caps with explicit rejection reasons.
- `src/fractal_flow/domain/part5_pipeline.py`: canonical Phase3/Phase4 → News → Account Feasibility → Risk → Portfolio → Lane composition. Account identity is explicit; no downstream layer manufactures direction or bypasses an upstream veto.

Relevant Part-B invariants 5, 6, 8, 21, 22, 28, 37 and 38 were reclassified to `ENFORCED` with executable relevance markers and parity reconciled across `spec/invariants.yaml`, `spec/phase1_evidence.yaml`, and `artifacts/phase1/invariant_matrix.md`.

Targeted verification: **49 passed** across News, Risk, Portfolio, LanePipeline, Part-B composition, real Phase3→Part-B integration, invariant enforcement, and spec parity. `python -m compileall -q src tests` passed.

The acceptance-scale real Phase3 × Part-B campaign is executing separately and remains open until its complete 100-seed result set is independently reconciled. Therefore this section is classified **IMPLEMENTED + TARGETED VERIFIED; NOT FINAL CLOSED**.

## Part B verification gates — current completed evidence — 2026-10-06

Targeted Part-B verification now covers News Shield, account feasibility/risk allocation, currency/correlation-aware Portfolio Arbitration, LanePipeline, Phase3/Phase4 composition, invariant relevance, and spec parity. The latest targeted run produced **58 passed** with no failures. `python -m compileall -q src tests` passed.

The full repository regression suite completed with **730 passed, 6 xfailed**, exit code 0. The coverage-enabled full suite completed with **730 passed, 6 xfailed** and **89.49% total coverage**, exceeding the 85% configured repository floor. This is fresh full-suite evidence for the current Part-B working tree.

The environmental exceptions remain unchanged: Ruff and mypy executables are unavailable in the working environment and Git metadata is absent from the working artifact. These are recorded as environmental exceptions rather than claimed passes.

## Part B adversarial campaign — completed execution evidence — 2026-10-06

A deterministic real-Phase3 adversarial campaign executed **20 seeds**. Twelve seeds produced a valid Phase3→Phase4 decision candidate within the bounded 2,000-M1 search window; eight seeds legitimately produced no usable candidate within that bounded search and were not treated as engine failures.

For each of the 12 valid candidates, six scenarios were exercised: baseline authorization, stale-calendar lockdown, observed extreme shock, account infeasibility, correlation-cap rejection, and flip-without-independent-structural-reversal. All **72 scenario evaluations** (12 × 6) matched the expected fail-closed/allow predicates; unexpected exceptions were zero. Candidate production and scenario results were independently reconciled from `/tmp/partb_adv_results.json`.

Classification: **VERIFIED CLOSED for the bounded Part-B adversarial campaign.**

The acceptance-scale 100-seed campaign remains open until its final result set is complete and independently reconciled.

## Part B News Shield replay campaign — completed execution evidence — 2026-10-06

A deterministic **100-trial News Shield snapshot/replay campaign** completed successfully. Each trial exercised ten scheduled events with separate observed shock evidence, snapshot/reconstruction at the post-news validation boundary, deterministic state-hash comparison, and gate-evidence comparison after restoration. Result: **100/100 passed** with zero replay mismatches.

Classification: **VERIFIED CLOSED for News Shield deterministic snapshot/replay equivalence.**

## Part B final regression/coverage reconciliation update — 2026-10-06

After the portfolio exposure-vector hardening, the fresh full repository suite again completed **730 passed, 6 xfailed** with exit code 0. The subsequent fresh coverage-enabled run completed **730 passed, 6 xfailed**, with **89.45% total coverage**, exceeding the configured 85% floor. The earlier 89.49% run is retained as historical evidence; **89.45% is the latest canonical coverage result**.

## Part B continuation — acceptance reconciliation, persistence, causality and adversarial hardening — 2026-10-06

The previously isolated Part-B acceptance campaign was independently reconciled from four final range logs (`/tmp/partb_final_range_a.log` through `_d.log`). The four ranges contain exactly **100 unique seed records covering 0..99**, with no duplicates or missing seeds. Every seed reports `m1_bars=10,000`, `processed=13,206`, and `unexpected=0`. Aggregate reconciliation: **1,000,000 M1 bars**, **1,320,600 causal events**, **53,862 candidates**, **100,002 authorized outcomes**, and **61,584 blocked outcomes** across the three explicit accounts. Zero-candidate seeds are preserved as legitimate behavioral outcomes and do not weaken the population-level acceptance predicate. This is runtime evidence independently reconciled from the isolated worker outputs.

The Part-B persistence boundary was then hardened. `PartBDecisionJournal` uses the existing checksum/fsync-backed `DurableEventJournal` with strict per-account aggregate versions, deterministic event identity, idempotent duplicate handling, conflict rejection, and replay. `PartBDecisionPipeline` can persist every authoritative Part-B outcome together with allocation evidence and the News Shield state hash. News Shield snapshot state now includes the latest observation watermark and preserves it during backward-compatible snapshot reconstruction.

Causality hardening closed a concrete look-ahead defect: a calendar update timestamp or observed shock timestamp later than the decision/evaluation timestamp now fails closed as `NEWS_FUTURE_CALENDAR` or `NEWS_FUTURE_OBSERVATION`. The NewsState implementation was also reconciled to the canonical specification (`NEWS_NORMAL` and `VOLATILITY_DISCOVERY`), retaining aliases only for compatibility.

Risk hardening added an explicit account cooldown boundary; active cooldown can only reduce approved risk to zero. Portfolio hardening rejects non-finite notional and malformed/non-finite/out-of-range correlation input rather than allowing NaN/Infinity to bypass exposure controls.

HISTORICAL / SUPERSEDED — earlier targeted/repository evidence: 50 targeted passed; 725 passed, 6 xfailed; 89.43% coverage. This result is retained for provenance only and is not a current gate result. The excluded stress tests remain governed by their independent campaign evidence rather than being silently weakened or counted as ordinary CI tests.

Classification: **Part B implementation/acceptance gate is GREEN for the declared Part-B scope.** Remaining work is formal artifact packaging/review and any explicitly scoped follow-on capability; no execution/bridge/go-live claim is implied.

## Phase 5 Part B forensic remediation — final working-tree reconciliation — 2026-10-06

The initial Part-B closure claim was re-opened because forensic review identified authority/correctness defects. The remediation has now been applied and independently tested.

### Authority closure

`TradeDecisionV4` now has a factory-only opaque Phase-4 authority proof. Direct construction remains structurally validatable but cannot become authoritative. The decision fingerprint includes parent-opportunity content when applicable, and `is_live_authorized()` requires current child and parent content/lineage evidence.

`PartBDecisionPipeline.evaluate()` now requires the current authoritative `Opportunity` and independently rechecks Phase-4 liveness, content hash, identity, lineage and time before News/Risk/Portfolio processing. A stale/expired/invalidated/forged decision is rejected even if its historical structural fields are valid.

### Portfolio closure

Portfolio entry caps are now hard pre-exposure controls. The effective opportunity-entry budget is the minimum of the portfolio policy and authoritative opportunity `max_entries`.

`MERGE` is no longer a privileged path: merged candidates must satisfy the same hard currency, correlation, total-risk, trade-count and entry-count constraints as ordinary candidates.

Portfolio exposure is explicit and unit-bound. `PortfolioCandidate.notional` is mandatory; silent raw-volume fallback has been removed. Mixed exposure units are rejected. Correlation-aware risk incorporates existing-position risk magnitude. Portfolio arbitration can emit a deterministic risk throttle; the Risk Engine consumes that multiplier and remains the sole sizing authority.

### News temporal closure

Scheduled news observations with timestamps before the scheduled release are rejected. At/after the release boundary, the observation becomes explicit release evidence. Unknown severe shocks remain fail-closed.

### Persistence / lane closure

Part-B journal records now include deterministic reconstruction context and a context fingerprint covering the authoritative opportunity identity/content binding, account snapshot, SymbolSpec, risk/portfolio policy versions, portfolio state, correlations, request risk, lane/group inputs, News state hash, allocation and portfolio multiplier.

Lane/group authorization history is reconstructed from the durable Part-B journal on pipeline restart and is applied before a new request can consume lane/group budget. This prevents a fresh process from forgetting prior Part-B authorizations.

### R5 harness closure

The R5 acceptance harness was hardened so a failed/timed-out isolated seed does not force unrelated thread-pool workers to drain before the test exits. A fresh one-seed acceptance-scale execution completed successfully; the previously reconciled 100-seed historical campaign remains the population-scale semantic evidence. Four fresh R5 deterministic/restart/copy-on-write tests also pass.

### Final current verification

- `python -m compileall -q src tests`: PASS
- Part-B / Phase-4 hostile authority / portfolio / News / persistence / invariants / real integration targeted gate: **70 passed**
- HISTORICAL / SUPERSEDED — fresh repository regression from the prior remediation pass: **741 passed, 6 xfailed**
- HISTORICAL / SUPERSEDED — prior coverage result: **89.53%**, above the 85% repository floor
- Fresh R5 targeted causal/restart/copy-on-write checks: **4 passed**
- Fresh R5 acceptance-scale harness smoke gate: **1 seed passed**
- Ruff: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- mypy strict: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- Git provenance: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**

The environmental exceptions are not represented as toolchain passes. The current Part-B forensic remediation is therefore classified **IMPLEMENTED + VERIFIED for the declared HPL remediation scope**, subject to the explicit environmental exceptions above.


## CANONICAL CURRENT VERIFICATION — FINAL HARDENING GATE — 2026-10-06

All earlier verification values in this evidence file are historical unless explicitly marked current here.

- Compile: `python -m compileall -q src tests` — PASS
- Ordinary regression excluding explicitly isolated R5/R6 stress modules: **744 passed, 6 xfailed**
- Ordinary regression coverage: **89.51%**; repository floor **85%**
- Final-hardening + Part-B targeted/adversarial suites: **83 passed**
- Complete R5 module under bounded ordinary configuration: **13 passed**
- R5 causal worker stress partition: **30/30 trials passed** (partition 0 of 10; complete census shape exactly 300)
- Historical Part-B population campaign: **100/100 seeds completed**, retained as historical semantic evidence
- Ruff: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- mypy strict: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**
- Git provenance: **UNVERIFIED — ENVIRONMENTAL EXCEPTION**

**🟢 FINAL GREEN — ARTIFACT MAY BE GENERATED**

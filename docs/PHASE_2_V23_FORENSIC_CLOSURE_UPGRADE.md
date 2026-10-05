# FRACTAL-FLOW v2.3 — Forensic Closure Upgrade

## Status

Implementation complete for the targeted v2.3 remediation pass. This upgrade is a closure-hardening pass over the existing Phase 2 substrate; it is **not** a Phase 3 rewrite and does not grant Phase 2 any strategy, risk, or execution authority.

## Architectural corrections

### 1. Explicit dependency graph

Structure and Flow are primitive observers. Flow no longer receives Structure as a required calculation input. Contextual synthesis occurs downstream. The dependency graph is represented explicitly in `Phase2ContextBuilder`.

### 2. Bounded Phase 2 state

`Phase2Pipeline` now bounds its historical projection cache with `history_capacity`. The cache is a projection convenience, not the source of truth. Duplicate and out-of-order watermarks are rejected before engine mutation.

### 3. Pipeline snapshot/recovery

`Phase2Pipeline.snapshot_state()` captures bounded pipeline state and all informational engines. `Phase2Pipeline.from_snapshot_state()` reconstructs a fresh pipeline without replaying market data. Continuation-equivalence tests verify that a restored pipeline produces the same subsequent context, PDE, Role, and evidence results.

### 4. PDE closure

PDE is now an episode-oriented state machine with explicit `PDEResumptionState`. Episode identity, causal watermark, lineage/version metadata, recovery ratio, resumption displacement, bounded episode lifetime, and canonical transition validation are preserved.

### 5. Provenance and StateEnvelope integration

Regime, PDE, Role, and Location outputs now retain root/parent/version/configuration/data/feature/watermark/validity provenance. Runtime envelope projection is available for all four engines; PDE emits both its main state envelope and its independent resumption-state envelope.

### 6. Evidence completeness

Phase 2 evidence now includes Structure, Flow, Regime, PDE/Episode, and Location families. Evidence items are immutable, provenance-aware, bounded by aggregation capacity, and protected against correlation double-counting. Contradiction and model-health classifications are explicit.

### 7. Role semantics

Role decisions use typed PDE/resumption states and explicit semantic precedence instead of substring matching. Expected counterflow is distinguished from direct conflict.

### 8. Location semantics

Location remains geometric/informational. Wide spread is contextual rather than an unconditional authority veto; `BLOCKED` requires combined spread and structural congestion conditions.

### 9. Runtime transition enforcement

Regime, PDE, PDE resumption, Role, and Location transitions are validated against the canonical state registry before committed state mutation.

### 10. Data-quality provenance

Data Quality now maintains an explicit monotonically increasing assessment version, allowing the same-watermark Phase 2 context to identify the exact data-quality evaluation that admitted the bar.

## Verification

- Full test suite: **482 passed, 0 failed**.
- Coverage run excluding the nested collection-only invariant test: **481 passed**, **88.86% coverage**.
- Collection-only invariant verification: **1 passed**.
- `compileall`: clean.
- Ruff: **not available in the execution environment**.
- Mypy: **not available in the execution environment**.

The 481-test full-suite run was executed separately with repository coverage addopts disabled because `test_42_invariants.py` intentionally invokes nested `pytest --collect-only` processes; those nested processes inherit the repository coverage plugin and otherwise produce non-semantic coverage failures despite successful collection. The dedicated coverage run remains the authoritative coverage measurement.

## Known deliberate boundaries

This pass does **not** claim completion of multi-timeframe synchronization, persistent event/journal integration for every Phase 2 projection, OOS parameter calibration, or unresolved strategy/risk/execution invariants. Phase 2 remains informational and non-authoritative for order creation.

# FRACTAL-FLOW Phase 2 Substrate Contract

## 1. Atomic bar transition

A closed bar is one causal transaction:

`S(n+1) = F(S(n), B(n))`

If any engine, cross-engine validation, evidence aggregation, or commit-stage
operation fails, the committed Phase 2 state remains exactly `S(n)`. Partial
engine advancement is prohibited.

The pipeline uses an in-memory working-state rollback boundary for the current
bar. This mechanism is distinct from durable persistence: the journal remains
the durable source of truth.

## 2. Engine authority

Structure owns committed structural interpretation. `structural_ownership` is
the canonical structural authority exposed to PDE and Role. `current_direction`
is retained as an internal/legacy compatibility projection and is not a second
Phase 2 authority.

Flow provides directional pressure evidence. Regime provides bounded context.
PDE provides episode/pullback evidence. Location provides geometric context.
Role provides semantic interpretation and is not an independent evidence vote.
EvidenceAggregator owns aggregation only.

No Phase 2 engine may submit, modify, or close an order.

## 3. State-machine contract

Each engine transition is validated against `spec/transitions.yaml`. The runtime
state graph must be compatible with all reachable implementation transitions.
Terminal episode states may explicitly reset to `PDE_NONE` before a new episode
is started; an invalidated episode is never silently reused as a live episode.

## 4. PDE contract

PDE distinguishes:

- committed impulse anchor and extreme;
- pullback geometry;
- recovery movement from the adverse pullback extreme;
- resumption confirmation by a new directional extreme;
- impulse-origin invalidation;
- episode expiry.

Recovery is not inferred from shallowness alone. A shallow pullback with no
counter-move recovery remains a pullback state.

Pullback depth and recovery are geometric measurements. Structure, Flow, and
Regime are contextual gates and cannot mutate upstream authority.

The original multi-timeframe PRIMARY/SECONDARY/MICRO hierarchy remains a
separate research/architecture boundary until explicit parent/execution
-timeframe mapping exists. It is not guessed from a single-timeframe Phase 2
pipeline.

## 5. Evidence validity

Evidence validity is timeframe-aware and derived from the canonical `Timeframe`
model. Hard-coded five-minute validity is prohibited for Phase 2 state/evidence
objects.

## 6. Durable store contract

Durable ordering is:

1. append immutable bar input to the fsync'd journal;
2. execute the atomic Phase 2 bar transaction;
3. publish the checkpoint.

If step 2 or 3 fails after step 1 succeeds, the store becomes `FAULTED` and
rejects further writes. Recovery replays the authoritative journal, installs
the reconstructed pipeline into the store, and returns it to `ACTIVE` only after
identity, watermark, checkpoint-prefix, and replay validation succeed.

## 7. Determinism

For the same bar prefix, effective configuration, engine versions, and canonical
input identity, replay and continuous execution must converge to the same
causal watermark and equivalent Phase 2 evaluation/state.

## 8. Historical state

Historical evaluations and structural projections are bounded read caches, not
durable recovery authority. Committed history is immutable from downstream
consumers' perspective.

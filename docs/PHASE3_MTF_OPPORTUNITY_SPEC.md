# FRACTAL-FLOW Phase 3 — Multi-Timeframe Behavioral State & Opportunity Construction

Status: **GREEN / IMPLEMENTED / VERIFIED**

## 1. Constitutional boundary

Phase 3 composes committed Phase 2 evaluations into a deterministic multi-timeframe
behavioral hierarchy. It remains informational. It MUST NOT authorize orders, size
positions, allocate portfolio risk, mutate execution state, or bypass Phase 2 engine
authority.

## 2. Canonical topology

```text
CONTEXT       4H
DIRECTION     1H
STRUCTURE    30M
PRIMARY      15M
SECONDARY     5M
CONFIRMATION  1M
EXECUTION     1M
MICRO         1M
```

Dynamic structural migration is versioned and monotonic:

```text
15M PRIMARY -> 5M PRIMARY -> 1M PRIMARY
```

The M1 floor is terminal. Context, Direction and Structure remain fixed.

## 3. Causal contract

For watermark `W`, every selected evaluation is the latest committed evaluation at
or before `W`. Same-timeframe ordering is strictly `(timestamp, sequence)`. Parent
and child timestamps satisfy:

```text
parent_timestamp <= child_timestamp <= W
```

Required roles are CONTEXT, DIRECTION, STRUCTURE, PRIMARY, SECONDARY, CONFIRMATION
and EXECUTION. Missing, future, stale, unusable or contradictory required state
fails closed.

## 4. Semantic fusion

Phase 3 explicitly fuses, without granting new execution authority:

- Flow alignment/contest;
- Regime alignment and TRANSITION state;
- Role alignment;
- Location alignment and BLOCKED state;
- PDE episode, direction, maturity and resumption evidence;
- false-resumption evidence;
- parent/child PDE episode containment;
- MICRO pullback/resumption semantics.

Contradictions are explicit reason codes and prevent opportunity construction.

## 5. Deterministic evidence

`MTFEvidenceSummary` provides bounded directional evidence across FLOW, STRUCTURE,
REGIME, PDE, ROLE and LOCATION families. It records directional bias, family count,
diversity, contradiction, false-resumption risk and model-health state. It is
informational and cannot authorize execution.

## 6. Setup contracts

The setup classifier is deterministic and precedence ordered:

- **FF-01 FLOW_CONTINUATION** — structural direction, active PDE pullback/resumption,
  aligned primary/secondary/confirmation flow and continuation-compatible role.
- **FF-02 COUNTERFLOW** — structurally directional opportunity with explicit
  counterflow role and active PDE evidence.
- **FF-03 RANGE_ROTATION** — aligned RANGE regime, RANGE_ROTATION role and extreme/
  congested location.
- **FF-04 TRANSITION_BREAK** — explicit regime TRANSITION with structural transition
  evidence.

Unclassified combinations fail closed.

## 7. Opportunity corridor and space

The structural corridor is bounded by committed protected structural levels. The
opportunity-space proxy is:

```text
LONG:  (protected_high - close) / ATR
SHORT: (close - protected_low) / ATR
```

Positive ATR and positive structural distance are mandatory. This is a structural
opportunity-space descriptor, not a fill/profit guarantee and not a risk decision.

## 8. Identity, migration and anti-overtrading

Repeated observations of the same episode under the same mapping version reuse the
same opportunity ID and increment its version. Confirmed migration creates a new
identity with `parent_opportunity_id` pointing to the prior opportunity.

Same-episode opposite-direction opportunities are rejected unless a committed
BOS/CHOCH transition confirms the flip. A bounded opportunity budget prevents
uncontrolled repeated opportunity creation.

## 9. Lifecycle and TTL

The lifecycle state machine is explicit:

```text
DISCOVERED -> VALIDATING -> VALID
VALID <-> TRIGGER_READY
VALID/TRIGGER_READY -> DEGRADED | STALE | INVALIDATED | EXPIRED
DEGRADED -> VALID | TRIGGER_READY | STALE | INVALIDATED | EXPIRED
STALE -> VALID | DEGRADED | INVALIDATED | EXPIRED
EXPIRED / INVALIDATED = terminal
```

TTL is deterministic from the authoritative primary timeframe. Terminal states are
sticky. Lifecycle transitions and reason codes are bounded and persisted.

## 10. Persistence and replay

Phase 3 is a derived informational layer and does not create a competing durable
journal. Phase 2 durable journals remain the authoritative source. Phase 3 snapshots
persist mapping history, causal indexes, opportunity identity and version, migration
lineage, hierarchy provenance, lifecycle state/history, TTL and source watermark.
Evidence policy version is persisted and bound to the evidence summary.

For deterministic recovery, the complete Phase 2 durable journal can be replayed into
a fresh Phase 3 orchestrator in causal watermark batches. Opportunities, migrations and
lifecycle transitions are then reconstructed through the same Phase 3 domain machinery.
The resulting identity, lineage, lifecycle, evidence and state hash must equal the
pre-recovery canonical state. Phase 3 snapshot restoration is a convenience checkpoint,
not an independent authority.

## 11. Atomic composite processing

A Phase3Pipeline bar is staged in both layers. Phase2 mutable state is isolated while
bounded append/replace-only caches use safe container-level copy-on-write. Phase3
orchestration stages its own containers. Neither layer becomes committed until both
succeed. Failure injection proves the composite state hash remains unchanged.

## 12. Research boundary

Kalman/NIS/Gyroscope mechanisms remain research-only until preregistered incremental-
information testing demonstrates value without violating deterministic authority.
No ML or research model has execution authority.

## 13. Verification exit criteria

Phase 3 closure requires:

- versioned MTF mapping and complete 15M→5M→1M migration;
- full required-role causal gating;
- parent/child semantic and temporal provenance;
- Flow/Regime/Role/Location/PDE fusion;
- false-resumption and MICRO semantics;
- FF-01..FF-04 deterministic setup contracts;
- bounded evidence aggregation;
- opportunity corridor and structural-space proxy;
- identity/versioning, anti-overtrading and flipping controls;
- lifecycle and TTL enforcement;
- restart/replay identity and lineage continuity;
- composite transaction atomicity;
- deterministic hashing;
- deterministic Phase2 durable-journal → Phase3 replay equivalence;
- migration composite atomicity;
- bounded-lineage preservation under history eviction;
- versioned evidence-policy provenance;
- adversarial tests;
- full-suite coverage verification;
- specification/code/test parity.

# FRACTAL-FLOW: Structure Engine v2 Canonical Specification & Architecture

## 1. Purpose
The Structure Engine v2 is the informational authority for market structure within FRACTAL-FLOW. Its purpose is to detect adaptive volatility-normalized market swings, structural levels (protected highs and lows), structural break events (Break of Structure - BOS, and Change of Character - CHoCH), structural damage, and reclaims without relying on fixed candle-count fractals, magic pip numbers, unconfirmed future information, or unbounded trailing running-extrema.

## 2. Authority Boundaries
Structure is strictly an **informational authority**.
- **Allowed Capabilities**:
  - `WRITE_STRUCTURE_STATE`: Derive and record internal structural state transitions and state envelopes.
  - `OUTPUT_STRUCTURAL_STOP_CANDIDATE`: Compute primary structural level stop loss candidates.
- **Forbidden Operations**:
  - Structure must **NEVER** act as a trading, risk, or execution authority.
  - Structure must **NEVER** directly construct execution intents, submit orders, adjust positions, set trade sizes, or evaluate account risk.

## 3. Inputs & Configuration
The Structure Engine consumes closed-bar observations, local volatility references, and versioned configuration:
- `bar`: Canonical `Bar` (symbol, timeframe, open, high, low, close, timestamps).
- `v_local`: Exact Decimal local volatility reference ($V_{\text{local}}$), computed via ATR-14 or local bar range floor ($V_{\text{local}} \ge \text{min\_v\_local\_floor}$).
- `config`: `StructureConfig` instance defining behavioral parameters:
  - `min_reversal_magnitude`: Minimum volatility-normalized displacement for swing confirmation (default $1.5$).
  - `displacement_threshold_mult`: Volatility multiplier for break confirmation (default $0.5$).
  - `persistence_bars_required`: Consecutive bars required for break persistence (default $2$).
  - `max_swing_history`: Maximum confirmed swings retained in memory (default $20$).
  - `min_v_local_floor`: Absolute minimum floor for $V_{\text{local}}$ (default $0.0001$).
  - `equality_tolerance_pips`: Instrument pip-scaled equality tolerance (default $0.00001$).
  - `atr_stop_buffer_mult`: ATR buffer multiplier for structural stop candidates (default $0.5$).
  - `pivot_neighborhood_bars`: retained only as a backward-compatible configuration field; v2.2 does not use a trailing neighborhood to create or supersede candidates.
  - `max_candidate_lifetime_bars`: Maximum candidate age in bars before expiration if unconfirmed (default $50$).
- Lineage & Provenance: `root_id`, `parent_id`, `parent_version`, `config_version`, `data_version`, `feature_version`.

## 4. State Model
Structure engine maintains three orthogonal state machines registered in `spec/states.yaml` and `spec/transitions.yaml`:
1. `SwingState`: `SWING_NONE` $\rightarrow$ `SWING_CANDIDATE` $\rightarrow$ `SWING_CONFIRMED` $\rightarrow$ `SWING_PROTECTED` $\rightarrow$ `SWING_BROKEN`.
2. `BreakState`: `BREAK_NONE` $\leftrightarrow$ `BREAK_CANDIDATE` $\leftrightarrow$ `BREAK_CONFIRMED` $\leftrightarrow$ `BREAK_ESTABLISHED` / `FAILED_BREAK`.
3. `StructuralDamageState`: `INTACT` $\leftrightarrow$ `DAMAGE_CANDIDATE` $\leftrightarrow$ `STRUCTURE_BROKEN` $\leftrightarrow$ `RECLAIM_CANDIDATE` $\leftrightarrow$ `RECLAIM_CONFIRMED`.

## 5. Structural-Excursion Mathematics (v2.2)

### 5.1 Core distinction
A `PivotCandidate` is **not** a confirmed pivot and is not a global running maximum/minimum. It is the current extreme of one bounded, causally observable **structural excursion**.

The engine separates four timestamps/concepts:
- `created_from_timestamp`: immutable origin of the unresolved excursion.
- `candidate_at`: timestamp of its latest causally observed extreme.
- `confirmed_at`: later timestamp at which reversal evidence satisfies the confirmation contract.
- `effective_from`: timestamp from which the confirmed swing is visible to downstream decisions (`effective_from == confirmed_at`).

A new extreme may extend an unresolved excursion, but it does **not** start a new pivot epoch and does not reset excursion age. Therefore monotonic trends produce one extending hypothesis rather than a sequence of synthetic pivots.

### 5.2 Excursion bootstrap
The first closed observation creates provisional HIGH and LOW extrema. No pivot can be confirmed on that same observation. The provisional owner is selected causally from close-location relative to those two extrema. If the evidence is exactly ambiguous, both provisional candidates remain until the next observation resolves the side.

After a confirmed/expired excursion, a new excursion is initialized from a subsequent observation's directional evidence. There is no look-ahead and no future-bar dependency.

### 5.3 Excursion extension
For a HIGH excursion, a new high extends the excursion only when the bar also provides directional continuation evidence (`close >= previous close`). For a LOW excursion, a new low extends only when `close <= previous close`. A wick that makes a new extreme while closing against the excursion is therefore treated as reversal evidence rather than as a new candidate.

When an excursion extends:
- `created_from_timestamp` is preserved;
- `candidate_at` moves to the new extreme timestamp;
- `price` moves to the new extreme price;
- `candidate_age_bars` increases monotonically;
- the excursion does not become a confirmed swing merely because its extreme moved.

This is intentionally different from both a fixed-window fractal and an unbounded `max(highs)`/`min(lows)` implementation. The authority is a bounded state-machine object with an explicit origin, age, extension rule, and expiry.

### 5.4 Causal reversal confirmation
For a HIGH excursion:
\[
D_{high} = P_{excursion\_high} - Close_t
\]
For a LOW excursion:
\[
D_{low} = Close_t - P_{excursion\_low}
\]

The normalized reversal magnitude is:
\[
M = D / V_{local}
\]

A candidate is confirmed only when:
1. it has existed beyond its creation observation;
2. the reversal displacement is positive; and
3. `M >= min_reversal_magnitude`.

The confirmed swing records the excursion's latest extreme price/timestamp, while `confirmed_at` remains the later causal observation.

### 5.5 Candidate expiry
If an unresolved excursion reaches `candidate_age_bars > max_candidate_lifetime_bars`, the excursion is invalidated. The engine does not silently recreate a fresh candidate from the same observation after expiry. A later observation must establish a new excursion.

### 5.6 Structural invariants
The v2.2 contract requires:
- monotonic trends produce no confirmed swings without reversal evidence;
- repeated new highs/lows within one excursion do not create repeated pivots;
- a shallow reversal below the normalized threshold does not confirm;
- a genuine reversal confirms only from information available at its confirmation timestamp;
- confirmed swing records are immutable historical facts;
- no protected level may originate from an unconfirmed excursion;
- equal-strength simultaneous HIGH/LOW confirmation remains unresolved rather than arbitrarily ordered;
- bounded candidate age and bounded swing history remain enforced.

### 5.7 Persistence and forensic state
`StructureEngine.authoritative_state()` is the canonical bounded state surface for causal-prefix and recovery testing. It includes configuration, candidates, active excursion ownership, recent bars, version guards, timestamps, persistence counters, structural records, and the last transition record. `snapshot_state()` serializes this complete surface under schema `structure-engine-v2.2`.

## 5.8 Deprecated local-neighborhood semantics
`pivot_neighborhood_bars` remains accepted solely for backward-compatible configuration/snapshot loading. It is **not** used by the v2.2 structural algorithm. No correctness claim may depend on a trailing local-dominance window.

## 6. Structural Ownership — Single Canonical Authority
Structural trend ownership is derived exclusively from canonical paired active confirmed structural swings. Zero heuristic fallbacks exist.

| Active High Classification | Active Low Classification | Structural Ownership |
|---|---|---|
| `HH` | `HL` | `BULLISH` |
| `HH` | `EQUAL_LOW` | `BULLISH` |
| `EQUAL_HIGH` | `HL` | `BULLISH` |
| `LL` | `LH` | `BEARISH` |
| `EQUAL_LOW` | `LH` | `BEARISH` |
| `EQUAL_HIGH` | `EQUAL_LOW` | `AMBIGUOUS` (consolidation/plateau) |
| `HH` | `LL` | `AMBIGUOUS` (expansion/divergence) |
| `LH` | `HL` | `AMBIGUOUS` (contraction/triangle) |
| *Any* | Missing Low | `UNKNOWN` |
| Missing High | *Any* | `UNKNOWN` |
| `NEUTRAL` | *Any* | `AMBIGUOUS` |
| *Any* | `NEUTRAL` | `AMBIGUOUS` |

## 7. Exact BOS/CHoCH Truth Table
When a structural break is confirmed ($\text{LevelCross} \times \text{DisplacementConfirmation} \times \text{PersistenceConfirmation}$):

| Ownership | Broken Level Type | Structural Break Result | Structural Action |
|---|---|---|---|
| `BULLISH` | `HIGH` | `BOS_BULLISH` | Structure Intact (Continuation) |
| `BULLISH` | `LOW` | `CHOCH_BEARISH` | Structure Broken (Damage & Direction Change) |
| `BEARISH` | `LOW` | `BOS_BEARISH` | Structure Intact (Continuation) |
| `BEARISH` | `HIGH` | `CHOCH_BULLISH` | Structure Broken (Damage & Direction Change) |
| `AMBIGUOUS` | `HIGH` | `NONE` | No Break Action |
| `AMBIGUOUS` | `LOW` | `NONE` | No Break Action |
| `UNKNOWN` | `HIGH` | `NONE` | No Break Action |
| `UNKNOWN` | `LOW` | `NONE` | No Break Action |

## 8. Confirmation, Damage, Failed Breaks & Reclaim Semantics
- **Continuation BOS Non-Destruction**: A `BOS_BULLISH` or `BOS_BEARISH` break confirms structural continuation and leaves `damage_state = INTACT`.
- **CHoCH Structural Damage**: A `CHOCH_BEARISH` or `CHOCH_BULLISH` break sets `damage_state = STRUCTURE_BROKEN`, `swing_state = SWING_BROKEN`, records a `ChangeOfCharacter` event, and updates direction.
- **Failed Break**: Occurs when `LevelCross` occurs without displacement/persistence confirmation, and subsequent bar closes back inside the protected level (`BREAK_CANDIDATE` $\rightarrow$ `FAILED_BREAK`), recording a `FailedBreak` event.
- **Reclaim State Machine**: `STRUCTURE_BROKEN` / `DAMAGE_CANDIDATE` $\rightarrow$ `RECLAIM_CANDIDATE` $\rightarrow$ `RECLAIM_CONFIRMED` $\rightarrow$ `INTACT`, emitting explicit `ReclaimEvent` objects and re-arming protected levels.

## 9. Protected Level Authority & Stale Level Invalidation
`protected_high` and `protected_low` derive exclusively from active confirmed structural swings via `_rearm_protected_levels()`. Unconfirmed candidates, current bar extremes, or arbitrary running extrema can NEVER become protected levels.

`_rearm_protected_levels()` explicitly enforces protected level authority and state-complete integrity:
- If a valid active confirmed High swing exists, `protected_high = high_swings[-1].price`.
- If no valid active confirmed High swing exists (or if it is invalidated/marked broken/evicted), `protected_high` is explicitly set to `None`.
- If a valid active confirmed Low swing exists, `protected_low = low_swings[-1].price`.
- If no valid active confirmed Low swing exists (or if it is invalidated/marked broken/evicted), `protected_low` is explicitly set to `None`.

Stale protected levels are never permitted to persist after the corresponding authoritative swing disappears or is broken.

## 10. Bounded-History Policy
- Active confirmed swings are bounded by `max_swing_history` (default 20).
- Eviction policy: Deterministic FIFO eviction, prioritizing eviction of broken/invalidated swings (`status == SWING_BROKEN`) before oldest confirmed swings.

## 11. Temporal Semantics & Causality
- **No Lookahead**: Future bars never alter past confirmed swings or structural states.
- `get_confirmed_swings(decision_timestamp)` returns strictly those swings where $\text{effective\_from} \le \text{decision\_timestamp}$.
- Monotonic timestamps: Incoming bar timestamps prior to active `last_timestamp` trigger strict fail-closed `ValueError`.
- Duplicate timestamp handling: Identical bars at duplicate timestamps are handled idempotently; conflicting bars at duplicate timestamps are rejected.

## 12. Provenance & Determinism
Every state output produces a `StructureTransitionRecord` convertible to `StateEnvelope` containing:
`root_id`, `parent_id`, `parent_version`, `version`, `configuration_version`, `data_version`, `feature_version`, `timestamp`, `valid_until`, `authority`.

Given identical bar sequences, $V_{\text{local}}$, and provenance metadata, Structure Engine produces 100% byte-identical state transitions, active swing records, break events, and `StateEnvelope` instances across runs and process restarts.

## 13. Persistence & Recovery
Structure Engine state can be serialized as a lossless, JSON-safe snapshot and reconstructed into a fresh engine.
The snapshot includes bounded recent bars, candidate objects, confirmed/broken swings, protected levels, persistence
counters, provenance/version guards, and the last transition record. The generic `SnapshotEngine` provides durable
checksum/state-hash persistence for this payload. Event-journal replay remains a separate integration concern and is
not claimed here as a StructureEngine-native reducer.

## 14. Failure Modes
Structure Engine fails closed on:
1. Symbol mismatch between bar and engine.
2. Parent identity discontinuity or version regression.
3. Chronology violation (backward timestamp).
4. Duplicate timestamp with conflicting bar data.
5. Missing or revoked runtime `AuthorityMatrix` capability.

## 15. Invariants
- **INVARIANT-STRUCT-001**: Structural confirmation requires LevelCross $\times$ DisplacementConfirmation $\times$ PersistenceConfirmation.
- **INVARIANT-STRUCT-002**: Swing detection is causal; future bars do not mutate past confirmed swings.
- **INVARIANT-STRUCT-003**: High and low persistence counters and candidate lifecycles are isolated to prevent cross-contamination.
- **INVARIANT-STRUCT-004**: State capacity is bounded by deterministic eviction policy.
- **INVARIANT-STRUCT-005**: Running extrema tracking is forbidden; candidates are immutable local pivots.

## 16. Explicit Non-Goals
- Structure Engine will NOT generate trading signals, calculate position sizes, or execute orders.
- Structure Engine will NOT implement multi-timeframe aggregation internally; each timeframe runs an isolated `StructureEngine` instance.

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
  - `pivot_neighborhood_bars`: Preceding bars required to establish candidate local dominance (default $1$).
  - `max_candidate_lifetime_bars`: Maximum candidate age in bars before expiration if unconfirmed (default $50$).
- Lineage & Provenance: `root_id`, `parent_id`, `parent_version`, `config_version`, `data_version`, `feature_version`.

## 4. State Model
Structure engine maintains three orthogonal state machines registered in `spec/states.yaml` and `spec/transitions.yaml`:
1. `SwingState`: `SWING_NONE` $\rightarrow$ `SWING_CANDIDATE` $\rightarrow$ `SWING_CONFIRMED` $\rightarrow$ `SWING_PROTECTED` $\rightarrow$ `SWING_BROKEN`.
2. `BreakState`: `BREAK_NONE` $\leftrightarrow$ `BREAK_CANDIDATE` $\leftrightarrow$ `BREAK_CONFIRMED` $\leftrightarrow$ `BREAK_ESTABLISHED` / `FAILED_BREAK`.
3. `StructuralDamageState`: `INTACT` $\leftrightarrow$ `DAMAGE_CANDIDATE` $\leftrightarrow$ `STRUCTURE_BROKEN` $\leftrightarrow$ `RECLAIM_CANDIDATE` $\leftrightarrow$ `RECLAIM_CONFIRMED`.

## 5. Bounded Causal Local-Pivot Mathematics

### 5.1 Local Dominance & Candidate Creation
A candidate pivot represents a specific, immutable historical bar $B_c$ (observed at timestamp $t_c$ with exact price $P_c$). Running extrema (`candidate_price = max(candidate_price, bar.high)`) are strictly forbidden.

- **HIGH Candidate Creation**:
  At bar $B_t$ (time $t$), $B_t$ satisfies local high dominance if:
  $$B_t.\text{high} \ge B_j.\text{high} \quad \forall j \in [t - N_{\text{pivot}}, t - 1]$$
  where $N_{\text{pivot}} = \text{pivot\_neighborhood\_bars}$.
  If $B_t$ satisfies local dominance:
  1. If no active HIGH candidate exists: Create new `PivotCandidate` with $\text{price} = B_t.\text{high}$, $\text{candidate\_at} = t$, $\text{age} = 0$.
  2. If active HIGH candidate $C_{\text{high}}$ exists:
     - If $B_t.\text{high} > C_{\text{high}}.\text{price}$: $C_{\text{high}}$ is **superseded** by $B_t$. A new `PivotCandidate` is instantiated with $\text{price} = B_t.\text{high}$, $\text{candidate\_at} = t$, $\text{age} = 0$.
     - If $B_t.\text{high} \le C_{\text{high}}.\text{price}$: $C_{\text{high}}$ remains active without price or timestamp mutation. Its candidate age increments: $\text{age} \leftarrow \text{age} + 1$.

- **LOW Candidate Creation**:
  At bar $B_t$ (time $t$), $B_t$ satisfies local low dominance if:
  $$B_t.\text{low} \le B_j.\text{low} \quad \forall j \in [t - N_{\text{pivot}}, t - 1]$$
  If $B_t$ satisfies local dominance:
  1. If no active LOW candidate exists: Create new `PivotCandidate` with $\text{price} = B_t.\text{low}$, $\text{candidate\_at} = t$, $\text{age} = 0$.
  2. If active LOW candidate $C_{\text{low}}$ exists:
     - If $B_t.\text{low} < C_{\text{low}}.\text{price}$: $C_{\text{low}}$ is **superseded** by $B_t$. A new `PivotCandidate` is instantiated with $\text{price} = B_t.\text{low}$, $\text{candidate\_at} = t$, $\text{age} = 0$.
     - If $B_t.\text{low} \ge C_{\text{low}}.\text{price}$: $C_{\text{low}}$ remains active without price or timestamp mutation. Its candidate age increments: $\text{age} \leftarrow \text{age} + 1$.

### 5.2 Candidate Invalidation & Expiration
If an active candidate reaches $\text{age} > \text{max\_candidate\_lifetime\_bars}$ without achieving reversal confirmation or supersession, it is **invalidated** and discarded, resetting candidate state to seek the next local pivot.

### 5.3 Candidate Confirmation
A candidate pivot $C$ is confirmed strictly via causal volatility-normalized reversal displacement measured from its fixed price $P_c$:
$$\text{ReversalDisplacement}_{\text{HIGH}} = C_{\text{high}}.\text{price} - B_t.\text{close}$$
$$\text{ReversalDisplacement}_{\text{LOW}} = B_t.\text{close} - C_{\text{low}}.\text{price}$$
$$\text{ReversalMagnitude} = \frac{\text{ReversalDisplacement}}{V_{\text{local}}}$$

When $\text{ReversalMagnitude} \ge \text{min\_reversal\_magnitude}$:
The candidate becomes a confirmed `SwingRecord` with:
- `candidate_at` $= t_c$ (exact timestamp of candidate bar $B_c$)
- `confirmed_at` $= t$ (timestamp of confirmation bar $B_t$)
- `effective_from` $= t$ ($\text{effective\_from} == \text{confirmed\_at} \ge \text{candidate\_at}$)
- `price` $= P_c$
- Candidate state resets to `None` upon confirmation.

### 5.4 Independent Lifecycles
HIGH and LOW candidate lifecycles, candidate objects, and persistence counters are strictly independent. Confirmation of a HIGH candidate occurs independently of LOW candidate state and vice versa.

### 5.5 Swing Classifications
Confirmed swings are classified relative to the prior confirmed swing of the same direction:
- `HH` (Higher High): High swing price > previous confirmed High swing price + tolerance.
- `LH` (Lower High): High swing price < previous confirmed High swing price - tolerance.
- `EQUAL_HIGH`: $| \text{price} - \text{prev\_high} | \le \text{equality\_tolerance\_pips}$.
- `HL` (Higher Low): Low swing price > previous confirmed Low swing price + tolerance.
- `LL` (Lower Low): Low swing price < previous confirmed Low swing price - tolerance.
- `EQUAL_LOW`: $| \text{price} - \text{prev\_low} | \le \text{equality\_tolerance\_pips}$.
- `NEUTRAL`: First swing in direction.

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
Structure Engine state can be snapshotted and reconstructed via event journal replay:
$$\text{ReconstructedState} = \text{Snapshot} + \text{ReplayedBarSequence}$$

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

# FRACTAL-FLOW: Structure Engine v2 Canonical Specification & Architecture

## 1. Purpose
The Structure Engine v2 is the informational authority for market structure within FRACTAL-FLOW. Its purpose is to detect adaptive volatility-normalized market swings, structural levels (protected highs and lows), structural break events (Break of Structure - BOS, and Change of Character - CHoCH), structural damage, and reclaims without relying on fixed candle-count fractals, magic pip numbers, or unconfirmed future information.

## 2. Authority Boundaries
Structure is strictly an **informational authority**.
- **Allowed Capabilities**:
  - `WRITE_STRUCTURE_STATE`: Derive and record internal structural state transitions and state envelopes.
  - `OUTPUT_STRUCTURAL_STOP_CANDIDATE`: Compute primary structural level stop loss candidates.
- **Forbidden Operations**:
  - Structure must **NEVER** act as a trading, risk, or execution authority.
  - Structure must **NEVER** directly construct execution intents, submit orders, adjust positions, set trade sizes, or evaluate account risk.

## 3. Inputs
The Structure Engine consumes closed-bar observations and local volatility references:
- `bar`: Canonical `Bar` (symbol, timeframe, open, high, low, close, timestamps).
- `v_local`: Exact Decimal local volatility reference ($V_{\text{local}}$), computed via ATR-14 or local bar range floor ($V_{\text{local}} \ge \text{min\_v\_local\_floor}$).
- Lineage & Provenance: `root_id`, `parent_id`, `parent_version`, `config_version`, `data_version`, `feature_version`.

## 4. State Model
Structure engine maintains three orthogonal state machines registered in `spec/states.yaml` and `spec/transitions.yaml`:
1. `SwingState`: `SWING_NONE` $\rightarrow$ `SWING_CANDIDATE` $\rightarrow$ `SWING_CONFIRMED` $\rightarrow$ `SWING_PROTECTED` $\rightarrow$ `SWING_BROKEN`.
2. `BreakState`: `BREAK_NONE` $\leftrightarrow$ `BREAK_CANDIDATE` $\leftrightarrow$ `BREAK_CONFIRMED` $\leftrightarrow$ `BREAK_ESTABLISHED` / `FAILED_BREAK`.
3. `StructuralDamageState`: `INTACT` $\leftrightarrow$ `DAMAGE_CANDIDATE` $\leftrightarrow$ `STRUCTURE_BROKEN` $\leftrightarrow$ `RECLAIM_CANDIDATE` $\leftrightarrow$ `RECLAIM_CONFIRMED`.

## 5. Pivot Model
Swings are detected adaptively using volatility-normalized reversal displacement:
$$\text{SwingReversalMagnitude} = \frac{\text{ReversalDisplacement}}{V_{\text{local}}}$$
A swing candidate requires $\text{SwingReversalMagnitude} \ge \text{min\_reversal\_magnitude}$ (default 1.5).
- **Pivot Timestamps**:
  - `pivot_timestamp`: Exact timestamp of the extreme bar where the pivot occurred.
  - `confirmed_at`: Timestamp of the bar where reversal magnitude was confirmed.
  - `effective_from`: Causal timestamp when the swing becomes visible downstream ($\text{effective\_from} \ge \text{confirmed\_at} > \text{pivot\_timestamp}$). In M1 closed-bar architecture, $\text{effective\_from} == \text{confirmed\_at}$.
- **Swing Classifications**:
  - `HH` (Higher High): High swing price > previous confirmed High swing price.
  - `LH` (Lower High): High swing price < previous confirmed High swing price.
  - `HL` (Higher Low): Low swing price > previous confirmed Low swing price.
  - `LL` (Lower Low): Low swing price < previous confirmed Low swing price.
  - `NEUTRAL`: First swing or unclassified.

## 6. Progression Model
Directional progression tracks market structure breaks and character changes:
- `BOS_BULLISH` / `BOS_BEARISH`: Continuation break of protected level in line with current dominant structural direction.
- `CHOCH_BULLISH` / `CHOCH_BEARISH`: Change of Character break reversing the structural direction.

## 7. Confirmation Semantics
A structural break is confirmed if and only if three conditions hold simultaneously:
$$\text{StructuralBreak} = \text{LevelCross} \times \text{DisplacementConfirmation} \times \text{PersistenceConfirmation}$$
- `LevelCross`: Bar close exceeds protected high or falls below protected low.
- `DisplacementConfirmation`: $\text{Displacement} \ge \text{displacement\_threshold\_mult} \times V_{\text{local}}$.
- `PersistenceConfirmation`: Number of consecutive displacement-confirming bars reaches $\text{persistence\_bars\_required}$ (default 2). High and Low levels maintain isolated persistence counters (`high_persistence_counter`, `low_persistence_counter`).

## 8. Invalidation & Reclaim Semantics
- **Structural Invalidation**: Occurs when a confirmed break damages a protected level (`damage_state = STRUCTURE_BROKEN`).
- **Failed Break**: Occurs when `LevelCross` occurs without displacement/persistence confirmation, and subsequent bar closes back inside the protected level (`BREAK_CANDIDATE` $\rightarrow$ `FAILED_BREAK`).
- **Reclaim State Machine**: `STRUCTURE_BROKEN` / `DAMAGE_CANDIDATE` $\rightarrow$ `RECLAIM_CANDIDATE` $\rightarrow$ `RECLAIM_CONFIRMED` $\rightarrow$ `INTACT`. Explicit `ReclaimEvent` objects record reclaimed price and timestamp.

## 9. Bounded-History Policy
To prevent unbounded memory growth and the historical-extrema flaw:
- Active confirmed swings are bounded by `max_swing_history` (default 20).
- Eviction policy: Deterministic FIFO eviction, prioritizing eviction of broken/invalidated swings (`status == SWING_BROKEN`) before oldest confirmed swings.

## 10. Temporal Semantics & Causality
- **No Lookahead**: Future bars never alter past confirmed swings or structural states.
- `get_confirmed_swings(decision_timestamp)` returns strictly those swings where $\text{effective\_from} \le \text{decision\_timestamp}$.
- Monotonic timestamps: Incoming bar timestamps prior to active `last_timestamp` trigger strict fail-closed `ValueError`.
- Duplicate timestamp handling: Identical bars at duplicate timestamps are handled idempotently; conflicting bars at duplicate timestamps are rejected.

## 11. Provenance
Every state output produces a `StructureTransitionRecord` convertible to `StateEnvelope` containing:
`root_id`, `parent_id`, `parent_version`, `version`, `configuration_version`, `data_version`, `feature_version`, `timestamp`, `valid_until`, `authority`.

## 12. Versioning
- `state_version` increments strictly monotonically on every processed bar.
- `parent_version` and `data_version` regression triggers fail-closed error.
- `config_version` mismatch triggers fail-closed error.

## 13. Determinism
Given identical bar sequences, $V_{\text{local}}$, and provenance metadata, Structure Engine produces 100% byte-identical state transitions, active swing records, break events, and `StateEnvelope` instances across runs and process restarts.

## 14. Persistence & Recovery
Structure Engine state can be snapshotted and reconstructed via event journal replay:
$$\text{ReconstructedState} = \text{Snapshot} + \text{ReplayedBarSequence}$$

## 15. Causality Verification
Verified via `CausalTestFramework`: decision state at $t$ remains invariant under future price spikes, crashes, spread explosions, volatility shocks, and news events.

## 16. Flow Interface
Structure Engine provides pure structural evidence to Flow Engine:
- Exposed via `get_confirmed_swings(decision_timestamp)`, `protected_high`, `protected_low`, `bos_type`, `last_choch`, `last_failed_break`, `last_reclaim`.
- Structure progression metrics ($\text{structure\_progression} \in [-1.0, 1.0]$) feed into `FlowEvidence` without Flow altering structural authority.

## 17. PDE Interface
Structure Engine provides upstream structural facts to the downstream Partial Differential Equation (PDE) engine:
- Directional anchors (`protected_high`, `protected_low`).
- Pivot locations for pullback depth and displacement calculations.
- Structural invalidation events for resetting PDE impulse states.

## 18. Failure Modes
Structure Engine fails closed on:
1. Symbol mismatch between bar and engine.
2. Parent identity discontinuity or version regression.
3. Chronology violation (backward timestamp).
4. Duplicate timestamp with conflicting bar data.
5. Missing or revoked runtime `AuthorityMatrix` capability.

## 19. Invariants
- **INVARIANT-STRUCT-001**: Structural confirmation requires LevelCross $\times$ DisplacementConfirmation $\times$ PersistenceConfirmation.
- **INVARIANT-STRUCT-002**: Swing detection is causal; future bars do not mutate past confirmed swings.
- **INVARIANT-STRUCT-003**: High and low persistence counters are isolated to prevent cross-contamination.
- **INVARIANT-STRUCT-004**: State capacity is bounded by deterministic eviction policy.

## 20. Explicit Non-Goals
- Structure Engine will NOT generate trading signals, calculate position sizes, or execute orders.
- Structure Engine will NOT implement multi-timeframe aggregation internally; each timeframe runs an isolated `StructureEngine` instance.

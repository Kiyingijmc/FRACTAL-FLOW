# Phase 2 PDE Formal Transition Specification

## Authority boundary

PDE is the informational authority for the evolving price-dynamics episode and
its pullback/recovery evidence. Structure remains committed structural truth.
PDE reads Structure ownership, Flow pressure and Regime context but never
mutates or rewrites those upstream authorities.

The implementation deliberately treats **Price Dynamics Episode** as the
current Phase 2 runtime abstraction. The original multi-timeframe **Pullback
Detection Engine** specification remains the research/architecture target for
parent/execution-timeframe hierarchy and is not silently approximated inside a
single-timeframe pipeline.

## Episode initiation

From `PDE_NONE`, `PDE_INVALIDATED`, `PDE_FOLLOW_THROUGH`, or
`PDE_RESUMPTION_FAILED`, the engine explicitly resets to `PDE_NONE` and then
attempts a new episode using the previous close as anchor when available,
otherwise the current bar open.

`impulse = |close - anchor| / max(v_local, epsilon)`.

An episode begins only when `impulse >= min_impulse` and the close differs from
the anchor.

## Committed impulse extreme

Before a pullback begins, a directional close can extend the committed episode
extreme. Once a pullback candidate exists, the committed impulse extreme is
frozen for the pullback lifecycle. This prevents the denominator/reference
point from moving while pullback evidence is being evaluated.

## Pullback depth

For LONG episodes:

`depth = clamp((extreme - close) / impulse_amplitude, 0, 1)`.

For SHORT episodes:

`depth = clamp((close - extreme) / impulse_amplitude, 0, 1)`.

`impulse_amplitude = |extreme - anchor|` is committed when the episode enters
the pullback lifecycle. The directional extreme may extend while the episode is
in `PDE_IMPULSE`; once pullback evidence begins, that extreme and its amplitude
are frozen for the pullback lifecycle. Current volatility therefore cannot
retroactively rescale historical pullback depth.

A close crossing the impulse origin invalidates the episode instead of being
reclassified as a deeper pullback.

## Recovery movement

Recovery is **not** defined as `1 - depth`.

The engine retains the adverse pullback extreme and measures actual movement
back toward the committed impulse extreme.

For LONG:

`recovery = clamp((close - pullback_extreme) / (extreme - pullback_extreme), 0, 1)`.

For SHORT:

`recovery = clamp((pullback_extreme - close) / (pullback_extreme - extreme), 0, 1)`.

Recovery is a geometric counter-movement descriptor. It is intentionally not
normalized by current volatility, so volatility changes cannot retroactively
change the recovery ratio of an established episode.

Therefore a shallow or flat pullback does not automatically become a recovery.
A recovery threshold requires observable counter-move progress.

## Current displacement

Current displacement remains volatility-normalized and is distinct from episode
geometry:

`displacement = |close - extreme| / v_local`.

Thus `v_local` is used for impulse qualification and current displacement, while
committed episode geometry governs pullback depth and recovery.

## State transitions

The canonical transition registry and runtime implementation agree on the
reachable lifecycle:

| Current | Condition | Next |
|---|---|---|
| `PDE_NONE` | qualifying impulse | `PDE_IMPULSE` |
| `PDE_IMPULSE` | depth >= `pullback_min` | `PDE_PULLBACK_CANDIDATE` |
| `PDE_PULLBACK_CANDIDATE` | candidate remains valid and depth persists | `PDE_PULLBACK_ACTIVE` |
| `PDE_PULLBACK_ACTIVE` | geometric depth >= `pullback_max` | `PDE_DEEPENING` |
| active pullback | depth/pressure weakens | `PDE_WEAKENING` / `PDE_STRENGTHENING` |
| active pullback | actual geometric recovery >= `recovery_threshold` and compatible context | `PDE_RESUMPTION_IN_PROGRESS` |
| deep pullback | geometric depth >= `pullback_max` | `DISPLACEMENT_CANDIDATE` resumption state; adverse context is recorded as evidence, not required for `PDE_DEEPENING` |
| `PDE_RESUMPTION_IN_PROGRESS` | new directional extreme | `PDE_FOLLOW_THROUGH` |
| `PDE_RESUMPTION_IN_PROGRESS` | adverse pressure/deep failure | `PDE_RESUMPTION_FAILED` |
| any active episode | origin broken or maximum maturity exceeded | `PDE_INVALIDATED` |

Terminal episode states explicitly reset before new episode detection; the
runtime never relies on an unregistered terminal-to-impulse jump.

## Context authority

Structure ownership, Regime state, and Flow imbalance are contextual gates and
confirmation evidence. They cannot mutate upstream state. The Phase 2 pipeline
passes canonical `structural_ownership` downstream rather than maintaining a
second structural-direction authority.

## Evidence validity

PDE evidence validity is derived from the canonical `Timeframe` model rather
than a fixed five-minute constant:

`valid_until = close_timestamp + timeframe_seconds * default_validity_bars`.

## Determinism requirements

All thresholds are immutable configuration parameters and are included in the
canonical Phase 2 effective configuration identity. Replay of the same closed
bar prefix under the same configuration and engine versions must reconstruct
identical PDE state, episode identity, version, causal watermark, and transition
outcome.

## Explicit research boundary

The original `docs/06_PULLBACK_ENGINE.md` additionally specifies:

- PRIMARY → SECONDARY → MICRO hierarchy;
- explicit parent/execution-timeframe mapping;
- impulse-quality vector;
- pullback maturity model;
- false-resumption risk;
- parent-state gating and opportunity migration.

Those features require explicit multi-timeframe/parent lineage contracts. They
are therefore **not guessed or hard-coded into the single-timeframe Phase 2
runtime**. They remain the next research/architecture gate before downstream
Opportunity/Tradeability authority is built.

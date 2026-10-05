# Phase 2 PDE Formal Transition Specification

## Authority boundary
PDE is the authority for the evolving Price Dynamics Episode. Structure remains
committed structural truth. PDE episode state must never mutate or rewrite
Structure history.

## Primitive episode initiation
From `PDE_NONE`, `PDE_INVALIDATED`, `PDE_FOLLOW_THROUGH`, or
`PDE_RESUMPTION_FAILED`, define the anchor as the previous close when available,
otherwise the current bar open. Let:

`impulse = |close - anchor| / max(v_local, epsilon)`.

An episode begins iff `impulse >= min_impulse` and the close differs from the
anchor. Direction is LONG for positive displacement and SHORT for negative.

## Pullback depth
For LONG episodes:

`depth = max(0, (extreme - close) / max(v_local, extreme - anchor))`.

For SHORT episodes:

`depth = max(0, (close - extreme) / max(v_local, anchor - extreme))`.

`recovery = 1 - min(1, depth)`.

## State transitions
The implementation enforces these transition families through the global state
registry. The semantic qualification is:

| Current | Condition | Next |
|---|---|---|
| IMPULSE | depth >= pullback_min | PULLBACK_CANDIDATE |
| PULLBACK_CANDIDATE | next episode bar | PULLBACK_ACTIVE |
| PULLBACK_ACTIVE | depth >= pullback_max | DEEPENING |
| PULLBACK_ACTIVE | otherwise | WEAKENING |
| WEAKENING/DEEPENING | recovery >= recovery_threshold, flow/structure/regime compatible | RESUMPTION_IN_PROGRESS |
| WEAKENING/DEEPENING | depth >= pullback_max and adverse flow/structure/regime | DISPLACEMENT_CANDIDATE (resumption state) |
| RESUMPTION_IN_PROGRESS | new directional extreme | FOLLOW_THROUGH |
| RESUMPTION_IN_PROGRESS | adverse flow with recovery < 0.5 | RESUMPTION_FAILED |
| any active episode | bars >= max_episode_bars | INVALIDATED |

SHORT-side conditions are directionally symmetric.

## Context authority
Structure direction and Regime state are contextual gates on PDE recovery and
displacement. Flow imbalance is the directional confirmation signal. None of
these inputs can mutate upstream engine state.

## Determinism requirements
All thresholds are immutable configuration parameters and therefore part of the
canonical Phase 2 effective configuration identity. Replay of the same closed-bar
prefix under the same effective configuration must reconstruct identical PDE
state, episode identity, version, and transition outcome.

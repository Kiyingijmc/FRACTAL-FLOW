# Phase 2 State-Machine Reconciliation

This document records the post-v2.3.4 runtime reconciliation of the Phase 2
state machines.

## PDEState

The implementation and canonical transition registry now agree on the
reachable lifecycle, including explicit terminal reset paths:

`NONE → IMPULSE → PULLBACK_CANDIDATE → PULLBACK_ACTIVE → WEAKENING / STRENGTHENING / DEEPENING → RESUMPTION_IN_PROGRESS → FOLLOW_THROUGH`

Invalidation and failed resumption can return to `NONE` before a new episode.
An impulse-origin violation produces `INVALIDATED` rather than attempting to
interpret the broken impulse as a pullback.

## PDEResumptionState

Recovery evidence is distinct from resumption confirmation. Recovery requires
actual movement away from the adverse pullback extreme. A new directional
extreme is required for `RESUMPTION_CONFIRMED` / `FOLLOW_THROUGH`.

## RoleState / LocationState

The registry allows direct semantic reclassification paths that are reachable
from their input predicates, while still rejecting unknown/undefined states.
This prevents ordinary market-state changes from becoming runtime exceptions.

## Structure

Structure v2.3 now has an explicit alternation guard for its V23 facade: an
uninterrupted same-side candidate is treated as an excursion extension rather
than a second confirmed structural swing. The legacy `StructureEngine` retains
its historical behavior for compatibility.

Break lifecycle fixes:

- a confirmed break can recover from `FAILED_BREAK` into `BREAK_CONFIRMED`;
- displacement without persistence remains a `BREAK_CANDIDATE`;
- a fallback can therefore produce a genuine `FAILED_BREAK` rather than an
  orphan reclaim.

`structural_ownership` is the canonical downstream structural authority.

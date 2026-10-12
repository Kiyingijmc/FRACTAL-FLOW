# Phase 2 v2.3 Durable Recovery Boundary

## Purpose

Phase 2 engine internals are not treated as a durable source of truth. In-memory
continuation snapshots remain useful for deterministic testing, but restart
recovery is now based on immutable closed-bar input events.

## Durable ordering

For each accepted closed bar:

1. Validate bar closure, symbol/timeframe identity, and causal watermark.
2. Append a `PHASE2_BAR_INPUT` event to the durable journal and fsync it.
3. Mutate the in-memory `Phase2Pipeline` deterministically.
4. Publish an explicit checkpoint containing only pipeline identity and causal
   checkpoint metadata.

If the process fails after journal fsync but before checkpoint publication, the
journal remains sufficient for recovery.

## Recovery authority

`Phase2DurableStore.recover()` creates a fresh pipeline from the explicit
identity carried by the journal and replays the complete Phase 2 bar stream.
The checkpoint is an integrity/checkpoint artifact, not the authoritative engine
state. A missing checkpoint therefore does not prevent recovery when the journal
contains a valid input stream.

Recovery fails closed on:

- journal aggregate-version gaps;
- unexpected event types;
- missing or malformed bar payloads;
- pipeline/configuration identity divergence;
- checkpoint ahead of the durable journal;
- unsupported checkpoint schema;
- recovered causal watermark divergence.

## Architectural consequence

The bounded `Phase2Pipeline._historical_evaluations` map remains a projection
cache. It is not required for restart recovery and is never treated as durable
truth.

This closes the immediate Phase 2 persistence gap without serializing engine
`__dict__` objects as a restart contract. Explicit engine-level DTO snapshots
remain a separate hardening task where direct engine-state checkpointing is
needed for performance rather than correctness.

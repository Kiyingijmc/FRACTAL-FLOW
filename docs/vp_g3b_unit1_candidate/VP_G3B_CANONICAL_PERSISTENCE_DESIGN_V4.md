# FRACTAL-FLOW Volume Profile G3b — Canonical Persistence Contract Freeze (V4)

**Status:** Design/contract freeze candidate only. No repository code changed by this artifact. Not implementation evidence and not G3b closure.
**Authority:** `ANALYTICAL_ONLY`; no trading, risk, order, broker, or execution authority.
**Evidence basis:** User-supplied source inspection output from `src/fractal_flow/domain/event.py`, `src/fractal_flow/domain/market.py`, `src/fractal_flow/persistence/journal.py`, `src/fractal_flow/persistence/phase2.py`, and the G3b resolver/tests. Repository state is represented only by the supplied command output, not an independent live checkout.

## 1. Determination

G3b currently has a pure in-memory revision resolver. The durable integration should reuse `Event` and `DurableEventJournal`, and must not introduce a second journal format or make a checkpoint authoritative. The first implementation slice should be a narrowly scoped Volume Profile revision codec and adapter.

This V4 freezes source-backed facts and proposes explicit decisions for Unit 0. It does not claim that the proposals are implemented or that the HPL has passed.

## 2. Source-backed facts

1. Canonical `Event` timestamps are integer fields with ordering `source_timestamp <= event_timestamp <= processing_timestamp`. The model itself does not declare their units.
2. `Bar.close_timestamp` is documented as UTC epoch seconds, and Phase 2 uses it directly in canonical `Event` timestamp fields.
3. `ProfileRevision.available_at_ns` and `ProfileEvent.event_time_ns` are nanosecond-domain values in the VP research contract. Their exact values must not be converted and then used as the causal authority.
4. `Event.aggregate_version` must be positive; `AggregateVersionTracker` requires consecutive per-aggregate versions.
5. The durable journal rejects duplicate event IDs, checks global journal sequence and aggregate version sequence, validates checksums on recovery, and has a crash-tail policy.
6. Phase 2 reconstruction treats the journal as authoritative and checkpoints as non-authoritative.
7. The current journal interface shown in the supplied output does not demonstrate an atomic public “validate chain head + append” operation. Its append lock, even if internally effective, does not by itself prove that an external read/validate/append sequence is atomic across writers.

## 3. Unit 0 contract decisions — freeze candidate

### 3.1 Time domains

- **Causal authority:** exact integer `available_at_ns` in the canonical revision payload and the resolver.
- **Observation event time:** exact integer `event_time_ns` in the embedded `ProfileEvent` payload.
- **Canonical Event envelope:** seconds-domain integer timestamps, consistent with the demonstrated market-bar convention. Convert nanoseconds to seconds by integer floor division only for envelope metadata; never use the envelope values to decide revision visibility.
- For UPSERT, envelope source/event timestamp metadata is derived from `event.event_time_ns // 1_000_000_000`; processing metadata is `max(source_seconds, available_at_ns // 1_000_000_000)`. The exact nanosecond values remain in payload.
- For CANCEL, derive the envelope source time from the most recent prior UPSERT's exact event time, floored to seconds. Reject cancellation if the chain has no prior UPSERT, rather than fabricate an observation timestamp. Envelope processing metadata is `max(source_seconds, available_at_ns // 1_000_000_000)`.
- The adapter validates non-negative supported timestamp ranges before conversion. Overflow/range policy must be tested; no silent saturation.

**Rationale:** the seconds-domain envelope preserves the existing convention while the payload retains nanosecond causal precision. A future global timestamp-unit migration is out of scope.

### 3.2 Identity and scope

- Use dedicated constants, versioned payload schema, and namespaced deterministic IDs.
- `event.event_id` is a deterministic ID derived from canonical encoding of the logical identity plus `revision_id`, not from the mutable observation ID alone.
- The logical identity must include the complete scope needed to isolate a chain (at minimum source, symbol, domain, and logical event identity). Use canonical JSON/length-prefix encoding or a digest of canonical bytes; do not concatenate unescaped delimiters.
- `aggregate_type` is a dedicated VP revision-chain type. `aggregate_id` is the collision-resistant canonical identity of that chain. `root_id` is stable for the chain. `parent_id` is the predecessor canonical event ID or a documented root sentinel.
- `revision_id` is immutable within the chain. The same revision ID cannot be reused with different contents. A revision ID collision across separate logical chains must not collide at the canonical event-ID level.

### 3.3 Aggregate version and predecessor

- `aggregate_version` is exactly the next sequential version for that chain, starting at 1.
- It is derived from validated authoritative journal history, never accepted from caller input.
- The adapter validates that `supersedes_revision_id` agrees with the current chain head before append; generic aggregate sequencing alone is not sufficient.
- The event payload repeats the predecessor revision ID so replay can independently validate lineage.

### 3.4 Retry and duplicate semantics

- Before appending, search the authoritative journal for the deterministic event ID.
- If exactly one existing canonical event has the same ID **and identical canonical revision content/envelope contract**, return an explicit idempotent-retry result without appending.
- If the ID exists but any canonical content differs, fail closed as an identity conflict.
- If no existing event is found, continue with head validation and append.
- The generic journal's duplicate-ID rejection remains a final invariant, not the adapter's retry API.
- Do not swallow journal corruption or turn a failed lookup into “not found.”

### 3.5 Cancellation semantics

- CANCEL has no active `ProfileEvent` payload. It must not fabricate price, weight, or an active observation.
- The durable payload records operation, revision ID, predecessor, exact `available_at_ns`, schema, and logical identity.
- A CANCEL must supersede a valid existing UPSERT-derived chain state; a cancellation with no prior UPSERT is rejected.
- A later UPSERT may reactivate the logical observation only by explicitly superseding the cancellation head.
- A second CANCEL may be rejected as a no-op unless the product contract explicitly needs repeated cancellation revisions. Default decision: reject CANCEL when the current head is already CANCEL.

### 3.6 Concurrency model

- **Unit 2 initial implementation is single-writer per VP revision store instance/process.** Protect each chain's read/validate/append sequence with an adapter-owned lock and document that this lock does not coordinate independent processes.
- If multi-process writers are required, implementation is blocked until a durable compare-and-append/transactional ownership mechanism is designed and tested. Do not claim cross-process safety from the journal's internal append lock.
- On a stale head, fork attempt, or version race, reject before append. Never retry by silently rebasing the submitted revision onto a different head.

### 3.7 Full history versus watermark

- Validate the complete durable chain structurally before producing a result, including records whose `available_at_ns` is later than the requested watermark. Corrupt persisted history cannot be hidden by choosing an earlier watermark.
- After integrity validation, resolve visibility using the exact inclusive predicate `available_at_ns <= watermark_ns`.
- Future revisions must not affect the profile observed at an earlier watermark.
- The chain's revision availability must be monotonic along predecessor edges; temporal inversion fails closed.

## 4. Canonical Event payload

Recommended schema identifier: `vp-revision-event-v1`.

Required fields:
- `schema`
- `logical_event_id`
- canonical logical scope (`source_id`, `symbol`, `domain`)
- `revision_id`
- `supersedes_revision_id` (null only for the first revision)
- `operation` (`UPSERT` or `CANCEL`)
- exact `available_at_ns`
- for UPSERT only: canonical complete `ProfileEvent` data, including exact `event_time_ns`, `source_sequence`, price, and weight
- for CANCEL: no active observation object

Canonical encoding must define Decimal serialization, key ordering, Unicode handling, and integer validation. No float conversion of Decimal price/weight is permitted.

## 5. Append transaction

1. Validate the incoming revision and canonical scope.
2. Read and structurally validate the authoritative chain history.
3. Apply duplicate/retry policy against the canonical event ID.
4. Validate the current head, operation semantics, availability monotonicity, and predecessor.
5. Derive the next aggregate version from the validated journal history.
6. Build the canonical `Event`; preserve exact nanosecond fields in payload and use seconds only in envelope timestamps.
7. Append through `DurableEventJournal`.
8. Publish derived in-memory state only after successful append.
9. If an exception occurs after durable append, mark the adapter faulted and require replay/recovery before another mutation.
10. Never mutate the generic journal, Phase 2 store, broker adapters, risk engine, or execution authority as part of this VP slice.

## 6. Recovery and replay

- Reopen/recover the existing journal using its established checksum and crash-tail policy.
- Decode only the dedicated VP revision event type and validate all envelope and payload fields.
- Validate all chains and all durable records before watermark filtering.
- Rebuild revision histories exclusively from journal records.
- Resolve the exact watermark and compare the result against independent fresh resolution.
- Compare every observable field: profile bins, totals, quality state, reason codes, fingerprint, active/inactive state, and relevant provenance.
- A checkpoint is not required in the first durable integration slice. If later added, it remains non-authoritative and must be proven equivalent to genesis replay plus suffix.

## 7. Scope boundaries

Out of scope:
- modifications to generic journal semantics;
- modifications to `Phase2DurableStore`;
- snapshots/checkpoints for VP;
- multi-process compare-and-append;
- any transition from `ANALYTICAL_ONLY`;
- strategy/execution integration.

## 8. Implementation sequence

- **Unit 0:** approve/freeze this contract and HPL decisions.
- **Unit 1:** pure canonical Event codec and round-trip/malformed-envelope tests; no persistence writes.
- **Unit 2:** single-writer journal adapter and append/retry tests.
- **Unit 3:** journal reopen/recovery and watermark replay equivalence.
- **Unit 4:** hostile proof: stale writers, post-append failures, corrupt records, incomplete tail, identity collisions, cancellations, late corrections, future-record corruption, Decimal canonicalization.
- **Unit 5:** regression suite, compileall, diff checks, Ruff/mypy where available, repository preservation/provenance report.

**Acceptance gate:** do not call durable G3b closed until HPL obligations are evidenced by tests/logs and the complete repository status is reconciled. This artifact alone is a design deliverable.

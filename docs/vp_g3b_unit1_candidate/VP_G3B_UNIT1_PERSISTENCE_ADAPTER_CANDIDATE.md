# FRACTAL-FLOW Volume Profile G3b — Unit 1 persistence adapter candidate

**Status:** implementation candidate; not applied to the user's repository and not closure evidence.
**Authority:** `ANALYTICAL_ONLY`.

## Files
- `src/fractal_flow/research/volume_profile_persistence.py` — journal-backed adapter.
- `tests/test_volume_profile_persistence_candidate.py` — candidate normal and hostile tests.

## Scope
This adapter deliberately does not modify the generic journal, Phase 2, execution authority, or trading behavior. It relies on a single-writer-per-store-process assumption. Cross-process compare-and-append is not implemented and must remain an explicit limitation.

## Failure semantics
Any exception thrown by `DurableEventJournal.append` faults this adapter instance. Recovery must create a fresh journal instance over the same durable path or a caller-supplied authoritative factory, with tail truncation disabled. Rebuild decodes and canonically re-encodes VP history, validates chain links, aggregate versions, availability monotonicity, and UPSERT/CANCEL lifecycle, then invokes the full-history resolver.

## Important integration notes
- The code expects the repository's existing `Event`, `DurableEventJournal`, `ProfileEvent`, revision resolver, and codec interfaces.
- CANCEL calls must pass `ProfileRevisionContext`, because CANCEL records intentionally contain no embedded observation.
- Do not apply this candidate to the primary worktree until the focused and hostile tests pass in the disposable repository and the resulting patch is reviewed.
- The candidate tests are not represented as having run against the target repository.

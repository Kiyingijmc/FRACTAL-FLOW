"""Hostile G4 proofs for journal-backed local subscriber continuity."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.contracts import InstrumentAlias, InstrumentRegistry, LaneScope, RawQuote, SourceIdentity, VolumeSemantics
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import CorrectionScope, encode_correction
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.journal_subscriber import (
    ContinuityError, ContinuityState, GapDetected, JournalBackedSubscriber,
    JournalDelivery, JournalReplayAuthority, RecoveryAuthorizationError,
)
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.persistence.journal import DurableEventJournal


def _quote(native_id: str, available_ns: int, source_id: str = "source-a") -> CanonicalQuote:
    source = SourceIdentity(source_id, "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(RawQuote(
        source, native_id, 1, "EURUSD", available_ns - 2, available_ns - 1,
        available_ns, "1.10000", "1.10002", "1", VolumeSemantics.TICK_ACTIVITY_COUNT,
    ))
    assert result.quote is not None
    return result.quote


def _root(quote: CanonicalQuote, revision_id: str = "r1") -> QuoteRevision:
    return QuoteRevision(revision_id, quote.event_id, None, RevisionOperation.UPSERT, quote.available_time_ns, quote)


def _setup(tmp_path: object, known_at_ns: int = 10_000) -> tuple[DurableCorrectionJournal, CorrectionScope, JournalBackedSubscriber, JournalReplayAuthority]:
    journal = DurableEventJournal(str(tmp_path / "continuity.journal"))  # type: ignore[operator]
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 100)
    root = store.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    authority = JournalReplayAuthority(store, {scope.source.key})
    subscriber = JournalBackedSubscriber(b"g4-test-secret", scope, {scope.source.key}, known_at_ns=known_at_ns)
    return store, scope, subscriber, authority


def _delivery(item: object) -> JournalDelivery:
    return JournalDelivery.from_correction(item, b"g4-test-secret")  # type: ignore[arg-type]


def test_disconnect_gap_replays_authoritative_history_and_returns_live(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    subscriber.receive(_delivery(first), authority)
    second = store.append(QuoteRevision("r2", first.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None))
    third_quote = _quote("n2", 300)
    third = store.append(QuoteRevision("r3", first.revision.logical_event_id, "r2", RevisionOperation.UPSERT, 300, third_quote))
    with pytest.raises(GapDetected):
        subscriber.receive(_delivery(third), authority)
    assert subscriber.state is ContinuityState.DEGRADED
    subscriber.recover(authority)
    assert subscriber.state is ContinuityState.LIVE
    assert subscriber.checkpoint.aggregate_version == 3
    assert subscriber.checkpoint.journal_sequence == third.journal_sequence
    assert [item.event_id for item in subscriber.visible()] == [first.event_id, second.event_id, third.event_id]


def test_exact_duplicate_is_idempotent_but_conflicting_duplicate_fails_closed(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    delivery = _delivery(first)
    subscriber.receive(delivery, authority)
    subscriber.receive(delivery, authority)
    assert subscriber.checkpoint.aggregate_version == 1
    conflict = JournalDelivery.with_payload_hash(delivery, "0" * 64, b"g4-test-secret")
    with pytest.raises(ContinuityError, match="conflicting"):
        subscriber.receive(conflict, authority)
    assert subscriber.state is ContinuityState.FAILED


@pytest.mark.parametrize("field", ["partition_id", "source_key"])
def test_partition_and_source_lane_mismatches_fail_closed(tmp_path: object, field: str) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    item = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    delivery = _delivery(item)
    if field == "partition_id":
        bad = JournalDelivery.with_partition(delivery, "foreign-partition", b"g4-test-secret")
    else:
        bad = JournalDelivery.with_source(delivery, ("foreign", "broker", "server", "REPLAY", "", ""), b"g4-test-secret")
    with pytest.raises(ContinuityError):
        subscriber.receive(bad, authority)
    assert subscriber.state is ContinuityState.FAILED


def test_missing_journal_event_and_stale_cursor_cannot_resume_live(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    forged_item = replace(first, journal_sequence=999, aggregate_version=2)
    forged = JournalDelivery.from_correction(forged_item, b"g4-test-secret")
    with pytest.raises(GapDetected, match="authoritative"):
        subscriber.receive(forged, authority)
    assert subscriber.state is ContinuityState.DEGRADED
    restarted = JournalBackedSubscriber(b"g4-test-secret", scope, {scope.source.key}, checkpoint=replace(subscriber.checkpoint, aggregate_version=9))
    with pytest.raises(ContinuityError, match="cursor"):
        restarted.recover(authority)
    assert restarted.state is ContinuityState.FAILED


def test_recovery_holds_live_delivery_and_closes_replay_live_race(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    subscriber.receive(_delivery(first), authority)
    second = store.append(QuoteRevision("r2", first.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None))
    third = store.append(QuoteRevision("r3", first.revision.logical_event_id, "r2", RevisionOperation.UPSERT, 300, _quote("n3", 300)))
    with pytest.raises(GapDetected):
        subscriber.receive(_delivery(third), authority)
    subscriber.begin_recovery(authority)
    subscriber.receive(_delivery(second), authority)
    subscriber.receive(_delivery(third), authority)
    fourth = store.append(QuoteRevision("r4", first.revision.logical_event_id, "r3", RevisionOperation.CANCEL, 400, None))
    subscriber.receive(_delivery(fourth), authority)
    subscriber.complete_recovery(authority)
    assert subscriber.state is ContinuityState.LIVE
    assert subscriber.checkpoint.aggregate_version == 4


def test_recovery_queue_saturation_and_interrupted_restart_require_replay(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    subscriber.receive(_delivery(first), authority)
    second = store.append(QuoteRevision("r2", first.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None))
    third = store.append(QuoteRevision("r3", first.revision.logical_event_id, "r2", RevisionOperation.UPSERT, 300, _quote("n3", 300)))
    with pytest.raises(GapDetected):
        subscriber.receive(_delivery(third), authority)
    subscriber.begin_recovery(authority, max_holdback=1)
    subscriber.receive(_delivery(second), authority)
    with pytest.raises(ContinuityError, match="saturated"):
        subscriber.receive(_delivery(third), authority)
    assert subscriber.state is ContinuityState.DEGRADED
    restarted = JournalBackedSubscriber(b"g4-test-secret", scope, {scope.source.key}, checkpoint=subscriber.checkpoint)
    assert restarted.state is ContinuityState.DEGRADED
    restarted.recover(authority)
    assert restarted.state is ContinuityState.LIVE
    assert restarted.checkpoint.aggregate_version == 3


def test_unauthorized_replay_and_future_available_records_do_not_leak(tmp_path: object) -> None:
    store, scope, subscriber, authority = _setup(tmp_path, known_at_ns=100)
    first = store.replay_batch_after(scope, subscriber.checkpoint).records[0]
    future = store.append(QuoteRevision("r2", first.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None))
    subscriber.degrade("disconnect")
    subscriber.recover(authority)
    assert subscriber.checkpoint.aggregate_version == 2
    assert [item.event_id for item in subscriber.visible()] == [first.event_id]
    subscriber.advance_knowledge_time(200)
    assert [item.event_id for item in subscriber.visible()] == [first.event_id, future.event_id]
    foreign = _quote("foreign", 100, "foreign-source")
    foreign_scope = CorrectionScope.from_quote(foreign)
    foreign_authority = JournalReplayAuthority(store, {foreign_scope.source.key})
    subscriber.degrade("test authorization")
    with pytest.raises(RecoveryAuthorizationError):
        subscriber.recover(foreign_authority)
    assert subscriber.state is ContinuityState.FAILED


def test_corrupt_authoritative_history_fails_recovery_before_live(tmp_path: object) -> None:
    path = tmp_path / "corrupt-continuity.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 100)
    root = store.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    malformed = QuoteRevision("r2", root.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None)
    journal.append(encode_correction(malformed, scope, 2, "wrong-parent-event"))
    subscriber = JournalBackedSubscriber(b"g4-test-secret", scope, {scope.source.key})
    subscriber.degrade("forced recovery")
    with pytest.raises(ContinuityError, match="history"):
        subscriber.recover(JournalReplayAuthority(store, {scope.source.key}))
    assert subscriber.state is ContinuityState.FAILED


def test_writer_handover_and_repeated_recovery_reconcile_same_checkpoint(tmp_path: object) -> None:
    path = tmp_path / "handover-continuity.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    writer = DurableCorrectionJournal(journal)
    quote = _quote("n1", 100)
    writer.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    journal.close()
    replacement = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    authority = JournalReplayAuthority(replacement, {scope.source.key})
    subscriber = JournalBackedSubscriber(b"g4-test-secret", scope, {scope.source.key})
    subscriber.degrade("writer handover")
    subscriber.recover(authority)
    first_checkpoint = subscriber.checkpoint
    subscriber.degrade("repeat recovery")
    subscriber.recover(authority)
    assert subscriber.state is ContinuityState.LIVE
    assert subscriber.checkpoint == first_checkpoint

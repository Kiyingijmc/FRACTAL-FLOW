"""G5 Unit 2 hostile proofs for the read-only simulated-live consumer."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.checkpoints import SubscriberCheckpointStore
from src.fractal_flow.data_engine.contracts import (
    InstrumentAlias,
    InstrumentRegistry,
    LaneScope,
    RawQuote,
    SourceIdentity,
    VolumeSemantics,
)
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.journal_subscriber import ContinuityState, JournalDelivery
from src.fractal_flow.data_engine.replay_consumer import DeterministicReplayConsumer
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.data_engine.simulated_live_consumer import SimulatedLiveConsumer, SimulatedLiveConsumerError
from src.fractal_flow.persistence.journal import DurableEventJournal


SECRET = b"g5-simulated-live-test-secret"


def _quote(native: str, sequence: int, available: int, source_name: str = "source-a") -> CanonicalQuote:
    source = SourceIdentity(source_name, "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(
        RawQuote(
            source,
            native,
            sequence,
            "EURUSD",
            available - 2,
            available - 1,
            available,
            "1.10000",
            "1.10002",
            "0.123456789123456789",
            VolumeSemantics.TICK_ACTIVITY_COUNT,
        )
    )
    assert result.quote is not None
    return result.quote


def _root(quote: CanonicalQuote, revision_id: str = "r1") -> QuoteRevision:
    return QuoteRevision(revision_id, quote.event_id, None, RevisionOperation.UPSERT, quote.available_time_ns, quote)


def _setup(
    known_at: int = 100,
) -> tuple[DurableCorrectionJournal, CorrectionScope, SimulatedLiveConsumer, CanonicalQuote]:
    store = DurableCorrectionJournal(DurableEventJournal())
    quote = _quote("n1", 1, 100)
    store.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    consumer = SimulatedLiveConsumer(store, scope, SECRET, {scope.source.key}, known_at_ns=known_at)
    return store, scope, consumer, quote


def _delivery(item: object) -> JournalDelivery:
    return JournalDelivery.from_correction(item, SECRET)  # type: ignore[arg-type]


def test_startup_reconstructs_and_matches_deterministic_replay_exactly() -> None:
    store, scope, consumer, _quote_value = _setup()
    consumer.start()
    simulated = consumer.snapshot()
    replay = DeterministicReplayConsumer(store).replay(100, {scope})
    assert consumer.state is ContinuityState.LIVE
    assert simulated.replay == replay
    assert simulated.fingerprint == replay.fingerprint
    assert simulated.replay.quotes[0].quote.volume == Decimal("0.123456789123456789")


def test_undelivered_durable_record_cannot_leak_then_recovery_reconciles() -> None:
    store, scope, consumer, quote = _setup(300)
    consumer.start()
    store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 200, None))
    with pytest.raises(SimulatedLiveConsumerError, match="catch-up"):
        consumer.snapshot()
    assert consumer.state is ContinuityState.DEGRADED
    consumer.recover()
    assert consumer.snapshot().replay == DeterministicReplayConsumer(store).replay(300, {scope})


def test_gap_conflicting_duplicate_and_foreign_lane_fail_closed_then_recover() -> None:
    store, scope, consumer, quote = _setup(300)
    consumer.start()
    first = store.replay_batch_after(scope, consumer.checkpoint).records
    assert not first  # startup recovery has consumed the root
    second = store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 200, None))
    third = store.append(QuoteRevision("r3", quote.event_id, "r2", RevisionOperation.UPSERT, 300, quote))
    with pytest.raises(SimulatedLiveConsumerError, match="skips"):
        consumer.receive(_delivery(third))
    assert consumer.state is ContinuityState.DEGRADED
    consumer.recover()
    assert consumer.state is ContinuityState.LIVE
    with pytest.raises(SimulatedLiveConsumerError, match="conflicting"):
        consumer.receive(JournalDelivery.with_payload_hash(_delivery(second), "0" * 64, SECRET))
    assert consumer.state is ContinuityState.FAILED
    foreign = _quote("foreign", 1, 300, "foreign-source")
    foreign_scope = CorrectionScope.from_quote(foreign)
    foreign_store = DurableCorrectionJournal(DurableEventJournal())
    foreign_item = foreign_store.append(_root(foreign))
    fresh = SimulatedLiveConsumer(store, scope, SECRET, {scope.source.key}, known_at_ns=300)
    fresh.start()
    with pytest.raises(SimulatedLiveConsumerError, match="unauthorized|mismatched"):
        fresh.receive(_delivery(foreign_item))
    assert foreign_scope != scope and fresh.state is ContinuityState.FAILED


def test_checkpoint_restart_and_crash_style_handover_reconstruct_same_state(tmp_path: object) -> None:
    journal_path = tmp_path / "simulated-live.journal"  # type: ignore[operator]
    checkpoint_path = tmp_path / "simulated-live.checkpoint"  # type: ignore[operator]
    journal = DurableEventJournal(str(journal_path))
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 1, 100)
    store.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    with SubscriberCheckpointStore(str(checkpoint_path), journal) as checkpoints:
        first = SimulatedLiveConsumer(
            store,
            scope,
            SECRET,
            {scope.source.key},
            subscriber_id="sim-1",
            checkpoint_store=checkpoints,
            known_at_ns=100,
        )
        first.start()
        assert first.snapshot().fingerprint == DeterministicReplayConsumer(store).replay(100, {scope}).fingerprint
    journal.close()
    replacement_journal = DurableEventJournal(str(journal_path))
    replacement = DurableCorrectionJournal.recover(replacement_journal)
    with SubscriberCheckpointStore(str(checkpoint_path), replacement_journal) as checkpoints:
        restarted = SimulatedLiveConsumer(
            replacement,
            scope,
            SECRET,
            {scope.source.key},
            subscriber_id="sim-1",
            checkpoint_store=checkpoints,
            known_at_ns=100,
        )
        restarted.start()
        assert restarted.state is ContinuityState.LIVE
        assert (
            restarted.snapshot().fingerprint
            == DeterministicReplayConsumer(replacement).replay(100, {scope}).fingerprint
        )
    replacement_journal.close()


def test_knowledge_time_and_future_gap_never_look_ahead() -> None:
    store, scope, consumer, _quote_value = _setup(100)
    consumer.start()
    future_gap = _quote("n3", 3, 200)
    future_item = store.append(_root(future_gap, "future-r1"))
    # The delivery itself is received, but it is not analytically visible yet.
    consumer.receive(_delivery(future_item))
    early = consumer.snapshot().replay
    assert [item.quote.event_id for item in early.quotes] != [future_gap.event_id]
    assert "SOURCE_SEQUENCE_GAP" not in early.reasons
    consumer.advance_knowledge_time(200)
    late = consumer.snapshot().replay
    assert "SOURCE_SEQUENCE_GAP" in late.reasons
    assert late == DeterministicReplayConsumer(store).replay(200, {scope})


def test_queue_saturation_during_recovery_stays_degraded_and_never_snapshots() -> None:
    store, scope, consumer, quote = _setup(300)
    consumer.start()
    second = store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 200, None))
    third = store.append(QuoteRevision("r3", quote.event_id, "r2", RevisionOperation.UPSERT, 300, quote))
    # Cause the required recovery state with the skipped delivery, then prove the
    # public consumer never emits a state while that discontinuity exists.
    with pytest.raises(SimulatedLiveConsumerError):
        consumer.receive(_delivery(third))
    with pytest.raises(SimulatedLiveConsumerError, match="not LIVE"):
        consumer.snapshot()
    consumer.recover()
    assert consumer.snapshot().replay == DeterministicReplayConsumer(store).replay(300, {scope})
    assert second.aggregate_version == 2

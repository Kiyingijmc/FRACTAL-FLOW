"""Hostile G5 Unit 1 proof for deterministic read-only correction replay."""

from __future__ import annotations

from decimal import Decimal

import pytest

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
from src.fractal_flow.data_engine.replay_consumer import DeterministicReplayConsumer, ReplayConsumerError
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.domain.context import DataStatus
from src.fractal_flow.persistence.journal import DurableEventJournal


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


def _store() -> tuple[DurableCorrectionJournal, CanonicalQuote]:
    store = DurableCorrectionJournal(DurableEventJournal())
    quote = _quote("n1", 1, 100)
    store.append(QuoteRevision("r1", quote.event_id, None, RevisionOperation.UPSERT, 100, quote))
    return store, quote


def test_replay_is_deterministic_exact_and_has_no_implicit_quality_or_lookahead() -> None:
    store, quote = _store()
    store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 200, None))
    store.append(QuoteRevision("r3", quote.event_id, "r2", RevisionOperation.UPSERT, 300, quote))
    consumer = DeterministicReplayConsumer(store)
    early, again, cancelled, restored = (consumer.replay(mark) for mark in (150, 150, 250, 300))
    assert early.fingerprint == again.fingerprint
    assert early.quotes[0].quote.bid == Decimal("1.10000")
    assert early.status is DataStatus.UNAVAILABLE and not early.suitable_for_trade
    assert early.reasons == ("QUALITY_NOT_DURABLE",)
    assert not cancelled.quotes and [item.revision_id for item in restored.quotes] == ["r3"]


def test_scope_isolation_gap_propagation_and_resource_bound_are_fail_closed() -> None:
    store, first = _store()
    second = _quote("n2", 1, 200, "source-b")
    store.append(QuoteRevision("r2", second.event_id, None, RevisionOperation.UPSERT, 200, second))
    gap = _quote("n3", 3, 200)
    store.append(QuoteRevision("r3", gap.event_id, None, RevisionOperation.UPSERT, 200, gap))
    consumer = DeterministicReplayConsumer(store)
    only_second = consumer.replay(200, {CorrectionScope.from_quote(second)})
    assert [item.quote.event_id for item in only_second.quotes] == [second.event_id]
    all_scopes = consumer.replay(200)
    assert "SOURCE_SEQUENCE_GAP" in all_scopes.reasons
    with pytest.raises(ReplayConsumerError, match="resource bound"):
        DeterministicReplayConsumer(store, max_records=2).replay(200)


def test_corrupt_or_unsupported_history_is_never_hidden_by_watermark(monkeypatch: pytest.MonkeyPatch) -> None:
    store, _quote_value = _store()
    consumer = DeterministicReplayConsumer(store)
    monkeypatch.setattr(store, "snapshot", lambda: (_ for _ in ()).throw(ValueError("forked future correction")))
    with pytest.raises(ReplayConsumerError, match="invalid"):
        consumer.replay(1)

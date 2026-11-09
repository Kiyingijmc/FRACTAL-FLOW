from dataclasses import replace
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
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore, QualityAssessment
from src.fractal_flow.data_engine.persistence import DataJournalAdapter, DataPersistenceConflict
from src.fractal_flow.persistence.journal import DurableEventJournal


def _quote() -> tuple[CanonicalQuote, QualityAssessment]:
    source = SourceIdentity("replay-source", "fixture", "fixture", LaneScope.REPLAY)
    registry = InstrumentRegistry(
        [InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), effective_from_ns=0)]
    )
    result = DataCore(registry).ingest(
        RawQuote(
            source=source,
            native_record_id="record-1",
            source_sequence=1,
            source_symbol="EURUSD",
            event_time_ns=1_000_000_001,
            received_time_ns=1_000_000_010,
            available_time_ns=1_000_000_020,
            bid="1.10000",
            ask="1.10002",
            volume="1",
            volume_semantics=VolumeSemantics.TICK_ACTIVITY_COUNT,
        )
    )
    assert result.quote is not None
    return result.quote, result.assessment


def test_durable_quote_append_is_exact_retry_idempotent_and_replays_after_restart(tmp_path) -> None:
    quote, assessment = _quote()
    path = tmp_path / "data.journal"
    adapter = DataJournalAdapter(DurableEventJournal(str(path)))

    first = adapter.append(quote, assessment)
    retry = adapter.append(quote, assessment)
    restarted = DataJournalAdapter(DurableEventJournal(str(path)))
    replayed = restarted.replay_as_known_at(1_000_000_020)

    assert retry == first
    assert len(replayed) == 1
    assert replayed[0].quote == quote
    assert replayed[0].assessment == assessment
    assert replayed[0].event_time_ns == 1_000_000_001
    assert replayed[0].available_time_ns == 1_000_000_020


def test_durable_adapter_rejects_event_identity_reuse_with_changed_payload(tmp_path) -> None:
    quote, assessment = _quote()
    adapter = DataJournalAdapter(DurableEventJournal(str(tmp_path / "data.journal")))
    adapter.append(quote, assessment)

    with pytest.raises(DataPersistenceConflict, match="different canonical payload"):
        adapter.append(replace(quote, bid=Decimal("1.10001")), assessment)


def test_as_known_at_filters_on_availability_not_event_time(tmp_path) -> None:
    quote, assessment = _quote()
    adapter = DataJournalAdapter(DurableEventJournal(str(tmp_path / "data.journal")))
    adapter.append(quote, assessment)

    assert adapter.replay_as_known_at(1_000_000_019) == ()
    assert len(adapter.replay_as_known_at(1_000_000_020)) == 1

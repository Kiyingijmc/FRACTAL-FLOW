from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.contracts import InstrumentAlias, InstrumentRegistry, LaneScope, RawQuote, SourceIdentity, VolumeSemantics
from src.fractal_flow.data_engine.core import DataCore
from src.fractal_flow.data_engine.persistence import PersistedQuote
from src.fractal_flow.data_engine.transport import GapDetected, LocalPublisher, LocalSubscriber, TransportError


def _record() -> PersistedQuote:
    source = SourceIdentity("source", "broker", "server", LaneScope.REPLAY)
    result = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)])).ingest(
        RawQuote(source, "record", 1, "EURUSD", 1, 2, 3, "1.10000", "1.10002", "1", VolumeSemantics.TICK_ACTIVITY_COUNT)
    )
    assert result.quote is not None
    return PersistedQuote(1, result.quote, result.assessment)


def test_local_transport_authenticates_sequences_and_rejects_bounded_overflow() -> None:
    record = _record()
    secret = b"test-only-secret"
    subscriber = LocalSubscriber(secret, {record.quote.source.key}, max_queue=1)
    publisher = LocalPublisher(secret)
    publisher.subscribe(subscriber)
    first = publisher.publish(record)
    assert subscriber.poll() == first
    publisher.publish(record)
    with pytest.raises(TransportError, match="saturated"):
        publisher.publish(record)


def test_local_transport_rejects_foreign_source_and_detects_gap() -> None:
    record = _record()
    secret = b"test-only-secret"
    subscriber = LocalSubscriber(secret, {record.quote.source.key})
    publisher = LocalPublisher(secret)
    envelope = publisher.publish(record)
    subscriber.accept(envelope)
    with pytest.raises(GapDetected):
        subscriber.accept(envelope)
    foreign = LocalSubscriber(secret, set())
    with pytest.raises(TransportError, match="unauthorized"):
        foreign.accept(envelope)

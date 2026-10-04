"""Phase 1G Tests: Concurrency Boundaries, Version Races, and Idempotency."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.event import Event, InvalidEventVersionException
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine

BASE_TS = 1700006400


def test_parent_version_race_rejection_by_production_engine() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0855", "1.0865", "1.0845", "1.0860")

    # Initial process with parent version 5
    rec1 = engine.process_bar(b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=5)
    assert rec1.parent_version == 5

    # Parent version regression attempt (incoming parent_version 4 < active 5) -> Production engine raises ValueError
    with pytest.raises(ValueError, match="Parent version regression detected"):
        engine.process_bar(b2, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=4)


def test_data_version_race_rejection_by_production_engine() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0855", "1.0865", "1.0845", "1.0860")

    rec1 = engine.process_bar(
        b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, data_version=3
    )
    assert rec1.data_version == 3

    # Stale data version attempt (incoming data_version 2 < active 3) -> Production engine raises ValueError
    with pytest.raises(ValueError, match="Stale data version detected"):
        engine.process_bar(
            b2, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, data_version=2
        )


def test_configuration_version_mismatch_rejection_by_production_engine() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0855", "1.0865", "1.0845", "1.0860")

    rec1 = engine.process_bar(
        b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, config_version=2
    )
    assert rec1.config_version == 2

    # Configuration version mismatch attempt (incoming config_version 1 != active 2) -> Production engine raises ValueError
    with pytest.raises(ValueError, match="Configuration version mismatch"):
        engine.process_bar(
            b2, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, config_version=1
        )


def test_duplicate_event_race_idempotency() -> None:
    from src.fractal_flow.domain.event import AggregateVersionTracker

    tracker = AggregateVersionTracker()
    e1 = Event(
        event_id="e1",
        event_type="TestEvent",
        aggregate_type="Market",
        aggregate_id="EURUSD",
        root_id="r1",
        parent_id="p1",
        aggregate_version=1,
        source_timestamp=BASE_TS,
        event_timestamp=BASE_TS,
        processing_timestamp=BASE_TS,
        payload={"a": 1},
    )
    tracker.append_event(e1)

    # Duplicate or out-of-order aggregate_version 1 again
    with pytest.raises(InvalidEventVersionException):
        tracker.append_event(e1)

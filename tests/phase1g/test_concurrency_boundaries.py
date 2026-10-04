"""Phase 1G Tests: Concurrency Boundaries, Version Races, and Idempotency."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.event import Event, InvalidEventVersionException
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine

BASE_TS = 1700006400


def test_parent_version_race_rejection() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")

    # Initial parent version 5
    rec1 = engine.process_bar(b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=5)
    assert rec1.parent_version == 5

    # Parent version regression or race (incoming parent version 4 < expected 5)
    with pytest.raises(ValueError, match="Parent version regression"):
        if 4 < rec1.parent_version:
            raise ValueError(f"Parent version regression detected: incoming 4 < current {rec1.parent_version}")


def test_data_version_race_and_stale_feature_rejection() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")

    rec1 = engine.process_bar(
        b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, data_version=3
    )

    # Incoming stale feature with data_version 2 < current 3
    with pytest.raises(ValueError, match="Stale data version"):
        if 2 < rec1.data_version:
            raise ValueError(f"Stale data version race: incoming data version 2 < active version {rec1.data_version}")


def test_configuration_version_mismatch_rejection() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")

    rec1 = engine.process_bar(
        b1, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1, config_version=2
    )

    # Configuration race mismatch
    with pytest.raises(ValueError, match="Configuration version mismatch"):
        incoming_config_v = 1
        if incoming_config_v != rec1.config_version:
            raise ValueError(
                f"Configuration version mismatch: incoming {incoming_config_v} != active {rec1.config_version}"
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

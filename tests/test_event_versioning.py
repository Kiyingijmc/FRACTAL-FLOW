"""Tests for Event Versioning, Version Gap Rejection, and Event Store Concurrency."""

import pytest
from src.fractal_flow.domain.event import Event, InvalidEventVersionException
from src.fractal_flow.persistence.interfaces import InMemoryEventStore


def make_event(version: int, aggregate_id: str = "agg_1") -> Event:
    return Event(
        event_id=f"evt_{version}",
        event_type="TEST_EVENT",
        aggregate_type="Opportunity",
        aggregate_id=aggregate_id,
        root_id="root_1",
        parent_id="parent_1",
        aggregate_version=version,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        payload={"data": "test"},
    )


def test_strict_event_version_sequence_accepted() -> None:
    store = InMemoryEventStore()
    store.append_event(make_event(1))
    store.append_event(make_event(2))
    store.append_event(make_event(3))
    events = store.get_events_for_aggregate("Opportunity", "agg_1")
    assert len(events) == 3


def test_duplicate_version_rejected() -> None:
    store = InMemoryEventStore()
    store.append_event(make_event(1))
    with pytest.raises(InvalidEventVersionException) as exc:
        store.append_event(make_event(1))
    assert "Strict event versioning failure" in str(exc.value)


def test_version_gap_rejected() -> None:
    store = InMemoryEventStore()
    store.append_event(make_event(1))
    with pytest.raises(InvalidEventVersionException) as exc:
        store.append_event(make_event(3))  # Gap: expected 2
    assert "Strict event versioning failure" in str(exc.value)


def test_zero_or_negative_version_rejected() -> None:
    with pytest.raises(InvalidEventVersionException) as exc:
        make_event(0)
    assert "must be positive integer" in str(exc.value)

    with pytest.raises(InvalidEventVersionException) as exc:
        make_event(-1)
    assert "must be positive integer" in str(exc.value)

"""Tests for Event Versioning, Schema Parity, Temporal Checks, and Event Store Concurrency."""

from pathlib import Path

import pytest
import yaml

from src.fractal_flow.domain.event import Event, ImmutablePayloadDict, InvalidEventVersionException
from src.fractal_flow.persistence.interfaces import InMemoryEventStore


def make_event(
    version: int,
    aggregate_id: str = "agg_1",
    src_ts: int = 100,
    evt_ts: int = 100,
    proc_ts: int = 100,
) -> Event:
    return Event(
        event_id=f"evt_{version}",
        event_type="TEST_EVENT",
        aggregate_type="Opportunity",
        aggregate_id=aggregate_id,
        root_id="root_1",
        parent_id="parent_1",
        aggregate_version=version,
        source_timestamp=src_ts,
        event_timestamp=evt_ts,
        processing_timestamp=proc_ts,
        payload={"data": "test", "nested": {"key": "value"}},
    )


def test_event_schema_parity_with_yaml() -> None:
    yaml_path = Path("spec/events.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    yaml_schema = set(data["events"]["schema"])

    evt = make_event(1)
    python_fields = set(evt.__dataclass_fields__.keys())

    assert yaml_schema == python_fields, (
        f"Event schema mismatch! YAML extra: {yaml_schema - python_fields}, Python extra: {python_fields - yaml_schema}"
    )


def test_event_deep_payload_immutability() -> None:
    """Verifies that Event payloads are deeply frozen as ImmutablePayloadDict and cannot be mutated post-issuance."""
    evt = Event(
        event_id="evt_1",
        event_type="TEST_EVENT",
        aggregate_type="Opportunity",
        aggregate_id="agg_1",
        root_id="root_1",
        parent_id="parent_1",
        aggregate_version=1,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        payload={"data": "test", "nested": {"key": "value", "list": [1, {"deep": 2}], "set": {3, 4}}},
        reason_codes=["REASON_1"],
    )
    assert isinstance(evt.payload, ImmutablePayloadDict)
    assert isinstance(evt.payload["nested"], ImmutablePayloadDict)
    assert isinstance(evt.payload["nested"]["list"], tuple)
    assert isinstance(evt.payload["nested"]["list"][1], ImmutablePayloadDict)
    assert isinstance(evt.payload["nested"]["set"], frozenset)
    assert isinstance(evt.reason_codes, tuple)

    # Attempting to mutate payload raises TypeError
    with pytest.raises(TypeError):
        evt.payload["data"] = "mutated"  # type: ignore[index]

    with pytest.raises(TypeError):
        evt.payload["nested"]["key"] = "mutated"  # type: ignore[index]

    with pytest.raises(TypeError):
        evt.payload["nested"]["list"][1]["deep"] = 99  # type: ignore[index]

    # Additional deep mutation attempts: pop, clear, update
    with pytest.raises(TypeError):
        evt.payload.pop("data")

    with pytest.raises(TypeError):
        evt.payload.clear()

    with pytest.raises(TypeError):
        evt.payload.update({"new_key": "val"})

    with pytest.raises(TypeError):
        evt.payload["nested"].pop("key")


def test_event_temporal_ordering_validation() -> None:
    # Valid ordering
    make_event(1, src_ts=100, evt_ts=100, proc_ts=105)

    # Inverted source and event timestamp
    with pytest.raises(ValueError) as exc:
        make_event(1, src_ts=200, evt_ts=100, proc_ts=200)
    assert "temporal ordering violation" in str(exc.value)


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
        store.append_event(make_event(3))
    assert "Strict event versioning failure" in str(exc.value)

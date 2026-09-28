"""Canonical Event Model with Optimistic Concurrency Protection."""

from dataclasses import dataclass, field
from typing import Dict, Any, List


class OptimisticConcurrencyException(Exception):
    """Raised when two events attempt to claim the same aggregate version."""
    pass


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    root_id: str
    parent_id: str
    aggregate_version: int
    source_timestamp: int
    event_timestamp: int
    processing_timestamp: int
    payload: Dict[str, Any]
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    reason_codes: List[str] = field(default_factory=list)


class AggregateVersionTracker:
    """Tracks highest aggregate version to prevent concurrent duplicate versions."""

    def __init__(self) -> None:
        self._versions: Dict[str, int] = {}

    def append_event(self, event: Event) -> None:
        key = f"{event.aggregate_type}:{event.aggregate_id}"
        current_version = self._versions.get(key, 0)
        if event.aggregate_version <= current_version:
            raise OptimisticConcurrencyException(
                f"Optimistic concurrency failure on aggregate '{key}': event version "
                f"{event.aggregate_version} <= current version {current_version}"
            )
        self._versions[key] = event.aggregate_version

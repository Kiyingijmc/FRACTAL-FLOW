"""Canonical Event Model with Strict Aggregate Versioning and Auditability."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class InvalidEventVersionException(Exception):
    """Raised when an event version is invalid, non-sequential, or represents a gap/duplicate/future version."""
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
    schema_version: int = 1
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    reason_codes: List[str] = field(default_factory=list)
    causation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    actor_id: str = "SYSTEM"

    def __post_init__(self) -> None:
        if self.aggregate_version <= 0:
            raise InvalidEventVersionException(
                f"Event aggregate_version must be positive integer, got {self.aggregate_version}"
            )


class AggregateVersionTracker:
    """Tracks aggregate version sequencing and enforces strictly sequential increments."""

    def __init__(self) -> None:
        self._versions: Dict[str, int] = {}

    def append_event(self, event: Event) -> None:
        key = f"{event.aggregate_type}:{event.aggregate_id}"
        current_version = self._versions.get(key, 0)

        expected_version = current_version + 1
        if event.aggregate_version != expected_version:
            raise InvalidEventVersionException(
                f"Strict event versioning failure on '{key}': incoming version {event.aggregate_version} "
                f"!= expected version {expected_version} (current={current_version}). "
                f"Version gaps, duplicates, or out-of-order events are strictly prohibited."
            )
        self._versions[key] = event.aggregate_version

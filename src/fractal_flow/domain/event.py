"""Canonical Event Model with Strict Aggregate Versioning, Temporal Checks, and Auditability."""

from dataclasses import dataclass, field
from typing import Any, Mapping


class InvalidEventVersionException(Exception):
    """Raised when an event version is invalid, non-sequential, or represents a gap/duplicate/future version."""


def _deep_freeze(v: Any) -> Any:
    if isinstance(v, dict) and not isinstance(v, ImmutablePayloadDict):
        return ImmutablePayloadDict(v)
    elif isinstance(v, (list, tuple)):
        return tuple(_deep_freeze(x) for x in v)
    elif isinstance(v, (set, frozenset)):
        return frozenset(_deep_freeze(x) for x in v)
    return v


class ImmutablePayloadDict(dict[str, Any]):
    """Dict subclass that prevents item assignment and deletion after initialization, enforcing event payload immutability while supporting deepcopy/serialization."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        temp = dict(*args, **kwargs)
        for k, v in temp.items():
            super().__setitem__(k, _deep_freeze(v))
        self._frozen = True

    def __setitem__(self, key: Any, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        super().__delitem__(key)

    def clear(self) -> None:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        super().clear()

    def pop(self, *args: Any, **kwargs: Any) -> Any:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        return super().pop(*args, **kwargs)

    def popitem(self, *args: Any, **kwargs: Any) -> Any:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        return super().popitem(*args, **kwargs)

    def update(self, *args: Any, **kwargs: Any) -> None:
        if getattr(self, "_frozen", False):
            raise TypeError("ImmutablePayloadDict payload cannot be modified post-issuance")
        super().update(*args, **kwargs)

    def __deepcopy__(self, memo: dict[int, Any]) -> "ImmutablePayloadDict":
        """Deep-copy immutable payloads without invoking guarded mutation methods."""
        import copy
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        copied = ImmutablePayloadDict({})
        memo[id(self)] = copied
        for key, value in self.items():
            dict.__setitem__(copied, copy.deepcopy(key, memo), copy.deepcopy(value, memo))
        copied._frozen = True
        return copied


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
    payload: Mapping[str, Any]
    schema_version: int = 1
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    reason_codes: list[str] = field(default_factory=list)
    causation_id: str | None = None
    correlation_id: str | None = None
    actor_id: str = "SYSTEM"
    authority: str = "SYSTEM"
    account_id: str = "ACT_PRIMARY"

    def __post_init__(self) -> None:
        if self.aggregate_version <= 0:
            raise InvalidEventVersionException(
                f"Event aggregate_version must be positive integer, got {self.aggregate_version}"
            )

        if not (self.source_timestamp <= self.event_timestamp <= self.processing_timestamp):
            raise ValueError(
                f"Event temporal ordering violation: source_timestamp ({self.source_timestamp}) "
                f"<= event_timestamp ({self.event_timestamp}) <= processing_timestamp ({self.processing_timestamp}) required."
            )

        # Deep freeze payload into ImmutablePayloadDict
        if not isinstance(self.payload, ImmutablePayloadDict):
            object.__setattr__(self, "payload", ImmutablePayloadDict(self.payload))
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


class AggregateVersionTracker:
    """Tracks aggregate version sequencing and enforces strictly sequential increments."""

    def __init__(self) -> None:
        self._versions: dict[str, int] = {}

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

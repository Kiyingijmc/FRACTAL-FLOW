"""Pure, deterministic revision resolution for Volume Profile observations.

This module deliberately does not persist records or change execution authority.
It is a G3b contract slice: resolve append-only revisions as known at a supplied
availability watermark, then hand the resulting observations to the existing
reference calculator.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Iterable

from src.fractal_flow.research.volume_profile import ProfileEvent


class RevisionOperation(StrEnum):
    UPSERT = "UPSERT"
    CANCEL = "CANCEL"


class RevisionHistoryError(ValueError):
    """Revision history is ambiguous or violates the immutable-chain contract."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ProfileRevision:
    """One immutable revision record.

    ``logical_event_id`` identifies the observation across corrections;
    ``revision_id`` identifies this immutable version. ``supersedes_revision_id``
    links to the prior revision, or is ``None`` for the chain root.

    The revision's ``available_at_ns`` is the time this revision became knowable.
    For UPSERT, ``event`` carries the normalized observation. CANCEL carries no
    event. Event-time semantics remain those of ``ProfileEvent``.
    """

    logical_event_id: str
    revision_id: str
    supersedes_revision_id: str | None
    operation: RevisionOperation
    available_at_ns: int
    event: ProfileEvent | None

    def __post_init__(self) -> None:
        if not isinstance(self.logical_event_id, str) or not self.logical_event_id.strip():
            raise RevisionHistoryError("INVALID_LOGICAL_EVENT_ID", "logical_event_id must be non-empty")
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise RevisionHistoryError("INVALID_REVISION_ID", "revision_id must be non-empty")
        if self.supersedes_revision_id is not None and (
            not isinstance(self.supersedes_revision_id, str) or not self.supersedes_revision_id.strip()
        ):
            raise RevisionHistoryError("INVALID_SUPERSEDES_ID", "supersedes_revision_id must be None or non-empty")
        if not isinstance(self.operation, RevisionOperation):
            raise RevisionHistoryError("INVALID_REVISION_OPERATION", "operation must be a RevisionOperation")
        if isinstance(self.available_at_ns, bool) or not isinstance(self.available_at_ns, int) or self.available_at_ns < 0:
            raise RevisionHistoryError("INVALID_REVISION_AVAILABILITY", "available_at_ns must be a non-negative integer")
        if self.operation is RevisionOperation.UPSERT and self.event is None:
            raise RevisionHistoryError("UPSERT_EVENT_REQUIRED", "UPSERT revision requires an event")
        if self.operation is RevisionOperation.CANCEL and self.event is not None:
            raise RevisionHistoryError("CANCEL_EVENT_FORBIDDEN", "CANCEL revision must not carry an event")
        if self.event is not None and not isinstance(self.event, ProfileEvent):
            raise RevisionHistoryError(
                "INVALID_REVISION_EVENT_TYPE",
                "revision event must be a ProfileEvent or None",
            )
        if self.event is not None and self.event.available_at_ns > self.available_at_ns:
            raise RevisionHistoryError(
                "EVENT_NOT_YET_AVAILABLE",
                "revision cannot be available before its embedded event",
            )


@dataclass(frozen=True, slots=True)
class ResolvedProfileRevision:
    logical_event_id: str
    revision_id: str
    operation: RevisionOperation
    available_at_ns: int
    event: ProfileEvent | None


@dataclass(frozen=True, slots=True)
class RevisionResolution:
    watermark_ns: int
    heads: tuple[ResolvedProfileRevision, ...]

    @property
    def active(self) -> tuple[ResolvedProfileRevision, ...]:
        """Visible UPSERT heads, sorted by logical event ID."""
        return tuple(head for head in self.heads if head.operation is RevisionOperation.UPSERT)

    def to_profile_events(self) -> tuple[ProfileEvent, ...]:
        """Adapt active heads to the reference calculator's stable event-ID contract.

        The logical ID is used as ProfileEvent.event_id so corrections replace an
        observation rather than double-counting it. The selected revision's
        availability is retained as the causal availability time.
        """
        return tuple(
            replace(head.event, event_id=head.logical_event_id, available_at_ns=head.available_at_ns)
            for head in self.active
            if head.event is not None
        )


def resolve_profile_revisions(
    revisions: Iterable[ProfileRevision], *, watermark_ns: int
) -> RevisionResolution:
    """Resolve unique linear revision chains as known at ``watermark_ns``.

    Records with availability strictly after the watermark are invisible and
    cannot alter the result. Within the visible set, revision IDs are globally
    unique, every non-root revision must point to a visible predecessor in the
    same logical chain, and each predecessor may have at most one child. Any
    ambiguity fails closed; input order never breaks ties.
    """
    if isinstance(watermark_ns, bool) or not isinstance(watermark_ns, int) or watermark_ns < 0:
        raise RevisionHistoryError("INVALID_WATERMARK", "watermark_ns must be a non-negative integer")

    try:
        revision_iterator = iter(revisions)
    except TypeError as exc:
        raise RevisionHistoryError(
            "INVALID_REVISION_ITERABLE", "revisions must be an iterable of ProfileRevision records"
        ) from exc

    records = list(revision_iterator)
    for index, item in enumerate(records):
        if not isinstance(item, ProfileRevision):
            raise RevisionHistoryError(
                "INVALID_REVISION_RECORD",
                f"revisions[{index}] must be a ProfileRevision",
            )

    visible = [item for item in records if item.available_at_ns <= watermark_ns]
    by_revision_id: dict[str, ProfileRevision] = {}
    for item in visible:
        prior = by_revision_id.get(item.revision_id)
        if prior is not None:
            if prior != item:
                raise RevisionHistoryError(
                    "CONFLICTING_REVISION_ID", f"revision_id {item.revision_id!r} has conflicting visible records"
                )
            raise RevisionHistoryError("DUPLICATE_REVISION_ID", f"revision_id {item.revision_id!r} appears more than once")
        by_revision_id[item.revision_id] = item

    children: dict[str, str] = {}
    roots: dict[str, str] = {}
    for item in visible:
        if item.supersedes_revision_id is None:
            if item.logical_event_id in roots:
                raise RevisionHistoryError(
                    "MULTIPLE_CHAIN_ROOTS", f"logical event {item.logical_event_id!r} has multiple visible roots"
                )
            roots[item.logical_event_id] = item.revision_id
            continue
        predecessor = by_revision_id.get(item.supersedes_revision_id)
        if predecessor is None:
            raise RevisionHistoryError(
                "MISSING_PREDECESSOR",
                f"revision {item.revision_id!r} references predecessor {item.supersedes_revision_id!r} not visible at watermark",
            )
        if predecessor.logical_event_id != item.logical_event_id:
            raise RevisionHistoryError(
                "CROSS_LOGICAL_PREDECESSOR",
                f"revision {item.revision_id!r} supersedes a different logical event",
            )
        if item.supersedes_revision_id in children:
            raise RevisionHistoryError(
                "REVISION_FORK", f"predecessor {item.supersedes_revision_id!r} has multiple visible children"
            )
        children[item.supersedes_revision_id] = item.revision_id

    logical_ids = {item.logical_event_id for item in visible}
    resolved: list[ResolvedProfileRevision] = []
    for logical_id in sorted(logical_ids):
        root_id = roots.get(logical_id)
        if root_id is None:
            raise RevisionHistoryError("MISSING_CHAIN_ROOT", f"logical event {logical_id!r} has no visible root")
        current_id = root_id
        visited: set[str] = set()
        while True:
            if current_id in visited:
                raise RevisionHistoryError("REVISION_CYCLE", f"cycle detected in logical event {logical_id!r}")
            visited.add(current_id)
            current = by_revision_id[current_id]
            child_id = children.get(current_id)
            if child_id is None:
                resolved.append(
                    ResolvedProfileRevision(
                        logical_event_id=current.logical_event_id,
                        revision_id=current.revision_id,
                        operation=current.operation,
                        available_at_ns=current.available_at_ns,
                        event=current.event,
                    )
                )
                break
            current_id = child_id
        chain_size = sum(1 for item in visible if item.logical_event_id == logical_id)
        if len(visited) != chain_size:
            # A disconnected cycle or secondary component can otherwise hide
            # behind a valid root chain and be silently ignored.
            raise RevisionHistoryError(
                "DISCONNECTED_REVISION_CHAIN",
                f"logical event {logical_id!r} contains revisions not reachable from its root",
            )

    # Run temporal checks only after the complete visible graph has passed
    # structural validation. This preserves deterministic structural errors
    # for forks, cycles, disconnected components, and invalid predecessor links.
    for item in visible:
        if item.supersedes_revision_id is None:
            continue

        predecessor = by_revision_id[item.supersedes_revision_id]
        if item.available_at_ns < predecessor.available_at_ns:
            raise RevisionHistoryError(
                "REVISION_PRECEDES_PREDECESSOR",
                f"revision {item.revision_id!r} is available before "
                f"its predecessor {predecessor.revision_id!r}",
            )

    return RevisionResolution(watermark_ns=watermark_ns, heads=tuple(sorted(resolved, key=lambda h: h.logical_event_id)))

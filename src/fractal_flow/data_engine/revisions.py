"""Immutable quote correction chains, resolved as known at an availability watermark."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from src.fractal_flow.data_engine.core import CanonicalQuote


class RevisionConflict(ValueError):
    """A correction chain is incomplete, contradictory, or temporally unsafe."""


class RevisionOperation(StrEnum):
    UPSERT = "UPSERT"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class QuoteRevision:
    revision_id: str
    logical_event_id: str
    supersedes_revision_id: str | None
    operation: RevisionOperation
    available_at_ns: int
    quote: CanonicalQuote | None

    def __post_init__(self) -> None:
        if not self.revision_id or not self.logical_event_id or self.available_at_ns < 0:
            raise RevisionConflict("revision identity and availability are required")
        if self.supersedes_revision_id is not None and not self.supersedes_revision_id:
            raise RevisionConflict("supersedes_revision_id must be non-empty or None")
        if self.operation is RevisionOperation.UPSERT and self.quote is None:
            raise RevisionConflict("UPSERT requires a quote")
        if self.operation is RevisionOperation.CANCEL and self.quote is not None:
            raise RevisionConflict("CANCEL must not carry a quote")
        if self.quote is not None and self.available_at_ns < self.quote.available_time_ns:
            raise RevisionConflict("revision availability precedes quote availability")


@dataclass(frozen=True)
class ResolvedQuote:
    logical_event_id: str
    revision_id: str
    quote: CanonicalQuote


def resolve_revisions(revisions: tuple[QuoteRevision, ...], watermark_ns: int) -> Mapping[str, ResolvedQuote]:
    """Validate the full chain before applying a visibility watermark.

    Validation must not be limited to visible records; otherwise a malformed future
    revision could become authoritative when the watermark later advances.
    """
    if type(watermark_ns) is not int or watermark_ns < 0:
        raise RevisionConflict("watermark_ns must be a non-negative integer")
    by_logical: dict[str, list[QuoteRevision]] = {}
    seen: set[str] = set()
    for revision in revisions:
        if revision.revision_id in seen:
            raise RevisionConflict("duplicate revision identity")
        seen.add(revision.revision_id)
        by_logical.setdefault(revision.logical_event_id, []).append(revision)
    resolved: dict[str, ResolvedQuote] = {}
    for logical_id, chain in by_logical.items():
        roots = [item for item in chain if item.supersedes_revision_id is None]
        if len(roots) != 1:
            raise RevisionConflict("each logical event requires exactly one root")
        by_id = {item.revision_id: item for item in chain}
        ordered: list[QuoteRevision] = []
        current = roots[0]
        while True:
            ordered.append(current)
            children = [item for item in chain if item.supersedes_revision_id == current.revision_id]
            if len(children) > 1:
                raise RevisionConflict("revision chain forks")
            if not children:
                break
            current = children[0]
        if len(ordered) != len(chain) or any(
            item.supersedes_revision_id is not None and item.supersedes_revision_id not in by_id for item in chain
        ):
            raise RevisionConflict("revision chain is disconnected")
        prior_available = -1
        source_key: tuple[str, str, str, str, str, str] | None = None
        instrument_id: str | None = None
        visible: QuoteRevision | None = None
        for item in ordered:
            if item.available_at_ns < prior_available:
                raise RevisionConflict("revision availability regressed")
            prior_available = item.available_at_ns
            if item.quote is not None:
                if source_key is None:
                    source_key, instrument_id = item.quote.source.key, item.quote.instrument_id
                elif source_key != item.quote.source.key or instrument_id != item.quote.instrument_id:
                    raise RevisionConflict("revision source or instrument changed")
            if item.available_at_ns <= watermark_ns:
                visible = item
        if visible is not None and visible.operation is RevisionOperation.UPSERT:
            assert visible.quote is not None
            resolved[logical_id] = ResolvedQuote(logical_id, visible.revision_id, visible.quote)
    return resolved

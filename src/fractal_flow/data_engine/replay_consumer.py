"""Deterministic, read-only analytical reconstruction from correction history."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json

from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.revisions import ResolvedQuote
from src.fractal_flow.domain.context import DataStatus


class ReplayConsumerError(ValueError):
    """Replay history cannot safely produce an analytical snapshot."""


def _wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


@dataclass(frozen=True)
class ReplaySnapshot:
    """Read-only state visible at one knowledge-time watermark."""

    watermark_ns: int
    scopes: tuple[str, ...]
    quotes: tuple[ResolvedQuote, ...]
    status: DataStatus
    reasons: tuple[str, ...]
    suitable_for_trade: bool
    fingerprint: str


class DeterministicReplayConsumer:
    """Pure correction-history reader; it cannot mutate the journal or authorities."""

    def __init__(self, corrections: DurableCorrectionJournal, *, max_records: int = 100_000) -> None:
        if not isinstance(corrections, DurableCorrectionJournal) or type(max_records) is not int or max_records < 1:
            raise TypeError("validated correction journal and positive max_records are required")
        self._corrections = corrections
        self._max_records = max_records

    def replay(self, watermark_ns: int, scopes: set[CorrectionScope] | None = None) -> ReplaySnapshot:
        if type(watermark_ns) is not int or watermark_ns < 0:
            raise ReplayConsumerError("knowledge-time watermark must be a non-negative integer")
        requested = None if scopes is None else frozenset(scopes)
        if requested is not None and any(not isinstance(scope, CorrectionScope) for scope in requested):
            raise ReplayConsumerError("requested replay scopes must be canonical correction scopes")
        try:
            history = self._corrections.snapshot()  # validates all records, including future ones.
        except Exception as exc:
            raise ReplayConsumerError(f"authoritative correction history is invalid: {exc}") from exc
        if len(history.records) > self._max_records:
            raise ReplayConsumerError("authoritative correction history exceeds replay resource bound")
        selected_scopes = {item.scope for item in history.records} if requested is None else set(requested)
        try:
            resolved = self._corrections.replay_as_known_at(watermark_ns)
        except Exception as exc:
            raise ReplayConsumerError(f"authoritative correction resolution failed: {exc}") from exc
        quotes = tuple(
            sorted(
                (item for item in resolved if CorrectionScope.from_quote(item.quote) in selected_scopes),
                key=lambda item: (item.quote.available_time_ns, item.logical_event_id, item.revision_id),
            )
        )
        reasons = ["QUALITY_NOT_DURABLE"]
        for scope in selected_scopes:
            sequences = sorted(
                {
                    item.revision.quote.source_sequence
                    for item in history.records
                    # History is validated in full above, but a later correction or
                    # source delivery cannot affect what this consumer knew at an
                    # earlier availability watermark.
                    if item.scope == scope
                    and item.revision.available_at_ns <= watermark_ns
                    and item.revision.quote is not None
                    and item.revision.quote.source_sequence is not None
                }
            )
            if any(right > left + 1 for left, right in zip(sequences, sequences[1:])):
                reasons.append("SOURCE_SEQUENCE_GAP")
        scope_ids = tuple(sorted(scope.partition_id for scope in selected_scopes))
        payload = {
            "schema": 1,
            "watermark_ns": watermark_ns,
            "scopes": scope_ids,
            "status": DataStatus.UNAVAILABLE.value,
            "reasons": sorted(reasons),
            "quotes": [
                {
                    "logical_event_id": item.logical_event_id,
                    "revision_id": item.revision_id,
                    "event_id": item.quote.event_id,
                    "source": item.quote.source.key,
                    "instrument_id": item.quote.instrument_id,
                    "event_time_ns": item.quote.event_time_ns,
                    "received_time_ns": item.quote.received_time_ns,
                    "available_time_ns": item.quote.available_time_ns,
                    "bid": _decimal(item.quote.bid),
                    "ask": _decimal(item.quote.ask),
                    "volume": _decimal(item.quote.volume),
                    "volume_semantics": item.quote.volume_semantics.value,
                }
                for item in quotes
            ],
        }
        return ReplaySnapshot(
            watermark_ns,
            scope_ids,
            quotes,
            DataStatus.UNAVAILABLE,
            tuple(sorted(reasons)),
            False,
            sha256(_wire(payload)).hexdigest(),
        )

"""Canonical, versioned encoding for durable Data Engine quote corrections.

The generic :class:`Event` envelope is only a journal carrier.  Its timestamp
fields retain the repository's legacy integer-second convention; all causal
nanoseconds and exact decimals remain in this payload and are validated again
on decode.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping

from src.fractal_flow.data_engine.contracts import LaneScope, SourceIdentity, VolumeSemantics, strict_decimal
from src.fractal_flow.data_engine.core import CanonicalQuote
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import JournalRecord


class CorrectionCodecError(ValueError):
    """A stored correction cannot be treated as canonical correction history."""


CORRECTION_SCHEMA_VERSION = 1
CORRECTION_EVENT_TYPE = "DATA_ENGINE_QUOTE_CORRECTION_V1"
CORRECTION_AGGREGATE_TYPE = "DATA_ENGINE_QUOTE_CORRECTION_V1"
CORRECTION_ACTOR = "DATA_ENGINE"
CORRECTION_AUTHORITY = "ANALYTICAL_ONLY"


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise CorrectionCodecError(f"{name} must be a non-negative integer")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorrectionCodecError(f"{name} must be a non-empty string")
    return value


def _decimal_text(value: object, name: str) -> Decimal:
    if not isinstance(value, str):
        raise CorrectionCodecError(f"{name} must be canonical decimal text")
    parsed = strict_decimal(value, name)
    if format(parsed, "f") != value:
        raise CorrectionCodecError(f"{name} is not canonical fixed-point decimal text")
    # Constructing from Decimal is value-preserving and makes this boundary
    # explicit even when imported contracts are type-skipped by narrow mypy.
    return Decimal(parsed)


@dataclass(frozen=True)
class CorrectionScope:
    """Immutable source/instrument scope inherited by every revision in a chain."""

    source: SourceIdentity
    instrument_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceIdentity):
            raise TypeError("source must be SourceIdentity")
        if not isinstance(self.instrument_id, str) or not self.instrument_id:
            raise CorrectionCodecError("instrument_id must be a non-empty string")

    @property
    def partition_id(self) -> str:
        return _digest({"source": self.source.key, "instrument_id": self.instrument_id})

    @classmethod
    def from_quote(cls, quote: CanonicalQuote) -> "CorrectionScope":
        return cls(quote.source, quote.instrument_id)


@dataclass(frozen=True)
class DecodedCorrection:
    journal_sequence: int
    aggregate_version: int
    event_id: str
    parent_event_id: str
    revision: QuoteRevision
    scope: CorrectionScope


def _source_payload(source: SourceIdentity) -> dict[str, str | None]:
    return {
        "source_id": source.source_id,
        "broker_id": source.broker_id,
        "server_id": source.server_id,
        "lane_scope": source.lane_scope.value,
        "account_id": source.account_id,
        "lane_id": source.lane_id,
    }


def _decode_source(value: object) -> SourceIdentity:
    if not isinstance(value, Mapping) or set(value) != {
        "source_id", "broker_id", "server_id", "lane_scope", "account_id", "lane_id"
    }:
        raise CorrectionCodecError("source must have exactly the canonical identity fields")
    try:
        return SourceIdentity(
            source_id=_text(value["source_id"], "source_id"),
            broker_id=_text(value["broker_id"], "broker_id"),
            server_id=_text(value["server_id"], "server_id"),
            lane_scope=LaneScope(_text(value["lane_scope"], "lane_scope")),
            account_id=None if value["account_id"] is None else _text(value["account_id"], "account_id"),
            lane_id=None if value["lane_id"] is None else _text(value["lane_id"], "lane_id"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise CorrectionCodecError(f"invalid source identity: {exc}") from exc


def _quote_payload(quote: CanonicalQuote) -> dict[str, Any]:
    return {
        "event_id": quote.event_id,
        "source": _source_payload(quote.source),
        "native_record_id": quote.native_record_id,
        "source_sequence": quote.source_sequence,
        "instrument_id": quote.instrument_id,
        "source_symbol": quote.source_symbol,
        "event_time_ns": quote.event_time_ns,
        "received_time_ns": quote.received_time_ns,
        "available_time_ns": quote.available_time_ns,
        "bid": format(quote.bid, "f"),
        "ask": format(quote.ask, "f"),
        "volume": None if quote.volume is None else format(quote.volume, "f"),
        "volume_semantics": quote.volume_semantics.value,
        "raw_payload": dict(quote.raw_payload),
    }


def _decode_quote(value: object) -> CanonicalQuote:
    required = {
        "event_id", "source", "native_record_id", "source_sequence", "instrument_id", "source_symbol",
        "event_time_ns", "received_time_ns", "available_time_ns", "bid", "ask", "volume",
        "volume_semantics", "raw_payload",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise CorrectionCodecError("quote must have exactly the canonical quote fields")
    raw = value["raw_payload"]
    if not isinstance(raw, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in raw.items()):
        raise CorrectionCodecError("raw_payload must be a string-to-string mapping")
    try:
        source_sequence = value["source_sequence"]
        if source_sequence is not None:
            source_sequence = _integer(source_sequence, "source_sequence")
        native_record_id = value["native_record_id"]
        if native_record_id is not None:
            native_record_id = _text(native_record_id, "native_record_id")
        volume = None if value["volume"] is None else _decimal_text(value["volume"], "volume")
        quote = CanonicalQuote(
            event_id=_text(value["event_id"], "quote.event_id"),
            source=_decode_source(value["source"]),
            native_record_id=native_record_id,
            source_sequence=source_sequence,
            instrument_id=_text(value["instrument_id"], "instrument_id"),
            source_symbol=_text(value["source_symbol"], "source_symbol"),
            event_time_ns=_integer(value["event_time_ns"], "event_time_ns"),
            received_time_ns=_integer(value["received_time_ns"], "received_time_ns"),
            available_time_ns=_integer(value["available_time_ns"], "available_time_ns"),
            bid=_decimal_text(value["bid"], "bid"),
            ask=_decimal_text(value["ask"], "ask"),
            volume=volume,
            volume_semantics=VolumeSemantics(_text(value["volume_semantics"], "volume_semantics")),
            raw_payload=dict(raw),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorrectionCodecError(f"invalid canonical quote: {exc}") from exc
    if not quote.event_time_ns <= quote.received_time_ns <= quote.available_time_ns:
        raise CorrectionCodecError("quote causal nanosecond order is invalid")
    return quote


def _scope_payload(scope: CorrectionScope) -> dict[str, object]:
    return {"source": _source_payload(scope.source), "instrument_id": scope.instrument_id}


def _decode_scope(value: object) -> CorrectionScope:
    if not isinstance(value, Mapping) or set(value) != {"source", "instrument_id"}:
        raise CorrectionCodecError("scope must have exactly source and instrument_id")
    return CorrectionScope(_decode_source(value["source"]), _text(value["instrument_id"], "scope.instrument_id"))


def event_id_for(revision: QuoteRevision, scope: CorrectionScope) -> str:
    return "data-engine-correction-v1:" + _digest(
        {"revision_id": revision.revision_id, "logical_event_id": revision.logical_event_id, "scope": _scope_payload(scope)}
    )


def encode_correction(revision: QuoteRevision, scope: CorrectionScope, aggregate_version: int, parent_event_id: str) -> Event:
    """Encode one immutable revision without losing exact Decimal/UTC-ns values."""
    if not isinstance(revision, QuoteRevision) or not isinstance(scope, CorrectionScope):
        raise TypeError("revision and scope must be canonical correction values")
    if type(aggregate_version) is not int or aggregate_version <= 0:
        raise CorrectionCodecError("aggregate_version must be a positive integer")
    if not isinstance(parent_event_id, str) or not parent_event_id:
        raise CorrectionCodecError("parent_event_id must be non-empty")
    if revision.quote is not None and CorrectionScope.from_quote(revision.quote) != scope:
        raise CorrectionCodecError("revision quote conflicts with immutable correction scope")
    quote_payload = None if revision.quote is None else _quote_payload(revision.quote)
    payload: dict[str, object] = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "kind": "QUOTE_CORRECTION",
        "revision_id": revision.revision_id,
        "logical_event_id": revision.logical_event_id,
        "supersedes_revision_id": revision.supersedes_revision_id,
        "operation": revision.operation.value,
        "available_at_ns": revision.available_at_ns,
        "scope": _scope_payload(scope),
        "quote": quote_payload,
    }
    if revision.quote is not None:
        source_ns = revision.quote.event_time_ns
        event_ns = revision.quote.received_time_ns
    else:
        source_ns = event_ns = revision.available_at_ns
    return Event(
        event_id=event_id_for(revision, scope),
        event_type=CORRECTION_EVENT_TYPE,
        aggregate_type=CORRECTION_AGGREGATE_TYPE,
        aggregate_id=scope.partition_id,
        root_id=scope.partition_id,
        parent_id=parent_event_id,
        aggregate_version=aggregate_version,
        source_timestamp=source_ns // 1_000_000_000,
        event_timestamp=event_ns // 1_000_000_000,
        processing_timestamp=revision.available_at_ns // 1_000_000_000,
        payload=payload,
        actor_id=CORRECTION_ACTOR,
        authority=CORRECTION_AUTHORITY,
    )


def decode_correction(record: JournalRecord) -> DecodedCorrection:
    """Decode and fully bind a journal record to the correction schema."""
    event = record.event
    if (
        event.event_type != CORRECTION_EVENT_TYPE or event.aggregate_type != CORRECTION_AGGREGATE_TYPE
        or event.actor_id != CORRECTION_ACTOR or event.authority != CORRECTION_AUTHORITY
    ):
        raise CorrectionCodecError("record is not a Data Engine analytical correction")
    payload = event.payload
    if not isinstance(payload, Mapping) or set(payload) != {
        "schema_version", "kind", "revision_id", "logical_event_id", "supersedes_revision_id", "operation",
        "available_at_ns", "scope", "quote",
    }:
        raise CorrectionCodecError("correction payload has unsupported or ambiguous fields")
    if payload["schema_version"] != CORRECTION_SCHEMA_VERSION or payload["kind"] != "QUOTE_CORRECTION":
        raise CorrectionCodecError("unsupported correction codec version or kind")
    try:
        operation = RevisionOperation(_text(payload["operation"], "operation"))
        supersedes = payload["supersedes_revision_id"]
        if supersedes is not None:
            supersedes = _text(supersedes, "supersedes_revision_id")
        scope = _decode_scope(payload["scope"])
        quote_payload = payload["quote"]
        quote = None if quote_payload is None else _decode_quote(quote_payload)
        revision = QuoteRevision(
            revision_id=_text(payload["revision_id"], "revision_id"),
            logical_event_id=_text(payload["logical_event_id"], "logical_event_id"),
            supersedes_revision_id=supersedes,
            operation=operation,
            available_at_ns=_integer(payload["available_at_ns"], "available_at_ns"),
            quote=quote,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorrectionCodecError(f"invalid correction payload: {exc}") from exc
    if revision.quote is not None and CorrectionScope.from_quote(revision.quote) != scope:
        raise CorrectionCodecError("quote conflicts with persisted correction scope")
    if event.aggregate_id != scope.partition_id or event.root_id != scope.partition_id:
        raise CorrectionCodecError("envelope partition is not bound to correction scope")
    if event.event_id != event_id_for(revision, scope):
        raise CorrectionCodecError("envelope event_id is not bound to correction content")
    if revision.supersedes_revision_id is None and event.parent_id != "DATA_ENGINE_CORRECTION_ROOT":
        raise CorrectionCodecError("root correction must use the canonical root parent")
    if revision.quote is None:
        source_ns = event_ns = revision.available_at_ns
    else:
        source_ns, event_ns = revision.quote.event_time_ns, revision.quote.received_time_ns
    if (event.source_timestamp, event.event_timestamp, event.processing_timestamp) != (
        source_ns // 1_000_000_000, event_ns // 1_000_000_000, revision.available_at_ns // 1_000_000_000
    ):
        raise CorrectionCodecError("generic seconds envelope does not match exact correction timestamps")
    return DecodedCorrection(record.sequence_number, event.aggregate_version, event.event_id, event.parent_id, revision, scope)

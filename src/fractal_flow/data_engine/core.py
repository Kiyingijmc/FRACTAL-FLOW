"""Deterministic, in-process Data Engine G2 ingress core.

This is a pure analytical boundary.  It has no dependency on execution, broker
truth, FFBP, or persistence and therefore cannot authorize an order or claim a
durable append.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Mapping

from src.fractal_flow.data_engine.contracts import (
    AmbiguousInstrumentAlias,
    InstrumentAlias,
    InstrumentRegistry,
    RawQuote,
    SourceIdentity,
    UnknownInstrumentAlias,
    VolumeSemantics,
    strict_decimal,
)
from src.fractal_flow.domain.context import DataStatus


class IngestDisposition(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class QualityAssessment:
    """Data-quality outcome using the repository's canonical ``DataStatus`` enum."""

    state: DataStatus
    reasons: tuple[str, ...]
    suitable_for_trade: bool


@dataclass(frozen=True)
class GapNotice:
    source: SourceIdentity
    instrument_id: str
    missing_from_sequence: int
    missing_through_sequence: int


@dataclass(frozen=True)
class CanonicalQuote:
    """Immutable normalized quote with explicit UTC-nanosecond causal times."""

    event_id: str
    source: SourceIdentity
    native_record_id: str | None
    source_sequence: int | None
    instrument_id: str
    source_symbol: str
    event_time_ns: int
    received_time_ns: int
    available_time_ns: int
    bid: Decimal
    ask: Decimal
    volume: Decimal | None
    volume_semantics: VolumeSemantics
    raw_payload: Mapping[str, str]


@dataclass(frozen=True)
class IngestResult:
    disposition: IngestDisposition
    quote: CanonicalQuote | None
    assessment: QualityAssessment
    gap: GapNotice | None = None


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class DataCore:
    """State-minimal validator/normalizer with explicit duplicate and gap outcomes.

    State is deliberately limited to source delivery identities and observed source
    sequences.  It is not durable; G3 must supply a dedicated adapter before any
    restart or durable-recovery claim is valid.
    """

    def __init__(self, registry: InstrumentRegistry) -> None:
        if not isinstance(registry, InstrumentRegistry):
            raise TypeError("registry must be InstrumentRegistry")
        self._registry = registry
        self._native_payloads: dict[tuple[tuple[str, str, str, str, str, str], str], str] = {}
        self._last_sequences: dict[tuple[tuple[str, str, str, str, str, str], str], int] = {}
        self._ingest_sequence = 0

    @staticmethod
    def _raw_fingerprint(raw: RawQuote) -> str:
        bid = strict_decimal(raw.bid, "bid")
        ask = strict_decimal(raw.ask, "ask")
        volume = None if raw.volume is None else strict_decimal(raw.volume, "volume")
        return _digest(
            {
                "source": raw.source.key,
                "native_record_id": raw.native_record_id,
                "source_sequence": raw.source_sequence,
                "source_symbol": raw.source_symbol,
                "event_time_ns": raw.event_time_ns,
                "received_time_ns": raw.received_time_ns,
                "available_time_ns": raw.available_time_ns,
                "bid": format(bid, "f"),
                "ask": format(ask, "f"),
                "volume": None if volume is None else format(volume, "f"),
                "volume_semantics": raw.volume_semantics.value,
                "raw_payload": dict(raw.raw_payload),
            }
        )

    @staticmethod
    def _quality(state: DataStatus, *reasons: str) -> QualityAssessment:
        return QualityAssessment(state=state, reasons=tuple(reasons), suitable_for_trade=state is DataStatus.VALID)

    @staticmethod
    def _on_tick_grid(price: Decimal, tick_size: Decimal) -> bool:
        units = price / tick_size
        return units == units.to_integral_value()

    @classmethod
    def _invalid_quote_reason(cls, raw: RawQuote, alias: InstrumentAlias) -> str | None:
        bid = strict_decimal(raw.bid, "bid")
        ask = strict_decimal(raw.ask, "ask")
        volume = None if raw.volume is None else strict_decimal(raw.volume, "volume")
        if bid <= 0 or ask <= 0:
            return "NON_POSITIVE_PRICE"
        if ask < bid:
            return "CROSSED_QUOTE"
        if not cls._on_tick_grid(bid, alias.tick_size) or not cls._on_tick_grid(ask, alias.tick_size):
            return "PRICE_OFF_TICK_GRID"
        if volume is not None and volume < 0:
            return "NEGATIVE_VOLUME"
        if raw.volume_semantics is not VolumeSemantics.UNKNOWN and raw.volume is None:
            return "VOLUME_SEMANTICS_MISMATCH"
        return None

    def ingest(self, raw: RawQuote) -> IngestResult:
        if not isinstance(raw, RawQuote):
            raise TypeError("raw must be RawQuote")
        self._ingest_sequence += 1
        try:
            alias = self._registry.resolve(raw.source, raw.source_symbol, raw.event_time_ns)
        except UnknownInstrumentAlias:
            return IngestResult(IngestDisposition.QUARANTINED, None, self._quality(DataStatus.INVALID, "UNKNOWN_INSTRUMENT_ALIAS"))
        except AmbiguousInstrumentAlias:
            return IngestResult(IngestDisposition.QUARANTINED, None, self._quality(DataStatus.CONFLICT, "AMBIGUOUS_INSTRUMENT_ALIAS"))

        invalid_reason = self._invalid_quote_reason(raw, alias)
        if invalid_reason is not None:
            return IngestResult(IngestDisposition.QUARANTINED, None, self._quality(DataStatus.INVALID, invalid_reason))

        fingerprint = self._raw_fingerprint(raw)
        if raw.native_record_id is not None:
            native_key = (raw.source.key, raw.native_record_id)
            prior = self._native_payloads.get(native_key)
            if prior is not None:
                if prior == fingerprint:
                    return IngestResult(
                        IngestDisposition.DUPLICATE,
                        None,
                        self._quality(DataStatus.DEGRADED, "DUPLICATE_DELIVERY"),
                    )
                return IngestResult(
                    IngestDisposition.QUARANTINED,
                    None,
                    self._quality(DataStatus.CONFLICT, "NATIVE_ID_PAYLOAD_CONFLICT"),
                )
            self._native_payloads[native_key] = fingerprint

        sequence_key = (raw.source.key, alias.instrument_id)
        gap: GapNotice | None = None
        reasons: list[str] = []
        if raw.source_sequence is not None:
            prior_sequence = self._last_sequences.get(sequence_key)
            if prior_sequence is not None:
                if raw.source_sequence <= prior_sequence:
                    reasons.append("SOURCE_SEQUENCE_REGRESSION")
                elif raw.source_sequence > prior_sequence + 1:
                    reasons.append("SOURCE_SEQUENCE_GAP")
                    gap = GapNotice(raw.source, alias.instrument_id, prior_sequence + 1, raw.source_sequence - 1)
            if prior_sequence is None or raw.source_sequence > prior_sequence:
                self._last_sequences[sequence_key] = raw.source_sequence

        if raw.native_record_id is not None:
            event_id = _digest({"namespace": "data-engine-v1", "source": raw.source.key, "native_id": raw.native_record_id})
        else:
            event_id = _digest(
                {"namespace": "data-engine-v1", "source": raw.source.key, "delivery_index": self._ingest_sequence, "raw": fingerprint}
            )
        bid = strict_decimal(raw.bid, "bid")
        ask = strict_decimal(raw.ask, "ask")
        volume = None if raw.volume is None else strict_decimal(raw.volume, "volume")
        quote = CanonicalQuote(
            event_id=event_id,
            source=raw.source,
            native_record_id=raw.native_record_id,
            source_sequence=raw.source_sequence,
            instrument_id=alias.instrument_id,
            source_symbol=raw.source_symbol,
            event_time_ns=raw.event_time_ns,
            received_time_ns=raw.received_time_ns,
            available_time_ns=raw.available_time_ns,
            bid=bid,
            ask=ask,
            volume=volume,
            volume_semantics=raw.volume_semantics,
            raw_payload=dict(raw.raw_payload),
        )
        assessment = self._quality(DataStatus.DEGRADED if reasons else DataStatus.VALID, *reasons)
        return IngestResult(IngestDisposition.ACCEPTED, quote, assessment, gap)

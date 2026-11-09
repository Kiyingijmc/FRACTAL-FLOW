"""Narrow G3 adapter from analytical quotes to the established durable journal.

The generic journal remains the durability authority.  Exact nanosecond times are
kept in the payload because the legacy generic Event timestamp fields are seconds
domain and are not a substitute for this data contract's causal timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from src.fractal_flow.data_engine.contracts import LaneScope, SourceIdentity, VolumeSemantics, strict_decimal
from src.fractal_flow.data_engine.core import CanonicalQuote, QualityAssessment
from src.fractal_flow.domain.context import DataStatus
from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalRecord


class DataPersistenceError(ValueError):
    """The data-journal adapter cannot safely encode or recover a quote."""


class DataPersistenceConflict(DataPersistenceError):
    """A supposedly stable data event identity was reused with changed content."""


class DataPersistenceCorruption(DataPersistenceError):
    """A generic journal event does not satisfy this adapter's payload contract."""


@dataclass(frozen=True)
class PersistedQuote:
    journal_sequence: int
    quote: CanonicalQuote
    assessment: QualityAssessment

    @property
    def event_time_ns(self) -> int:
        return self.quote.event_time_ns

    @property
    def available_time_ns(self) -> int:
        return self.quote.available_time_ns


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class DataJournalAdapter:
    """Append/replay adapter with exact-retry idempotency in one application process.

    It deliberately offers no cross-process atomicity guarantee: callers needing
    that property must establish an external single-writer/transaction authority.
    """

    AGGREGATE_TYPE = "DATA_ENGINE_QUOTE_V1"
    EVENT_TYPE = "DATA_ENGINE_QUOTE_RECORDED_V1"
    ACTOR = "DATA_ENGINE"
    AUTHORITY = "ANALYTICAL_ONLY"
    PAYLOAD_VERSION = 1

    def __init__(self, journal: DurableEventJournal) -> None:
        if not isinstance(journal, DurableEventJournal):
            raise TypeError("journal must be DurableEventJournal")
        self._journal = journal

    @staticmethod
    def _partition_id(quote: CanonicalQuote) -> str:
        return _digest({"source": quote.source.key, "instrument_id": quote.instrument_id})

    @staticmethod
    def _source_payload(source: SourceIdentity) -> dict[str, str | None]:
        return {
            "source_id": source.source_id,
            "broker_id": source.broker_id,
            "server_id": source.server_id,
            "lane_scope": source.lane_scope.value,
            "account_id": source.account_id,
            "lane_id": source.lane_id,
        }

    @classmethod
    def _payload(cls, quote: CanonicalQuote, assessment: QualityAssessment) -> dict[str, Any]:
        return {
            "payload_version": cls.PAYLOAD_VERSION,
            "kind": "CANONICAL_QUOTE",
            "quote": {
                "event_id": quote.event_id,
                "source": cls._source_payload(quote.source),
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
            },
            "quality": {
                "state": assessment.state.value,
                "reasons": list(assessment.reasons),
                "suitable_for_trade": assessment.suitable_for_trade,
            },
        }

    @staticmethod
    def _default_assessment() -> QualityAssessment:
        # An omitted quality assessment must never silently become trade-suitable.
        return QualityAssessment(DataStatus.UNAVAILABLE, ("QUALITY_ASSESSMENT_OMITTED",), False)

    @classmethod
    def _event_id(cls, quote: CanonicalQuote) -> str:
        return f"data-engine-quote-v1:{quote.event_id}"

    @classmethod
    def _event_for(cls, quote: CanonicalQuote, assessment: QualityAssessment, aggregate_version: int) -> Event:
        payload = cls._payload(quote, assessment)
        partition = cls._partition_id(quote)
        return Event(
            event_id=cls._event_id(quote),
            event_type=cls.EVENT_TYPE,
            aggregate_type=cls.AGGREGATE_TYPE,
            aggregate_id=partition,
            root_id=partition,
            parent_id="DATA_INGRESS",
            aggregate_version=aggregate_version,
            # These integer-second fields preserve legacy Event invariants only.
            # The payload values above remain the exact data-engine causal times.
            source_timestamp=quote.event_time_ns // 1_000_000_000,
            event_timestamp=quote.received_time_ns // 1_000_000_000,
            processing_timestamp=quote.available_time_ns // 1_000_000_000,
            payload=payload,
            actor_id=cls.ACTOR,
            authority=cls.AUTHORITY,
        )

    @classmethod
    def _decode(cls, record: JournalRecord) -> PersistedQuote:
        event = record.event
        if (
            event.event_type != cls.EVENT_TYPE
            or event.aggregate_type != cls.AGGREGATE_TYPE
            or event.actor_id != cls.ACTOR
            or event.authority != cls.AUTHORITY
        ):
            raise DataPersistenceCorruption("journal event is not a data-engine analytical quote record")
        payload = dict(event.payload)
        try:
            if payload.get("payload_version") != cls.PAYLOAD_VERSION or payload.get("kind") != "CANONICAL_QUOTE":
                raise ValueError("unsupported payload version or kind")
            quote_payload = payload["quote"]
            quality_payload = payload["quality"]
            if not isinstance(quote_payload, Mapping) or not isinstance(quality_payload, Mapping):
                raise ValueError("quote and quality payloads must be objects")
            source_payload = quote_payload["source"]
            if not isinstance(source_payload, Mapping):
                raise ValueError("source payload must be an object")
            source = SourceIdentity(
                source_id=str(source_payload["source_id"]),
                broker_id=str(source_payload["broker_id"]),
                server_id=str(source_payload["server_id"]),
                lane_scope=LaneScope(str(source_payload["lane_scope"])),
                account_id=None if source_payload.get("account_id") is None else str(source_payload["account_id"]),
                lane_id=None if source_payload.get("lane_id") is None else str(source_payload["lane_id"]),
            )
            event_id = str(quote_payload["event_id"])
            if event.event_id != cls._event_id_from_string(event_id):
                raise ValueError("generic event identity is not bound to canonical quote identity")
            quote = CanonicalQuote(
                event_id=event_id,
                source=source,
                native_record_id=None
                if quote_payload.get("native_record_id") is None
                else str(quote_payload["native_record_id"]),
                source_sequence=cls._optional_nonnegative_int(quote_payload.get("source_sequence"), "source_sequence"),
                instrument_id=str(quote_payload["instrument_id"]),
                source_symbol=str(quote_payload["source_symbol"]),
                event_time_ns=cls._nonnegative_int(quote_payload["event_time_ns"], "event_time_ns"),
                received_time_ns=cls._nonnegative_int(quote_payload["received_time_ns"], "received_time_ns"),
                available_time_ns=cls._nonnegative_int(quote_payload["available_time_ns"], "available_time_ns"),
                bid=strict_decimal(quote_payload["bid"], "bid"),
                ask=strict_decimal(quote_payload["ask"], "ask"),
                volume=None
                if quote_payload.get("volume") is None
                else strict_decimal(quote_payload["volume"], "volume"),
                volume_semantics=VolumeSemantics(str(quote_payload["volume_semantics"])),
                raw_payload={str(key): str(value) for key, value in dict(quote_payload.get("raw_payload", {})).items()},
            )
            if not quote.event_time_ns <= quote.received_time_ns <= quote.available_time_ns:
                raise ValueError("exact nanosecond causal order is invalid")
            assessment = QualityAssessment(
                state=DataStatus(str(quality_payload["state"])),
                reasons=tuple(str(reason) for reason in quality_payload["reasons"]),
                suitable_for_trade=bool(quality_payload["suitable_for_trade"]),
            )
            if assessment.suitable_for_trade != (assessment.state is DataStatus.VALID):
                raise ValueError("trade suitability does not match fail-closed data status")
            if event.aggregate_id != cls._partition_id(quote):
                raise ValueError("aggregate partition is not bound to source and instrument")
            return PersistedQuote(record.sequence_number, quote, assessment)
        except (KeyError, TypeError, ValueError) as exc:
            raise DataPersistenceCorruption(f"invalid data-engine quote payload: {exc}") from exc

    @classmethod
    def _event_id_from_string(cls, quote_event_id: str) -> str:
        return f"data-engine-quote-v1:{quote_event_id}"

    @staticmethod
    def _nonnegative_int(value: object, field_name: str) -> int:
        if type(value) is not int or value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        return value

    @classmethod
    def _optional_nonnegative_int(cls, value: object, field_name: str) -> int | None:
        return None if value is None else cls._nonnegative_int(value, field_name)

    def append(self, quote: CanonicalQuote, assessment: QualityAssessment | None = None) -> PersistedQuote:
        if not isinstance(quote, CanonicalQuote):
            raise TypeError("quote must be CanonicalQuote")
        if assessment is None:
            assessment = self._default_assessment()
        if not isinstance(assessment, QualityAssessment):
            raise TypeError("assessment must be QualityAssessment")
        event_id = self._event_id(quote)
        desired_payload = self._payload(quote, assessment)
        for record in self._journal.get_all_records():
            if record.event.event_id == event_id:
                persisted = self._decode(record)
                if _canonical_json(dict(record.event.payload)) != _canonical_json(desired_payload):
                    raise DataPersistenceConflict("data event identity reused with different canonical payload")
                return persisted
        partition = self._partition_id(quote)
        event = self._event_for(
            quote, assessment, self._journal.get_aggregate_sequence(self.AGGREGATE_TYPE, partition) + 1
        )
        try:
            record = self._journal.append(event)
        except Exception as exc:
            # Preserve the generic journal's explicit durability/fault semantics.
            raise DataPersistenceError(f"data quote append failed: {exc}") from exc
        return self._decode(record)

    def replay_as_known_at(self, available_at_ns: int) -> tuple[PersistedQuote, ...]:
        if type(available_at_ns) is not int or available_at_ns < 0:
            raise ValueError("available_at_ns must be a non-negative integer")
        records = [
            self._decode(record)
            for record in self._journal.get_all_records()
            if record.event.aggregate_type == self.AGGREGATE_TYPE
        ]
        visible = [record for record in records if record.quote.available_time_ns <= available_at_ns]
        return tuple(
            sorted(visible, key=lambda item: (item.quote.available_time_ns, item.journal_sequence, item.quote.event_id))
        )

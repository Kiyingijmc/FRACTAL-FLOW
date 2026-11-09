"""Additive data-ingress contracts with explicit identity and nanosecond units.

The repository's legacy ``Event``, ``Tick``, and ``Bar`` contracts use seconds-domain
timestamps.  These types do not reinterpret those fields: ``*_ns`` is an explicit,
separate UTC-nanosecond causal contract for the Data Engine boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class DataContractError(ValueError):
    """A data-engine contract was malformed or unsafe."""


class UnknownInstrumentAlias(DataContractError):
    """No effective, source-scoped alias resolves a source symbol."""


class AmbiguousInstrumentAlias(DataContractError):
    """More than one effective alias resolves a source symbol."""


class LaneScope(StrEnum):
    """Explicit visibility scope; this is not execution authorization."""

    SHARED_MARKET = "SHARED_MARKET"
    ACCOUNT_PRIVATE = "ACCOUNT_PRIVATE"
    REPLAY = "REPLAY"


class VolumeSemantics(StrEnum):
    """Volume meanings that must never be silently promoted to traded volume."""

    TRADED_UNITS = "TRADED_UNITS"
    TICK_ACTIVITY_COUNT = "TICK_ACTIVITY_COUNT"
    BROKER_REPORTED_VOLUME = "BROKER_REPORTED_VOLUME"
    DERIVED_ESTIMATE = "DERIVED_ESTIMATE"
    UNKNOWN = "UNKNOWN"


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataContractError(f"{field_name} must be a non-empty string")
    return value


def _require_ns(value: int, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise DataContractError(f"{field_name} must be a non-negative integer UTC nanosecond value")
    return value


def strict_decimal(value: Decimal | str | int, field_name: str) -> Decimal:
    """Parse an exact finite decimal without accepting a binary-float authority input."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must not be boolean")
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not be float; use Decimal or decimal text")
    if not isinstance(value, (Decimal, str, int)):
        raise TypeError(f"{field_name} must be Decimal, decimal text, or integer")
    try:
        parsed = Decimal(value) if isinstance(value, str) else Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise DataContractError(f"{field_name} is not a decimal") from exc
    if not parsed.is_finite():
        raise DataContractError(f"{field_name} must be finite")
    return parsed


@dataclass(frozen=True)
class SourceIdentity:
    """Adapter identity and visibility scope, deliberately separate from broker truth."""

    source_id: str
    broker_id: str
    server_id: str
    lane_scope: LaneScope
    account_id: str | None = None
    lane_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        _require_text(self.broker_id, "broker_id")
        _require_text(self.server_id, "server_id")
        if not isinstance(self.lane_scope, LaneScope):
            raise DataContractError("lane_scope must be LaneScope")
        if self.lane_scope is LaneScope.ACCOUNT_PRIVATE:
            _require_text(self.account_id or "", "account_id")
            _require_text(self.lane_id or "", "lane_id")
        elif self.account_id is not None or self.lane_id is not None:
            raise DataContractError("shared and replay sources must not carry account or lane identity")

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.source_id,
            self.broker_id,
            self.server_id,
            self.lane_scope.value,
            self.account_id or "",
            self.lane_id or "",
        )


@dataclass(frozen=True)
class InstrumentAlias:
    """One versioned source-symbol mapping, scoped to an exact source identity."""

    source: SourceIdentity
    native_symbol: str
    instrument_id: str
    tick_size: Decimal
    effective_from_ns: int
    effective_until_ns: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceIdentity):
            raise DataContractError("source must be SourceIdentity")
        _require_text(self.native_symbol, "native_symbol")
        _require_text(self.instrument_id, "instrument_id")
        tick_size = strict_decimal(self.tick_size, "tick_size")
        if tick_size <= 0:
            raise DataContractError("tick_size must be positive")
        object.__setattr__(self, "tick_size", tick_size)
        _require_ns(self.effective_from_ns, "effective_from_ns")
        if self.effective_until_ns is not None:
            _require_ns(self.effective_until_ns, "effective_until_ns")
            if self.effective_until_ns < self.effective_from_ns:
                raise DataContractError("effective_until_ns cannot precede effective_from_ns")

    def is_effective_at(self, timestamp_ns: int) -> bool:
        return timestamp_ns >= self.effective_from_ns and (
            self.effective_until_ns is None or timestamp_ns <= self.effective_until_ns
        )


class InstrumentRegistry:
    """Immutable, fail-closed alias resolver; it does not mutate broker metadata."""

    def __init__(self, aliases: list[InstrumentAlias] | tuple[InstrumentAlias, ...]) -> None:
        if not aliases:
            raise DataContractError("at least one instrument alias is required")
        grouped: dict[tuple[tuple[str, str, str, str, str, str], str], list[InstrumentAlias]] = {}
        for alias in aliases:
            if not isinstance(alias, InstrumentAlias):
                raise TypeError("aliases must contain InstrumentAlias")
            grouped.setdefault((alias.source.key, alias.native_symbol), []).append(alias)
        for key, group in grouped.items():
            ordered = sorted(group, key=lambda item: item.effective_from_ns)
            for previous, current in zip(ordered, ordered[1:]):
                if previous.effective_until_ns is None or current.effective_from_ns <= previous.effective_until_ns:
                    raise AmbiguousInstrumentAlias(f"overlapping alias effective intervals for {key!r}")
        self._aliases = tuple(aliases)

    def resolve(self, source: SourceIdentity, native_symbol: str, timestamp_ns: int) -> InstrumentAlias:
        _require_text(native_symbol, "native_symbol")
        _require_ns(timestamp_ns, "timestamp_ns")
        matches = [
            alias
            for alias in self._aliases
            if alias.source == source and alias.native_symbol == native_symbol and alias.is_effective_at(timestamp_ns)
        ]
        if not matches:
            raise UnknownInstrumentAlias("no effective source-scoped instrument alias")
        if len(matches) != 1:
            raise AmbiguousInstrumentAlias("multiple effective source-scoped instrument aliases")
        return matches[0]


@dataclass(frozen=True)
class RawQuote:
    """Validated source observation before source alias normalization.

    ``raw_payload`` is retained as read-only provenance.  It is not interpreted as
    broker truth and must not contain credentials.
    """

    source: SourceIdentity
    native_record_id: str | None
    source_sequence: int | None
    source_symbol: str
    event_time_ns: int
    received_time_ns: int
    available_time_ns: int
    bid: Decimal | str | int
    ask: Decimal | str | int
    volume: Decimal | str | int | None
    volume_semantics: VolumeSemantics
    raw_payload: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceIdentity):
            raise DataContractError("source must be SourceIdentity")
        if self.native_record_id is not None:
            _require_text(self.native_record_id, "native_record_id")
        if self.source_sequence is not None and (type(self.source_sequence) is not int or self.source_sequence < 0):
            raise DataContractError("source_sequence must be a non-negative integer or None")
        _require_text(self.source_symbol, "source_symbol")
        event_time = _require_ns(self.event_time_ns, "event_time_ns")
        received_time = _require_ns(self.received_time_ns, "received_time_ns")
        available_time = _require_ns(self.available_time_ns, "available_time_ns")
        if not event_time <= received_time <= available_time:
            raise DataContractError("timestamp ordering event <= received <= available is required")
        object.__setattr__(self, "bid", strict_decimal(self.bid, "bid"))
        object.__setattr__(self, "ask", strict_decimal(self.ask, "ask"))
        if self.volume is not None:
            object.__setattr__(self, "volume", strict_decimal(self.volume, "volume"))
        if not isinstance(self.volume_semantics, VolumeSemantics):
            raise DataContractError("volume_semantics must be VolumeSemantics")
        if not isinstance(self.raw_payload, Mapping):
            raise DataContractError("raw_payload must be a mapping")
        object.__setattr__(
            self,
            "raw_payload",
            MappingProxyType({str(key): str(value) for key, value in sorted(self.raw_payload.items())}),
        )

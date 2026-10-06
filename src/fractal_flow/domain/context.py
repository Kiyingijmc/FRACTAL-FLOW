"""Canonical causal market context for FRACTAL-FLOW v2.3.

This module is deliberately informational: it normalizes instrument geometry,
time and validity without manufacturing direction or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum, unique
from typing import Any


@unique
class DataStatus(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    tick_size: Decimal
    price_precision: int
    volume_step: Decimal = Decimal("0.01")
    contract_size: Decimal = Decimal("1")
    timezone: str = "UTC"
    asset_class: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not self.symbol or self.tick_size <= 0 or self.price_precision < 0:
            raise ValueError("InstrumentSpec requires positive tick_size and non-negative price_precision")
        if self.volume_step <= 0 or self.contract_size <= 0:
            raise ValueError("InstrumentSpec volume_step and contract_size must be positive")

    def quantize_price(self, price: Decimal) -> Decimal:
        """Quantize to the instrument tick grid using deterministic half-even rounding."""
        units = (price / self.tick_size).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
        return units * self.tick_size

    def price_relation(self, left: Decimal, right: Decimal) -> str:
        l = self.quantize_price(left)
        r = self.quantize_price(right)
        if l > r:
            return "GT"
        if l < r:
            return "LT"
        return "EQ"


@dataclass(frozen=True)
class CausalWatermark:
    """Latest event-time boundary that an engine is allowed to consume."""

    timestamp: int
    sequence: int = 0

    def __post_init__(self) -> None:
        if self.timestamp < 0 or self.sequence < 0:
            raise ValueError("CausalWatermark fields must be non-negative")

    def admits(self, event_timestamp: int, event_sequence: int = 0) -> bool:
        return (event_timestamp, event_sequence) <= (self.timestamp, self.sequence)


@dataclass(frozen=True)
class MarketContextSnapshot:
    """Same-watermark bundle used to prevent cross-engine temporal skew."""

    root_id: str
    symbol: str
    timeframe: str
    watermark: CausalWatermark
    instrument: InstrumentSpec
    data_status: DataStatus
    volatility: Decimal
    volatility_valid: bool
    structure_version: int
    flow_version: int
    regime_version: int
    pde_version: int
    role_version: int = 0
    location_version: int = 0
    volatility_version: int = 0
    evidence_version: int = 0
    data_quality_version: int = 0
    feature_version: int = 1
    configuration_version: int = 1
    configuration_id: str = ""
    valid_until: int | None = None
    states: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.root_id or not self.symbol:
            raise ValueError("MarketContextSnapshot requires root_id and symbol")
        if self.configuration_version <= 0:
            raise ValueError("configuration_version must be positive")
        if self.volatility < 0:
            raise ValueError("volatility cannot be negative")
        if self.valid_until is not None and self.valid_until < self.watermark.timestamp:
            raise ValueError("valid_until cannot precede causal watermark")

    def is_usable(self, now_timestamp: int | None = None) -> bool:
        if self.data_status not in (DataStatus.VALID, DataStatus.DEGRADED):
            return False
        if not self.volatility_valid:
            return False
        return self.valid_until is None or now_timestamp is None or now_timestamp <= self.valid_until

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "watermark": {"timestamp": self.watermark.timestamp, "sequence": self.watermark.sequence},
            "instrument": {
                "symbol": self.instrument.symbol,
                "tick_size": str(self.instrument.tick_size),
                "price_precision": self.instrument.price_precision,
                "volume_step": str(self.instrument.volume_step),
                "contract_size": str(self.instrument.contract_size),
                "timezone": self.instrument.timezone,
                "asset_class": self.instrument.asset_class,
            },
            "data_status": self.data_status.value,
            "volatility": str(self.volatility),
            "volatility_valid": self.volatility_valid,
            "structure_version": self.structure_version,
            "flow_version": self.flow_version,
            "regime_version": self.regime_version,
            "pde_version": self.pde_version,
            "role_version": self.role_version,
            "location_version": self.location_version,
            "volatility_version": self.volatility_version,
            "evidence_version": self.evidence_version,
            "data_quality_version": self.data_quality_version,
            "feature_version": self.feature_version,
            "configuration_version": self.configuration_version,
            "configuration_id": self.configuration_id,
            "valid_until": self.valid_until,
            "states": dict(self.states or {}),
        }

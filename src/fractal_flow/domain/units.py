"""Unit-safe representations, exact Decimal arithmetic, and instrument-specific conversions for FRACTAL FLOW domain primitives."""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Price:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value) or self.value <= 0.0:
            raise ValueError(f"Price must be a finite positive number, got {self.value}")


@dataclass(frozen=True)
class PricePips:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"PricePips cannot be NaN or Infinity, got {self.value}")


@dataclass(frozen=True)
class PriceDistance:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value) or self.value < 0.0:
            raise ValueError(f"PriceDistance must be a finite non-negative number, got {self.value}")


@dataclass(frozen=True)
class Points:
    value: float


@dataclass(frozen=True)
class Ticks:
    value: int


@dataclass(frozen=True)
class Volume:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value) or self.value <= 0.0:
            raise ValueError(f"Volume must be a finite positive number, got {self.value}")


@dataclass(frozen=True)
class PositiveCurrencyAmount:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value) or self.value < 0.0:
            raise ValueError(f"PositiveCurrencyAmount cannot be negative or infinite, got {self.value}")


@dataclass(frozen=True)
class SignedCurrencyAmount:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"SignedCurrencyAmount cannot be NaN or Infinity, got {self.value}")


@dataclass(frozen=True)
class DurationNs:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"DurationNs cannot be negative, got {self.value}")


@dataclass(frozen=True)
class Timestamp:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Timestamp cannot be negative, got {self.value}")


@dataclass(frozen=True)
class Ratio:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Ratio cannot be NaN or Infinity, got {self.value}")


@dataclass(frozen=True)
class BoundedRatio:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or not (0.0 <= self.value <= 1.0):
            raise ValueError(f"BoundedRatio must be between 0.0 and 1.0, got {self.value}")


@dataclass(frozen=True)
class Score:
    value: float

    def __post_init__(self) -> None:
        if math.isnan(self.value) or not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.value}")


def price_to_pips(distance: float, digits: int) -> PricePips:
    """Converts price distance to pips using exact Decimal arithmetic based on symbol digits."""
    pip_scale = Decimal("0.0001") if digits in (4, 5) else Decimal("0.01")
    dist_dec = Decimal(str(distance))
    pips = (dist_dec / pip_scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return PricePips(value=float(pips))


def pips_to_price(pips: float, digits: int) -> float:
    """Converts pips to absolute price distance using exact Decimal arithmetic."""
    pip_scale = Decimal("0.0001") if digits in (4, 5) else Decimal("0.01")
    pips_dec = Decimal(str(pips))
    price_dist = (pips_dec * pip_scale).quantize(
        Decimal("0.00001") if digits in (4, 5) else Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )
    return float(price_dist)

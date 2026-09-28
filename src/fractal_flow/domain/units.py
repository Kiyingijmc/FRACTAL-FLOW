"""Unit-safe representations and conversions for FRACTAL FLOW domain primitives."""

from dataclasses import dataclass
from typing import NewType

# Type aliases / NewTypes for strict domain safety
PriceValue = float
PricePipsValue = float
VolumeValue = float
CurrencyAmountValue = float
DurationNsValue = int
TimestampNsValue = int
RatioValue = float
ScoreValue = float


@dataclass(frozen=True)
class Price:
    value: float

    def __post_init__(self) -> None:
        if self.value <= 0.0:
            raise ValueError(f"Price must be positive, got {self.value}")


@dataclass(frozen=True)
class PricePips:
    value: float


@dataclass(frozen=True)
class PriceDistance:
    value: float

    def __post_init__(self) -> None:
        if self.value < 0.0:
            raise ValueError(f"PriceDistance cannot be negative, got {self.value}")


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
        if self.value <= 0.0:
            raise ValueError(f"Volume must be positive, got {self.value}")


@dataclass(frozen=True)
class CurrencyAmount:
    value: float

    def __post_init__(self) -> None:
        if self.value < 0.0:
            raise ValueError(f"CurrencyAmount cannot be negative, got {self.value}")


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


@dataclass(frozen=True)
class Score:
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.value}")


def price_to_pips(distance: float, digits: int) -> PricePips:
    """Converts price distance to pips based on symbol digits (5-digit / 4-digit vs 3-digit / 2-digit JPY)."""
    pip_scale = 10.0 ** (-4 if digits in (4, 5) else -2)
    return PricePips(value=round(distance / pip_scale, 2))


def pips_to_price(pips: float, digits: int) -> float:
    """Converts pips to absolute price distance based on symbol digits."""
    pip_scale = 10.0 ** (-4 if digits in (4, 5) else -2)
    return pips * pip_scale

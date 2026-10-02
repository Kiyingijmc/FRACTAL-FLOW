"""Broker Constraint Model with exact Decimal volume step, stops level, freeze level, and tick normalization."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

from src.fractal_flow.domain.units import Volume


def _to_decimal(val: Union[Decimal, float, int, str]) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


@dataclass(frozen=True)
class BrokerConstraints:
    symbol: str
    base_currency: str
    quote_currency: str
    account_currency: str
    contract_size: Decimal
    tick_size: Decimal
    tick_value: Decimal
    digits: int
    min_volume: Decimal
    max_volume: Decimal
    volume_step: Decimal
    stops_level: Decimal  # In pips
    freeze_level: Decimal  # In pips
    trade_mode: str = "FULL"
    filling_mode: str = "IOC"
    order_mode: str = "MARKET"

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_size", _to_decimal(self.contract_size))
        object.__setattr__(self, "tick_size", _to_decimal(self.tick_size))
        object.__setattr__(self, "tick_value", _to_decimal(self.tick_value))
        object.__setattr__(self, "min_volume", _to_decimal(self.min_volume))
        object.__setattr__(self, "max_volume", _to_decimal(self.max_volume))
        object.__setattr__(self, "volume_step", _to_decimal(self.volume_step))
        object.__setattr__(self, "stops_level", _to_decimal(self.stops_level))
        object.__setattr__(self, "freeze_level", _to_decimal(self.freeze_level))

    def validate_volume(self, requested_volume: Union[Decimal, float, str]) -> Volume:
        """Validates volume alignment using exact Decimal arithmetic."""
        req_dec = _to_decimal(requested_volume)
        min_dec = self.min_volume
        max_dec = self.max_volume
        step_dec = self.volume_step

        if req_dec < min_dec:
            raise ValueError(
                f"Requested volume {requested_volume} below min_volume {self.min_volume} for {self.symbol}"
            )
        if req_dec > max_dec:
            raise ValueError(
                f"Requested volume {requested_volume} above max_volume {self.max_volume} for {self.symbol}"
            )

        # Exact Decimal step alignment check
        remainder = (req_dec - min_dec) % step_dec
        if remainder != Decimal(0):
            raise ValueError(
                f"Requested volume {requested_volume} does not align with min_volume {self.min_volume} "
                f"and volume_step {self.volume_step}"
            )
        return Volume(value=req_dec)

    def validate_stop_distance(self, sl_distance_pips: Union[Decimal, float, str]) -> None:
        """Ensures stop loss distance respects broker stops level and freeze level."""
        sl_dec = _to_decimal(sl_distance_pips)
        stops_dec = self.stops_level
        freeze_dec = self.freeze_level

        if sl_dec < stops_dec:
            raise ValueError(
                f"Stop distance {sl_distance_pips} pips is below broker stops_level {self.stops_level} pips"
            )

        if sl_dec < freeze_dec:
            raise ValueError(
                f"Stop distance {sl_distance_pips} pips violates broker freeze_level {self.freeze_level} pips"
            )

    def validate_price_tick_alignment(self, price: Union[Decimal, float, str]) -> None:
        """Ensures price aligns with broker tick_size."""
        p_dec = _to_decimal(price)
        t_dec = self.tick_size
        remainder = p_dec % t_dec
        if remainder != Decimal(0):
            raise ValueError(f"Price {price} does not align with tick_size {self.tick_size} for {self.symbol}")

"""Broker Constraint Model with exact Decimal volume step, stops level, freeze level, and tick normalization."""

from dataclasses import dataclass
from decimal import Decimal

from src.fractal_flow.domain.units import Volume


@dataclass(frozen=True)
class BrokerConstraints:
    symbol: str
    base_currency: str
    quote_currency: str
    account_currency: str
    contract_size: float
    tick_size: float
    tick_value: float
    digits: int
    min_volume: float
    max_volume: float
    volume_step: float
    stops_level: float  # In pips
    freeze_level: float  # In pips
    trade_mode: str = "FULL"
    filling_mode: str = "IOC"
    order_mode: str = "MARKET"

    def validate_volume(self, requested_volume: float) -> Volume:
        """Validates volume alignment using exact Decimal arithmetic."""
        req_dec = Decimal(str(requested_volume))
        min_dec = Decimal(str(self.min_volume))
        max_dec = Decimal(str(self.max_volume))
        step_dec = Decimal(str(self.volume_step))

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
        return Volume(value=requested_volume)

    def validate_stop_distance(self, sl_distance_pips: float) -> None:
        """Ensures stop loss distance respects broker stops level and freeze level."""
        sl_dec = Decimal(str(sl_distance_pips))
        stops_dec = Decimal(str(self.stops_level))
        freeze_dec = Decimal(str(self.freeze_level))

        if sl_dec < stops_dec:
            raise ValueError(
                f"Stop distance {sl_distance_pips} pips is below broker stops_level {self.stops_level} pips"
            )

        if sl_dec < freeze_dec:
            raise ValueError(
                f"Stop distance {sl_distance_pips} pips violates broker freeze_level {self.freeze_level} pips"
            )

    def validate_price_tick_alignment(self, price: float) -> None:
        """Ensures price aligns with broker tick_size."""
        p_dec = Decimal(str(price))
        t_dec = Decimal(str(self.tick_size))
        remainder = p_dec % t_dec
        if remainder != Decimal(0):
            raise ValueError(
                f"Price {price} does not align with tick_size {self.tick_size} for {self.symbol}"
            )

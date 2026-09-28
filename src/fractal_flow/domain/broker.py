"""Broker Constraint Model and validation logic."""

from dataclasses import dataclass
from src.fractal_flow.domain.units import Volume, PricePips


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
        """Validates and aligns volume against broker constraints."""
        if requested_volume < self.min_volume:
            raise ValueError(
                f"Requested volume {requested_volume} below min_volume {self.min_volume} for {self.symbol}"
            )
        if requested_volume > self.max_volume:
            raise ValueError(
                f"Requested volume {requested_volume} above max_volume {self.max_volume} for {self.symbol}"
            )

        # Check step alignment
        steps = round((requested_volume - self.min_volume) / self.volume_step, 6)
        if not steps.is_integer():
            raise ValueError(
                f"Requested volume {requested_volume} does not align with volume_step {self.volume_step}"
            )
        return Volume(value=requested_volume)

    def validate_stop_distance(self, sl_distance_pips: float) -> None:
        """Ensures stop loss distance respects broker stops level."""
        if sl_distance_pips < self.stops_level:
            raise ValueError(
                f"Stop distance {sl_distance_pips} pips is below broker stops_level {self.stops_level} pips"
            )

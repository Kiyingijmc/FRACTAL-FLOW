"""Location Engine for FRACTAL FLOW.

Evaluates spatial location relative to nearby structure, liquidity boundaries,
session extremes, and higher-timeframe obstacles:
OPEN, FAVORABLE, NEUTRAL, CONGESTED, BLOCKED, EXTREME.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Optional

from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.reason_codes import ReasonCode


@unique
class LocationState(str, Enum):
    OPEN = "OPEN"
    FAVORABLE = "FAVORABLE"
    NEUTRAL = "NEUTRAL"
    CONGESTED = "CONGESTED"
    BLOCKED = "BLOCKED"
    EXTREME = "EXTREME"


@dataclass
class LocationTransitionRecord:
    symbol: str
    timeframe: str
    location_state: LocationState
    previous_location_state: LocationState
    nearby_obstacle_distance: Decimal
    timestamp: int
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "LOCATION"

    def to_envelope(
        self,
        object_id: str,
        source_ts: int = 0,
        event_ts: int = 0,
        processing_ts: int = 0,
    ) -> StateEnvelope:
        s_ts = source_ts or self.timestamp
        e_ts = event_ts or s_ts
        p_ts = processing_ts or e_ts

        return StateEnvelope(
            state_id=f"location_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="LocationState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.location_state.value,
            previous_state=self.previous_location_state.value,
            version=self.state_version,
            source_timestamp=s_ts,
            event_timestamp=e_ts,
            processing_timestamp=p_ts,
            valid_until=p_ts + 300,
            last_seen=s_ts,
            reason_codes=[r.value for r in self.reason_codes],
            configuration_version=self.config_version,
            data_version=self.data_version,
            feature_version=self.feature_version,
            authority=self.authority,
        )


class LocationEngine:
    """Location Engine assessing spatial context and structural obstacles."""

    def __init__(self, symbol: str, timeframe: str = "1M") -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.location_state = LocationState.NEUTRAL
        self.previous_location_state = LocationState.NEUTRAL
        self.state_version = 0

        self._last_parent_version: Optional[int] = None

    def evaluate(
        self,
        bar: Bar,
        protected_high: Optional[Decimal],
        protected_low: Optional[Decimal],
        v_local: Decimal,
        root_id: str,
        parent_id: str,
        parent_version: int,
        htf_obstacle_price: Optional[Decimal] = None,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> LocationTransitionRecord:
        AuthorityMatrix.verify_capability("Location", "WRITE_LOCATION_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"LocationEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        if self._last_parent_version is not None and parent_version < self._last_parent_version:
            raise ValueError(
                f"Parent version regression detected: incoming {parent_version} < current {self._last_parent_version}"
            )

        self._last_parent_version = parent_version

        old_state = self.location_state
        min_dist = Decimal("999999")

        for lvl in (protected_high, protected_low, htf_obstacle_price):
            if lvl is not None:
                dist = abs(bar.close - lvl)
                if dist < min_dist:
                    min_dist = dist

        dist_mult = min_dist / v_local if v_local > Decimal("0.0") else Decimal("10.0")

        if htf_obstacle_price is not None and min_dist <= (Decimal("0.2") * v_local):
            new_state = LocationState.BLOCKED
        elif dist_mult < Decimal("0.5"):
            new_state = LocationState.CONGESTED
        elif dist_mult > Decimal("3.0"):
            new_state = LocationState.OPEN
        elif dist_mult >= Decimal("1.5"):
            new_state = LocationState.FAVORABLE
        else:
            new_state = LocationState.NEUTRAL

        if new_state != old_state:
            self.previous_location_state = old_state
            self.location_state = new_state
            self.state_version += 1

        return LocationTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            location_state=self.location_state,
            previous_location_state=self.previous_location_state,
            nearby_obstacle_distance=min_dist,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            authority="LOCATION",
        )

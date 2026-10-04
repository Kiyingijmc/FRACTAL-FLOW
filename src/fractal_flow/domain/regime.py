"""Regime Engine for FRACTAL FLOW.

Integrates direction, trend strength, structure, momentum, volatility,
pullback context, and structural integrity to determine RegimeState.
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
class RegimeState(str, Enum):
    UNKNOWN = "UNKNOWN"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    CHAOTIC = "CHAOTIC"


@dataclass
class RegimeTransitionRecord:
    symbol: str
    timeframe: str
    regime_state: RegimeState
    previous_regime_state: RegimeState
    trend_strength: Decimal
    volatility_context: Decimal
    timestamp: int
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "REGIME"

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
            state_id=f"regime_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="RegimeState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.regime_state.value,
            previous_state=self.previous_regime_state.value,
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


class RegimeEngine:
    """Regime Engine classifying overall market environment."""

    def __init__(self, symbol: str, timeframe: str = "1M") -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.regime_state = RegimeState.UNKNOWN
        self.previous_regime_state = RegimeState.UNKNOWN
        self.state_version = 0

        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None

    def evaluate(
        self,
        bar: Bar,
        flow_state: str,
        v_local: Decimal,
        is_vol_extreme: bool,
        root_id: str,
        parent_id: str,
        parent_version: int,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> RegimeTransitionRecord:
        AuthorityMatrix.verify_capability("Regime", "WRITE_REGIME_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"RegimeEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        if self._last_parent_version is not None and parent_version < self._last_parent_version:
            raise ValueError(
                f"Parent version regression detected: incoming {parent_version} < current {self._last_parent_version}"
            )

        self._last_parent_version = parent_version
        self._last_data_version = data_version
        self._last_config_version = config_version

        old_state = self.regime_state

        if flow_state in ("UNKNOWN", "CONTESTED") or is_vol_extreme:
            if is_vol_extreme:
                new_state = RegimeState.CHAOTIC
            elif flow_state == "CONTESTED":
                new_state = RegimeState.TRANSITION
            else:
                new_state = RegimeState.UNKNOWN
        elif "LONG" in flow_state:
            new_state = RegimeState.TREND_UP
        elif "SHORT" in flow_state:
            new_state = RegimeState.TREND_DOWN
        elif flow_state == "BALANCED":
            new_state = RegimeState.RANGE
        else:
            new_state = RegimeState.TRANSITION

        if new_state != old_state:
            self.previous_regime_state = old_state
            self.regime_state = new_state
            self.state_version += 1

        return RegimeTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            regime_state=self.regime_state,
            previous_regime_state=self.previous_regime_state,
            trend_strength=Decimal("0.8") if "TREND" in self.regime_state.value else Decimal("0.3"),
            volatility_context=v_local,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            authority="REGIME",
        )

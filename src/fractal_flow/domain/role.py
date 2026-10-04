"""Market Role Engine for FRACTAL FLOW.

Classifies directional role independently from directional bias:
UNKNOWN, CONTINUATION, PULLBACK, COUNTERFLOW, RANGE_ROTATION, BREAKOUT,
RECLAIM, TRANSITION, EXHAUSTION, NOISE, AMBIGUOUS.
"""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Optional

from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.reason_codes import ReasonCode


@unique
class RoleState(str, Enum):
    UNKNOWN = "UNKNOWN"
    CONTINUATION = "CONTINUATION"
    PULLBACK = "PULLBACK"
    COUNTERFLOW = "COUNTERFLOW"
    RANGE_ROTATION = "RANGE_ROTATION"
    BREAKOUT = "BREAKOUT"
    RECLAIM = "RECLAIM"
    TRANSITION = "TRANSITION"
    EXHAUSTION = "EXHAUSTION"
    NOISE = "NOISE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class RoleTransitionRecord:
    symbol: str
    timeframe: str
    role_state: RoleState
    previous_role_state: RoleState
    direction: str
    timestamp: int
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "ROLE"

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
            state_id=f"role_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="RoleState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.role_state.value,
            previous_state=self.previous_role_state.value,
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


class RoleEngine:
    """Market Role Engine determining structural market role independently from direction."""

    def __init__(self, symbol: str, timeframe: str = "1M") -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.role_state = RoleState.UNKNOWN
        self.previous_role_state = RoleState.UNKNOWN
        self.state_version = 0

        self._last_parent_version: Optional[int] = None

    def evaluate(
        self,
        bar: Bar,
        direction: str,
        regime_state: str,
        pde_state: str,
        break_state: str,
        damage_state: str,
        root_id: str,
        parent_id: str,
        parent_version: int,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> RoleTransitionRecord:
        AuthorityMatrix.verify_capability("Role", "WRITE_ROLE_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"RoleEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        if self._last_parent_version is not None and parent_version < self._last_parent_version:
            raise ValueError(
                f"Parent version regression detected: incoming {parent_version} < current {self._last_parent_version}"
            )

        self._last_parent_version = parent_version

        old_state = self.role_state

        if regime_state in ("UNKNOWN", "CHAOTIC") or pde_state == "PDE_INVALIDATED":
            new_state = RoleState.AMBIGUOUS
        elif "RECLAIM" in damage_state:
            new_state = RoleState.RECLAIM
        elif break_state in ("BREAK_CONFIRMED", "BREAK_ESTABLISHED"):
            new_state = RoleState.BREAKOUT
        elif "PULLBACK" in pde_state:
            new_state = RoleState.PULLBACK
        elif regime_state in ("TREND_UP", "TREND_DOWN"):
            new_state = RoleState.CONTINUATION
        elif regime_state == "RANGE":
            new_state = RoleState.RANGE_ROTATION
        else:
            new_state = RoleState.TRANSITION

        if new_state != old_state:
            self.previous_role_state = old_state
            self.role_state = new_state
            self.state_version += 1

        return RoleTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            role_state=self.role_state,
            previous_role_state=self.previous_role_state,
            direction=direction,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            authority="ROLE",
        )

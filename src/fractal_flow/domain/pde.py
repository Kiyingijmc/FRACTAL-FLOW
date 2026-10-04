"""Pullback Detection Engine (PDE) and Resumption State Machine for FRACTAL FLOW.

Evaluates impulses, primary/secondary/micro pullbacks, impulse quality,
and resumption lifecycles according to canonical contracts.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Optional

from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.reason_codes import ReasonCode
from src.fractal_flow.domain.structure import StructureTransitionRecord


@unique
class PDEState(str, Enum):
    PDE_NONE = "PDE_NONE"
    PDE_IMPULSE = "PDE_IMPULSE"
    PDE_PULLBACK_CANDIDATE = "PDE_PULLBACK_CANDIDATE"
    PDE_PULLBACK_ACTIVE = "PDE_PULLBACK_ACTIVE"
    PDE_WEAKENING = "PDE_WEAKENING"
    PDE_STRENGTHENING = "PDE_STRENGTHENING"
    PDE_DEEPENING = "PDE_DEEPENING"
    PDE_RESUMPTION_IN_PROGRESS = "PDE_RESUMPTION_IN_PROGRESS"
    PDE_FOLLOW_THROUGH = "PDE_FOLLOW_THROUGH"
    PDE_RESUMPTION_FAILED = "PDE_RESUMPTION_FAILED"
    PDE_INVALIDATED = "PDE_INVALIDATED"


@unique
class PDEResumptionState(str, Enum):
    RESUMPTION_NONE = "RESUMPTION_NONE"
    RECOVERY_CANDIDATE = "RECOVERY_CANDIDATE"
    RECOVERY_CONFIRMED = "RECOVERY_CONFIRMED"
    DISPLACEMENT_CANDIDATE = "DISPLACEMENT_CANDIDATE"
    RESUMPTION_CONFIRMED = "RESUMPTION_CONFIRMED"
    FOLLOW_THROUGH = "FOLLOW_THROUGH"
    RESUMPTION_FAILED = "RESUMPTION_FAILED"


@unique
class PullbackTier(str, Enum):
    PRIMARY_PULLBACK = "PRIMARY_PULLBACK"
    SECONDARY_PULLBACK = "SECONDARY_PULLBACK"
    MICRO_PULLBACK = "MICRO_PULLBACK"


TIMEFRAME_RANK: dict[str, int] = {
    "4H": 6,
    "1H": 5,
    "30M": 4,
    "15M": 3,
    "5M": 2,
    "1M": 1,
}


def compare_timeframes(tf1: str, tf2: str) -> int:
    """Returns positive if tf1 > tf2, negative if tf1 < tf2, 0 if equal."""
    rank1 = TIMEFRAME_RANK.get(tf1, 0)
    rank2 = TIMEFRAME_RANK.get(tf2, 0)
    if rank1 == 0 or rank2 == 0:
        raise ValueError(f"Unknown timeframe for comparison: {tf1} or {tf2}")
    return rank1 - rank2


@dataclass(frozen=True)
class ImpulseQuality:
    displacement: Decimal
    efficiency: Decimal
    structural_progression: Decimal
    persistence: int
    volatility_score: Decimal
    directional_coherence: Decimal
    composite_score: Decimal


@dataclass(frozen=True)
class PullbackObject:
    pullback_id: str
    symbol: str
    timeframe: str
    tier: PullbackTier
    direction: str  # LONG or SHORT
    depth_ratio: Decimal
    impulse_high: Decimal
    impulse_low: Decimal
    pullback_extreme: Decimal
    started_at: int
    quality: ImpulseQuality
    root_id: str
    parent_id: str
    parent_version: int


@dataclass
class PDETransitionRecord:
    symbol: str
    timeframe: str
    pde_state: PDEState
    previous_pde_state: PDEState
    resumption_state: PDEResumptionState
    previous_resumption_state: PDEResumptionState
    active_pullback: Optional[PullbackObject]
    timestamp: int
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "PDE"

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
            state_id=f"pde_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="PDEState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.pde_state.value,
            previous_state=self.previous_pde_state.value,
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


class PDEEngine:
    """Pullback Detection Engine & Resumption State Machine."""

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        min_impulse_v_mult: Decimal = Decimal("2.0"),
        max_pullback_depth: Decimal = Decimal("0.80"),
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.min_impulse_v_mult = min_impulse_v_mult
        self.max_pullback_depth = max_pullback_depth

        self.pde_state = PDEState.PDE_NONE
        self.previous_pde_state = PDEState.PDE_NONE
        self.resumption_state = PDEResumptionState.RESUMPTION_NONE
        self.previous_resumption_state = PDEResumptionState.RESUMPTION_NONE

        self.state_version = 0
        self.active_pullback: Optional[PullbackObject] = None

        self.impulse_high: Optional[Decimal] = None
        self.impulse_low: Optional[Decimal] = None
        self.impulse_direction: Optional[str] = None
        self.impulse_start_ts: Optional[int] = None

        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None

    def evaluate_bar(
        self,
        bar: Bar,
        structure_record: Optional[StructureTransitionRecord],
        v_local: Decimal,
        root_id: str,
        parent_id: str,
        parent_version: int,
        htf_pde_state: Optional[PDEState] = None,
        htf_timeframe: Optional[str] = None,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> PDETransitionRecord:
        AuthorityMatrix.verify_capability("PDE", "WRITE_PDE_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"PDEEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        if htf_timeframe is not None:
            if compare_timeframes(htf_timeframe, self.timeframe) <= 0:
                raise ValueError(
                    f"Invariant 26 Violation: HTF timeframe {htf_timeframe} is not strictly higher than LTF {self.timeframe}"
                )

        if self._last_parent_version is not None and parent_version < self._last_parent_version:
            raise ValueError(
                f"Parent version regression detected: incoming {parent_version} < current {self._last_parent_version}"
            )
        if self._last_data_version is not None and data_version < self._last_data_version:
            raise ValueError(
                f"Stale data version detected: incoming data version {data_version} < active version {self._last_data_version}"
            )
        if self._last_config_version is not None and config_version != self._last_config_version:
            raise ValueError(
                f"Configuration version mismatch: incoming {config_version} != active {self._last_config_version}"
            )

        self._last_parent_version = parent_version
        self._last_data_version = data_version
        self._last_config_version = config_version

        reasons: list[ReasonCode] = []
        old_pde = self.pde_state
        old_resumption = self.resumption_state

        bar_range = bar.high - bar.low
        displacement = abs(bar.close - bar.open)
        efficiency = displacement / bar_range if bar_range > Decimal("0.0") else Decimal("0.5")

        if displacement >= (self.min_impulse_v_mult * v_local):
            self.pde_state = PDEState.PDE_IMPULSE
            self.impulse_high = bar.high
            self.impulse_low = bar.low
            self.impulse_direction = "LONG" if bar.close > bar.open else "SHORT"
            self.impulse_start_ts = bar.close_timestamp

            quality = ImpulseQuality(
                displacement=displacement,
                efficiency=efficiency,
                structural_progression=Decimal("1.0"),
                persistence=1,
                volatility_score=v_local,
                directional_coherence=Decimal("1.0"),
                composite_score=min(Decimal("1.0"), displacement / (self.min_impulse_v_mult * v_local)),
            )

            tier = PullbackTier.PRIMARY_PULLBACK if self.timeframe in ("4H", "1H", "30M") else PullbackTier.MICRO_PULLBACK

            self.active_pullback = PullbackObject(
                pullback_id=f"pb_{self.symbol}_{self.timeframe}_{bar.close_timestamp}_{self.state_version}",
                symbol=self.symbol,
                timeframe=self.timeframe,
                tier=tier,
                direction=self.impulse_direction,
                depth_ratio=Decimal("0.0"),
                impulse_high=bar.high,
                impulse_low=bar.low,
                pullback_extreme=bar.low if self.impulse_direction == "LONG" else bar.high,
                started_at=bar.close_timestamp,
                quality=quality,
                root_id=root_id,
                parent_id=parent_id,
                parent_version=parent_version,
            )

        elif self.pde_state in (PDEState.PDE_IMPULSE, PDEState.PDE_PULLBACK_CANDIDATE, PDEState.PDE_PULLBACK_ACTIVE):
            if self.impulse_direction == "LONG":
                retracement = (self.impulse_high - bar.close) if self.impulse_high else Decimal("0.0")
                impulse_span = (self.impulse_high - self.impulse_low) if (self.impulse_high and self.impulse_low) else Decimal("1.0")
                depth_ratio = retracement / impulse_span if impulse_span > Decimal("0.0") else Decimal("0.0")

                if depth_ratio > self.max_pullback_depth:
                    self.pde_state = PDEState.PDE_INVALIDATED
                    self.resumption_state = PDEResumptionState.RESUMPTION_FAILED
                elif bar.close < bar.open:
                    if self.pde_state == PDEState.PDE_IMPULSE:
                        self.pde_state = PDEState.PDE_PULLBACK_CANDIDATE
                    elif self.pde_state == PDEState.PDE_PULLBACK_CANDIDATE:
                        self.pde_state = PDEState.PDE_PULLBACK_ACTIVE
                        self.resumption_state = PDEResumptionState.RECOVERY_CANDIDATE
                elif bar.close > bar.open:
                    if self.resumption_state == PDEResumptionState.RECOVERY_CANDIDATE:
                        self.resumption_state = PDEResumptionState.RECOVERY_CONFIRMED
                    elif self.resumption_state == PDEResumptionState.RECOVERY_CONFIRMED:
                        self.resumption_state = PDEResumptionState.DISPLACEMENT_CANDIDATE
                    elif self.resumption_state == PDEResumptionState.DISPLACEMENT_CANDIDATE:
                        self.resumption_state = PDEResumptionState.RESUMPTION_CONFIRMED
                        self.pde_state = PDEState.PDE_RESUMPTION_IN_PROGRESS
                    elif self.resumption_state == PDEResumptionState.RESUMPTION_CONFIRMED:
                        self.resumption_state = PDEResumptionState.FOLLOW_THROUGH
                        self.pde_state = PDEState.PDE_FOLLOW_THROUGH

        if self.pde_state != old_pde:
            self.previous_pde_state = old_pde
        if self.resumption_state != old_resumption:
            self.previous_resumption_state = old_resumption

        self.state_version += 1

        return PDETransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            pde_state=self.pde_state,
            previous_pde_state=self.previous_pde_state,
            resumption_state=self.resumption_state,
            previous_resumption_state=self.previous_resumption_state,
            active_pullback=self.active_pullback,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            reason_codes=reasons,
            authority="PDE",
        )

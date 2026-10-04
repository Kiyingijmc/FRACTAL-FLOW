"""Flow Ownership Engine for FRACTAL FLOW.

Evaluates market ownership using observable evidence:
long strength, short strength, imbalance, momentum, efficiency, structural progression,
persistence, and confidence.

Uses hysteresis and dwell-time filters to prevent noisy ownership flipping and
requires structural evidence for ownership reversal transitions.
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
class FlowState(str, Enum):
    UNKNOWN = "UNKNOWN"
    LONG_EMERGING = "LONG_EMERGING"
    LONG_DOMINANT = "LONG_DOMINANT"
    LONG_WEAKENING = "LONG_WEAKENING"
    BALANCED = "BALANCED"
    CONTESTED = "CONTESTED"
    SHORT_EMERGING = "SHORT_EMERGING"
    SHORT_DOMINANT = "SHORT_DOMINANT"
    SHORT_WEAKENING = "SHORT_WEAKENING"
    TRANSITIONING = "TRANSITIONING"


LEGAL_FLOW_TRANSITIONS: dict[FlowState, set[FlowState]] = {
    FlowState.UNKNOWN: {
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.LONG_EMERGING,
        FlowState.SHORT_EMERGING,
        FlowState.TRANSITIONING,
    },
    FlowState.BALANCED: {
        FlowState.LONG_EMERGING,
        FlowState.SHORT_EMERGING,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
    },
    FlowState.CONTESTED: {
        FlowState.BALANCED,
        FlowState.LONG_EMERGING,
        FlowState.SHORT_EMERGING,
        FlowState.TRANSITIONING,
    },
    FlowState.LONG_EMERGING: {
        FlowState.LONG_DOMINANT,
        FlowState.LONG_WEAKENING,
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
    },
    FlowState.LONG_DOMINANT: {
        FlowState.LONG_WEAKENING,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
    },
    FlowState.LONG_WEAKENING: {
        FlowState.LONG_DOMINANT,
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
        FlowState.SHORT_EMERGING,
    },
    FlowState.SHORT_EMERGING: {
        FlowState.SHORT_DOMINANT,
        FlowState.SHORT_WEAKENING,
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
    },
    FlowState.SHORT_DOMINANT: {
        FlowState.SHORT_WEAKENING,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
    },
    FlowState.SHORT_WEAKENING: {
        FlowState.SHORT_DOMINANT,
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.TRANSITIONING,
        FlowState.LONG_EMERGING,
    },
    FlowState.TRANSITIONING: {
        FlowState.BALANCED,
        FlowState.CONTESTED,
        FlowState.LONG_EMERGING,
        FlowState.SHORT_EMERGING,
        FlowState.UNKNOWN,
    },
}


@dataclass(frozen=True)
class FlowMetrics:
    long_strength: Decimal
    short_strength: Decimal
    imbalance: Decimal
    momentum: Decimal
    efficiency: Decimal
    structural_progression: Decimal
    persistence: int
    confidence: Decimal


@dataclass
class FlowTransitionRecord:
    symbol: str
    timeframe: str
    flow_state: FlowState
    previous_flow_state: FlowState
    metrics: FlowMetrics
    timestamp: int
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "FLOW"

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
            state_id=f"flow_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="FlowState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.flow_state.value,
            previous_state=self.previous_flow_state.value,
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


class FlowEngine:
    """Flow Ownership Engine determining directional order-flow dominance."""

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        hysteresis_margin: Decimal = Decimal("0.15"),
        dwell_bars_required: int = 2,
        dominance_threshold: Decimal = Decimal("0.65"),
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.hysteresis_margin = hysteresis_margin
        self.dwell_bars_required = dwell_bars_required
        self.dominance_threshold = dominance_threshold

        self.flow_state = FlowState.UNKNOWN
        self.previous_flow_state = FlowState.UNKNOWN
        self.state_version = 0

        self.dwell_counter = 0
        self.candidate_state: Optional[FlowState] = None

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
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> FlowTransitionRecord:
        """Evaluates FlowState for bar given structural evidence."""
        AuthorityMatrix.verify_capability("Flow", "WRITE_FLOW_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"FlowEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

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

        bar_range = bar.high - bar.low
        body = abs(bar.close - bar.open)
        efficiency = body / bar_range if bar_range > Decimal("0.0") else Decimal("0.5")

        long_strength = (
            ((bar.close - bar.low) / bar_range) if bar_range > Decimal("0.0") else Decimal("0.5")
        ) * efficiency
        short_strength = (
            ((bar.high - bar.close) / bar_range) if bar_range > Decimal("0.0") else Decimal("0.5")
        ) * efficiency

        imbalance = long_strength - short_strength
        momentum = (bar.close - bar.open) / v_local if v_local > Decimal("0.0") else Decimal("0.0")

        struct_prog = Decimal("0.0")
        has_structural_reversal = False

        if structure_record is not None:
            if structure_record.bos_type in ("BOS_BULLISH", "CHOCH_BULLISH"):
                struct_prog = Decimal("1.0")
                if "SHORT" in self.flow_state.value:
                    has_structural_reversal = True
            elif structure_record.bos_type in ("BOS_BEARISH", "CHOCH_BEARISH"):
                struct_prog = Decimal("-1.0")
                if "LONG" in self.flow_state.value:
                    has_structural_reversal = True

        confidence = min(Decimal("1.0"), max(Decimal("0.0"), (abs(imbalance) + efficiency + abs(struct_prog)) / Decimal("3.0")))

        metrics = FlowMetrics(
            long_strength=long_strength,
            short_strength=short_strength,
            imbalance=imbalance,
            momentum=momentum,
            efficiency=efficiency,
            structural_progression=struct_prog,
            persistence=self.dwell_counter,
            confidence=confidence,
        )

        target_state = self._determine_raw_state(imbalance, struct_prog, has_structural_reversal)
        next_state = self._apply_hysteresis_and_dwell(target_state, has_structural_reversal)

        old_state = self.flow_state
        if next_state != old_state:
            if next_state not in LEGAL_FLOW_TRANSITIONS.get(old_state, set()):
                next_state = FlowState.TRANSITIONING

            self.previous_flow_state = old_state
            self.flow_state = next_state
            self.state_version += 1

        return FlowTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            flow_state=self.flow_state,
            previous_flow_state=self.previous_flow_state,
            metrics=metrics,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            authority="FLOW",
        )

    def _determine_raw_state(
        self, imbalance: Decimal, struct_prog: Decimal, has_structural_reversal: bool
    ) -> FlowState:
        if abs(imbalance) < Decimal("0.10") and struct_prog == Decimal("0.0"):
            return FlowState.BALANCED

        if imbalance > self.dominance_threshold or struct_prog > Decimal("0.5"):
            return FlowState.LONG_DOMINANT
        elif imbalance > Decimal("0.20"):
            return FlowState.LONG_EMERGING
        elif imbalance < -self.dominance_threshold or struct_prog < Decimal("-0.5"):
            return FlowState.SHORT_DOMINANT
        elif imbalance < Decimal("-0.20"):
            return FlowState.SHORT_EMERGING

        return FlowState.CONTESTED

    def _apply_hysteresis_and_dwell(self, target_state: FlowState, has_structural_reversal: bool) -> FlowState:
        if self.flow_state == FlowState.UNKNOWN:
            if target_state == FlowState.LONG_DOMINANT:
                target_state = FlowState.LONG_EMERGING
            elif target_state == FlowState.SHORT_DOMINANT:
                target_state = FlowState.SHORT_EMERGING
            return target_state

        is_long = "LONG" in self.flow_state.value
        is_short = "SHORT" in self.flow_state.value
        target_is_long = "LONG" in target_state.value
        target_is_short = "SHORT" in target_state.value

        if (is_long and target_is_short) or (is_short and target_is_long):
            if not has_structural_reversal:
                return FlowState.LONG_WEAKENING if is_long else FlowState.SHORT_WEAKENING

        if target_state == self.candidate_state:
            self.dwell_counter += 1
        else:
            self.candidate_state = target_state
            self.dwell_counter = 1

        if self.dwell_counter >= self.dwell_bars_required:
            return target_state

        return self.flow_state

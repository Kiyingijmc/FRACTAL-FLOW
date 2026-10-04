"""Flow Ownership Engine for FRACTAL FLOW.

Computes directional pressure ownership, strength, imbalance, and state transitions
using causal evidence, hysteresis, state dwell, and fail-closed authority validation.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Optional

from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY, StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.reason_codes import ReasonCode


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


@dataclass(frozen=True)
class FlowEvidence:
    long_strength: Decimal
    short_strength: Decimal
    imbalance: Decimal
    directional_displacement: Decimal
    directional_efficiency: Decimal
    structure_progression: Decimal
    persistence: Decimal
    volatility_context: Decimal
    timestamp: int

    def __post_init__(self) -> None:
        for name, val in [
            ("long_strength", self.long_strength),
            ("short_strength", self.short_strength),
            ("imbalance", self.imbalance),
            ("directional_displacement", self.directional_displacement),
            ("directional_efficiency", self.directional_efficiency),
            ("structure_progression", self.structure_progression),
            ("persistence", self.persistence),
            ("volatility_context", self.volatility_context),
        ]:
            if not isinstance(val, Decimal):
                raise TypeError(f"FlowEvidence field '{name}' must be a Decimal, got {type(val)}")
            if val.is_nan() or val.is_infinite():
                raise ValueError(f"FlowEvidence field '{name}' must be a finite Decimal, got {val}")


@dataclass
class FlowTransitionRecord:
    symbol: str
    timeframe: str
    flow_state: FlowState
    previous_flow_state: FlowState
    evidence: FlowEvidence
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
    """Causal, Hysteresis-Aware Flow Ownership Engine."""

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        dominance_threshold: Decimal = Decimal("0.60"),
        emerging_threshold: Decimal = Decimal("0.30"),
        weakening_threshold: Decimal = Decimal("0.40"),
        min_persistence_bars: int = 2,
        min_dwell_bars: int = 2,
        transition_confirm_bars: int = 2,
        max_history_capacity: int = 100,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.dominance_threshold = dominance_threshold
        self.emerging_threshold = emerging_threshold
        self.weakening_threshold = weakening_threshold
        self.min_persistence_bars = min_persistence_bars
        self.min_dwell_bars = min_dwell_bars
        self.transition_confirm_bars = transition_confirm_bars
        self.max_history_capacity = max_history_capacity

        self.flow_state = FlowState.UNKNOWN
        self.previous_flow_state = FlowState.UNKNOWN
        self.state_version = 0

        self._dwell_counter = 0
        self._long_persistence_counter = 0
        self._short_persistence_counter = 0
        self._transition_counter = 0

        self._history: list[FlowEvidence] = []
        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None
        self._last_timestamp: int = 0

    @property
    def history(self) -> tuple[FlowEvidence, ...]:
        return tuple(self._history)

    def _record_history(self, evidence: FlowEvidence) -> None:
        self._history.append(evidence)
        if len(self._history) > self.max_history_capacity:
            self._history.pop(0)

    def calculate_evidence(
        self,
        bar: Bar,
        v_local: Decimal,
        structure_progression: Decimal = Decimal("0.0"),
    ) -> FlowEvidence:
        if v_local <= Decimal("0.0"):
            return FlowEvidence(
                long_strength=Decimal("0.0"),
                short_strength=Decimal("0.0"),
                imbalance=Decimal("0.0"),
                directional_displacement=Decimal("0.0"),
                directional_efficiency=Decimal("0.0"),
                structure_progression=Decimal("0.0"),
                persistence=Decimal("0.0"),
                volatility_context=v_local,
                timestamp=bar.close_timestamp,
            )

        bar_range = bar.high - bar.low
        close_displacement = bar.close - bar.open

        # Directional displacement normalized by v_local
        displacement = close_displacement / v_local

        # Directional efficiency
        efficiency = close_displacement / bar_range if bar_range > Decimal("0.0") else Decimal("0.0")

        # Persistence calculation based on recent history
        if close_displacement > Decimal("0.0"):
            self._long_persistence_counter += 1
            self._short_persistence_counter = 0
        elif close_displacement < Decimal("0.0"):
            self._short_persistence_counter += 1
            self._long_persistence_counter = 0
        else:
            # Neutral bar
            pass

        p_long = Decimal(str(self._long_persistence_counter))
        p_short = Decimal(str(self._short_persistence_counter))

        # Raw directional strengths (0.0 to 1.0 clamped)
        # Combination of displacement, efficiency, persistence and structural progression
        long_raw = (
            max(Decimal("0.0"), displacement) * Decimal("0.3")
            + max(Decimal("0.0"), efficiency) * Decimal("0.3")
            + min(Decimal("1.0"), p_long / Decimal("5.0")) * Decimal("0.2")
            + max(Decimal("0.0"), structure_progression) * Decimal("0.2")
        )
        short_raw = (
            max(Decimal("0.0"), -displacement) * Decimal("0.3")
            + max(Decimal("0.0"), -efficiency) * Decimal("0.3")
            + min(Decimal("1.0"), p_short / Decimal("5.0")) * Decimal("0.2")
            + max(Decimal("0.0"), -structure_progression) * Decimal("0.2")
        )

        long_str = min(Decimal("1.0"), max(Decimal("0.0"), long_raw))
        short_str = min(Decimal("1.0"), max(Decimal("0.0"), short_raw))
        imbalance = long_str - short_str

        return FlowEvidence(
            long_strength=long_str,
            short_strength=short_str,
            imbalance=imbalance,
            directional_displacement=displacement,
            directional_efficiency=efficiency,
            structure_progression=structure_progression,
            persistence=p_long if close_displacement >= Decimal("0.0") else p_short,
            volatility_context=v_local,
            timestamp=bar.close_timestamp,
        )

    def process_bar(
        self,
        bar: Bar,
        v_local: Decimal,
        root_id: str,
        parent_id: str,
        parent_version: int,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
        structure_progression: Decimal = Decimal("0.0"),
        override_evidence: Optional[FlowEvidence] = None,
    ) -> FlowTransitionRecord:
        AuthorityMatrix.verify_capability("Flow", "WRITE_FLOW_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"FlowEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        # Parent and version validation
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

        if bar.close_timestamp < self._last_timestamp:
            raise ValueError(
                f"Chronology violation: incoming bar timestamp {bar.close_timestamp} prior to last seen {self._last_timestamp}"
            )

        self._last_parent_version = parent_version
        self._last_data_version = data_version
        self._last_config_version = config_version
        self._last_timestamp = bar.close_timestamp

        evidence = override_evidence or self.calculate_evidence(bar, v_local, structure_progression)
        self._record_history(evidence)

        # Evaluate target flow state given current evidence and state machine rules
        target_state = self._determine_target_state(evidence)

        reasons: list[ReasonCode] = []
        old_state = self.flow_state

        if target_state != old_state:
            GLOBAL_STATE_REGISTRY.validate_transition("FlowState", old_state.value, target_state.value)
            self.previous_flow_state = old_state
            self.flow_state = target_state
            self._dwell_counter = 1
        else:
            self._dwell_counter += 1

        self.state_version += 1

        return FlowTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            flow_state=self.flow_state,
            previous_flow_state=self.previous_flow_state,
            evidence=evidence,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            reason_codes=reasons,
            authority="FLOW",
        )

    def _determine_target_state(self, ev: FlowEvidence) -> FlowState:
        # Fail closed to UNKNOWN if volatility invalid
        if ev.volatility_context <= Decimal("0.0"):
            return FlowState.UNKNOWN

        curr = self.flow_state
        l_str, s_str = ev.long_strength, ev.short_strength

        # Evaluate potential next states adhering strictly to canonical graph
        if curr == FlowState.UNKNOWN:
            if l_str >= self.emerging_threshold and l_str > s_str + Decimal("0.10"):
                return FlowState.LONG_EMERGING
            elif s_str >= self.emerging_threshold and s_str > l_str + Decimal("0.10"):
                return FlowState.SHORT_EMERGING
            elif l_str >= self.emerging_threshold and s_str >= self.emerging_threshold:
                return FlowState.CONTESTED
            else:
                return FlowState.BALANCED

        elif curr == FlowState.LONG_EMERGING:
            if (
                l_str >= self.dominance_threshold
                and ev.persistence >= Decimal(str(self.min_persistence_bars))
                and self._dwell_counter >= self.min_dwell_bars
            ):
                return FlowState.LONG_DOMINANT
            elif s_str >= self.emerging_threshold and l_str >= self.emerging_threshold:
                return FlowState.CONTESTED
            elif s_str >= self.dominance_threshold and l_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif l_str < self.weakening_threshold:
                return FlowState.LONG_WEAKENING
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            return FlowState.LONG_EMERGING

        elif curr == FlowState.LONG_DOMINANT:
            if s_str >= self.dominance_threshold and l_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif s_str >= self.emerging_threshold and l_str >= self.weakening_threshold:
                return FlowState.CONTESTED
            elif l_str < self.weakening_threshold:
                return FlowState.LONG_WEAKENING
            return FlowState.LONG_DOMINANT

        elif curr == FlowState.LONG_WEAKENING:
            if l_str >= self.dominance_threshold:
                return FlowState.LONG_DOMINANT
            elif s_str >= self.dominance_threshold and l_str < self.weakening_threshold:
                return FlowState.SHORT_EMERGING
            elif s_str >= self.emerging_threshold and l_str >= self.weakening_threshold:
                return FlowState.CONTESTED
            elif s_str >= self.emerging_threshold and l_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            return FlowState.LONG_WEAKENING

        elif curr == FlowState.SHORT_EMERGING:
            if (
                s_str >= self.dominance_threshold
                and ev.persistence >= Decimal(str(self.min_persistence_bars))
                and self._dwell_counter >= self.min_dwell_bars
            ):
                return FlowState.SHORT_DOMINANT
            elif l_str >= self.emerging_threshold and s_str >= self.emerging_threshold:
                return FlowState.CONTESTED
            elif l_str >= self.dominance_threshold and s_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif s_str < self.weakening_threshold:
                return FlowState.SHORT_WEAKENING
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            return FlowState.SHORT_EMERGING

        elif curr == FlowState.SHORT_DOMINANT:
            if l_str >= self.dominance_threshold and s_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif l_str >= self.emerging_threshold and s_str >= self.weakening_threshold:
                return FlowState.CONTESTED
            elif s_str < self.weakening_threshold:
                return FlowState.SHORT_WEAKENING
            return FlowState.SHORT_DOMINANT

        elif curr == FlowState.SHORT_WEAKENING:
            if s_str >= self.dominance_threshold:
                return FlowState.SHORT_DOMINANT
            elif l_str >= self.dominance_threshold and s_str < self.weakening_threshold:
                return FlowState.LONG_EMERGING
            elif l_str >= self.emerging_threshold and s_str >= self.weakening_threshold:
                return FlowState.CONTESTED
            elif l_str >= self.emerging_threshold and s_str < self.weakening_threshold:
                return FlowState.TRANSITIONING
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            return FlowState.SHORT_WEAKENING

        elif curr == FlowState.BALANCED:
            if l_str >= self.emerging_threshold and l_str > s_str + Decimal("0.10"):
                return FlowState.LONG_EMERGING
            elif s_str >= self.emerging_threshold and s_str > l_str + Decimal("0.10"):
                return FlowState.SHORT_EMERGING
            elif l_str >= self.emerging_threshold and s_str >= self.emerging_threshold:
                return FlowState.CONTESTED
            return FlowState.BALANCED

        elif curr == FlowState.CONTESTED:
            if l_str >= self.emerging_threshold and s_str < self.weakening_threshold:
                return FlowState.LONG_EMERGING
            elif s_str >= self.emerging_threshold and l_str < self.weakening_threshold:
                return FlowState.SHORT_EMERGING
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            elif (l_str >= self.dominance_threshold or s_str >= self.dominance_threshold) and abs(
                l_str - s_str
            ) >= Decimal("0.20"):
                return FlowState.TRANSITIONING
            return FlowState.CONTESTED

        elif curr == FlowState.TRANSITIONING:
            if l_str >= self.emerging_threshold and l_str > s_str + Decimal("0.10"):
                return FlowState.LONG_EMERGING
            elif s_str >= self.emerging_threshold and s_str > l_str + Decimal("0.10"):
                return FlowState.SHORT_EMERGING
            elif l_str >= self.emerging_threshold and s_str >= self.emerging_threshold:
                return FlowState.CONTESTED
            elif l_str < self.emerging_threshold and s_str < self.emerging_threshold:
                return FlowState.BALANCED
            return FlowState.TRANSITIONING

        return FlowState.UNKNOWN

"""Deterministic Price Dynamics Episode engine with explicit resumption state."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY, StateEnvelope
from src.fractal_flow.domain.market import Bar

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

@dataclass(frozen=True)
class PDEEvidence:
    state: PDEState
    direction: str
    impulse_amplitude: Decimal
    pullback_depth: Decimal
    recovery_ratio: Decimal
    resumption_displacement: Decimal
    timestamp: int
    version: int
    resumption_state: PDEResumptionState = PDEResumptionState.RESUMPTION_NONE
    episode_id: str = ""
    root_id: str = ""
    parent_id: str = ""
    parent_version: int = 1
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    causal_watermark: int | None = None
    valid_until: int | None = None
    authority: str = "PDE"
    reason_codes: tuple[str, ...] = ()

class PDEEngine:
    def to_envelopes(self, object_id: str) -> tuple[StateEnvelope, StateEnvelope]:
        valid_until = self._last_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe)
        common = dict(object_id=object_id, symbol=self.symbol, timeframe=self.timeframe, root_id=self._root_id, parent_id=self._parent_id, parent_version=self._parent_version, source_timestamp=self._last_timestamp, event_timestamp=self._last_timestamp, processing_timestamp=self._last_timestamp, valid_until=valid_until, last_seen=self._last_timestamp, configuration_version=self._configuration_version, data_version=self._data_version, feature_version=self._feature_version, authority="PDE")
        pde = StateEnvelope(state_id=f"pde_state_{object_id}_{self.version}", object_type="PDEState", state=self.state.value, previous_state=self._previous_state.value, version=self.version, **common)
        res = StateEnvelope(state_id=f"pde_resumption_{object_id}_{self.version}", object_type="PDEResumption", state=self.resumption_state.value, previous_state=self._previous_resumption_state.value, version=self.version, **common)
        return pde, res

    def __init__(self, symbol: str, timeframe: str = "1M", max_episode_bars: int = 30,
                 pullback_min: Decimal = Decimal("0.10"), pullback_max: Decimal = Decimal("0.80"),
                 min_impulse: Decimal = Decimal("1.0"), recovery_threshold: Decimal = Decimal("0.75")) -> None:
        if not (Decimal("0") < pullback_min < pullback_max <= Decimal("1")):
            raise ValueError("PDE pullback thresholds must satisfy 0 < min < max <= 1")
        self.symbol, self.timeframe = symbol, timeframe
        self.max_episode_bars = max(3, max_episode_bars)
        self.pullback_min, self.pullback_max = pullback_min, pullback_max
        self.min_impulse, self.recovery_threshold = min_impulse, recovery_threshold
        self.state = PDEState.PDE_NONE
        self._previous_state = PDEState.PDE_NONE
        self.resumption_state = PDEResumptionState.RESUMPTION_NONE
        self._previous_resumption_state = PDEResumptionState.RESUMPTION_NONE
        self.direction = "UNKNOWN"
        self.version = 0
        self._anchor: Decimal | None = None
        self._extreme: Decimal | None = None
        self._pullback_extreme: Decimal | None = None
        self._bars = 0
        self._last_close: Decimal | None = None
        self._last_timestamp = -1
        self._root_id=""; self._parent_id="market"; self._parent_version=1; self._configuration_version=1; self._data_version=1; self._feature_version=1
        self._episode_counter = 0
        self._episode_id = ""

    def _transition(self, new_state: PDEState) -> None:
        if new_state == self.state:
            return
        GLOBAL_STATE_REGISTRY.validate_transition("PDEState", self.state.value, new_state.value)
        self._previous_state = self.state
        self.state = new_state

    def _resume_transition(self, new_state: PDEResumptionState) -> None:
        if new_state == self.resumption_state:
            return
        GLOBAL_STATE_REGISTRY.validate_transition("PDEResumptionState", self.resumption_state.value, new_state.value)
        self._previous_resumption_state = self.resumption_state
        self.resumption_state = new_state

    def process_bar(self, bar: Bar, v_local: Decimal, flow_imbalance: Decimal = Decimal("0"),
                    structure_direction: str = "UNKNOWN", regime_state: str = "UNKNOWN",
                    root_id: str = "", parent_id: str = "market", parent_version: int = 1,
                    data_version: int = 1, feature_version: int = 1, configuration_version: int = 1) -> PDEEvidence:
        AuthorityMatrix.verify_capability("PDE", "WRITE_PDE_STATE")
        if bar.symbol != self.symbol or v_local <= 0:
            raise ValueError("PDEEngine invalid symbol or volatility")
        if bar.close_timestamp <= self._last_timestamp:
            raise ValueError("PDEEngine requires strictly increasing bar timestamps")
        self._last_timestamp = bar.close_timestamp
        self._root_id=root_id; self._parent_id=parent_id; self._parent_version=parent_version; self._configuration_version=configuration_version; self._data_version=data_version; self._feature_version=feature_version
        close = bar.close
        self._bars += 1
        reason: list[str] = []

        # Primitive episode detection is independent of Structure/Flow. Those inputs
        # contextualize confirmation but never mutate upstream authority.
        if self.state in (PDEState.PDE_NONE, PDEState.PDE_INVALIDATED, PDEState.PDE_FOLLOW_THROUGH, PDEState.PDE_RESUMPTION_FAILED):
            self._anchor = self._last_close if self._last_close is not None else bar.open
            impulse = abs(close - self._anchor) / v_local
            if impulse >= self.min_impulse:
                self.direction = "LONG" if close > self._anchor else "SHORT" if close < self._anchor else "UNKNOWN"
                if self.direction != "UNKNOWN":
                    self._episode_counter += 1
                    self._episode_id = f"{self.symbol}:{self.timeframe}:episode:{self._episode_counter}"
                    self._extreme = close
                    self._pullback_extreme = close
                    self._bars = 1
                    self._transition(PDEState.PDE_IMPULSE)
                    self._resume_transition(PDEResumptionState.RESUMPTION_NONE)
        elif self._anchor is not None and self._extreme is not None:
            if self._bars >= self.max_episode_bars:
                self._transition(PDEState.PDE_INVALIDATED)
                self._resume_transition(PDEResumptionState.RESUMPTION_FAILED)
                reason.append("EPISODE_EXPIRED")
            else:
                if self.direction == "LONG":
                    if close > self._extreme:
                        self._extreme = close
                        # A new extreme extends the existing episode; it does not
                        # retroactively rewrite a committed pullback/resumption state.
                    depth = max(Decimal("0"), (self._extreme - close) / max(v_local, self._extreme - self._anchor))
                    recovery = Decimal("1") - min(Decimal("1"), depth)
                    if depth >= self.pullback_min and self.state == PDEState.PDE_IMPULSE:
                        self._pullback_extreme = close; self._transition(PDEState.PDE_PULLBACK_CANDIDATE); self._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
                    elif self.state == PDEState.PDE_PULLBACK_CANDIDATE:
                        self._transition(PDEState.PDE_PULLBACK_ACTIVE)
                    elif self.state == PDEState.PDE_PULLBACK_ACTIVE:
                        self._transition(PDEState.PDE_DEEPENING if depth >= self.pullback_max else PDEState.PDE_WEAKENING)
                    elif self.state in (PDEState.PDE_WEAKENING, PDEState.PDE_DEEPENING):
                        regime_adverse = regime_state == "TREND_DOWN"
                        structure_adverse = structure_direction in {"SHORT", "BEARISH"}
                        if recovery >= self.recovery_threshold and flow_imbalance >= 0 and not regime_adverse and not structure_adverse:
                            self._resume_transition(PDEResumptionState.RECOVERY_CONFIRMED)
                            self._transition(PDEState.PDE_RESUMPTION_IN_PROGRESS)
                            if regime_state not in {"UNKNOWN", ""}:
                                reason.append("REGIME_COMPATIBLE_RECOVERY")
                            if structure_direction not in {"UNKNOWN", ""}:
                                reason.append("STRUCTURE_COMPATIBLE_RECOVERY")
                        elif depth >= self.pullback_max and (flow_imbalance < 0 or regime_adverse or structure_adverse):
                            self._resume_transition(PDEResumptionState.DISPLACEMENT_CANDIDATE)
                            if regime_adverse:
                                reason.append("REGIME_ADVERSE_DISPLACEMENT")
                            if structure_adverse:
                                reason.append("STRUCTURE_ADVERSE_DISPLACEMENT")
                    elif self.state == PDEState.PDE_RESUMPTION_IN_PROGRESS:
                        if close > self._extreme:
                            self._resume_transition(PDEResumptionState.RESUMPTION_CONFIRMED); self._transition(PDEState.PDE_FOLLOW_THROUGH)
                        elif flow_imbalance < 0 and recovery < Decimal("0.5"):
                            self._resume_transition(PDEResumptionState.RESUMPTION_FAILED); self._transition(PDEState.PDE_RESUMPTION_FAILED)
                else:
                    if close < self._extreme:
                        self._extreme = close
                        # A new extreme extends the existing episode without
                        # rewriting historical state.
                    depth = max(Decimal("0"), (close - self._extreme) / max(v_local, self._anchor - self._extreme))
                    recovery = Decimal("1") - min(Decimal("1"), depth)
                    if depth >= self.pullback_min and self.state == PDEState.PDE_IMPULSE:
                        self._pullback_extreme = close; self._transition(PDEState.PDE_PULLBACK_CANDIDATE); self._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
                    elif self.state == PDEState.PDE_PULLBACK_CANDIDATE:
                        self._transition(PDEState.PDE_PULLBACK_ACTIVE)
                    elif self.state == PDEState.PDE_PULLBACK_ACTIVE:
                        self._transition(PDEState.PDE_DEEPENING if depth >= self.pullback_max else PDEState.PDE_WEAKENING)
                    elif self.state in (PDEState.PDE_WEAKENING, PDEState.PDE_DEEPENING):
                        regime_adverse = regime_state == "TREND_UP"
                        structure_adverse = structure_direction in {"LONG", "BULLISH"}
                        if recovery >= self.recovery_threshold and flow_imbalance <= 0 and not regime_adverse and not structure_adverse:
                            self._resume_transition(PDEResumptionState.RECOVERY_CONFIRMED); self._transition(PDEState.PDE_RESUMPTION_IN_PROGRESS)
                            if regime_state not in {"UNKNOWN", ""}: reason.append("REGIME_COMPATIBLE_RECOVERY")
                            if structure_direction not in {"UNKNOWN", ""}: reason.append("STRUCTURE_COMPATIBLE_RECOVERY")
                        elif depth >= self.pullback_max and (flow_imbalance > 0 or regime_adverse or structure_adverse):
                            self._resume_transition(PDEResumptionState.DISPLACEMENT_CANDIDATE)
                            if regime_adverse: reason.append("REGIME_ADVERSE_DISPLACEMENT")
                            if structure_adverse: reason.append("STRUCTURE_ADVERSE_DISPLACEMENT")
                    elif self.state == PDEState.PDE_RESUMPTION_IN_PROGRESS:
                        if close < self._extreme:
                            self._resume_transition(PDEResumptionState.RESUMPTION_CONFIRMED); self._transition(PDEState.PDE_FOLLOW_THROUGH)
                        elif flow_imbalance > 0 and recovery < Decimal("0.5"):
                            self._resume_transition(PDEResumptionState.RESUMPTION_FAILED); self._transition(PDEState.PDE_RESUMPTION_FAILED)
        self._last_close = close
        self.version += 1
        anchor = self._anchor if self._anchor is not None else close
        extreme = self._extreme if self._extreme is not None else close
        amplitude = max(v_local, abs(extreme - anchor))
        depth = max(Decimal("0"), min(Decimal("1"), abs(extreme - close) / amplitude))
        recovery = Decimal("1") - depth
        displacement = abs(close - extreme) / v_local
        return PDEEvidence(self.state, self.direction, amplitude, depth, recovery, displacement,
                           bar.close_timestamp, self.version, self.resumption_state, self._episode_id,
                           root_id, parent_id, parent_version, configuration_version, data_version,
                           feature_version, bar.close_timestamp, bar.close_timestamp + 300, "PDE", tuple(reason))

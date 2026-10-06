"""Deterministic price-dynamics episode and pullback evidence engine.

The engine separates episode geometry from resumption evidence.  It never
mutates upstream Structure/Flow/Regime authority and only emits informational
state/evidence for downstream consumers.
"""
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
class PDEImpulseState(str, Enum):
    START = "START"
    DEVELOPING = "DEVELOPING"
    EXTENDING = "EXTENDING"
    MATURING = "MATURING"
    EXHAUSTING = "EXHAUSTING"


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
    maturity: str = "EARLY"
    impulse_state: PDEImpulseState = PDEImpulseState.START
    impulse_displacement: Decimal = Decimal("0")
    impulse_efficiency: Decimal = Decimal("0")
    impulse_structure_progression: Decimal = Decimal("0")
    impulse_persistence: Decimal = Decimal("0")
    impulse_range_expansion: Decimal = Decimal("0")
    impulse_quality: Decimal = Decimal("0")


class PDEEngine:
    def to_envelopes(self, object_id: str) -> tuple[StateEnvelope, StateEnvelope]:
        valid_until = self._last_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe)
        common = dict(
            object_id=object_id,
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self._root_id,
            parent_id=self._parent_id,
            parent_version=self._parent_version,
            source_timestamp=self._last_timestamp,
            event_timestamp=self._last_timestamp,
            processing_timestamp=self._last_timestamp,
            valid_until=valid_until,
            last_seen=self._last_timestamp,
            configuration_version=self._configuration_version,
            data_version=self._data_version,
            feature_version=self._feature_version,
            authority="PDE",
        )
        pde = StateEnvelope(
            state_id=f"pde_state_{object_id}_{self.version}",
            object_type="PDEState",
            state=self.state.value,
            previous_state=self._previous_state.value,
            version=self.version,
            **common,
        )
        res = StateEnvelope(
            state_id=f"pde_resumption_{object_id}_{self.version}",
            object_type="PDEResumption",
            state=self.resumption_state.value,
            previous_state=self._previous_resumption_state.value,
            version=self.version,
            **common,
        )
        return pde, res

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        max_episode_bars: int = 30,
        pullback_min: Decimal = Decimal("0.10"),
        pullback_max: Decimal = Decimal("0.80"),
        min_impulse: Decimal = Decimal("1.0"),
        recovery_threshold: Decimal = Decimal("0.75"),
        impulse_displacement_weight: Decimal = Decimal("0.20"),
        impulse_efficiency_weight: Decimal = Decimal("0.20"),
        impulse_structure_weight: Decimal = Decimal("0.20"),
        impulse_persistence_weight: Decimal = Decimal("0.20"),
        impulse_range_weight: Decimal = Decimal("0.20"),
    ) -> None:
        if not (Decimal("0") < pullback_min < pullback_max <= Decimal("1")):
            raise ValueError("PDE pullback thresholds must satisfy 0 < min < max <= 1")
        if not (Decimal("0") < recovery_threshold <= Decimal("1")):
            raise ValueError("PDE recovery_threshold must satisfy 0 < threshold <= 1")
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_episode_bars = max(3, max_episode_bars)
        self.pullback_min = pullback_min
        self.pullback_max = pullback_max
        self.min_impulse = min_impulse
        self.recovery_threshold = recovery_threshold
        self.impulse_weights = (impulse_displacement_weight, impulse_efficiency_weight, impulse_structure_weight, impulse_persistence_weight, impulse_range_weight)
        if any(weight < 0 for weight in self.impulse_weights) or sum(self.impulse_weights, Decimal("0")) <= 0:
            raise ValueError("PDE impulse weights must be non-negative and not all zero")
        self.state = PDEState.PDE_NONE
        self._previous_state = PDEState.PDE_NONE
        self.resumption_state = PDEResumptionState.RESUMPTION_NONE
        self._previous_resumption_state = PDEResumptionState.RESUMPTION_NONE
        self.direction = "UNKNOWN"
        self.version = 0
        self._anchor: Decimal | None = None
        self._extreme: Decimal | None = None
        self._pullback_extreme: Decimal | None = None
        # Geometric episode scale is fixed once an impulse extreme is committed.
        # Volatility is used for episode qualification and displacement, not to
        # retroactively distort pullback geometry.
        self._impulse_amplitude = Decimal("0")
        self._impulse_path = Decimal("0")
        self._impulse_bars = 0
        self._extension_count = 0
        self._last_depth = Decimal("0")
        self._bars = 0
        self._last_close: Decimal | None = None
        self._last_timestamp = -1
        self._root_id = ""
        self._parent_id = "market"
        self._parent_version = 1
        self._configuration_version = 1
        self._data_version = 1
        self._feature_version = 1
        self._episode_counter = 0
        self._episode_id = ""

    def _transition(self, new_state: PDEState) -> None:
        if new_state == self.state:
            return
        path = GLOBAL_STATE_REGISTRY.resolve_transition("PDEState", self.state.value, new_state.value)
        for next_state in path:
            self._previous_state = self.state
            self.state = PDEState(next_state)

    def _resume_transition(self, new_state: PDEResumptionState) -> None:
        if new_state == self.resumption_state:
            return
        path = GLOBAL_STATE_REGISTRY.resolve_transition("PDEResumptionState", self.resumption_state.value, new_state.value)
        for next_state in path:
            self._previous_resumption_state = self.resumption_state
            self.resumption_state = PDEResumptionState(next_state)

    def _clear_episode_state(self) -> None:
        """Clear all episode-local fields without altering global clock/version state."""
        self.direction = "UNKNOWN"
        self._anchor = None
        self._extreme = None
        self._pullback_extreme = None
        self._impulse_amplitude = Decimal("0")
        self._impulse_path = Decimal("0")
        self._impulse_bars = 0
        self._extension_count = 0
        self._last_depth = Decimal("0")
        self._bars = 0
        self._episode_id = ""

    def _start_episode(self, bar: Bar, anchor: Decimal, v_local: Decimal) -> None:
        """Attempt a fresh episode from a clean episode-local state."""
        self._clear_episode_state()
        impulse = abs(bar.close - anchor) / v_local
        if impulse < self.min_impulse or bar.close == anchor:
            return
        self.direction = "LONG" if bar.close > anchor else "SHORT"
        self._episode_counter += 1
        self._episode_id = f"{self.symbol}:{self.timeframe}:episode:{self._episode_counter}"
        self._anchor = anchor
        self._extreme = bar.close
        self._impulse_amplitude = abs(bar.close - anchor)
        self._impulse_path = abs(bar.close - anchor)
        self._impulse_bars = 1
        self._extension_count = 1
        self._pullback_extreme = None
        self._last_depth = Decimal("0")
        self._bars = 1
        self._transition(PDEState.PDE_IMPULSE)
        self._resume_transition(PDEResumptionState.RESUMPTION_NONE)

    def _invalidate(self, reason: str, reasons: list[str]) -> None:
        self._transition(PDEState.PDE_INVALIDATED)
        if self.resumption_state in {
            PDEResumptionState.RECOVERY_CANDIDATE,
            PDEResumptionState.RECOVERY_CONFIRMED,
            PDEResumptionState.DISPLACEMENT_CANDIDATE,
            PDEResumptionState.RESUMPTION_CONFIRMED,
        }:
            self._resume_transition(PDEResumptionState.RESUMPTION_FAILED)
        reasons.append(reason)

    def _impulse_metrics(self, bar: Bar, v_local: Decimal, structure_progression: Decimal) -> tuple[PDEImpulseState, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        displacement = self._impulse_amplitude / v_local if v_local > 0 else Decimal("0")
        efficiency = self._impulse_amplitude / self._impulse_path if self._impulse_path > 0 else Decimal("0")
        efficiency = max(Decimal("0"), min(Decimal("1"), efficiency))
        persistence = min(Decimal("1"), Decimal(self._extension_count) / Decimal(max(1, self._impulse_bars)))
        range_expansion = (bar.high - bar.low) / v_local if v_local > 0 else Decimal("0")
        if self.state in {PDEState.PDE_INVALIDATED, PDEState.PDE_RESUMPTION_FAILED, PDEState.PDE_DEEPENING, PDEState.PDE_WEAKENING}:
            impulse_state = PDEImpulseState.EXHAUSTING
        elif self.state in {PDEState.PDE_PULLBACK_CANDIDATE, PDEState.PDE_PULLBACK_ACTIVE, PDEState.PDE_STRENGTHENING, PDEState.PDE_RESUMPTION_IN_PROGRESS}:
            impulse_state = PDEImpulseState.MATURING
        elif self._extension_count > 0 and self._impulse_bars > 1:
            impulse_state = PDEImpulseState.EXTENDING
        elif self._impulse_bars > 1:
            impulse_state = PDEImpulseState.DEVELOPING
        else:
            impulse_state = PDEImpulseState.START
        weights = self.impulse_weights
        quality = (displacement * weights[0] + efficiency * weights[1] + max(Decimal("0"), min(Decimal("1"), (structure_progression + Decimal("1")) / Decimal("2"))) * weights[2] + persistence * weights[3] + min(Decimal("1"), range_expansion) * weights[4]) / sum(weights, Decimal("0"))
        return impulse_state, displacement, efficiency, structure_progression, persistence, range_expansion, max(Decimal("0"), min(Decimal("1"), quality))

    def _maturity(self) -> str:
        """Descriptive pullback maturity; never an entry/authorization gate."""
        if self.state in {PDEState.PDE_INVALIDATED, PDEState.PDE_RESUMPTION_FAILED}:
            return "EXHAUSTED"
        if self.state in {PDEState.PDE_FOLLOW_THROUGH, PDEState.PDE_RESUMPTION_IN_PROGRESS}:
            return "MATURE"
        if self.state == PDEState.PDE_DEEPENING:
            return "LATE"
        if self.state in {PDEState.PDE_PULLBACK_ACTIVE, PDEState.PDE_WEAKENING, PDEState.PDE_STRENGTHENING}:
            return "DEVELOPING"
        return "EARLY"

    def process_bar(
        self,
        bar: Bar,
        v_local: Decimal,
        flow_imbalance: Decimal = Decimal("0"),
        structure_direction: str = "UNKNOWN",
        regime_state: str = "UNKNOWN",
        root_id: str = "",
        parent_id: str = "market",
        parent_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
        configuration_version: int = 1,
        structure_progression: Decimal = Decimal("0"),
    ) -> PDEEvidence:
        AuthorityMatrix.verify_capability("PDE", "WRITE_PDE_STATE")
        if bar.symbol != self.symbol or bar.timeframe != self.timeframe or v_local <= 0:
            raise ValueError("PDEEngine invalid symbol, timeframe, or volatility")
        if bar.close_timestamp <= self._last_timestamp:
            raise ValueError("PDEEngine requires strictly increasing bar timestamps")

        self._last_timestamp = bar.close_timestamp
        self._root_id = root_id
        self._parent_id = parent_id
        self._parent_version = parent_version
        self._configuration_version = configuration_version
        self._data_version = data_version
        self._feature_version = feature_version
        self._bars += 1
        close = bar.close
        reasons: list[str] = []

        # A completed/failed/invalidated episode may start a new episode from
        # the current close.  The terminal state transition is explicit rather
        # than relying on an illegal terminal -> impulse jump.
        if self.state in {
            PDEState.PDE_NONE,
            PDEState.PDE_INVALIDATED,
            PDEState.PDE_FOLLOW_THROUGH,
            PDEState.PDE_RESUMPTION_FAILED,
        }:
            anchor = self._last_close if self._last_close is not None else bar.open
            if self.state != PDEState.PDE_NONE:
                self._transition(PDEState.PDE_NONE)
                self._resume_transition(PDEResumptionState.RESUMPTION_NONE)
            self._start_episode(bar, anchor, v_local)
            if self.state == PDEState.PDE_IMPULSE:
                reasons.append("NEW_EPISODE")
        elif self._anchor is not None and self._extreme is not None:
            if self._bars > self.max_episode_bars:
                self._invalidate("EPISODE_EXPIRED", reasons)
            else:
                # Once a pullback starts, the committed impulse extreme is frozen.
                # This prevents the denominator/reference point from moving while
                # pullback evidence is being evaluated.
                in_pullback = self.state in {
                    PDEState.PDE_PULLBACK_CANDIDATE,
                    PDEState.PDE_PULLBACK_ACTIVE,
                    PDEState.PDE_WEAKENING,
                    PDEState.PDE_STRENGTHENING,
                    PDEState.PDE_DEEPENING,
                    PDEState.PDE_RESUMPTION_IN_PROGRESS,
                }
                if not in_pullback:
                    self._impulse_bars += 1
                    self._impulse_path += abs(close - (self._last_close if self._last_close is not None else self._anchor))
                    extended = False
                    if self.direction == "LONG" and close > self._extreme:
                        self._extreme = close
                        self._impulse_amplitude = abs(self._extreme - self._anchor)
                        extended = True
                    elif self.direction == "SHORT" and close < self._extreme:
                        self._extreme = close
                        self._impulse_amplitude = abs(self._extreme - self._anchor)
                        extended = True
                    self._extension_count = self._extension_count + 1 if extended else 0

                if self._impulse_amplitude <= 0:
                    self._impulse_amplitude = abs(self._extreme - self._anchor)

                if self.direction == "LONG":
                    if close <= self._anchor:
                        self._invalidate("IMPULSE_ORIGIN_BROKEN", reasons)
                    else:
                        impulse_range = self._impulse_amplitude
                        depth = max(Decimal("0"), min(Decimal("1"), (self._extreme - close) / impulse_range))
                        if self.state == PDEState.PDE_IMPULSE and depth >= self.pullback_min:
                            self._pullback_extreme = close
                            self._last_depth = depth
                            self._transition(PDEState.PDE_PULLBACK_CANDIDATE)
                            self._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
                            reasons.append("PULLBACK_CANDIDATE")
                        elif self.state == PDEState.PDE_PULLBACK_CANDIDATE:
                            if depth >= self.pullback_min:
                                self._pullback_extreme = min(self._pullback_extreme or close, close)
                                self._last_depth = depth
                                self._transition(PDEState.PDE_PULLBACK_ACTIVE)
                                reasons.append("PULLBACK_CONFIRMED")
                            else:
                                self._transition(PDEState.PDE_IMPULSE)
                                self._resume_transition(PDEResumptionState.RESUMPTION_NONE)
                                self._pullback_extreme = None
                                self._last_depth = depth
                                reasons.append("PULLBACK_CANDIDATE_REJECTED")
                        elif self.state in {PDEState.PDE_PULLBACK_ACTIVE, PDEState.PDE_WEAKENING, PDEState.PDE_STRENGTHENING, PDEState.PDE_DEEPENING}:
                            self._pullback_extreme = min(self._pullback_extreme or close, close)
                            previous_depth = self._last_depth
                            self._last_depth = depth
                            pullback_range = abs(self._extreme - (self._pullback_extreme or close))
                            recovery = Decimal("0") if pullback_range <= 0 else max(Decimal("0"), min(Decimal("1"), (close - (self._pullback_extreme or close)) / pullback_range))
                            if depth >= self.pullback_max:
                                if self.state != PDEState.PDE_DEEPENING:
                                    self._transition(PDEState.PDE_DEEPENING)
                                if self.resumption_state == PDEResumptionState.RECOVERY_CANDIDATE:
                                    self._resume_transition(PDEResumptionState.DISPLACEMENT_CANDIDATE)
                                reasons.append("PULLBACK_DEEPENING")
                                if (flow_imbalance < 0 or structure_direction in {"SHORT", "BEARISH"} or regime_state == "TREND_DOWN"):
                                    reasons.append("ADVERSE_CONTEXT")
                            elif depth < previous_depth:
                                if self.state != PDEState.PDE_STRENGTHENING:
                                    self._transition(PDEState.PDE_STRENGTHENING)
                                reasons.append("PULLBACK_STRENGTHENING")
                            else:
                                if self.state != PDEState.PDE_WEAKENING:
                                    self._transition(PDEState.PDE_WEAKENING)
                                reasons.append("PULLBACK_WEAKENING")
                            if recovery >= self.recovery_threshold and flow_imbalance >= 0 and structure_direction not in {"SHORT", "BEARISH"} and regime_state != "TREND_DOWN":
                                if self.resumption_state in {PDEResumptionState.RECOVERY_CANDIDATE, PDEResumptionState.DISPLACEMENT_CANDIDATE}:
                                    self._resume_transition(PDEResumptionState.RECOVERY_CONFIRMED)
                                if self.state != PDEState.PDE_RESUMPTION_IN_PROGRESS:
                                    self._transition(PDEState.PDE_RESUMPTION_IN_PROGRESS)
                                reasons.append("RECOVERY_CONFIRMED")
                                if regime_state not in {"UNKNOWN", ""}:
                                    reasons.append("REGIME_COMPATIBLE_RECOVERY")
                                if structure_direction not in {"UNKNOWN", ""}:
                                    reasons.append("STRUCTURE_COMPATIBLE_RECOVERY")
                        elif self.state == PDEState.PDE_RESUMPTION_IN_PROGRESS:
                            if close > self._extreme:
                                self._resume_transition(PDEResumptionState.RESUMPTION_CONFIRMED)
                                self._transition(PDEState.PDE_FOLLOW_THROUGH)
                                reasons.append("RESUMPTION_CONFIRMED")
                            else:
                                # Recovery is not permanent: renewed adverse movement
                                # must be evaluated against the same impulse geometry.
                                if self._pullback_extreme is not None and close < self._pullback_extreme:
                                    self._pullback_extreme = close
                                pullback_range = abs(self._extreme - (self._pullback_extreme or close))
                                renewed_depth = (self._extreme - close) / self._impulse_amplitude if self._impulse_amplitude > 0 else Decimal("0")
                                renewed_depth = max(Decimal("0"), min(Decimal("1"), renewed_depth))
                                if pullback_range > 0 and renewed_depth >= self.pullback_max:
                                    self._last_depth = renewed_depth
                                    self._resume_transition(PDEResumptionState.RESUMPTION_FAILED)
                                    self._transition(PDEState.PDE_RESUMPTION_FAILED)
                                    reasons.append("RESUMPTION_FAILED")
                else:
                    if close >= self._anchor:
                        self._invalidate("IMPULSE_ORIGIN_BROKEN", reasons)
                    else:
                        impulse_range = self._impulse_amplitude
                        depth = max(Decimal("0"), min(Decimal("1"), (close - self._extreme) / impulse_range))
                        if self.state == PDEState.PDE_IMPULSE and depth >= self.pullback_min:
                            self._pullback_extreme = close
                            self._last_depth = depth
                            self._transition(PDEState.PDE_PULLBACK_CANDIDATE)
                            self._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
                            reasons.append("PULLBACK_CANDIDATE")
                        elif self.state == PDEState.PDE_PULLBACK_CANDIDATE:
                            if depth >= self.pullback_min:
                                self._pullback_extreme = max(self._pullback_extreme or close, close)
                                self._last_depth = depth
                                self._transition(PDEState.PDE_PULLBACK_ACTIVE)
                                reasons.append("PULLBACK_CONFIRMED")
                            else:
                                self._transition(PDEState.PDE_IMPULSE)
                                self._resume_transition(PDEResumptionState.RESUMPTION_NONE)
                                self._pullback_extreme = None
                                self._last_depth = depth
                                reasons.append("PULLBACK_CANDIDATE_REJECTED")
                        elif self.state in {PDEState.PDE_PULLBACK_ACTIVE, PDEState.PDE_WEAKENING, PDEState.PDE_STRENGTHENING, PDEState.PDE_DEEPENING}:
                            self._pullback_extreme = max(self._pullback_extreme or close, close)
                            previous_depth = self._last_depth
                            self._last_depth = depth
                            pullback_range = abs((self._pullback_extreme or close) - self._extreme)
                            recovery = Decimal("0") if pullback_range <= 0 else max(Decimal("0"), min(Decimal("1"), ((self._pullback_extreme or close) - close) / pullback_range))
                            if depth >= self.pullback_max:
                                if self.state != PDEState.PDE_DEEPENING:
                                    self._transition(PDEState.PDE_DEEPENING)
                                if self.resumption_state == PDEResumptionState.RECOVERY_CANDIDATE:
                                    self._resume_transition(PDEResumptionState.DISPLACEMENT_CANDIDATE)
                                reasons.append("PULLBACK_DEEPENING")
                                if (flow_imbalance > 0 or structure_direction in {"LONG", "BULLISH"} or regime_state == "TREND_UP"):
                                    reasons.append("ADVERSE_CONTEXT")
                            elif depth < previous_depth:
                                if self.state != PDEState.PDE_STRENGTHENING:
                                    self._transition(PDEState.PDE_STRENGTHENING)
                                reasons.append("PULLBACK_STRENGTHENING")
                            else:
                                if self.state != PDEState.PDE_WEAKENING:
                                    self._transition(PDEState.PDE_WEAKENING)
                                reasons.append("PULLBACK_WEAKENING")
                            if recovery >= self.recovery_threshold and flow_imbalance <= 0 and structure_direction not in {"LONG", "BULLISH"} and regime_state != "TREND_UP":
                                if self.resumption_state in {PDEResumptionState.RECOVERY_CANDIDATE, PDEResumptionState.DISPLACEMENT_CANDIDATE}:
                                    self._resume_transition(PDEResumptionState.RECOVERY_CONFIRMED)
                                if self.state != PDEState.PDE_RESUMPTION_IN_PROGRESS:
                                    self._transition(PDEState.PDE_RESUMPTION_IN_PROGRESS)
                                reasons.append("RECOVERY_CONFIRMED")
                                if regime_state not in {"UNKNOWN", ""}:
                                    reasons.append("REGIME_COMPATIBLE_RECOVERY")
                                if structure_direction not in {"UNKNOWN", ""}:
                                    reasons.append("STRUCTURE_COMPATIBLE_RECOVERY")
                        elif self.state == PDEState.PDE_RESUMPTION_IN_PROGRESS:
                            if close < self._extreme:
                                self._resume_transition(PDEResumptionState.RESUMPTION_CONFIRMED)
                                self._transition(PDEState.PDE_FOLLOW_THROUGH)
                                reasons.append("RESUMPTION_CONFIRMED")
                            else:
                                if self._pullback_extreme is not None and close > self._pullback_extreme:
                                    self._pullback_extreme = close
                                pullback_range = abs(self._extreme - (self._pullback_extreme or close))
                                renewed_depth = (close - self._extreme) / self._impulse_amplitude if self._impulse_amplitude > 0 else Decimal("0")
                                renewed_depth = max(Decimal("0"), min(Decimal("1"), renewed_depth))
                                if pullback_range > 0 and renewed_depth >= self.pullback_max:
                                    self._last_depth = renewed_depth
                                    self._resume_transition(PDEResumptionState.RESUMPTION_FAILED)
                                    self._transition(PDEState.PDE_RESUMPTION_FAILED)
                                    reasons.append("RESUMPTION_FAILED")

        self._last_close = close
        self.version += 1
        anchor = self._anchor if self._anchor is not None else close
        extreme = self._extreme if self._extreme is not None else close
        amplitude = self._impulse_amplitude if self._impulse_amplitude > 0 else abs(extreme - anchor)
        if self.direction == "LONG":
            depth = max(Decimal("0"), min(Decimal("1"), (extreme - close) / amplitude))
        elif self.direction == "SHORT":
            depth = max(Decimal("0"), min(Decimal("1"), (close - extreme) / amplitude))
        else:
            depth = Decimal("0")
        recovery = Decimal("0")
        if self._pullback_extreme is not None:
            pullback_range = abs(extreme - self._pullback_extreme)
            if pullback_range > 0:
                recovery = max(Decimal("0"), min(Decimal("1"), (close - self._pullback_extreme) / pullback_range if self.direction == "LONG" else (self._pullback_extreme - close) / pullback_range))
        displacement = abs(close - extreme) / v_local
        valid_until = bar.close_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe)
        impulse_state, impulse_d, impulse_e, impulse_s, impulse_p, impulse_r, impulse_q = self._impulse_metrics(bar, v_local, structure_progression)
        return PDEEvidence(
            state=self.state, direction=self.direction, impulse_amplitude=amplitude, pullback_depth=depth,
            recovery_ratio=recovery, resumption_displacement=displacement, timestamp=bar.close_timestamp,
            version=self.version, resumption_state=self.resumption_state, episode_id=self._episode_id, root_id=root_id,
            parent_id=parent_id, parent_version=parent_version, configuration_version=configuration_version,
            data_version=data_version, feature_version=feature_version, causal_watermark=bar.close_timestamp,
            valid_until=valid_until, authority="PDE", reason_codes=tuple(reasons), maturity=self._maturity(),
            impulse_state=impulse_state, impulse_displacement=impulse_d, impulse_efficiency=impulse_e,
            impulse_structure_progression=impulse_s, impulse_persistence=impulse_p,
            impulse_range_expansion=impulse_r, impulse_quality=impulse_q,
        )

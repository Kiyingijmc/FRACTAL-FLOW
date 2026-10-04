"""Adaptive Volatility-Normalized Structure Engine for FRACTAL FLOW.

Implements adaptive swings (SwingReversalMagnitude = ReversalDisplacement / V_local),
structural break confirmation (LevelCross x DisplacementConfirmation x PersistenceConfirmation),
state transitions with lineage tracking, and primary structural stop candidates.
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
class SwingState(str, Enum):
    SWING_NONE = "SWING_NONE"
    SWING_CANDIDATE = "SWING_CANDIDATE"
    SWING_CONFIRMED = "SWING_CONFIRMED"
    SWING_PROTECTED = "SWING_PROTECTED"
    SWING_BROKEN = "SWING_BROKEN"


@unique
class BreakState(str, Enum):
    BREAK_NONE = "BREAK_NONE"
    BREAK_CANDIDATE = "BREAK_CANDIDATE"
    BREAK_CONFIRMED = "BREAK_CONFIRMED"
    BREAK_ESTABLISHED = "BREAK_ESTABLISHED"
    FAILED_BREAK = "FAILED_BREAK"


@unique
class StructuralDamageState(str, Enum):
    INTACT = "INTACT"
    DAMAGE_CANDIDATE = "DAMAGE_CANDIDATE"
    DAMAGE_CONFIRMED = "DAMAGE_CONFIRMED"
    STRUCTURE_BROKEN = "STRUCTURE_BROKEN"
    RECLAIM_CANDIDATE = "RECLAIM_CANDIDATE"
    RECLAIM_CONFIRMED = "RECLAIM_CONFIRMED"


@dataclass(frozen=True)
class StructuralBreak:
    symbol: str
    level_price: Decimal
    level_type: str  # HIGH or LOW
    level_cross: bool
    displacement_confirmed: bool
    persistence_confirmed: bool
    persistence_count: int
    v_local: Decimal

    @property
    def is_confirmed_break(self) -> bool:
        """StructuralBreak = LevelCross x DisplacementConfirmation x PersistenceConfirmation."""
        return self.level_cross and self.displacement_confirmed and self.persistence_confirmed


@dataclass(frozen=True)
class StructuralStopCandidate:
    symbol: str
    direction: str  # LONG or SHORT
    protected_level_price: Decimal
    atr_buffer: Decimal
    recommended_stop_price: Decimal
    timeframe: str = "1M"


@dataclass
class StructureTransitionRecord:
    symbol: str
    timeframe: str
    swing_state: SwingState
    previous_swing_state: SwingState
    break_state: BreakState
    previous_break_state: BreakState
    damage_state: StructuralDamageState
    previous_damage_state: StructuralDamageState
    timestamp: int
    v_local: Decimal
    root_id: str
    parent_id: str
    parent_version: int
    state_version: int
    config_version: int
    data_version: int
    feature_version: int
    reason_codes: list[ReasonCode] = field(default_factory=list)
    authority: str = "STRUCTURE"

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
            state_id=f"struct_state_{object_id}_{self.state_version}",
            object_id=object_id,
            object_type="SwingState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=self.root_id,
            parent_id=self.parent_id,
            parent_version=self.parent_version,
            state=self.swing_state.value,
            previous_state=self.previous_swing_state.value,
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


class StructureEngine:
    """Adaptive, Volatility-Normalized Structure Engine."""

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        min_reversal_magnitude: Decimal = Decimal("1.5"),
        displacement_threshold_mult: Decimal = Decimal("0.5"),
        persistence_bars_required: int = 2,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.min_reversal_magnitude = min_reversal_magnitude
        self.displacement_threshold_mult = displacement_threshold_mult
        self.persistence_bars_required = persistence_bars_required

        self.swing_state = SwingState.SWING_NONE
        self.previous_swing_state = SwingState.SWING_NONE
        self.break_state = BreakState.BREAK_NONE
        self.previous_break_state = BreakState.BREAK_NONE
        self.damage_state = StructuralDamageState.INTACT
        self.previous_damage_state = StructuralDamageState.INTACT

        self.state_version = 0
        self.protected_high: Optional[Decimal] = None
        self.protected_low: Optional[Decimal] = None
        self.last_extreme_high: Optional[Decimal] = None
        self.last_extreme_low: Optional[Decimal] = None
        self.persistence_counter = 0

        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None

    def calculate_v_local(self, current_bar: Bar, atr_14: Optional[Decimal] = None) -> Decimal:
        """Executably defines V_local as local volatility reference (ATR-14 or minimum pip floor)."""
        if atr_14 is not None and atr_14 > Decimal("0.0"):
            return atr_14
        bar_range = current_bar.high - current_bar.low
        return max(bar_range, Decimal("0.0001"))

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
    ) -> StructureTransitionRecord:
        AuthorityMatrix.verify_capability("Structure", "WRITE_STRUCTURE_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"StructureEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        # Version Race & Stale Version Validations
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

        # Update high/low extremes
        if self.last_extreme_high is None or bar.high > self.last_extreme_high:
            self.last_extreme_high = bar.high
        if self.last_extreme_low is None or bar.low < self.last_extreme_low:
            self.last_extreme_low = bar.low

        # 1. Adaptive Swing Reversal Magnitude Evaluation
        high_displacement = self.last_extreme_high - bar.close
        low_displacement = bar.close - self.last_extreme_low

        high_magnitude = high_displacement / v_local if v_local > Decimal("0.0") else Decimal("0.0")
        low_magnitude = low_displacement / v_local if v_local > Decimal("0.0") else Decimal("0.0")

        # Swing state transitions
        old_swing = self.swing_state
        if high_magnitude >= self.min_reversal_magnitude or low_magnitude >= self.min_reversal_magnitude:
            if self.swing_state == SwingState.SWING_NONE:
                self.swing_state = SwingState.SWING_CANDIDATE
            elif self.swing_state == SwingState.SWING_CANDIDATE:
                self.swing_state = SwingState.SWING_CONFIRMED
                if high_magnitude >= self.min_reversal_magnitude:
                    self.protected_high = self.last_extreme_high
                if low_magnitude >= self.min_reversal_magnitude:
                    self.protected_low = self.last_extreme_low
            elif self.swing_state == SwingState.SWING_CONFIRMED:
                self.swing_state = SwingState.SWING_PROTECTED

        if self.swing_state != old_swing:
            self.previous_swing_state = old_swing

        # 2. Structural Break Evaluation (LevelCross x DisplacementConfirmation x PersistenceConfirmation)
        level_cross = False
        disp_confirmed = False
        persist_confirmed = False

        if self.protected_high is not None and bar.close > self.protected_high:
            level_cross = True
            disp = bar.close - self.protected_high
            if disp >= (self.displacement_threshold_mult * v_local):
                disp_confirmed = True
                self.persistence_counter += 1
                if self.persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.persistence_counter = 0

        elif self.protected_low is not None and bar.close < self.protected_low:
            level_cross = True
            disp = self.protected_low - bar.close
            if disp >= (self.displacement_threshold_mult * v_local):
                disp_confirmed = True
                self.persistence_counter += 1
                if self.persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.persistence_counter = 0
        else:
            self.persistence_counter = 0

        struct_break = StructuralBreak(
            symbol=self.symbol,
            level_price=self.protected_high or self.protected_low or bar.close,
            level_type="HIGH" if self.protected_high else "LOW",
            level_cross=level_cross,
            displacement_confirmed=disp_confirmed,
            persistence_confirmed=persist_confirmed,
            persistence_count=self.persistence_counter,
            v_local=v_local,
        )

        old_break = self.break_state
        if struct_break.is_confirmed_break:
            if self.break_state in (BreakState.BREAK_NONE, BreakState.BREAK_CANDIDATE):
                self.break_state = BreakState.BREAK_CONFIRMED
            elif self.break_state == BreakState.BREAK_CONFIRMED:
                self.break_state = BreakState.BREAK_ESTABLISHED
        elif level_cross and not disp_confirmed:
            self.break_state = BreakState.BREAK_CANDIDATE
        elif old_break == BreakState.BREAK_CANDIDATE and not level_cross:
            self.break_state = BreakState.FAILED_BREAK

        if self.break_state != old_break:
            self.previous_break_state = old_break

        # 3. Structural Damage State Evaluation
        old_damage = self.damage_state
        if struct_break.is_confirmed_break:
            self.damage_state = StructuralDamageState.STRUCTURE_BROKEN
            self.swing_state = SwingState.SWING_BROKEN
            reasons.append(ReasonCode.STRUCTURE_INVALIDATED)
        elif level_cross:
            self.damage_state = StructuralDamageState.DAMAGE_CANDIDATE

        if self.damage_state != old_damage:
            self.previous_damage_state = old_damage

        self.state_version += 1

        return StructureTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            swing_state=self.swing_state,
            previous_swing_state=self.previous_swing_state,
            break_state=self.break_state,
            previous_break_state=self.previous_break_state,
            damage_state=self.damage_state,
            previous_damage_state=self.previous_damage_state,
            timestamp=bar.close_timestamp,
            v_local=v_local,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            reason_codes=reasons,
            authority="STRUCTURE",
        )

    def get_structural_stop_candidate(self, direction: str, atr_14: Decimal) -> Optional[StructuralStopCandidate]:
        """Outputs primary structural stop candidate strictly without sizing, authorizing, or submitting orders."""
        AuthorityMatrix.verify_capability("Structure", "OUTPUT_STRUCTURAL_STOP_CANDIDATE")
        buffer = atr_14 * Decimal("0.5")
        if direction == "LONG" and self.protected_low is not None:
            stop_price = self.protected_low - buffer
            return StructuralStopCandidate(
                symbol=self.symbol,
                direction="LONG",
                protected_level_price=self.protected_low,
                atr_buffer=buffer,
                recommended_stop_price=stop_price,
                timeframe=self.timeframe,
            )
        elif direction == "SHORT" and self.protected_high is not None:
            stop_price = self.protected_high + buffer
            return StructuralStopCandidate(
                symbol=self.symbol,
                direction="SHORT",
                protected_level_price=self.protected_high,
                atr_buffer=buffer,
                recommended_stop_price=stop_price,
                timeframe=self.timeframe,
            )
        return None

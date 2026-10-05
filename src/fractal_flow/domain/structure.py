"""Adaptive Volatility-Normalized Structure Engine v2 for FRACTAL FLOW.

Implements adaptive swings (SwingReversalMagnitude = ReversalDisplacement / V_local),
causal local candidate pivot detection (candidate_at, confirmed_at, effective_from),
independent HIGH and LOW candidate lifecycles with re-arm capability,
formal HH/HL/LH/LL/EQUAL classifications against previous confirmed swing of same direction,
instrument-aware equality tolerance, canonical structural trend ownership,
exact BOS vs CHoCH break truth table, reclaim/rearm state machine, isolated persistence counters,
versioned configuration schema, bounded swing record history with deterministic eviction,
and primary structural stop candidate generation strictly without trading authority.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Optional

from src.fractal_flow.config.config import StructureConfig
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
class PivotCandidate:
    side: str  # HIGH or LOW
    price: Decimal
    candidate_at: int
    created_from_timestamp: int
    status: SwingState
    v_local_at_candidate: Decimal
    version: int


@dataclass(frozen=True)
class SwingRecord:
    swing_id: str
    symbol: str
    timeframe: str
    candidate_at: int
    confirmed_at: int
    effective_from: int
    price: Decimal
    swing_type: str  # HIGH or LOW
    classification: str  # HH, HL, LH, LL, EQUAL_HIGH, EQUAL_LOW, NEUTRAL
    status: SwingState
    version: int
    v_local: Decimal = Decimal("0.0001")
    reversal_magnitude: Decimal = Decimal("1.5")
    root_id: str = "r0"
    parent_id: str = "p0"
    parent_version: int = 1

    @property
    def pivot_timestamp(self) -> int:
        """Alias for candidate_at timestamp for backward compatibility."""
        return self.candidate_at


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
    break_timestamp: int = 0

    @property
    def is_confirmed_break(self) -> bool:
        """StructuralBreak = LevelCross x DisplacementConfirmation x PersistenceConfirmation."""
        return self.level_cross and self.displacement_confirmed and self.persistence_confirmed


@dataclass(frozen=True)
class ChangeOfCharacter:
    symbol: str
    timeframe: str
    prior_direction: str
    new_direction: str
    trigger_price: Decimal
    protected_level_price: Decimal
    confirmed_at: int


@dataclass(frozen=True)
class FailedBreak:
    symbol: str
    timeframe: str
    level_price: Decimal
    level_type: str
    breach_price: Decimal
    attempt_timestamp: int
    failed_at: int


@dataclass(frozen=True)
class ReclaimEvent:
    symbol: str
    timeframe: str
    level_price: Decimal
    level_type: str
    reclaim_price: Decimal
    reclaimed_at: int


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
    active_swings: list[SwingRecord] = field(default_factory=list)
    bos_type: str = "NONE"
    reclaim_type: str = "NONE"
    protected_high: Optional[Decimal] = None
    protected_low: Optional[Decimal] = None
    last_choch: Optional[ChangeOfCharacter] = None
    last_failed_break: Optional[FailedBreak] = None
    last_reclaim: Optional[ReclaimEvent] = None
    structural_ownership: str = "AMBIGUOUS"
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
        validity_window = StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe)

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
            valid_until=p_ts + validity_window,
            last_seen=s_ts,
            reason_codes=[r.value for r in self.reason_codes],
            configuration_version=self.config_version,
            data_version=self.data_version,
            feature_version=self.feature_version,
            authority=self.authority,
        )


class StructureEngine:
    """Adaptive, Volatility-Normalized Structure Engine v2."""

    @staticmethod
    def get_default_pip_size(symbol: str) -> Decimal:
        """Determines instrument-aware default pip size."""
        sym = symbol.upper()
        if sym.startswith("XAU"):
            return Decimal("0.1")
        elif "JPY" in sym:
            return Decimal("0.01")
        else:
            return Decimal("0.0001")

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        config: Optional[StructureConfig] = None,
        min_reversal_magnitude: Optional[Decimal] = None,
        displacement_threshold_mult: Optional[Decimal] = None,
        persistence_bars_required: Optional[int] = None,
        max_swing_history: Optional[int] = None,
        min_v_local_floor: Optional[Decimal] = None,
        equality_tolerance_pips: Optional[Decimal] = None,
        atr_stop_buffer_mult: Optional[Decimal] = None,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.config = config or StructureConfig()

        self.min_reversal_magnitude = (
            min_reversal_magnitude if min_reversal_magnitude is not None else self.config.min_reversal_magnitude
        )
        self.displacement_threshold_mult = (
            displacement_threshold_mult
            if displacement_threshold_mult is not None
            else self.config.displacement_threshold_mult
        )
        self.persistence_bars_required = (
            persistence_bars_required
            if persistence_bars_required is not None
            else self.config.persistence_bars_required
        )
        self.max_swing_history = max_swing_history if max_swing_history is not None else self.config.max_swing_history
        self.min_v_local_floor = min_v_local_floor if min_v_local_floor is not None else self.config.min_v_local_floor

        default_pip = self.get_default_pip_size(self.symbol)
        self.equality_tolerance_pips = (
            equality_tolerance_pips
            if equality_tolerance_pips is not None
            else (self.config.equality_tolerance_pips * (default_pip / Decimal("0.0001")))
        )
        self.atr_stop_buffer_mult = (
            atr_stop_buffer_mult if atr_stop_buffer_mult is not None else self.config.atr_stop_buffer_mult
        )

        self.swing_state = SwingState.SWING_NONE
        self.previous_swing_state = SwingState.SWING_NONE
        self.break_state = BreakState.BREAK_NONE
        self.previous_break_state = BreakState.BREAK_NONE
        self.damage_state = StructuralDamageState.INTACT
        self.previous_damage_state = StructuralDamageState.INTACT

        self.state_version = 0
        self.protected_high: Optional[Decimal] = None
        self.protected_low: Optional[Decimal] = None

        # Independent Local Candidate Pivot State Machine
        self._high_candidate: Optional[PivotCandidate] = None
        self._low_candidate: Optional[PivotCandidate] = None

        self.high_persistence_counter = 0
        self.low_persistence_counter = 0
        self.current_direction: str = "UNKNOWN"

        self.swings: list[SwingRecord] = []
        self.last_choch: Optional[ChangeOfCharacter] = None
        self.last_failed_break: Optional[FailedBreak] = None
        self.last_reclaim: Optional[ReclaimEvent] = None

        self.last_break_candidate_level_type: str = "NONE"
        self.last_break_candidate_level_price: Optional[Decimal] = None

        self._last_bar: Optional[Bar] = None
        self._last_parent_id: Optional[str] = None
        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None
        self._last_timestamp: int = 0
        self._last_transition_record: Optional[StructureTransitionRecord] = None

    @property
    def _candidate_high_price(self) -> Optional[Decimal]:
        return self._high_candidate.price if self._high_candidate else None

    @property
    def _candidate_low_price(self) -> Optional[Decimal]:
        return self._low_candidate.price if self._low_candidate else None

    @property
    def persistence_counter(self) -> int:
        """Backward-compatible persistence counter property."""
        return max(self.high_persistence_counter, self.low_persistence_counter)

    @property
    def structural_ownership(self) -> str:
        """Single Source of Truth for structural trend ownership ('BULLISH', 'BEARISH', 'AMBIGUOUS', or 'UNKNOWN')."""
        high_swings = [s for s in self.swings if s.swing_type == "HIGH" and s.status != SwingState.SWING_BROKEN]
        low_swings = [s for s in self.swings if s.swing_type == "LOW" and s.status != SwingState.SWING_BROKEN]

        if not high_swings or not low_swings:
            return "UNKNOWN" if not self.swings else "AMBIGUOUS"

        latest_high = high_swings[-1]
        latest_low = low_swings[-1]

        if (latest_high.classification in ("HH", "EQUAL_HIGH")) and (latest_low.classification in ("HL", "NEUTRAL")):
            return "BULLISH"
        elif (latest_low.classification in ("LL", "EQUAL_LOW")) and (latest_high.classification in ("LH", "NEUTRAL")):
            return "BEARISH"
        elif latest_high.classification == "HH" and latest_low.classification == "LL":
            return "AMBIGUOUS"
        elif latest_high.classification == "LH" and latest_low.classification == "HL":
            return "AMBIGUOUS"

        return "AMBIGUOUS"

    def _rearm_protected_levels(self) -> None:
        """Re-arms protected high and low levels from active confirmed swings."""
        high_swings = [s for s in self.swings if s.swing_type == "HIGH" and s.status != SwingState.SWING_BROKEN]
        low_swings = [s for s in self.swings if s.swing_type == "LOW" and s.status != SwingState.SWING_BROKEN]
        if high_swings:
            self.protected_high = high_swings[-1].price
        if low_swings:
            self.protected_low = low_swings[-1].price

    def calculate_v_local(self, current_bar: Bar, atr_14: Optional[Decimal] = None) -> Decimal:
        """Executably defines V_local as local volatility reference (ATR-14 or minimum pip floor)."""
        if atr_14 is not None and atr_14 > Decimal("0.0"):
            return max(atr_14, self.min_v_local_floor)
        bar_range = current_bar.high - current_bar.low
        return max(bar_range, self.min_v_local_floor)

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

        # Parent Identity & Version Monotonicity Validation
        if self._last_parent_id is not None and parent_id != self._last_parent_id:
            raise ValueError(
                f"Parent identity discontinuity: incoming parent_id '{parent_id}' != active '{self._last_parent_id}'"
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

        if bar.close_timestamp < self._last_timestamp:
            raise ValueError(
                f"Chronology violation: incoming bar timestamp {bar.close_timestamp} prior to last seen {self._last_timestamp}"
            )

        # Duplicate timestamp handling: idempotent replay if identical bar, error if conflicting bar
        if bar.close_timestamp == self._last_timestamp and self._last_bar is not None:
            if bar != self._last_bar:
                raise ValueError(
                    f"Duplicate timestamp conflict at {bar.close_timestamp}: differing bar observation rejected."
                )
            if self._last_transition_record is not None:
                return self._last_transition_record

        effective_v_local = max(v_local, self.min_v_local_floor)

        self._last_bar = bar
        self._last_parent_id = parent_id
        self._last_parent_version = parent_version
        self._last_data_version = data_version
        self._last_config_version = config_version
        self._last_timestamp = bar.close_timestamp

        reasons: list[ReasonCode] = []
        bos_type = "NONE"
        reclaim_type = "NONE"

        # 1. Independent Local Candidate Pivot Maintenance & Extension
        if self._high_candidate is None:
            self._high_candidate = PivotCandidate(
                side="HIGH",
                price=bar.high,
                candidate_at=bar.close_timestamp,
                created_from_timestamp=bar.close_timestamp,
                status=SwingState.SWING_CANDIDATE,
                v_local_at_candidate=effective_v_local,
                version=self.state_version + 1,
            )
        elif bar.high > self._high_candidate.price:
            self._high_candidate = PivotCandidate(
                side="HIGH",
                price=bar.high,
                candidate_at=bar.close_timestamp,
                created_from_timestamp=self._high_candidate.created_from_timestamp,
                status=SwingState.SWING_CANDIDATE,
                v_local_at_candidate=effective_v_local,
                version=self.state_version + 1,
            )

        if self._low_candidate is None:
            self._low_candidate = PivotCandidate(
                side="LOW",
                price=bar.low,
                candidate_at=bar.close_timestamp,
                created_from_timestamp=bar.close_timestamp,
                status=SwingState.SWING_CANDIDATE,
                v_local_at_candidate=effective_v_local,
                version=self.state_version + 1,
            )
        elif bar.low < self._low_candidate.price:
            self._low_candidate = PivotCandidate(
                side="LOW",
                price=bar.low,
                candidate_at=bar.close_timestamp,
                created_from_timestamp=self._low_candidate.created_from_timestamp,
                status=SwingState.SWING_CANDIDATE,
                v_local_at_candidate=effective_v_local,
                version=self.state_version + 1,
            )

        # Update swing_state to SWING_CANDIDATE if candidate is active and state is SWING_NONE or SWING_BROKEN
        if self.swing_state in (SwingState.SWING_NONE, SwingState.SWING_BROKEN):
            self.swing_state = SwingState.SWING_CANDIDATE

        # 2. Causal Reversal Magnitude Evaluation from Local Candidates
        high_magnitude = Decimal("0.0")
        if self._high_candidate is not None:
            high_disp = self._high_candidate.price - bar.close
            high_magnitude = high_disp / effective_v_local if high_disp > Decimal("0.0") else Decimal("0.0")

        low_magnitude = Decimal("0.0")
        if self._low_candidate is not None:
            low_disp = bar.close - self._low_candidate.price
            low_magnitude = low_disp / effective_v_local if low_disp > Decimal("0.0") else Decimal("0.0")

        old_swing = self.swing_state
        if high_magnitude >= self.min_reversal_magnitude or low_magnitude >= self.min_reversal_magnitude:
            if high_magnitude >= self.min_reversal_magnitude and self._high_candidate is not None:
                self.protected_high = self._high_candidate.price
                self._register_swing(
                    swing_type="HIGH",
                    price=self._high_candidate.price,
                    candidate_at=self._high_candidate.candidate_at,
                    confirmed_at=bar.close_timestamp,
                    status=SwingState.SWING_CONFIRMED,
                    v_local=effective_v_local,
                    reversal_magnitude=high_magnitude,
                    root_id=root_id,
                    parent_id=parent_id,
                    parent_version=parent_version,
                )
                self._high_candidate = None

            if low_magnitude >= self.min_reversal_magnitude and self._low_candidate is not None:
                self.protected_low = self._low_candidate.price
                self._register_swing(
                    swing_type="LOW",
                    price=self._low_candidate.price,
                    candidate_at=self._low_candidate.candidate_at,
                    confirmed_at=bar.close_timestamp,
                    status=SwingState.SWING_CONFIRMED,
                    v_local=effective_v_local,
                    reversal_magnitude=low_magnitude,
                    root_id=root_id,
                    parent_id=parent_id,
                    parent_version=parent_version,
                )
                self._low_candidate = None

            if self.swing_state == SwingState.SWING_CANDIDATE:
                self.swing_state = SwingState.SWING_CONFIRMED
            elif self.swing_state == SwingState.SWING_CONFIRMED:
                self.swing_state = SwingState.SWING_PROTECTED

        if self.swing_state != old_swing:
            self.previous_swing_state = old_swing

        # 3. Structural Break Evaluation (LevelCross x DisplacementConfirmation x PersistenceConfirmation)
        high_cross = False
        low_cross = False
        disp_confirmed = False
        persist_confirmed = False

        if self.protected_high is not None and bar.close > self.protected_high:
            high_cross = True
            disp = bar.close - self.protected_high
            if disp >= (self.displacement_threshold_mult * effective_v_local):
                disp_confirmed = True
                self.high_persistence_counter += 1
                if self.high_persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.high_persistence_counter = 0
        else:
            self.high_persistence_counter = 0

        if self.protected_low is not None and bar.close < self.protected_low:
            low_cross = True
            disp = self.protected_low - bar.close
            if disp >= (self.displacement_threshold_mult * effective_v_local):
                disp_confirmed = True
                self.low_persistence_counter += 1
                if self.low_persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.low_persistence_counter = 0
        else:
            self.low_persistence_counter = 0

        level_cross = high_cross or low_cross
        active_level_type = "HIGH" if high_cross else ("LOW" if low_cross else "NONE")

        active_level_price: Decimal
        if high_cross and self.protected_high is not None:
            active_level_price = self.protected_high
        elif low_cross and self.protected_low is not None:
            active_level_price = self.protected_low
        elif self.protected_high is not None:
            active_level_price = self.protected_high
        elif self.protected_low is not None:
            active_level_price = self.protected_low
        else:
            active_level_price = bar.close

        active_persistence_count = (
            self.high_persistence_counter if active_level_type == "HIGH" else self.low_persistence_counter
        )

        if level_cross and not disp_confirmed:
            self.last_break_candidate_level_type = active_level_type
            self.last_break_candidate_level_price = active_level_price

        struct_break = StructuralBreak(
            symbol=self.symbol,
            level_price=active_level_price,
            level_type=active_level_type,
            level_cross=level_cross,
            displacement_confirmed=disp_confirmed,
            persistence_confirmed=persist_confirmed,
            persistence_count=active_persistence_count,
            v_local=effective_v_local,
            break_timestamp=bar.close_timestamp,
        )

        old_break = self.break_state
        if struct_break.is_confirmed_break:
            if self.break_state in (BreakState.BREAK_NONE, BreakState.BREAK_CANDIDATE):
                self.break_state = BreakState.BREAK_CONFIRMED
            elif self.break_state == BreakState.BREAK_CONFIRMED:
                self.break_state = BreakState.BREAK_ESTABLISHED

            ownership = self.structural_ownership
            # Exact Canonical 8-Row Truth Table Evaluation
            if ownership == "BULLISH":
                if active_level_type == "HIGH":
                    bos_type = "BOS_BULLISH"
                elif active_level_type == "LOW":
                    bos_type = "CHOCH_BEARISH"
                    if self.current_direction != "SHORT":
                        self.last_choch = ChangeOfCharacter(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            prior_direction=self.current_direction,
                            new_direction="SHORT",
                            trigger_price=bar.close,
                            protected_level_price=struct_break.level_price,
                            confirmed_at=bar.close_timestamp,
                        )
                        self.current_direction = "SHORT"
            elif ownership == "BEARISH":
                if active_level_type == "LOW":
                    bos_type = "BOS_BEARISH"
                elif active_level_type == "HIGH":
                    bos_type = "CHOCH_BULLISH"
                    if self.current_direction != "LONG":
                        self.last_choch = ChangeOfCharacter(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            prior_direction=self.current_direction,
                            new_direction="LONG",
                            trigger_price=bar.close,
                            protected_level_price=struct_break.level_price,
                            confirmed_at=bar.close_timestamp,
                        )
                        self.current_direction = "LONG"
            else:
                # AMBIGUOUS or UNKNOWN: No CHoCH allowed from UNKNOWN/AMBIGUOUS!
                bos_type = "NONE"

        elif level_cross and not disp_confirmed:
            self.break_state = BreakState.BREAK_CANDIDATE
        elif old_break == BreakState.BREAK_CANDIDATE and not level_cross:
            self.break_state = BreakState.FAILED_BREAK
            f_type = (
                self.last_break_candidate_level_type
                if self.last_break_candidate_level_type != "NONE"
                else active_level_type
            )
            f_price = (
                self.last_break_candidate_level_price
                if self.last_break_candidate_level_price is not None
                else active_level_price
            )
            self.last_failed_break = FailedBreak(
                symbol=self.symbol,
                timeframe=self.timeframe,
                level_price=f_price,
                level_type=f_type,
                breach_price=bar.high if f_type == "HIGH" else bar.low,
                attempt_timestamp=bar.close_timestamp,
                failed_at=bar.close_timestamp,
            )
        elif not level_cross:
            self.break_state = BreakState.BREAK_NONE

        if self.break_state != old_break:
            self.previous_break_state = old_break

        # 4. Structural Damage & Reclaim State Machine (Strictly matching spec/transitions.yaml)
        old_damage = self.damage_state
        if struct_break.is_confirmed_break:
            if bos_type in ("CHOCH_BULLISH", "CHOCH_BEARISH"):
                self.damage_state = StructuralDamageState.STRUCTURE_BROKEN
                self.swing_state = SwingState.SWING_BROKEN
                reasons.append(ReasonCode.STRUCTURE_INVALIDATED)
            else:
                # Continuation break (BOS_BULLISH / BOS_BEARISH) does NOT destroy structure!
                self.damage_state = StructuralDamageState.INTACT
        elif level_cross:
            self.damage_state = StructuralDamageState.DAMAGE_CANDIDATE
        elif (
            old_damage in (StructuralDamageState.STRUCTURE_BROKEN, StructuralDamageState.DAMAGE_CANDIDATE)
            and not level_cross
        ):
            self.damage_state = StructuralDamageState.RECLAIM_CANDIDATE
        elif old_damage == StructuralDamageState.RECLAIM_CANDIDATE and not level_cross:
            self.damage_state = StructuralDamageState.RECLAIM_CONFIRMED
            reclaim_type = "RECLAIM_CONFIRMED"
            r_type = (
                self.last_break_candidate_level_type
                if self.last_break_candidate_level_type != "NONE"
                else active_level_type
            )
            r_price = (
                self.last_break_candidate_level_price
                if self.last_break_candidate_level_price is not None
                else active_level_price
            )
            self.last_reclaim = ReclaimEvent(
                symbol=self.symbol,
                timeframe=self.timeframe,
                level_price=r_price,
                level_type=r_type,
                reclaim_price=bar.close,
                reclaimed_at=bar.close_timestamp,
            )
            # Re-arm protected levels upon reclaim
            self._rearm_protected_levels()
        elif old_damage == StructuralDamageState.RECLAIM_CONFIRMED and not level_cross:
            self.damage_state = StructuralDamageState.INTACT
            self._rearm_protected_levels()

        if self.damage_state != old_damage:
            self.previous_damage_state = old_damage

        self.state_version += 1

        rec = StructureTransitionRecord(
            symbol=self.symbol,
            timeframe=self.timeframe,
            swing_state=self.swing_state,
            previous_swing_state=self.previous_swing_state,
            break_state=self.break_state,
            previous_break_state=self.previous_break_state,
            damage_state=self.damage_state,
            previous_damage_state=self.previous_damage_state,
            timestamp=bar.close_timestamp,
            v_local=effective_v_local,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            active_swings=list(self.swings),
            bos_type=bos_type,
            reclaim_type=reclaim_type,
            protected_high=self.protected_high,
            protected_low=self.protected_low,
            last_choch=self.last_choch,
            last_failed_break=self.last_failed_break,
            last_reclaim=self.last_reclaim,
            structural_ownership=self.structural_ownership,
            reason_codes=reasons,
            authority="STRUCTURE",
        )
        self._last_transition_record = rec
        return rec

    def _register_swing(
        self,
        swing_type: str,
        price: Decimal,
        candidate_at: int = 0,
        confirmed_at: int = 0,
        status: SwingState = SwingState.SWING_CONFIRMED,
        v_local: Decimal = Decimal("0.0001"),
        reversal_magnitude: Decimal = Decimal("1.5"),
        root_id: str = "r0",
        parent_id: str = "p0",
        parent_version: int = 1,
        pivot_ts: Optional[int] = None,
    ) -> SwingRecord:
        """Registers a new confirmed swing with HH/HL/LH/LL/EQUAL classification and bounded history eviction."""
        c_at = candidate_at if candidate_at != 0 else (pivot_ts or confirmed_at)
        conf_at = confirmed_at if confirmed_at != 0 else c_at
        if conf_at < c_at:
            raise ValueError(
                f"Temporal causality invariant violation: confirmed_at ({conf_at}) < candidate_at ({c_at})"
            )

        prev_same_type = [s for s in self.swings if s.swing_type == swing_type and s.status != SwingState.SWING_BROKEN]
        classification = "NEUTRAL"

        if prev_same_type:
            last_same = prev_same_type[-1]
            diff = abs(price - last_same.price)
            if diff <= self.equality_tolerance_pips:
                classification = "EQUAL_HIGH" if swing_type == "HIGH" else "EQUAL_LOW"
            elif swing_type == "HIGH":
                classification = "HH" if price > last_same.price else "LH"
            elif swing_type == "LOW":
                classification = "HL" if price > last_same.price else "LL"

        swing_id = f"swing_{self.symbol}_{self.timeframe}_{swing_type}_{c_at}_{self.state_version}"
        rec = SwingRecord(
            swing_id=swing_id,
            symbol=self.symbol,
            timeframe=self.timeframe,
            candidate_at=c_at,
            confirmed_at=conf_at,
            effective_from=conf_at,
            price=price,
            swing_type=swing_type,
            classification=classification,
            status=status,
            version=self.state_version,
            v_local=v_local,
            reversal_magnitude=reversal_magnitude,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
        )

        self.swings.append(rec)
        self._evict_swing_history()
        return rec

    def _evict_swing_history(self) -> None:
        """Bounded deterministic eviction of old/broken swings."""
        if len(self.swings) <= self.max_swing_history:
            return
        for idx, s in enumerate(self.swings):
            if s.status == SwingState.SWING_BROKEN:
                self.swings.pop(idx)
                return
        self.swings.pop(0)

    def get_confirmed_swings(self, decision_timestamp: int) -> list[SwingRecord]:
        """Returns confirmed swings causally available at decision_timestamp."""
        return [s for s in self.swings if s.effective_from <= decision_timestamp]

    def get_structural_stop_candidate(self, direction: str, atr_14: Decimal) -> Optional[StructuralStopCandidate]:
        """Outputs primary structural stop candidate strictly without sizing, authorizing, or submitting orders."""
        AuthorityMatrix.verify_capability("Structure", "OUTPUT_STRUCTURAL_STOP_CANDIDATE")
        buffer = atr_14 * self.atr_stop_buffer_mult
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

"""Adaptive Volatility-Normalized Structure Engine for FRACTAL FLOW (Phase 2A — Structure v2).

Implements:
- Bounded, deterministic SwingRecord sets with replay equivalence and stable ordering.
- Causal swing detection preserving strict pivot_timestamp vs confirmed_at / effective_from semantics.
- Volatility-normalized reversal magnitude (SwingReversalMagnitude = ReversalDisplacement / V_local).
- Causal HH/HL/LH/LL structural classification.
- Deterministic Break of Structure (BOS) and Change of Character (CHoCH).
- Failed break detection, reclaim/rearm state machine, and structural damage/invalidation.
- Primary structural stop candidate generation strictly without trading authority.
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


@unique
class SwingType(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


@unique
class StructuralClassification(str, Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    HH = "HH"  # Higher High
    HL = "HL"  # Higher Low
    LH = "LH"  # Lower High
    LL = "LL"  # Lower Low


@dataclass(frozen=True)
class SwingPoint:
    """Causal, deterministic representation of a structural swing extreme."""

    swing_id: str
    symbol: str
    timeframe: str
    swing_type: SwingType
    price: Decimal
    pivot_timestamp: int  # Market observation timestamp when the structural extreme occurred
    confirmed_at: int  # Information availability timestamp when confirmation occurred
    v_local: Decimal
    classification: StructuralClassification = StructuralClassification.UNCLASSIFIED

    @property
    def effective_from(self) -> int:
        """Timestamp at which this confirmed swing point becomes available to downstream consumers."""
        return self.confirmed_at

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at >= self.pivot_timestamp


@dataclass(frozen=True)
class StructuralLevel:
    """Protected or internal structural level anchor."""

    level_id: str
    symbol: str
    timeframe: str
    level_type: SwingType
    price: Decimal
    created_at_ts: int
    confirmed_at_ts: int
    is_protected: bool = True
    is_broken: bool = False


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
    """Informational event representing a structural posture transition (CHoCH)."""

    symbol: str
    timeframe: str
    prior_direction: str  # LONG, SHORT, or NEUTRAL
    new_direction: str  # LONG or SHORT
    trigger_price: Decimal
    protected_level_price: Decimal
    confirmed_at: int


@dataclass(frozen=True)
class FailedBreak:
    """Informational record of a failed structural break attempt."""

    symbol: str
    timeframe: str
    level_price: Decimal
    level_type: str  # HIGH or LOW
    breach_price: Decimal
    attempt_timestamp: int
    failed_at: int


@dataclass(frozen=True)
class ReclaimEvent:
    """Informational record of a structural level reclaim following a failed break."""

    symbol: str
    timeframe: str
    level_price: Decimal
    level_type: str  # HIGH or LOW
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


class BoundedSwingRecordSet:
    """Deterministic, bounded collection of confirmed swing points with FIFO eviction and stable ordering."""

    def __init__(self, capacity: int = 50) -> None:
        if capacity <= 0:
            raise ValueError("BoundedSwingRecordSet capacity must be a positive integer.")
        self.capacity = capacity
        self._records: list[SwingPoint] = []

    def add(self, swing: SwingPoint) -> None:
        """Adds a swing point deterministically; evicts oldest if capacity is reached."""
        # Idempotency check: ignore exact duplicate swing IDs
        if any(s.swing_id == swing.swing_id for s in self._records):
            return

        self._records.append(swing)
        # Sort stably by confirmed_at, then pivot_timestamp, then swing_id
        self._records.sort(key=lambda s: (s.confirmed_at, s.pivot_timestamp, s.swing_id))

        if len(self._records) > self.capacity:
            self._records.pop(0)  # Evict oldest confirmed swing

    def get_last_swing(self, swing_type: Optional[SwingType] = None) -> Optional[SwingPoint]:
        """Returns the most recently confirmed swing point matching the given type."""
        for s in reversed(self._records):
            if swing_type is None or s.swing_type == swing_type:
                return s
        return None

    def get_records(self) -> list[SwingPoint]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)


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
    last_choch: Optional[ChangeOfCharacter] = None
    last_failed_break: Optional[FailedBreak] = None
    last_reclaim: Optional[ReclaimEvent] = None
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
    """Adaptive Volatility-Normalized Structure Engine (v2).

    Produces causal swings, protected levels, HH/HL/LH/LL, BOS, CHoCH, failed breaks,
    reclaims, and structural stops in a strictly informational capacity.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1M",
        min_reversal_magnitude: Decimal = Decimal("1.5"),
        displacement_threshold_mult: Decimal = Decimal("0.5"),
        persistence_bars_required: int = 2,
        min_v_local_floor: Decimal = Decimal("0.0001"),
        swing_capacity: int = 50,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.min_reversal_magnitude = min_reversal_magnitude
        self.displacement_threshold_mult = displacement_threshold_mult
        self.persistence_bars_required = persistence_bars_required
        self.min_v_local_floor = min_v_local_floor

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
        self.last_extreme_high_ts: int = 0
        self.last_extreme_low: Optional[Decimal] = None
        self.last_extreme_low_ts: int = 0

        # Track break candidate level details
        self.last_break_candidate_level_type: str = "NONE"
        self.last_break_candidate_level_price: Optional[Decimal] = None

        # Isolated directional persistence counters
        self.high_persistence_counter = 0
        self.low_persistence_counter = 0

        self.swing_records = BoundedSwingRecordSet(capacity=swing_capacity)
        self.current_direction: str = "NEUTRAL"

        self.last_choch: Optional[ChangeOfCharacter] = None
        self.last_failed_break: Optional[FailedBreak] = None
        self.last_reclaim: Optional[ReclaimEvent] = None

        self._last_parent_version: Optional[int] = None
        self._last_data_version: Optional[int] = None
        self._last_config_version: Optional[int] = None

    def calculate_v_local(self, current_bar: Bar, atr_14: Optional[Decimal] = None) -> Decimal:
        """Executably defines V_local as local volatility reference bounded by min_v_local_floor."""
        if atr_14 is not None:
            if atr_14 < Decimal("0.0"):
                raise ValueError(f"ATR-14 cannot be negative, got {atr_14}")
            if atr_14 > Decimal("0.0"):
                return max(atr_14, self.min_v_local_floor)

        bar_range = current_bar.high - current_bar.low
        if bar_range < Decimal("0.0"):
            raise ValueError(f"Bar range cannot be negative, got {bar_range}")

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

        if v_local < Decimal("0.0"):
            raise ValueError(f"V_local volatility reference cannot be negative, got {v_local}")

        effective_v_local = max(v_local, self.min_v_local_floor)

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

        # Update candidate extreme high and low
        if self.last_extreme_high is None or bar.high > self.last_extreme_high:
            self.last_extreme_high = bar.high
            self.last_extreme_high_ts = bar.close_timestamp
        if self.last_extreme_low is None or bar.low < self.last_extreme_low:
            self.last_extreme_low = bar.low
            self.last_extreme_low_ts = bar.close_timestamp

        # 1. Adaptive Swing Reversal Magnitude Evaluation
        high_displacement = self.last_extreme_high - bar.close
        low_displacement = bar.close - self.last_extreme_low

        high_magnitude = high_displacement / effective_v_local if effective_v_local > Decimal("0.0") else Decimal("0.0")
        low_magnitude = low_displacement / effective_v_local if effective_v_local > Decimal("0.0") else Decimal("0.0")

        # Causal Swing Confirmation & Classification
        has_reversal = (high_magnitude >= self.min_reversal_magnitude) or (low_magnitude >= self.min_reversal_magnitude)

        old_swing = self.swing_state
        if has_reversal:
            if high_magnitude >= self.min_reversal_magnitude and self.protected_high != self.last_extreme_high:
                self.protected_high = self.last_extreme_high
                prev_high = self.swing_records.get_last_swing(SwingType.HIGH)
                classification = (
                    StructuralClassification.HH
                    if prev_high and self.last_extreme_high > prev_high.price
                    else StructuralClassification.LH
                    if prev_high and self.last_extreme_high < prev_high.price
                    else StructuralClassification.UNCLASSIFIED
                )

                swing_pt = SwingPoint(
                    swing_id=f"swing_high_{self.symbol}_{self.last_extreme_high_ts}",
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    swing_type=SwingType.HIGH,
                    price=self.last_extreme_high,
                    pivot_timestamp=self.last_extreme_high_ts,
                    confirmed_at=bar.close_timestamp,
                    v_local=effective_v_local,
                    classification=classification,
                )
                self.swing_records.add(swing_pt)
                # Reset candidate low extreme to track next pullback low
                self.last_extreme_low = bar.low
                self.last_extreme_low_ts = bar.close_timestamp

            if low_magnitude >= self.min_reversal_magnitude and self.protected_low != self.last_extreme_low:
                self.protected_low = self.last_extreme_low
                prev_low = self.swing_records.get_last_swing(SwingType.LOW)
                classification = (
                    StructuralClassification.HL
                    if prev_low and self.last_extreme_low > prev_low.price
                    else StructuralClassification.LL
                    if prev_low and self.last_extreme_low < prev_low.price
                    else StructuralClassification.UNCLASSIFIED
                )

                swing_pt = SwingPoint(
                    swing_id=f"swing_low_{self.symbol}_{self.last_extreme_low_ts}",
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    swing_type=SwingType.LOW,
                    price=self.last_extreme_low,
                    pivot_timestamp=self.last_extreme_low_ts,
                    confirmed_at=bar.close_timestamp,
                    v_local=effective_v_local,
                    classification=classification,
                )
                self.swing_records.add(swing_pt)
                # Reset candidate high extreme to track next rally high
                self.last_extreme_high = bar.high
                self.last_extreme_high_ts = bar.close_timestamp

            if self.swing_state == SwingState.SWING_NONE:
                self.swing_state = SwingState.SWING_CANDIDATE
            elif self.swing_state == SwingState.SWING_CANDIDATE:
                self.swing_state = SwingState.SWING_CONFIRMED
            elif self.swing_state == SwingState.SWING_CONFIRMED:
                self.swing_state = SwingState.SWING_PROTECTED

        if self.swing_state != old_swing:
            self.previous_swing_state = old_swing

        # 2. Structural Break & CHoCH Evaluation with Isolated Directional Persistence
        level_cross = False
        disp_confirmed = False
        persist_confirmed = False
        active_level_type = "NONE"
        active_level_price = bar.close

        if self.protected_high is not None and bar.close > self.protected_high:
            level_cross = True
            active_level_type = "HIGH"
            active_level_price = self.protected_high
            self.low_persistence_counter = 0  # Reset low persistence when high break is active
            disp = bar.close - self.protected_high
            if disp >= (self.displacement_threshold_mult * effective_v_local):
                disp_confirmed = True
                self.high_persistence_counter += 1
                if self.high_persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.high_persistence_counter = 0

        elif self.protected_low is not None and bar.close < self.protected_low:
            level_cross = True
            active_level_type = "LOW"
            active_level_price = self.protected_low
            self.high_persistence_counter = 0  # Reset high persistence when low break is active
            disp = self.protected_low - bar.close
            if disp >= (self.displacement_threshold_mult * effective_v_local):
                disp_confirmed = True
                self.low_persistence_counter += 1
                if self.low_persistence_counter >= self.persistence_bars_required:
                    persist_confirmed = True
            else:
                self.low_persistence_counter = 0
        else:
            self.high_persistence_counter = 0
            self.low_persistence_counter = 0

        if level_cross:
            self.last_break_candidate_level_type = active_level_type
            self.last_break_candidate_level_price = active_level_price

        active_persistence_count = (
            self.high_persistence_counter if active_level_type == "HIGH" else self.low_persistence_counter
        )

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

            # Change of Character (CHoCH) detection
            new_dir = "LONG" if active_level_type == "HIGH" else "SHORT"
            if self.current_direction != new_dir:
                self.last_choch = ChangeOfCharacter(
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    prior_direction=self.current_direction,
                    new_direction=new_dir,
                    trigger_price=bar.close,
                    protected_level_price=struct_break.level_price,
                    confirmed_at=bar.close_timestamp,
                )
                self.current_direction = new_dir

        elif level_cross and not disp_confirmed:
            self.break_state = BreakState.BREAK_CANDIDATE
        elif old_break == BreakState.BREAK_CANDIDATE and not level_cross:
            self.break_state = BreakState.FAILED_BREAK
            # Record FailedBreak attempt with explicit candidate level identity
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

        if self.break_state != old_break:
            self.previous_break_state = old_break

        # 3. Structural Damage & Reclaim State Machine
        old_damage = self.damage_state
        if struct_break.is_confirmed_break:
            self.damage_state = StructuralDamageState.STRUCTURE_BROKEN
            self.swing_state = SwingState.SWING_BROKEN
            reasons.append(ReasonCode.STRUCTURE_INVALIDATED)
        elif level_cross:
            self.damage_state = StructuralDamageState.DAMAGE_CANDIDATE
        elif old_damage == StructuralDamageState.DAMAGE_CANDIDATE and not level_cross:
            self.damage_state = StructuralDamageState.RECLAIM_CANDIDATE
        elif old_damage == StructuralDamageState.RECLAIM_CANDIDATE and not level_cross:
            self.damage_state = StructuralDamageState.RECLAIM_CONFIRMED
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
            v_local=effective_v_local,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state_version=self.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
            last_choch=self.last_choch,
            last_failed_break=self.last_failed_break,
            last_reclaim=self.last_reclaim,
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

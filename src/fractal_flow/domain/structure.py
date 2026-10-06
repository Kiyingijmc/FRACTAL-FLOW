"""Adaptive Volatility-Normalized Structure Engine v2.2 for FRACTAL FLOW.

Implements adaptive swings (SwingReversalMagnitude = ReversalDisplacement / V_local),
causal structural-excursion detection (candidate_at, confirmed_at, effective_from),
explicit excursion ownership, immutable excursion origin, and bounded expiry,
formal HH/HL/LH/LL/EQUAL classifications against previous confirmed swing of same direction,
instrument-aware equality tolerance, canonical structural trend ownership,
exact BOS vs CHoCH break truth table, reclaim/rearm state machine, isolated persistence counters,
versioned configuration schema, bounded swing record history with deterministic eviction,
and primary structural stop candidate generation strictly without trading authority.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Any, Optional

from src.fractal_flow.config.config import StructureConfig
from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.reason_codes import ReasonCode
from src.fractal_flow.persistence.adapter import domain_to_primitive, primitive_to_decimal


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
    """Causal structural excursion, not a confirmed pivot.

    ``created_from_timestamp`` is the immutable excursion origin. ``candidate_at``
    and ``price`` are the latest causally observed extreme *within that same
    excursion*. Extending an excursion therefore never resets its age or origin.
    A confirmed SwingRecord is created only after a later reversal satisfies the
    explicit normalized confirmation rule.
    """

    side: str  # HIGH or LOW
    price: Decimal  # latest excursion extreme
    candidate_at: int  # timestamp of latest excursion extreme
    created_from_timestamp: int  # immutable excursion origin
    status: SwingState
    v_local_at_candidate: Decimal
    version: int
    candidate_age_bars: int = 0


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
    """Adaptive, Volatility-Normalized Structure Engine v2.2."""

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
        pivot_neighborhood_bars: Optional[int] = None,
        max_candidate_lifetime_bars: Optional[int] = None,
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
        # Retained only for snapshot/config backward compatibility. Structure v2.1
        # no longer uses a trailing neighborhood to create or supersede candidates.
        self.pivot_neighborhood_bars = (
            pivot_neighborhood_bars if pivot_neighborhood_bars is not None else self.config.pivot_neighborhood_bars
        )
        self.max_candidate_lifetime_bars = (
            max_candidate_lifetime_bars
            if max_candidate_lifetime_bars is not None
            else self.config.max_candidate_lifetime_bars
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
        self._recent_bars: list[Bar] = []

        self.high_persistence_counter = 0
        self.low_persistence_counter = 0
        # Diagnostic/event context only. This is NOT structural authority and is
        # never consumed by downstream Phase 2 engines. Canonical structural
        # direction is exposed exclusively through ``structural_ownership``.
        self.current_direction: str = "UNKNOWN"
        # Direction of the unresolved structural excursion. This is intentionally
        # distinct from confirmed structural ownership.
        self._active_excursion_side: Optional[str] = None

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
        self.enforce_swing_alternation = False

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
        """Canonical structural-direction authority.

        ``current_direction`` is deliberately excluded from this calculation;
        it is retained only as historical/event context for BOS/CHOCH records.
        Downstream engines must consume this property rather than the diagnostic
        direction field.
        """
        high_swings = [s for s in self.swings if s.swing_type == "HIGH" and s.status != SwingState.SWING_BROKEN]
        low_swings = [s for s in self.swings if s.swing_type == "LOW" and s.status != SwingState.SWING_BROKEN]

        if not high_swings or not low_swings:
            return "UNKNOWN"

        latest_high = high_swings[-1]
        latest_low = low_swings[-1]

        h_class = latest_high.classification
        l_class = latest_low.classification

        # NEUTRAL classifications (first swing in direction) represent incomplete relative evidence -> AMBIGUOUS
        if h_class == "NEUTRAL" or l_class == "NEUTRAL":
            return "AMBIGUOUS"

        # Double equal plateau is consolidation -> AMBIGUOUS
        if h_class == "EQUAL_HIGH" and l_class == "EQUAL_LOW":
            return "AMBIGUOUS"

        is_bullish_high = h_class in ("HH", "EQUAL_HIGH")
        is_bullish_low = l_class in ("HL", "EQUAL_LOW")

        is_bearish_low = l_class in ("LL", "EQUAL_LOW")
        is_bearish_high = h_class in ("LH", "EQUAL_HIGH")

        if is_bullish_high and is_bullish_low:
            return "BULLISH"
        elif is_bearish_high and is_bearish_low:
            return "BEARISH"

        return "AMBIGUOUS"

    def _mark_active_swings_broken(self, swing_type: str) -> None:
        """Invalidate all active swings on the broken structural side.

        Older same-side swings must not become the new protected level after the
        latest protected swing is broken; doing so would resurrect stale authority.
        Historical records remain present for audit/replay but are excluded from
        active ownership and protected-level derivation.
        """
        for idx, swing in enumerate(self.swings):
            if swing.swing_type == swing_type and swing.status != SwingState.SWING_BROKEN:
                self.swings[idx] = SwingRecord(
                    swing_id=swing.swing_id,
                    symbol=swing.symbol,
                    timeframe=swing.timeframe,
                    candidate_at=swing.candidate_at,
                    confirmed_at=swing.confirmed_at,
                    effective_from=swing.effective_from,
                    price=swing.price,
                    swing_type=swing.swing_type,
                    classification=swing.classification,
                    status=SwingState.SWING_BROKEN,
                    version=swing.version,
                    v_local=swing.v_local,
                    reversal_magnitude=swing.reversal_magnitude,
                    root_id=swing.root_id,
                    parent_id=swing.parent_id,
                    parent_version=swing.parent_version,
                )

    def _rearm_protected_levels(self) -> None:
        """Re-arms protected high and low levels strictly from active confirmed swings, explicitly clearing stale levels when source disappears."""
        high_swings = [s for s in self.swings if s.swing_type == "HIGH" and s.status != SwingState.SWING_BROKEN]
        low_swings = [s for s in self.swings if s.swing_type == "LOW" and s.status != SwingState.SWING_BROKEN]
        self.protected_high = high_swings[-1].price if high_swings else None
        self.protected_low = low_swings[-1].price if low_swings else None

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

        # Bounded recent bar history retained for causal context and deterministic recovery
        preceding_bars = list(self._recent_bars)
        self._recent_bars.append(bar)
        if len(self._recent_bars) > 20:
            self._recent_bars.pop(0)

        self._last_bar = bar
        self._last_parent_id = parent_id
        self._last_parent_version = parent_version
        self._last_data_version = data_version
        self._last_config_version = config_version
        self._last_timestamp = bar.close_timestamp

        reasons: list[ReasonCode] = []
        bos_type = "NONE"
        reclaim_type = "NONE"

        # Transition SWING_CONFIRMED to SWING_PROTECTED on subsequent bar if protected levels active
        if self.swing_state == SwingState.SWING_CONFIRMED and (
            self.protected_high is not None or self.protected_low is not None
        ):
            self.swing_state = SwingState.SWING_PROTECTED

        # 1. Causal structural-excursion lifecycle.
        #
        # A candidate is a hypothesis about one unresolved directional excursion.
        # A new extreme may extend that excursion, but it does NOT create a new
        # pivot epoch and does not reset its age/origin. This removes the former
        # former trailing-neighborhood/running-extreme ambiguity.
        #
        # Extension requires directional close evidence relative to the previous
        # observation. A wick that makes a new extreme while closing against the
        # excursion is treated as reversal evidence, not as a fresh candidate.
        previous_bar = preceding_bars[-1] if preceding_bars else None
        close_up = previous_bar is None or bar.close >= previous_bar.close
        close_down = previous_bar is None or bar.close <= previous_bar.close

        def advance_high(candidate: Optional[PivotCandidate]) -> Optional[PivotCandidate]:
            if candidate is None:
                return PivotCandidate(
                    side="HIGH", price=bar.high, candidate_at=bar.close_timestamp,
                    created_from_timestamp=bar.close_timestamp,
                    status=SwingState.SWING_CANDIDATE, v_local_at_candidate=effective_v_local,
                    version=self.state_version + 1, candidate_age_bars=0,
                )
            age = candidate.candidate_age_bars + 1
            if age > self.max_candidate_lifetime_bars:
                self._active_excursion_side = None
                return None
            if bar.high > candidate.price and close_up:
                return PivotCandidate(
                    side="HIGH", price=bar.high, candidate_at=bar.close_timestamp,
                    created_from_timestamp=candidate.created_from_timestamp,
                    status=candidate.status, v_local_at_candidate=effective_v_local,
                    version=candidate.version, candidate_age_bars=age,
                )
            return PivotCandidate(
                side="HIGH", price=candidate.price, candidate_at=candidate.candidate_at,
                created_from_timestamp=candidate.created_from_timestamp,
                status=candidate.status, v_local_at_candidate=candidate.v_local_at_candidate,
                version=candidate.version, candidate_age_bars=age,
            )

        def advance_low(candidate: Optional[PivotCandidate]) -> Optional[PivotCandidate]:
            if candidate is None:
                return PivotCandidate(
                    side="LOW", price=bar.low, candidate_at=bar.close_timestamp,
                    created_from_timestamp=bar.close_timestamp,
                    status=SwingState.SWING_CANDIDATE, v_local_at_candidate=effective_v_local,
                    version=self.state_version + 1, candidate_age_bars=0,
                )
            age = candidate.candidate_age_bars + 1
            if age > self.max_candidate_lifetime_bars:
                self._active_excursion_side = None
                return None
            if bar.low < candidate.price and close_down:
                return PivotCandidate(
                    side="LOW", price=bar.low, candidate_at=bar.close_timestamp,
                    created_from_timestamp=candidate.created_from_timestamp,
                    status=candidate.status, v_local_at_candidate=effective_v_local,
                    version=candidate.version, candidate_age_bars=age,
                )
            return PivotCandidate(
                side="LOW", price=candidate.price, candidate_at=candidate.candidate_at,
                created_from_timestamp=candidate.created_from_timestamp,
                status=candidate.status, v_local_at_candidate=candidate.v_local_at_candidate,
                version=candidate.version, candidate_age_bars=age,
            )

        # Bootstrap one observation without directional commitment. On the next
        # observation the close-to-close direction selects the unresolved
        # excursion side. Thereafter only that side can extend until confirmation.
        # This is the key distinction from a trailing running extreme: the engine
        # tracks one bounded structural excursion, not an independent max/min over
        # the entire recent history.
        if self._active_excursion_side is None:
            # First observation: retain both provisional extremes, but establish
            # an excursion owner from close-location. The close nearer the high
            # implies an upward excursion hypothesis; nearer the low implies a
            # downward excursion hypothesis. An exact midpoint remains ambiguous
            # until the next observation supplies causal evidence.
            if previous_bar is None and self._high_candidate is None and self._low_candidate is None:
                pass
            elif previous_bar is not None and self._high_candidate is None and self._low_candidate is None:
                if bar.close > bar.open:
                    self._active_excursion_side = "HIGH"
                elif bar.close < bar.open:
                    self._active_excursion_side = "LOW"
            elif self._high_candidate is not None and self._low_candidate is not None:
                high_probe = self._high_candidate.price - bar.close
                low_probe = bar.close - self._low_candidate.price
                if high_probe > low_probe and high_probe > Decimal("0"):
                    self._active_excursion_side = "HIGH"
                elif low_probe > high_probe and low_probe > Decimal("0"):
                    self._active_excursion_side = "LOW"
            elif self._high_candidate is not None and bar.close < self._high_candidate.price:
                self._active_excursion_side = "HIGH"
            elif self._low_candidate is not None and bar.close > self._low_candidate.price:
                self._active_excursion_side = "LOW"

        if self._active_excursion_side == "HIGH":
            self._high_candidate = advance_high(self._high_candidate)
            self._low_candidate = None
        elif self._active_excursion_side == "LOW":
            self._low_candidate = advance_low(self._low_candidate)
            self._high_candidate = None
        else:
            self._high_candidate = advance_high(self._high_candidate)
            self._low_candidate = advance_low(self._low_candidate)
            if previous_bar is None and self._active_excursion_side is None:
                if self._high_candidate is not None and self._low_candidate is not None:
                    high_distance = abs(bar.close - self._high_candidate.price)
                    low_distance = abs(bar.close - self._low_candidate.price)
                    if high_distance < low_distance:
                        self._active_excursion_side = "HIGH"
                    elif low_distance < high_distance:
                        self._active_excursion_side = "LOW"

        # Update swing_state to SWING_CANDIDATE if candidate is active and state is SWING_NONE or SWING_BROKEN
        if self.swing_state in (SwingState.SWING_NONE, SwingState.SWING_BROKEN):
            if self._high_candidate is not None or self._low_candidate is not None:
                self.swing_state = SwingState.SWING_CANDIDATE

        # 2. Causal Reversal Magnitude Evaluation from Fixed Candidate Pivots
        high_magnitude = Decimal("0.0")
        if self._high_candidate is not None:
            high_disp = self._high_candidate.price - bar.close
            high_magnitude = high_disp / effective_v_local if high_disp > Decimal("0.0") else Decimal("0.0")

        low_magnitude = Decimal("0.0")
        if self._low_candidate is not None:
            low_disp = bar.close - self._low_candidate.price
            low_magnitude = low_disp / effective_v_local if low_disp > Decimal("0.0") else Decimal("0.0")

        old_swing = self.swing_state
        # Independent candidate lifecycles may coexist, but a single bar must not
        # confirm both sides: doing so creates two structural events at one causal
        # timestamp with no deterministic ordering. If both qualify, select the
        # stronger normalized reversal; an exact tie remains unconfirmed.
        eligible_high = (
            self._high_candidate is not None
            and self._high_candidate.candidate_age_bars > 0
            and high_magnitude >= self.min_reversal_magnitude
        )
        eligible_low = (
            self._low_candidate is not None
            and self._low_candidate.candidate_age_bars > 0
            and low_magnitude >= self.min_reversal_magnitude
        )

        confirm_side: Optional[str] = None
        if eligible_high and not eligible_low:
            confirm_side = "HIGH"
        elif eligible_low and not eligible_high:
            confirm_side = "LOW"
        elif eligible_high and eligible_low:
            if high_magnitude > low_magnitude:
                confirm_side = "HIGH"
            elif low_magnitude > high_magnitude:
                confirm_side = "LOW"

        if confirm_side == "HIGH" and self._high_candidate is not None:
            candidate_price = self._high_candidate.price
            last_active = next((s for s in reversed(self.swings) if s.status != SwingState.SWING_BROKEN), None)
            if self.enforce_swing_alternation and last_active is not None and last_active.swing_type == "HIGH":
                self.protected_high = max(self.protected_high or candidate_price, candidate_price)
                self._high_candidate = None
                self._low_candidate = None
                self._active_excursion_side = None
                self.swing_state = SwingState.SWING_PROTECTED
            else:
                self.protected_high = candidate_price
                self._register_swing(
                    swing_type="HIGH",
                    price=candidate_price,
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
                self._low_candidate = None
                self._active_excursion_side = None
                self.swing_state = SwingState.SWING_CONFIRMED
        elif confirm_side == "LOW" and self._low_candidate is not None:
            candidate_price = self._low_candidate.price
            last_active = next((s for s in reversed(self.swings) if s.status != SwingState.SWING_BROKEN), None)
            if self.enforce_swing_alternation and last_active is not None and last_active.swing_type == "LOW":
                self.protected_low = min(self.protected_low or candidate_price, candidate_price)
                self._low_candidate = None
                self._high_candidate = None
                self._active_excursion_side = None
                self.swing_state = SwingState.SWING_PROTECTED
            else:
                self.protected_low = candidate_price
                self._register_swing(
                    swing_type="LOW",
                    price=candidate_price,
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
                self._high_candidate = None
                self._active_excursion_side = None
                self.swing_state = SwingState.SWING_CONFIRMED
        elif self.swing_state == SwingState.SWING_CONFIRMED and (
            self.protected_high is not None or self.protected_low is not None
        ):
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
            self.last_break_candidate_level_type = active_level_type
            self.last_break_candidate_level_price = active_level_price
            if self.break_state in (BreakState.BREAK_NONE, BreakState.BREAK_CANDIDATE, BreakState.FAILED_BREAK):
                self.break_state = BreakState.BREAK_CONFIRMED
            elif self.break_state == BreakState.BREAK_CONFIRMED:
                self.break_state = BreakState.BREAK_ESTABLISHED

            ownership = self.structural_ownership
            # Exact Canonical 8-Row Truth Table Evaluation
            if ownership == "BULLISH":
                if active_level_type == "HIGH":
                    bos_type = "BOS_BULLISH"
                    self.current_direction = "LONG"
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
                    self.current_direction = "SHORT"
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
                # AMBIGUOUS or UNKNOWN -> NONE
                bos_type = "NONE"

        elif level_cross and disp_confirmed:
            # Displacement without persistence is still a live break attempt;
            # preserving it as BREAK_CANDIDATE makes a subsequent fallback a
            # genuine FAILED_BREAK instead of an orphan reclaim.
            self.last_break_candidate_level_type = active_level_type
            self.last_break_candidate_level_price = active_level_price
            self.break_state = BreakState.BREAK_CANDIDATE
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
                broken_side = "HIGH" if bos_type == "CHOCH_BULLISH" else "LOW"
                self._mark_active_swings_broken(broken_side)
                self._rearm_protected_levels()
                if broken_side == "HIGH":
                    self.high_persistence_counter = 0
                else:
                    self.low_persistence_counter = 0
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
            diff = abs(price - last_last_same_price if (last_last_same_price := last_same.price) else Decimal("0"))
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

    def authoritative_state(self) -> dict[str, Any]:
        """Return the complete bounded decision state used for future behavior.

        This is deliberately broader than the public transition record. It is the
        canonical forensic state surface for causal-prefix and recovery equivalence.
        """
        return {
            "symbol": self.symbol, "timeframe": self.timeframe,
            "config": self.config,
            "min_reversal_magnitude": self.min_reversal_magnitude,
            "displacement_threshold_mult": self.displacement_threshold_mult,
            "persistence_bars_required": self.persistence_bars_required,
            "max_swing_history": self.max_swing_history,
            "min_v_local_floor": self.min_v_local_floor,
            "equality_tolerance_pips": self.equality_tolerance_pips,
            "atr_stop_buffer_mult": self.atr_stop_buffer_mult,
            "pivot_neighborhood_bars": self.pivot_neighborhood_bars,
            "max_candidate_lifetime_bars": self.max_candidate_lifetime_bars,
            "swing_state": self.swing_state, "previous_swing_state": self.previous_swing_state,
            "break_state": self.break_state, "previous_break_state": self.previous_break_state,
            "damage_state": self.damage_state, "previous_damage_state": self.previous_damage_state,
            "state_version": self.state_version,
            "protected_high": self.protected_high, "protected_low": self.protected_low,
            "high_candidate": self._high_candidate, "low_candidate": self._low_candidate,
            "recent_bars": list(self._recent_bars),
            "high_persistence_counter": self.high_persistence_counter,
            "low_persistence_counter": self.low_persistence_counter,
            "current_direction": self.current_direction,
            "active_excursion_side": self._active_excursion_side,
            "swings": list(self.swings),
            "last_choch": self.last_choch, "last_failed_break": self.last_failed_break,
            "last_reclaim": self.last_reclaim,
            "last_break_candidate_level_type": self.last_break_candidate_level_type,
            "last_break_candidate_level_price": self.last_break_candidate_level_price,
            "last_bar": self._last_bar, "last_parent_id": self._last_parent_id,
            "last_parent_version": self._last_parent_version, "last_data_version": self._last_data_version,
            "last_config_version": self._last_config_version, "last_timestamp": self._last_timestamp,
            "last_transition_record": self._last_transition_record,
        }

    def snapshot_state(self) -> dict[str, Any]:
        """Lossless JSON-safe snapshot of the complete bounded decision state."""
        payload = {"schema_version": "structure-engine-v2.2", **self.authoritative_state()}
        return domain_to_primitive(payload)

    @staticmethod
    def _restore_swing(payload: dict[str, Any]) -> SwingRecord:
        return SwingRecord(**payload)

    @staticmethod
    def _restore_candidate(payload: Optional[dict[str, Any]]) -> Optional[PivotCandidate]:
        return PivotCandidate(**payload) if payload is not None else None

    @staticmethod
    def _restore_choch(payload: Optional[dict[str, Any]]) -> Optional[ChangeOfCharacter]:
        return ChangeOfCharacter(**payload) if payload is not None else None

    @staticmethod
    def _restore_failed_break(payload: Optional[dict[str, Any]]) -> Optional[FailedBreak]:
        return FailedBreak(**payload) if payload is not None else None

    @staticmethod
    def _restore_reclaim(payload: Optional[dict[str, Any]]) -> Optional[ReclaimEvent]:
        return ReclaimEvent(**payload) if payload is not None else None

    @classmethod
    def from_snapshot_state(cls, payload: dict[str, Any]) -> "StructureEngine":
        """Construct a fresh StructureEngine from a validated snapshot payload."""
        decoded = primitive_to_decimal(payload)
        if decoded.get("schema_version") not in {"structure-engine-v2.1", "structure-engine-v2.2"}:
            raise ValueError(f"Unsupported StructureEngine snapshot schema: {decoded.get('schema_version')!r}")

        config = StructureConfig(**decoded["config"])
        engine = cls(
            symbol=decoded["symbol"],
            timeframe=decoded["timeframe"],
            config=config,
            min_reversal_magnitude=decoded["min_reversal_magnitude"],
            displacement_threshold_mult=decoded["displacement_threshold_mult"],
            persistence_bars_required=decoded["persistence_bars_required"],
            max_swing_history=decoded["max_swing_history"],
            min_v_local_floor=decoded["min_v_local_floor"],
            equality_tolerance_pips=decoded["equality_tolerance_pips"],
            atr_stop_buffer_mult=decoded["atr_stop_buffer_mult"],
            pivot_neighborhood_bars=decoded["pivot_neighborhood_bars"],
            max_candidate_lifetime_bars=decoded["max_candidate_lifetime_bars"],
        )

        engine.swing_state = SwingState(decoded["swing_state"])
        engine.previous_swing_state = SwingState(decoded["previous_swing_state"])
        engine.break_state = BreakState(decoded["break_state"])
        engine.previous_break_state = BreakState(decoded["previous_break_state"])
        engine.damage_state = StructuralDamageState(decoded["damage_state"])
        engine.previous_damage_state = StructuralDamageState(decoded["previous_damage_state"])
        engine.state_version = decoded["state_version"]
        engine.protected_high = decoded["protected_high"]
        engine.protected_low = decoded["protected_low"]
        engine._high_candidate = cls._restore_candidate(decoded["high_candidate"])
        engine._low_candidate = cls._restore_candidate(decoded["low_candidate"])
        engine._recent_bars = [Bar.from_dict(item) for item in decoded["recent_bars"]]
        engine.high_persistence_counter = decoded["high_persistence_counter"]
        engine.low_persistence_counter = decoded["low_persistence_counter"]
        engine.current_direction = decoded["current_direction"]
        engine._active_excursion_side = decoded.get("active_excursion_side")
        engine.swings = [cls._restore_swing(item) for item in decoded["swings"]]
        engine.last_choch = cls._restore_choch(decoded["last_choch"])
        engine.last_failed_break = cls._restore_failed_break(decoded["last_failed_break"])
        engine.last_reclaim = cls._restore_reclaim(decoded["last_reclaim"])
        engine.last_break_candidate_level_type = decoded["last_break_candidate_level_type"]
        engine.last_break_candidate_level_price = decoded["last_break_candidate_level_price"]
        engine._last_bar = Bar.from_dict(decoded["last_bar"]) if decoded["last_bar"] is not None else None
        engine._last_parent_id = decoded["last_parent_id"]
        engine._last_parent_version = decoded["last_parent_version"]
        engine._last_data_version = decoded["last_data_version"]
        engine._last_config_version = decoded["last_config_version"]
        engine._last_timestamp = decoded["last_timestamp"]

        rec = decoded["last_transition_record"]
        if rec is None:
            engine._last_transition_record = None
        else:
            engine._last_transition_record = StructureTransitionRecord(
                symbol=rec["symbol"],
                timeframe=rec["timeframe"],
                swing_state=SwingState(rec["swing_state"]),
                previous_swing_state=SwingState(rec["previous_swing_state"]),
                break_state=BreakState(rec["break_state"]),
                previous_break_state=BreakState(rec["previous_break_state"]),
                damage_state=StructuralDamageState(rec["damage_state"]),
                previous_damage_state=StructuralDamageState(rec["previous_damage_state"]),
                timestamp=rec["timestamp"],
                v_local=rec["v_local"],
                root_id=rec["root_id"],
                parent_id=rec["parent_id"],
                parent_version=rec["parent_version"],
                state_version=rec["state_version"],
                config_version=rec["config_version"],
                data_version=rec["data_version"],
                feature_version=rec["feature_version"],
                active_swings=[cls._restore_swing(item) for item in rec["active_swings"]],
                bos_type=rec["bos_type"],
                reclaim_type=rec["reclaim_type"],
                protected_high=rec["protected_high"],
                protected_low=rec["protected_low"],
                last_choch=cls._restore_choch(rec["last_choch"]),
                last_failed_break=cls._restore_failed_break(rec["last_failed_break"]),
                last_reclaim=cls._restore_reclaim(rec["last_reclaim"]),
                structural_ownership=rec["structural_ownership"],
                reason_codes=[ReasonCode(value) for value in rec["reason_codes"]],
                authority=rec["authority"],
            )
        return engine

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

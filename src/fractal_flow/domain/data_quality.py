"""Data Quality State Machine and Anomaly Evaluator for FRACTAL FLOW.

Enforces strict data quality state transitions, comprehensive anomaly detection,
reason code assignment, StateEnvelope integration, and the non-negotiable rule:
DATA != VALID -> NEW EXPOSURE FORBIDDEN.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Any, Optional

from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.reason_codes import ReasonCode


@unique
class DataQualityState(str, Enum):
    DATA_BOOT = "DATA_BOOT"
    DATA_VALIDATING = "DATA_VALIDATING"
    DATA_NORMAL = "DATA_NORMAL"
    DATA_DEGRADED = "DATA_DEGRADED"
    DATA_STALE = "DATA_STALE"
    DATA_CORRUPTED = "DATA_CORRUPTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    DATA_VALID = "DATA_VALID"

    def is_valid_for_exposure(self) -> bool:
        """Enforces: DATA != VALID -> NEW EXPOSURE FORBIDDEN."""
        return self in (DataQualityState.DATA_NORMAL, DataQualityState.DATA_VALID)


@dataclass
class DataQualityAssessment:
    symbol: str
    state: DataQualityState
    previous_state: DataQualityState
    reason_codes: list[ReasonCode]
    exposure_allowed: bool
    last_timestamp: int
    last_sequence: int
    version: int = 1
    details: dict[str, Any] = field(default_factory=dict)

    def to_envelope(
        self,
        object_id: str,
        root_id: str,
        parent_id: str,
        parent_version: int,
        version: int = 1,
        source_ts: int = 0,
        event_ts: int = 0,
        processing_ts: int = 0,
    ) -> StateEnvelope:
        spec_state = (
            DataQualityState.DATA_VALID.value
            if self.state in (DataQualityState.DATA_NORMAL, DataQualityState.DATA_VALID)
            else self.state.value
        )
        spec_prev_state = (
            DataQualityState.DATA_VALID.value
            if self.previous_state in (DataQualityState.DATA_NORMAL, DataQualityState.DATA_VALID)
            else self.previous_state.value
        )

        s_ts = source_ts or self.last_timestamp or 1
        e_ts = event_ts or s_ts
        p_ts = processing_ts or e_ts

        return StateEnvelope(
            state_id=f"dq_state_{object_id}_{version}",
            object_id=object_id,
            object_type="DataQualityState",
            symbol=self.symbol,
            timeframe="1M",
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state=spec_state,
            previous_state=spec_prev_state,
            version=version,
            source_timestamp=s_ts,
            event_timestamp=e_ts,
            processing_timestamp=p_ts,
            valid_until=p_ts + 300,
            last_seen=s_ts,
            reason_codes=[r.value for r in self.reason_codes],
            authority="DATA_QUALITY",
        )


class DataQualityEngine:
    """Canonical Data Quality Engine evaluating data integrity, state transitions, and exposure eligibility."""

    def __init__(
        self,
        symbol: str,
        max_staleness_seconds: int = 60,
        max_allowed_spread_pips: Decimal = Decimal("5.0"),
        is_jpy_pair: bool = False,
    ) -> None:
        self.symbol = symbol
        self.max_staleness_seconds = max_staleness_seconds
        self.max_allowed_spread_pips = max_allowed_spread_pips
        self.pip_scale = Decimal("0.01") if is_jpy_pair or "JPY" in symbol else Decimal("0.0001")

        self.current_state = DataQualityState.DATA_BOOT
        self.previous_state = DataQualityState.DATA_BOOT
        self.last_timestamp: Optional[int] = None
        self.last_sequence: int = 0
        self.version: int = 0
        self.seen_fingerprints: set[str] = set()
        self.max_fingerprints_cache = 10000

    def _transition_to(self, new_state: DataQualityState) -> None:
        if new_state != self.current_state:
            self.previous_state = self.current_state
            self.current_state = new_state

    def evaluate_tick(self, tick: Tick, current_processing_time: Optional[int] = None) -> DataQualityAssessment:
        AuthorityMatrix.verify_capability("DataQuality", "WRITE_DATA_QUALITY_STATE")
        if tick.symbol != self.symbol:
            raise ValueError(f"DataQualityEngine symbol mismatch: expected {self.symbol}, got {tick.symbol}")

        reasons: list[ReasonCode] = []
        now_ts = current_processing_time or tick.timestamp

        # 1. Malformed Timestamp & UTC/DST Anomaly Checks
        if tick.timestamp < 0:
            reasons.append(ReasonCode.TIMESTAMP_MALFORMED)
        if current_processing_time is not None and tick.timestamp > current_processing_time + 300:
            reasons.append(ReasonCode.UTC_DST_ANOMALY)

        # 2. Duplicate Detection
        fp = tick.fingerprint()
        if fp in self.seen_fingerprints:
            reasons.append(ReasonCode.DUPLICATE_DATA)
        else:
            self.seen_fingerprints.add(fp)
            if len(self.seen_fingerprints) > self.max_fingerprints_cache:
                self.seen_fingerprints.clear()

        # 3. Sequence Gaps & Out-of-Order Checks
        if self.last_timestamp is not None:
            if tick.timestamp < self.last_timestamp:
                reasons.append(ReasonCode.OUT_OF_ORDER_DATA)
            elif tick.timestamp == self.last_timestamp and tick.sequence <= self.last_sequence:
                if ReasonCode.DUPLICATE_DATA not in reasons:
                    reasons.append(ReasonCode.DUPLICATE_DATA)

            if tick.sequence > self.last_sequence + 1 and self.last_sequence > 0:
                reasons.append(ReasonCode.SEQUENCE_GAP)

            if tick.timestamp - self.last_timestamp > 172800:
                reasons.append(ReasonCode.SESSION_DISCONTINUITY)

        # 4. Staleness Check
        if now_ts - tick.timestamp > self.max_staleness_seconds:
            reasons.append(ReasonCode.DATA_STALE)

        # 5. Spread Checks (Zero, Negative, or Spiking)
        spread_pips = (tick.spread / self.pip_scale) if self.pip_scale > Decimal("0.0") else tick.spread
        if tick.spread <= Decimal("0.0"):
            reasons.append(ReasonCode.SPREAD_ZERO_OR_NEGATIVE)
        elif spread_pips > self.max_allowed_spread_pips:
            reasons.append(ReasonCode.SPREAD_SPIKE_DETECTED)

        if self.last_timestamp is None or tick.timestamp >= self.last_timestamp:
            self.last_timestamp = tick.timestamp
            self.last_sequence = tick.sequence

        if ReasonCode.TIMESTAMP_MALFORMED in reasons or ReasonCode.SPREAD_ZERO_OR_NEGATIVE in reasons:
            self._transition_to(DataQualityState.DATA_CORRUPTED)
        elif ReasonCode.DATA_STALE in reasons:
            self._transition_to(DataQualityState.DATA_STALE)
        elif (
            ReasonCode.DUPLICATE_DATA in reasons
            or ReasonCode.SEQUENCE_GAP in reasons
            or ReasonCode.OUT_OF_ORDER_DATA in reasons
            or ReasonCode.SPREAD_SPIKE_DETECTED in reasons
            or ReasonCode.SESSION_DISCONTINUITY in reasons
        ):
            self._transition_to(DataQualityState.DATA_DEGRADED)
        elif not reasons:
            self._transition_to(DataQualityState.DATA_NORMAL)

        if not self.current_state.is_valid_for_exposure():
            reasons.append(ReasonCode.EXPOSURE_FORBIDDEN_DATA_INVALID)

        self.version += 1
        return DataQualityAssessment(
            symbol=self.symbol,
            state=self.current_state,
            previous_state=self.previous_state,
            reason_codes=reasons,
            exposure_allowed=self.current_state.is_valid_for_exposure(),
            last_timestamp=self.last_timestamp or tick.timestamp,
            last_sequence=self.last_sequence,
            version=self.version,
            details={"tick_spread_pips": str(spread_pips)},
        )

    def evaluate_bar(self, bar: Bar, current_processing_time: Optional[int] = None) -> DataQualityAssessment:
        AuthorityMatrix.verify_capability("DataQuality", "WRITE_DATA_QUALITY_STATE")
        if bar.symbol != self.symbol:
            raise ValueError(f"DataQualityEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        reasons: list[ReasonCode] = []
        now_ts = current_processing_time or bar.close_timestamp

        if (
            bar.high < max(bar.open, bar.close, bar.low)
            or bar.low > min(bar.open, bar.close, bar.high)
            or bar.open <= Decimal("0.0")
            or bar.high <= Decimal("0.0")
            or bar.low <= Decimal("0.0")
            or bar.close <= Decimal("0.0")
        ):
            reasons.append(ReasonCode.IMPOSSIBLE_OHLC)

        fp = bar.fingerprint()
        if fp in self.seen_fingerprints:
            reasons.append(ReasonCode.DUPLICATE_DATA)
        else:
            self.seen_fingerprints.add(fp)

        if bar.open_timestamp < 0 or bar.close_timestamp < bar.open_timestamp:
            reasons.append(ReasonCode.TIMESTAMP_MALFORMED)

        if self.last_timestamp is not None:
            if bar.open_timestamp < self.last_timestamp:
                reasons.append(ReasonCode.OUT_OF_ORDER_DATA)

            expected_next_ts = self.last_timestamp + bar.timeframe.seconds
            if bar.open_timestamp > expected_next_ts:
                reasons.append(ReasonCode.TIMEFRAME_OBSERVATION_MISSING)

        if now_ts - bar.close_timestamp > (self.max_staleness_seconds * 5):
            reasons.append(ReasonCode.DATA_STALE)

        if self.last_timestamp is None or bar.open_timestamp >= self.last_timestamp:
            self.last_timestamp = bar.close_timestamp
            self.last_sequence = bar.sequence

        if ReasonCode.IMPOSSIBLE_OHLC in reasons or ReasonCode.TIMESTAMP_MALFORMED in reasons:
            self._transition_to(DataQualityState.DATA_CORRUPTED)
        elif ReasonCode.DATA_STALE in reasons:
            self._transition_to(DataQualityState.DATA_STALE)
        elif (
            ReasonCode.DUPLICATE_DATA in reasons
            or ReasonCode.TIMEFRAME_OBSERVATION_MISSING in reasons
            or ReasonCode.OUT_OF_ORDER_DATA in reasons
        ):
            self._transition_to(DataQualityState.DATA_DEGRADED)
        elif not reasons:
            self._transition_to(DataQualityState.DATA_NORMAL)

        if not self.current_state.is_valid_for_exposure():
            reasons.append(ReasonCode.EXPOSURE_FORBIDDEN_DATA_INVALID)

        self.version += 1
        return DataQualityAssessment(
            symbol=self.symbol,
            state=self.current_state,
            previous_state=self.previous_state,
            reason_codes=reasons,
            exposure_allowed=self.current_state.is_valid_for_exposure(),
            last_timestamp=self.last_timestamp or bar.close_timestamp,
            last_sequence=self.last_sequence,
            version=self.version,
            details={"bar_timeframe": bar.timeframe.value},
        )

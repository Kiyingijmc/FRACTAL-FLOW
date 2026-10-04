"""Volatility Engine for FRACTAL FLOW.

Calculates Wilder ATR, realized volatility, local volatility, short volatility, session volatility,
rolling percentile, range percentile, expansion rate, contraction rate, and shock score.
Enforces Decimal numerical policy for prices/spreads and float for statistical metrics.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
import math
from typing import Any, Optional

from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.persistence.adapter import (
    canonical_json_dumps,
    compute_canonical_fingerprint,
    domain_to_primitive,
)


@unique
class VolatilityState(str, Enum):
    VOL_UNKNOWN = "VOL_UNKNOWN"
    VOL_COMPRESSION = "VOL_COMPRESSION"
    VOL_NORMAL = "VOL_NORMAL"
    VOL_EXPANSION = "VOL_EXPANSION"
    VOL_EXTREME = "VOL_EXTREME"
    VOL_COLLAPSE = "VOL_COLLAPSE"


@dataclass(frozen=True)
class VolatilityMetrics:
    symbol: str
    timeframe: str
    state: VolatilityState
    previous_state: VolatilityState
    timestamp: int
    true_range: Decimal  # Financial Decimal
    atr_14: Decimal  # Financial Decimal
    session_range: Decimal  # Financial Decimal
    realized_volatility: float  # Statistical float
    local_volatility: float  # Statistical float
    short_volatility: float  # Statistical float
    rolling_percentile: float  # Statistical float
    range_percentile: float  # Statistical float
    expansion_rate: float  # Statistical float
    contraction_rate: float  # Statistical float
    shock_score: float  # Statistical float
    warmup_complete: bool
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        res = domain_to_primitive(self)
        res["state"] = self.state.value
        res["previous_state"] = self.previous_state.value
        return res

    def to_json(self) -> str:
        return canonical_json_dumps(self)

    def fingerprint(self) -> str:
        return compute_canonical_fingerprint(self)

    def to_envelope(
        self,
        object_id: str,
        root_id: str,
        parent_id: str,
        parent_version: int,
        source_ts: int = 0,
        event_ts: int = 0,
        processing_ts: int = 0,
    ) -> StateEnvelope:
        s_ts = source_ts or self.timestamp or 1
        e_ts = event_ts or s_ts
        p_ts = processing_ts or e_ts

        return StateEnvelope(
            state_id=f"vol_state_{object_id}_{self.version}",
            object_id=object_id,
            object_type="VolatilityState",
            symbol=self.symbol,
            timeframe=self.timeframe,
            root_id=root_id,
            parent_id=parent_id,
            parent_version=parent_version,
            state=self.state.value,
            previous_state=self.previous_state.value,
            version=self.version,
            source_timestamp=s_ts,
            event_timestamp=e_ts,
            processing_timestamp=p_ts,
            valid_until=p_ts + 300,
            last_seen=s_ts,
            authority="VOLATILITY",
        )


class VolatilityEngine:
    """Canonical Volatility Engine processing price bars and computing causal volatility metrics."""

    def __init__(self, symbol: str, timeframe: str = "1M", atr_period: int = 14, window_size: int = 100) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.atr_period = atr_period
        self.window_size = window_size

        self.current_state = VolatilityState.VOL_UNKNOWN
        self.previous_state = VolatilityState.VOL_UNKNOWN
        self.version = 0

        self._prev_close: Optional[Decimal] = None
        self._atr: Optional[Decimal] = None
        self._close_history: list[Decimal] = []
        self._tr_history: list[Decimal] = []
        self._atr_history: list[Decimal] = []
        self._range_history: list[Decimal] = []
        self._session_open_ts: Optional[int] = None
        self._session_high: Optional[Decimal] = None
        self._session_low: Optional[Decimal] = None

    def update_bar(self, bar: Bar) -> VolatilityMetrics:
        if bar.symbol != self.symbol:
            raise ValueError(f"VolatilityEngine symbol mismatch: expected {self.symbol}, got {bar.symbol}")

        # 1. True Range Calculation (Decimal)
        high = bar.high
        low = bar.low
        close = bar.close
        open_p = bar.open
        bar_range = high - low

        if self._prev_close is None:
            tr = bar_range
        else:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))

        self._prev_close = close
        self._tr_history.append(tr)
        self._range_history.append(bar_range)
        self._close_history.append(close)

        # 2. Wilder's Smoothed ATR (Decimal)
        if len(self._tr_history) < self.atr_period:
            atr = sum(self._tr_history, Decimal("0.0")) / Decimal(str(len(self._tr_history)))
            warmup_complete = False
        elif self._atr is None:
            # Initial SMA ATR for period
            atr = sum(self._tr_history[: self.atr_period], Decimal("0.0")) / Decimal(str(self.atr_period))
            self._atr = atr
            warmup_complete = True
        else:
            # Wilder Smoothing: ATR = (ATR_prev * 13 + TR_curr) / 14
            p = Decimal(str(self.atr_period))
            atr = ((self._atr * (p - Decimal("1.0"))) + tr) / p
            self._atr = atr
            warmup_complete = True

        self._atr_history.append(atr)

        # Maintain window sizes
        if len(self._atr_history) > self.window_size:
            self._atr_history.pop(0)
            self._range_history.pop(0)
            self._close_history.pop(0)

        # 3. Session Volatility Range (Decimal)
        session_sec = 86400  # Daily session
        session_start = (bar.open_timestamp // session_sec) * session_sec
        if self._session_open_ts != session_start:
            self._session_open_ts = session_start
            self._session_high = high
            self._session_low = low
        else:
            self._session_high = max(self._session_high or high, high)
            self._session_low = min(self._session_low or low, low)

        session_range = (
            (self._session_high - self._session_low) if (self._session_high and self._session_low) else bar_range
        )

        # 4. Statistical Metrics (float)
        # Realized Volatility (N=20 log returns std dev)
        realized_vol = 0.0
        if len(self._close_history) >= 2:
            n = min(20, len(self._close_history) - 1)
            recent_closes = self._close_history[-(n + 1) :]
            log_returns = [
                math.log(float(recent_closes[i] / recent_closes[i - 1])) for i in range(1, len(recent_closes))
            ]
            mean_ret = sum(log_returns) / len(log_returns)
            var = sum((r - mean_ret) ** 2 for r in log_returns) / max(1, len(log_returns) - 1)
            realized_vol = math.sqrt(var) * math.sqrt(252 * 1440)  # Annualized

        # Local Volatility (N=5 standard deviation of close prices / current price)
        local_vol = 0.0
        if len(self._close_history) >= 5:
            n_loc = 5
            closes_5 = [float(c) for c in self._close_history[-n_loc:]]
            m_5 = sum(closes_5) / n_loc
            var_5 = sum((c - m_5) ** 2 for c in closes_5) / max(1, n_loc - 1)
            local_vol = math.sqrt(var_5) / float(close)

        # Short Volatility (atr / close price ratio)
        short_vol = float(atr / close) if close > Decimal("0.0") else 0.0

        # Percentiles (0.0 to 1.0)
        rolling_pct = 0.5
        if len(self._atr_history) > 1:
            atr_floats = [float(x) for x in self._atr_history]
            current_atr_f = float(atr)
            below_count = sum(1 for x in atr_floats if x <= current_atr_f)
            rolling_pct = below_count / len(atr_floats)

        range_pct = 0.5
        if len(self._range_history) > 1:
            range_floats = [float(x) for x in self._range_history]
            current_r_f = float(bar_range)
            below_r_count = sum(1 for x in range_floats if x <= current_r_f)
            range_pct = below_r_count / len(range_floats)

        # Expansion / Contraction Rates
        atr_short = (
            sum([float(x) for x in self._atr_history[-5:]]) / min(5, len(self._atr_history))
            if self._atr_history
            else float(atr)
        )
        atr_long = float(atr)
        expansion_rate = (atr_short / atr_long) - 1.0 if atr_long > 0 else 0.0
        contraction_rate = 1.0 - (atr_short / atr_long) if atr_long > 0 else 0.0

        # Shock Score (abs(close - open) / atr)
        body = abs(close - open_p)
        shock_score = float(body / atr) if atr > Decimal("0.0") else 0.0

        # 5. Volatility State Transition Logic
        new_state = VolatilityState.VOL_UNKNOWN
        if not warmup_complete:
            new_state = VolatilityState.VOL_UNKNOWN
        elif shock_score > 3.0 or rolling_pct > 0.95:
            new_state = VolatilityState.VOL_EXTREME
        elif self.current_state == VolatilityState.VOL_EXTREME and (shock_score < 1.0 or expansion_rate < -0.2):
            new_state = VolatilityState.VOL_COLLAPSE
        elif expansion_rate > 0.25 or rolling_pct > 0.75:
            new_state = VolatilityState.VOL_EXPANSION
        elif contraction_rate > 0.25 or rolling_pct < 0.25:
            new_state = VolatilityState.VOL_COMPRESSION
        else:
            new_state = VolatilityState.VOL_NORMAL

        if new_state != self.current_state:
            self.previous_state = self.current_state
            self.current_state = new_state
            self.version += 1

        return VolatilityMetrics(
            symbol=self.symbol,
            timeframe=self.timeframe,
            state=self.current_state,
            previous_state=self.previous_state,
            timestamp=bar.close_timestamp,
            true_range=tr,
            atr_14=atr,
            session_range=session_range,
            realized_volatility=realized_vol,
            local_volatility=local_vol,
            short_volatility=short_vol,
            rolling_percentile=rolling_pct,
            range_percentile=range_pct,
            expansion_rate=expansion_rate,
            contraction_rate=contraction_rate,
            shock_score=shock_score,
            warmup_complete=warmup_complete,
            version=self.version or 1,
        )

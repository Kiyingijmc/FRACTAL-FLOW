"""Canonical Market Primitives for FRACTAL FLOW.

Implements unit-safe, Decimal-preserving, UTC-normalized Tick and Bar primitives,
canonical Timeframe hierarchy, deterministic serialization, and causal bar aggregation.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
import json
from typing import Any, Iterable, Optional, Union, cast

from src.fractal_flow.persistence.adapter import (
    canonical_json_dumps,
    compute_canonical_fingerprint,
    domain_to_primitive,
    primitive_to_decimal,
)


@unique
class Timeframe(str, Enum):
    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    M30 = "30M"
    H1 = "1H"
    H4 = "4H"

    @classmethod
    def validate(cls, value: Union[str, "Timeframe"]) -> "Timeframe":
        if isinstance(value, Timeframe):
            return value
        for member in cls:
            if member.value == value or member.name == value:
                return member
        raise ValueError(f"Invalid timeframe: '{value}'. Canonical timeframes are: {[m.value for m in cls]}")

    @property
    def seconds(self) -> int:
        mapping = {
            "1M": 60,
            "5M": 300,
            "15M": 900,
            "30M": 1800,
            "1H": 3600,
            "4H": 14400,
        }
        return mapping[self.value]

    @property
    def level(self) -> int:
        order = {"1M": 1, "5M": 2, "15M": 3, "30M": 4, "1H": 5, "4H": 6}
        return order[self.value]

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, (Timeframe, str)):
            return NotImplemented
        other_tf = Timeframe.validate(other)
        return self.level < other_tf.level

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, (Timeframe, str)):
            return NotImplemented
        other_tf = Timeframe.validate(other)
        return self.level <= other_tf.level

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, (Timeframe, str)):
            return NotImplemented
        other_tf = Timeframe.validate(other)
        return self.level > other_tf.level

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, (Timeframe, str)):
            return NotImplemented
        other_tf = Timeframe.validate(other)
        return self.level >= other_tf.level


def _ensure_decimal(val: Union[Decimal, float, int, str]) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


@dataclass(frozen=True)
class Tick:
    symbol: str
    timestamp: int  # UTC epoch seconds
    bid: Decimal
    ask: Decimal
    spread: Decimal
    source: str = "DEFAULT"
    sequence: int = 0
    data_version: int = 1
    is_closed: bool = True

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("Tick symbol must be a non-empty string")
        if self.timestamp < 0:
            raise ValueError(f"Tick timestamp must be non-negative, got {self.timestamp}")

        bid_dec = _ensure_decimal(self.bid)
        ask_dec = _ensure_decimal(self.ask)
        spread_dec = _ensure_decimal(self.spread)

        if bid_dec <= Decimal("0.0"):
            raise ValueError(f"Tick bid must be positive, got {bid_dec}")
        if ask_dec <= Decimal("0.0"):
            raise ValueError(f"Tick ask must be positive, got {ask_dec}")
        if ask_dec < bid_dec:
            raise ValueError(f"Tick ask ({ask_dec}) cannot be less than bid ({bid_dec})")
        if spread_dec < Decimal("0.0"):
            raise ValueError(f"Tick spread cannot be negative, got {spread_dec}")

        object.__setattr__(self, "bid", bid_dec)
        object.__setattr__(self, "ask", ask_dec)
        object.__setattr__(self, "spread", spread_dec)

    @classmethod
    def create(
        cls,
        symbol: str,
        timestamp: int,
        bid: Union[Decimal, float, int, str],
        ask: Union[Decimal, float, int, str],
        spread: Optional[Union[Decimal, float, int, str]] = None,
        source: str = "DEFAULT",
        sequence: int = 0,
        data_version: int = 1,
        is_closed: bool = True,
    ) -> "Tick":
        bid_dec = _ensure_decimal(bid)
        ask_dec = _ensure_decimal(ask)
        spread_dec = _ensure_decimal(spread) if spread is not None else (ask_dec - bid_dec)
        return cls(
            symbol=symbol,
            timestamp=int(timestamp),
            bid=bid_dec,
            ask=ask_dec,
            spread=spread_dec,
            source=source,
            sequence=int(sequence),
            data_version=int(data_version),
            is_closed=bool(is_closed),
        )

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], domain_to_primitive(self))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Tick":
        decoded = primitive_to_decimal(d)
        return cls.create(
            symbol=decoded["symbol"],
            timestamp=decoded["timestamp"],
            bid=decoded["bid"],
            ask=decoded["ask"],
            spread=decoded.get("spread"),
            source=decoded.get("source", "DEFAULT"),
            sequence=decoded.get("sequence", 0),
            data_version=decoded.get("data_version", 1),
            is_closed=decoded.get("is_closed", True),
        )

    def to_json(self) -> str:
        return canonical_json_dumps(self)

    @classmethod
    def from_json(cls, json_str: str) -> "Tick":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def fingerprint(self) -> str:
        return compute_canonical_fingerprint(self)


@dataclass(frozen=True)
class Bar:
    symbol: str
    timeframe: Timeframe
    open_timestamp: int  # UTC epoch seconds
    close_timestamp: int  # UTC epoch seconds
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    spread: Decimal
    source: str = "DEFAULT"
    sequence: int = 0
    data_version: int = 1
    is_closed: bool = True

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("Bar symbol must be a non-empty string")

        tf = Timeframe.validate(self.timeframe)
        object.__setattr__(self, "timeframe", tf)

        if self.open_timestamp < 0:
            raise ValueError(f"Bar open_timestamp must be non-negative, got {self.open_timestamp}")
        if self.close_timestamp < self.open_timestamp:
            raise ValueError(
                f"Bar close_timestamp ({self.close_timestamp}) cannot precede open_timestamp ({self.open_timestamp})"
            )

        o_dec = _ensure_decimal(self.open)
        h_dec = _ensure_decimal(self.high)
        l_dec = _ensure_decimal(self.low)
        c_dec = _ensure_decimal(self.close)
        s_dec = _ensure_decimal(self.spread)

        if o_dec <= Decimal("0.0") or h_dec <= Decimal("0.0") or l_dec <= Decimal("0.0") or c_dec <= Decimal("0.0"):
            raise ValueError("Bar OHLC prices must be strictly positive")
        if h_dec < max(o_dec, c_dec, l_dec):
            raise ValueError(f"Bar high ({h_dec}) must be >= open, close, and low ({o_dec}, {c_dec}, {l_dec})")
        if l_dec > min(o_dec, c_dec, h_dec):
            raise ValueError(f"Bar low ({l_dec}) must be <= open, close, and high ({o_dec}, {c_dec}, {h_dec})")
        if s_dec < Decimal("0.0"):
            raise ValueError(f"Bar spread cannot be negative, got {s_dec}")

        object.__setattr__(self, "open", o_dec)
        object.__setattr__(self, "high", h_dec)
        object.__setattr__(self, "low", l_dec)
        object.__setattr__(self, "close", c_dec)
        object.__setattr__(self, "spread", s_dec)

    @classmethod
    def create(
        cls,
        symbol: str,
        timeframe: Union[str, Timeframe],
        open_timestamp: int,
        close_timestamp: int,
        open: Union[Decimal, float, int, str],
        high: Union[Decimal, float, int, str],
        low: Union[Decimal, float, int, str],
        close: Union[Decimal, float, int, str],
        spread: Union[Decimal, float, int, str] = Decimal("0.0"),
        source: str = "DEFAULT",
        sequence: int = 0,
        data_version: int = 1,
        is_closed: bool = True,
    ) -> "Bar":
        return cls(
            symbol=symbol,
            timeframe=Timeframe.validate(timeframe),
            open_timestamp=int(open_timestamp),
            close_timestamp=int(close_timestamp),
            open=_ensure_decimal(open),
            high=_ensure_decimal(high),
            low=_ensure_decimal(low),
            close=_ensure_decimal(close),
            spread=_ensure_decimal(spread),
            source=source,
            sequence=int(sequence),
            data_version=int(data_version),
            is_closed=bool(is_closed),
        )

    def to_dict(self) -> dict[str, Any]:
        res = cast(dict[str, Any], domain_to_primitive(self))
        res["timeframe"] = self.timeframe.value
        return res

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Bar":
        decoded = primitive_to_decimal(d)
        return cls.create(
            symbol=decoded["symbol"],
            timeframe=decoded["timeframe"],
            open_timestamp=decoded["open_timestamp"],
            close_timestamp=decoded["close_timestamp"],
            open=decoded["open"],
            high=decoded["high"],
            low=decoded["low"],
            close=decoded["close"],
            spread=decoded.get("spread", Decimal("0.0")),
            source=decoded.get("source", "DEFAULT"),
            sequence=decoded.get("sequence", 0),
            data_version=decoded.get("data_version", 1),
            is_closed=decoded.get("is_closed", True),
        )

    def to_json(self) -> str:
        return canonical_json_dumps(self)

    @classmethod
    def from_json(cls, json_str: str) -> "Bar":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def fingerprint(self) -> str:
        return compute_canonical_fingerprint(self)


class BarAggregator:
    """Deterministic, causal bar aggregator for Ticks or lower-timeframe Bars into canonical Timeframe Bars."""

    def __init__(self, symbol: str, timeframe: Union[str, Timeframe], source: str = "DEFAULT") -> None:
        self.symbol = symbol
        self.timeframe = Timeframe.validate(timeframe)
        self.source = source
        self._current_bar_open_ts: Optional[int] = None
        self._ticks_in_bar: list[Tick] = []
        self._bars_in_bar: list[Bar] = []
        self._completed_bars: list[Bar] = []
        self._sequence = 0

    def get_period_open_ts(self, timestamp: int) -> int:
        """UTC normalized period start timestamp."""
        tf_sec = self.timeframe.seconds
        return (timestamp // tf_sec) * tf_sec

    def process_tick(self, tick: Tick) -> Optional[Bar]:
        """Processes a single tick causally. Emits a closed Bar when a tick crosses into a new bar period."""
        if tick.symbol != self.symbol:
            raise ValueError(f"Symbol mismatch: expected {self.symbol}, got {tick.symbol}")

        tick_period_open = self.get_period_open_ts(tick.timestamp)
        emitted_bar: Optional[Bar] = None

        if self._current_bar_open_ts is not None and tick_period_open > self._current_bar_open_ts:
            # Finalize previous bar
            emitted_bar = self._finalize_current_bar(is_closed=True)

        if self._current_bar_open_ts is None or tick_period_open > self._current_bar_open_ts:
            self._current_bar_open_ts = tick_period_open
            self._ticks_in_bar = []

        self._ticks_in_bar.append(tick)
        return emitted_bar

    def process_bar(self, bar: Bar) -> Optional[Bar]:
        """Aggregates a lower-timeframe bar into a higher-timeframe bar causally."""
        if bar.symbol != self.symbol:
            raise ValueError(f"Symbol mismatch: expected {self.symbol}, got {bar.symbol}")
        if bar.timeframe >= self.timeframe:
            raise ValueError(
                f"Cannot aggregate bar of timeframe {bar.timeframe.value} into equal or lower timeframe {self.timeframe.value}"
            )

        bar_period_open = self.get_period_open_ts(bar.open_timestamp)
        emitted_bar: Optional[Bar] = None

        if self._current_bar_open_ts is not None and bar_period_open > self._current_bar_open_ts:
            emitted_bar = self._finalize_current_bar(is_closed=True)

        if self._current_bar_open_ts is None or bar_period_open > self._current_bar_open_ts:
            self._current_bar_open_ts = bar_period_open
            self._bars_in_bar = []

        self._bars_in_bar.append(bar)

        # Check if the lower TF bar completes the higher TF bar boundary
        if bar.close_timestamp >= self._current_bar_open_ts + self.timeframe.seconds:
            emitted_bar = self._finalize_current_bar(is_closed=True)

        return emitted_bar

    def _finalize_current_bar(self, is_closed: bool = True) -> Optional[Bar]:
        if self._current_bar_open_ts is None:
            return None

        if self._ticks_in_bar:
            # Deterministic sorting
            sorted_ticks = sorted(self._ticks_in_bar, key=lambda t: (t.timestamp, t.sequence))
            prices = [t.bid for t in sorted_ticks]
            spreads = [t.spread for t in sorted_ticks]
            open_p = prices[0]
            high_p = max(prices)
            low_p = min(prices)
            close_p = prices[-1]
            avg_spread = sum(spreads, Decimal("0.0")) / Decimal(str(len(spreads)))

            self._sequence += 1
            bar = Bar.create(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_timestamp=self._current_bar_open_ts,
                close_timestamp=self._current_bar_open_ts + self.timeframe.seconds,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                spread=avg_spread,
                source=self.source,
                sequence=self._sequence,
                is_closed=is_closed,
            )
            self._ticks_in_bar = []
            self._current_bar_open_ts = None
            self._completed_bars.append(bar)
            return bar

        if self._bars_in_bar:
            sorted_bars = sorted(self._bars_in_bar, key=lambda b: (b.open_timestamp, b.sequence))
            open_p = sorted_bars[0].open
            high_p = max(b.high for b in sorted_bars)
            low_p = min(b.low for b in sorted_bars)
            close_p = sorted_bars[-1].close
            spreads = [b.spread for b in sorted_bars]
            avg_spread = sum(spreads, Decimal("0.0")) / Decimal(str(len(spreads)))

            self._sequence += 1
            bar = Bar.create(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_timestamp=self._current_bar_open_ts,
                close_timestamp=self._current_bar_open_ts + self.timeframe.seconds,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                spread=avg_spread,
                source=self.source,
                sequence=self._sequence,
                is_closed=is_closed,
            )
            self._bars_in_bar = []
            self._current_bar_open_ts = None
            self._completed_bars.append(bar)
            return bar

        return None

    def flush(self) -> Optional[Bar]:
        """Flushes any pending partial bar as unclosed or closed."""
        return self._finalize_current_bar(is_closed=False)


def aggregate_ticks_to_bars(
    ticks: Iterable[Tick], timeframe: Union[str, Timeframe], symbol: Optional[str] = None
) -> list[Bar]:
    """Deterministically aggregates an iterable of ticks into a list of closed Bars."""
    tick_list = list(ticks)
    if not tick_list:
        return []
    target_symbol = symbol or tick_list[0].symbol
    # Sort deterministically by timestamp and sequence
    sorted_ticks = sorted(tick_list, key=lambda t: (t.timestamp, t.sequence))
    aggregator = BarAggregator(symbol=target_symbol, timeframe=timeframe)
    bars: list[Bar] = []
    for t in sorted_ticks:
        b = aggregator.process_tick(t)
        if b is not None:
            bars.append(b)
    last_bar = aggregator.flush()
    if last_bar is not None and last_bar not in bars:
        bars.append(last_bar)
    return bars

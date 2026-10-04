"""Phase 1A Tests: Tick-to-Bar Equivalence."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import (
    Bar,
    BarAggregator,
    Tick,
    Timeframe,
    aggregate_ticks_to_bars,
)


def test_tick_and_bar_construction_and_decimal_preservation() -> None:
    tick = Tick.create(
        symbol="EURUSD",
        timestamp=1700000000,
        bid=Decimal("1.08500"),
        ask=Decimal("1.08515"),
        source="BROKER_FEED",
        sequence=1,
    )
    assert tick.symbol == "EURUSD"
    assert tick.timestamp == 1700000000
    assert isinstance(tick.bid, Decimal)
    assert tick.bid == Decimal("1.08500")
    assert isinstance(tick.ask, Decimal)
    assert tick.ask == Decimal("1.08515")
    assert isinstance(tick.spread, Decimal)
    assert tick.spread == Decimal("0.00015")

    bar = Bar.create(
        symbol="EURUSD",
        timeframe="5M",
        open_timestamp=1700000000,
        close_timestamp=1700000300,
        open="1.08500",
        high="1.08550",
        low="1.08480",
        close="1.08520",
        spread="0.00015",
    )
    assert bar.timeframe == Timeframe.M5
    assert isinstance(bar.open, Decimal)
    assert bar.open == Decimal("1.08500")
    assert bar.high == Decimal("1.08550")
    assert bar.low == Decimal("1.08480")
    assert bar.close == Decimal("1.08520")
    assert bar.spread == Decimal("0.00015")


def test_invalid_timeframe_rejection() -> None:
    with pytest.raises(ValueError, match="Invalid timeframe"):
        Timeframe.validate("2M")

    with pytest.raises(ValueError, match="Invalid timeframe"):
        Timeframe.validate("10M")

    with pytest.raises(ValueError, match="Invalid timeframe"):
        Bar.create(
            symbol="EURUSD",
            timeframe="7M",
            open_timestamp=1000,
            close_timestamp=1060,
            open=1.0,
            high=1.1,
            low=0.9,
            close=1.05,
        )


def test_invalid_ohlc_rejection() -> None:
    with pytest.raises(ValueError, match="high .* must be >="):
        Bar.create(
            symbol="EURUSD",
            timeframe="1M",
            open_timestamp=1000,
            close_timestamp=1060,
            open=1.1000,
            high=1.0500,
            low=1.0000,
            close=1.0200,
        )

    with pytest.raises(ValueError, match="low .* must be <="):
        Bar.create(
            symbol="EURUSD",
            timeframe="1M",
            open_timestamp=1000,
            close_timestamp=1060,
            open=1.0500,
            high=1.1000,
            low=1.0800,
            close=1.0600,
        )


def test_batch_vs_incremental_tick_to_bar_equivalence() -> None:
    ticks = [
        Tick.create("EURUSD", 1700006405, "1.08500", "1.08510", sequence=1),
        Tick.create("EURUSD", 1700006415, "1.08540", "1.08550", sequence=2),
        Tick.create("EURUSD", 1700006430, "1.08480", "1.08490", sequence=3),
        Tick.create("EURUSD", 1700006455, "1.08520", "1.08530", sequence=4),
        Tick.create("EURUSD", 1700006465, "1.08530", "1.08540", sequence=5),
        Tick.create("EURUSD", 1700006490, "1.08560", "1.08570", sequence=6),
        Tick.create("EURUSD", 1700006525, "1.08510", "1.08520", sequence=7),
    ]

    batch_bars = aggregate_ticks_to_bars(ticks, timeframe="1M", symbol="EURUSD")

    aggregator = BarAggregator("EURUSD", "1M")
    incremental_bars: list[Bar] = []
    for t in ticks:
        b = aggregator.process_tick(t)
        if b is not None:
            incremental_bars.append(b)
    last_b = aggregator.flush()
    if last_b is not None:
        incremental_bars.append(last_b)

    assert len(batch_bars) == len(incremental_bars)
    for b_batch, b_inc in zip(batch_bars, incremental_bars):
        assert b_batch == b_inc
        assert b_batch.fingerprint() == b_inc.fingerprint()

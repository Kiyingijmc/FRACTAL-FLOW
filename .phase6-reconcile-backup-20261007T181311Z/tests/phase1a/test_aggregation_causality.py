"""Phase 1A Tests: Aggregation Causality, Closed-Bar Semantics, and UTC Alignment."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import Bar, BarAggregator, Tick, Timeframe

BASE_TS = 1700006400


def test_utc_boundary_alignment() -> None:
    aggregator = BarAggregator("EURUSD", Timeframe.M5)
    assert aggregator.get_period_open_ts(BASE_TS + 123) == BASE_TS

    agg_h1 = BarAggregator("EURUSD", Timeframe.H1)
    assert agg_h1.get_period_open_ts(BASE_TS + 3500) == BASE_TS


def test_closed_bar_causality_no_future_data() -> None:
    agg = BarAggregator("EURUSD", Timeframe.M1)

    t1 = Tick.create("EURUSD", BASE_TS + 10, "1.08500", "1.08510")
    t2 = Tick.create("EURUSD", BASE_TS + 30, "1.08550", "1.08560")
    t3 = Tick.create("EURUSD", BASE_TS + 50, "1.08490", "1.08500")

    assert agg.process_tick(t1) is None
    assert agg.process_tick(t2) is None
    assert agg.process_tick(t3) is None

    t4_next_period = Tick.create("EURUSD", BASE_TS + 65, "1.08520", "1.08530")
    emitted_bar = agg.process_tick(t4_next_period)

    assert emitted_bar is not None
    assert emitted_bar.open_timestamp == BASE_TS
    assert emitted_bar.close_timestamp == BASE_TS + 60
    assert emitted_bar.open == Decimal("1.08500")
    assert emitted_bar.high == Decimal("1.08550")
    assert emitted_bar.low == Decimal("1.08490")
    assert emitted_bar.close == Decimal("1.08490")
    assert emitted_bar.is_closed is True


def test_lower_timeframe_bar_aggregation_into_higher_timeframe() -> None:
    m1_bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.08500", "1.08550", "1.08490", "1.08520", "0.00010"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.08520", "1.08580", "1.08510", "1.08570", "0.00010"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.08570", "1.08600", "1.08550", "1.08590", "0.00010"),
        Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.08590", "1.08620", "1.08560", "1.08600", "0.00010"),
        Bar.create("EURUSD", "1M", BASE_TS + 240, BASE_TS + 300, "1.08600", "1.08650", "1.08580", "1.08630", "0.00010"),
    ]

    agg_m5 = BarAggregator("EURUSD", Timeframe.M5)
    m5_bars: list[Bar] = []
    for m1 in m1_bars:
        res = agg_m5.process_bar(m1)
        if res is not None:
            m5_bars.append(res)

    assert len(m5_bars) == 1
    m5_bar = m5_bars[0]
    assert m5_bar.timeframe == Timeframe.M5
    assert m5_bar.open_timestamp == BASE_TS
    assert m5_bar.close_timestamp == BASE_TS + 300
    assert m5_bar.open == Decimal("1.08500")
    assert m5_bar.high == Decimal("1.08650")
    assert m5_bar.low == Decimal("1.08490")
    assert m5_bar.close == Decimal("1.08630")
    assert m5_bar.is_closed is True


def test_invalid_aggregation_hierarchy_rejection() -> None:
    agg_m1 = BarAggregator("EURUSD", Timeframe.M1)
    m5_bar = Bar.create("EURUSD", "5M", BASE_TS, BASE_TS + 300, "1.085", "1.086", "1.084", "1.085")

    with pytest.raises(ValueError, match="Cannot aggregate bar of timeframe 5M into equal or lower timeframe 1M"):
        agg_m1.process_bar(m5_bar)


def test_missing_observation_gap_handling() -> None:
    agg = BarAggregator("EURUSD", Timeframe.M1)

    agg.process_tick(Tick.create("EURUSD", BASE_TS + 10, "1.08500", "1.08510"))

    t_gap = Tick.create("EURUSD", BASE_TS + 310, "1.08600", "1.08610")
    emitted = agg.process_tick(t_gap)

    assert emitted is not None
    assert emitted.open_timestamp == BASE_TS
    assert emitted.close_timestamp == BASE_TS + 60
    assert emitted.close == Decimal("1.08500")

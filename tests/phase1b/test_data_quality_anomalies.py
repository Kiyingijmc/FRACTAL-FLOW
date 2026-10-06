"""Phase 1B Tests: Comprehensive Data Quality Anomaly Detection."""

from decimal import Decimal

from src.fractal_flow.domain.data_quality import DataQualityEngine, DataQualityState
from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.reason_codes import ReasonCode

BASE_TS = 1700006400


def test_duplicate_tick_and_bar_detection() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851", sequence=1)
    a1 = engine.evaluate_tick(t1, current_processing_time=BASE_TS)
    assert a1.state == DataQualityState.DATA_NORMAL
    assert a1.exposure_allowed is True

    a2 = engine.evaluate_tick(t1, current_processing_time=BASE_TS)
    assert a2.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.DUPLICATE_DATA in a2.reason_codes

    bar1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.085", "1.086", "1.084", "1.085", sequence=1)
    bar_engine = DataQualityEngine("EURUSD")
    ba1 = bar_engine.evaluate_bar(bar1, current_processing_time=BASE_TS + 60)
    assert ba1.state == DataQualityState.DATA_NORMAL

    ba2 = bar_engine.evaluate_bar(bar1, current_processing_time=BASE_TS + 60)
    assert ba2.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.DUPLICATE_DATA in ba2.reason_codes


def test_sequence_gap_detection() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851", sequence=1)
    engine.evaluate_tick(t1, current_processing_time=BASE_TS)

    t2_gap = Tick.create("EURUSD", BASE_TS + 1, "1.0851", "1.0852", sequence=10)
    a2 = engine.evaluate_tick(t2_gap, current_processing_time=BASE_TS + 1)
    assert a2.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.SEQUENCE_GAP in a2.reason_codes


def test_out_of_order_data_detection() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS + 10, "1.0850", "1.0851", sequence=1)
    engine.evaluate_tick(t1, current_processing_time=BASE_TS + 10)

    t_ooo = Tick.create("EURUSD", BASE_TS + 5, "1.0849", "1.0850", sequence=2)
    a_ooo = engine.evaluate_tick(t_ooo, current_processing_time=BASE_TS + 10)
    assert a_ooo.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.OUT_OF_ORDER_DATA in a_ooo.reason_codes


def test_stale_quotes_and_bars_detection() -> None:
    engine = DataQualityEngine("EURUSD", max_staleness_seconds=30)
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851")

    a_stale = engine.evaluate_tick(t1, current_processing_time=BASE_TS + 100)
    assert a_stale.state == DataQualityState.DATA_STALE
    assert ReasonCode.DATA_STALE in a_stale.reason_codes


def test_zero_negative_and_spiking_spread_detection() -> None:
    engine = DataQualityEngine("EURUSD", max_allowed_spread_pips=Decimal("3.0"))

    t_zero = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0850", spread="0.0")
    a_zero = engine.evaluate_tick(t_zero, current_processing_time=BASE_TS)
    assert a_zero.state == DataQualityState.DATA_CORRUPTED
    assert ReasonCode.SPREAD_ZERO_OR_NEGATIVE in a_zero.reason_codes

    t_spike = Tick.create("EURUSD", BASE_TS + 1, "1.0850", "1.0860", spread="0.0010")
    a_spike = engine.evaluate_tick(t_spike, current_processing_time=BASE_TS + 1)
    assert a_spike.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.SPREAD_SPIKE_DETECTED in a_spike.reason_codes


def test_malformed_timestamps_and_utc_anomalies() -> None:
    engine = DataQualityEngine("EURUSD")
    t_future = Tick.create("EURUSD", BASE_TS + 1000, "1.0850", "1.0851")

    a_utc = engine.evaluate_tick(t_future, current_processing_time=BASE_TS)
    assert ReasonCode.UTC_DST_ANOMALY in a_utc.reason_codes


def test_weekend_session_discontinuity_detection() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851")
    engine.evaluate_tick(t1, current_processing_time=BASE_TS)

    t_gap = Tick.create("EURUSD", BASE_TS + 300000, "1.0850", "1.0851")
    a_gap = engine.evaluate_tick(t_gap, current_processing_time=BASE_TS + 300000)
    assert ReasonCode.SESSION_DISCONTINUITY in a_gap.reason_codes


def test_impossible_ohlc_detection() -> None:
    engine = DataQualityEngine("EURUSD")
    valid_bar = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0850")
    object.__setattr__(valid_bar, "high", Decimal("1.0830"))

    a_bad = engine.evaluate_bar(valid_bar, current_processing_time=BASE_TS + 60)
    assert a_bad.state == DataQualityState.DATA_CORRUPTED
    assert ReasonCode.IMPOSSIBLE_OHLC in a_bad.reason_codes


def test_missing_timeframe_observation_gap() -> None:
    engine = DataQualityEngine("EURUSD")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.085", "1.086", "1.084", "1.085")
    engine.evaluate_bar(b1, current_processing_time=BASE_TS + 60)

    b_gap = Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.085", "1.086", "1.084", "1.085")
    a_gap = engine.evaluate_bar(b_gap, current_processing_time=BASE_TS + 420)
    assert a_gap.state == DataQualityState.DATA_DEGRADED
    assert ReasonCode.TIMEFRAME_OBSERVATION_MISSING in a_gap.reason_codes

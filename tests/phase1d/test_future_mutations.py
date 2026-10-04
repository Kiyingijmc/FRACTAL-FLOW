"""Phase 1D Tests: Causal Framework Future Mutation Suite.

Executes all 12 required future mutation scenarios and proves decision state invariant at time 't'.
"""

from typing import Any

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.market import Tick
from src.fractal_flow.simulation.causal_framework import CausalTestFramework

BASE_TS = 1700006400


def dummy_data_quality_processor(ticks: list[Tick], decision_time: int) -> dict[str, Any]:
    # Causal processor processes ticks strictly up to decision_time
    valid_ticks = [t for t in ticks if t.timestamp <= decision_time]
    if not valid_ticks:
        return {}
    engine = DataQualityEngine("EURUSD")
    last_assessment = None
    for t in valid_ticks:
        last_assessment = engine.evaluate_tick(t, current_processing_time=t.timestamp)
    assert last_assessment is not None
    return {
        "state": last_assessment.state.value,
        "symbol": last_assessment.symbol,
        "exposure_allowed": last_assessment.exposure_allowed,
        "reason_codes": [r.value for r in last_assessment.reason_codes],
        "processing_timestamp": valid_ticks[-1].timestamp + 10,  # Processing metadata
    }


def test_1_future_price_spike() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "1.1500", "1.1501")]  # Spike

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True
    assert res.latest_permissible_input_timestamp <= decision_time


def test_2_future_crash() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "0.9000", "0.9001")]  # Crash

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_3_future_spread_explosion() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0950", spread="0.0100")]  # Spread explosion

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_4_future_volatility_explosion() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50 + i * 2, "1.0850", "1.0851") for i in range(5)]
    future_b = [
        Tick.create("EURUSD", BASE_TS + 50 + i * 2, str(1.0850 + (i % 2) * 0.0200), str(1.0851 + (i % 2) * 0.0200))
        for i in range(5)
    ]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_5_future_structural_break() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "1.1000", "1.1001")]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_6_future_news_event() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "1.0950", "1.0955")]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_7_future_session_close() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 300000, "1.0850", "1.0851")]  # Session close gap

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_8_future_bar_replacement() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 60, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 60, "1.0860", "1.0861")]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_9_future_duplicate_data() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853")]
    future_b = [
        Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853"),
        Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853"),
    ]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_10_future_missing_data() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0852", "1.0853")]
    future_b = [Tick.create("EURUSD", BASE_TS + 500, "1.0852", "1.0853")]  # Gap

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_11_future_normalization_regime_change() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "1.2500", "1.2501")]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True


def test_12_future_extreme_value() -> None:
    prefix = [Tick.create("EURUSD", BASE_TS + i * 10, "1.0850", "1.0851") for i in range(5)]
    decision_time = BASE_TS + 40

    future_a = [Tick.create("EURUSD", BASE_TS + 50, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 50, "9.9999", "9.9999")]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, dummy_data_quality_processor)
    assert res.is_causal is True

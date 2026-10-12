"""Phase 1E Tests: Volatility Engine Causality and Determinism."""

from decimal import Decimal
from typing import Any

from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.volatility import VolatilityEngine
from src.fractal_flow.simulation.causal_framework import CausalTestFramework

BASE_TS = 1700006400


def test_volatility_causality_no_future_data() -> None:
    prefix_bars = [
        Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            open=str(1.0850 + (i % 2) * 0.0005),
            high=str(1.0860 + (i % 2) * 0.0005),
            low=str(1.0840 + (i % 2) * 0.0005),
            close=str(1.0855 + (i % 2) * 0.0005),
        )
        for i in range(15)
    ]

    decision_time_bar = prefix_bars[-1]

    def volatility_processor(ticks: list[Tick], decision_time: int) -> dict[str, Any]:
        engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)
        last_m = None
        for b in prefix_bars:
            if b.close_timestamp <= decision_time:
                last_m = engine.update_bar(b)
        assert last_m is not None
        return {
            "state": last_m.state.value,
            "atr_14": str(last_m.atr_14),
            "realized_volatility": last_m.realized_volatility,
            "shock_score": last_m.shock_score,
            "processing_timestamp": last_m.timestamp + 5,
        }

    prefix_ticks = [
        Tick.create("EURUSD", b.close_timestamp, str(b.close), str(b.close + Decimal("0.0001"))) for b in prefix_bars
    ]
    future_a = [Tick.create("EURUSD", BASE_TS + 16 * 60, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 16 * 60, "1.1500", "1.1501")]

    res = CausalTestFramework.verify_causality(
        prefix_ticks, future_a, future_b, decision_time_bar.close_timestamp, volatility_processor
    )
    assert res.is_causal is True


def test_volatility_metrics_serialization_and_fingerprint() -> None:
    engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    m1 = engine.update_bar(b1)

    json_str = m1.to_json()
    fp1 = m1.fingerprint()

    d = m1.to_dict()
    assert d["atr_14"]["value"] == str(m1.atr_14)
    assert isinstance(fp1, str)
    assert len(fp1) == 64

"""Phase 1E Tests: Volatility Engine Formulas and State Machine."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.volatility import VolatilityEngine, VolatilityState

BASE_TS = 1700006400


def test_wilder_atr_computation() -> None:
    engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)

    bars = []
    for i in range(20):
        # High - Low = 0.0010, Open = 1.0850, Close = 1.0855
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            open="1.0850",
            high="1.0860",
            low="1.0850",
            close="1.0855",
            spread="0.0001",
        )
        bars.append(b)

    metrics_list = [engine.update_bar(b) for b in bars]

    # Warmup check: bars 0..12 are not fully warmed up
    assert metrics_list[0].warmup_complete is False
    assert metrics_list[0].state == VolatilityState.VOL_UNKNOWN

    # Bar 13 (14th bar) completes initial SMA ATR
    assert metrics_list[13].warmup_complete is True
    assert isinstance(metrics_list[13].atr_14, Decimal)
    assert metrics_list[13].atr_14 == Decimal("0.0010")


def test_volatility_state_machine_extreme_and_expansion() -> None:
    engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)

    # 1. Warmup with normal bars
    for i in range(15):
        b = Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            open="1.0850",
            high="1.0855",
            low="1.0845",
            close="1.0850",
        )
        engine.update_bar(b)

    # 2. Extreme Price Shock (Open 1.0850 -> Close 1.1050, range 200 pips >> ATR)
    b_shock = Bar.create(
        "EURUSD",
        "1M",
        BASE_TS + 15 * 60,
        BASE_TS + 16 * 60,
        open="1.0850",
        high="1.1060",
        low="1.0840",
        close="1.1050",
    )
    m_shock = engine.update_bar(b_shock)

    assert m_shock.state == VolatilityState.VOL_EXTREME
    assert m_shock.shock_score > 3.0

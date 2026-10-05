"""Phase 1E Tests: Volatility Numerical Policy and Type Assertions."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.volatility import VolatilityEngine, VolatilityState

BASE_TS = 1700006400


def test_volatility_metrics_exact_type_policy() -> None:
    engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)

    bars = [
        Bar.create(
            "EURUSD",
            "1M",
            BASE_TS + i * 60,
            BASE_TS + (i + 1) * 60,
            open="1.0850",
            high="1.0860",
            low="1.0840",
            close="1.0855",
            spread="0.0001",
        )
        for i in range(15)
    ]

    metrics = [engine.update_bar(b) for b in bars][-1]

    # Mandatory Decimal Financial Fields
    assert isinstance(metrics.true_range, Decimal)
    assert isinstance(metrics.atr_14, Decimal)
    assert isinstance(metrics.session_range, Decimal)

    # Mandatory Float Statistical Fields
    assert isinstance(metrics.realized_volatility, float)
    assert isinstance(metrics.local_volatility, float)
    assert isinstance(metrics.short_volatility, float)
    assert isinstance(metrics.rolling_percentile, float)
    assert isinstance(metrics.range_percentile, float)
    assert isinstance(metrics.expansion_rate, float)
    assert isinstance(metrics.contraction_rate, float)
    assert isinstance(metrics.shock_score, float)


def test_volatility_state_envelope_conversion() -> None:
    engine = VolatilityEngine("EURUSD", timeframe="1M", atr_period=14)
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
    m1 = engine.update_bar(b1)

    envelope = m1.to_envelope(
        object_id="vol_obj_01",
        root_id="root_01",
        parent_id="parent_01",
        parent_version=1,
        source_ts=BASE_TS,
        event_ts=BASE_TS + 60,
        processing_ts=BASE_TS + 60,
    )

    assert envelope.object_type == "VolatilityState"
    assert envelope.state == VolatilityState.VOL_UNKNOWN.value
    assert envelope.authority == "VOLATILITY"
    assert envelope.symbol == "EURUSD"

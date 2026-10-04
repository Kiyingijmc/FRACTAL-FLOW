"""Tests for Flow Evidence Calculation, Numerical Policy, and Bounded History."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.flow import FlowEngine, FlowEvidence
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar(
    open_p: str = "1.1000",
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1015",
    ts: int = 1700000000,
) -> Bar:
    return Bar.create(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=ts,
        close_timestamp=ts + 60,
        open=Decimal(open_p),
        high=Decimal(high_p),
        low=Decimal(low_p),
        close=Decimal(close_p),
        spread=Decimal("0.0001"),
    )


def test_flow_evidence_types_and_imbalance():
    ev = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000000,
    )
    assert ev.imbalance == Decimal("0.50")
    assert isinstance(ev.long_strength, Decimal)
    assert isinstance(ev.short_strength, Decimal)


def test_flow_evidence_rejects_non_decimal_and_non_finite():
    with pytest.raises(TypeError, match="must be a Decimal"):
        FlowEvidence(
            long_strength=0.70,  # float instead of Decimal
            short_strength=Decimal("0.20"),
            imbalance=Decimal("0.50"),
            directional_displacement=Decimal("1.5"),
            directional_efficiency=Decimal("0.8"),
            structure_progression=Decimal("0.5"),
            persistence=Decimal("3"),
            volatility_context=Decimal("0.0010"),
            timestamp=1700000000,
        )

    with pytest.raises(ValueError, match="must be a finite Decimal"):
        FlowEvidence(
            long_strength=Decimal("NaN"),
            short_strength=Decimal("0.20"),
            imbalance=Decimal("0.50"),
            directional_displacement=Decimal("1.5"),
            directional_efficiency=Decimal("0.8"),
            structure_progression=Decimal("0.5"),
            persistence=Decimal("3"),
            volatility_context=Decimal("0.0010"),
            timestamp=1700000000,
        )


def test_zero_volatility_handling():
    engine = FlowEngine(symbol="EURUSD")
    bar = make_bar()
    ev = engine.calculate_evidence(bar, v_local=Decimal("0.0"))
    assert ev.long_strength == Decimal("0.0")
    assert ev.short_strength == Decimal("0.0")
    assert ev.imbalance == Decimal("0.0")


def test_bounded_history_capacity():
    engine = FlowEngine(symbol="EURUSD", max_history_capacity=5)
    for i in range(10):
        bar = make_bar(ts=1700000000 + i * 60)
        engine.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
        )

    assert len(engine.history) == 5
    assert engine.history[-1].timestamp == 1700000000 + 9 * 60 + 60

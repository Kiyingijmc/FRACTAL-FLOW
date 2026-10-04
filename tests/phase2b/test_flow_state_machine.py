"""Tests for Flow State Machine Transitions and Hysteresis."""

from decimal import Decimal

from src.fractal_flow.domain.flow import FlowEngine, FlowEvidence, FlowState
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


def test_initial_state_and_first_transition():
    engine = FlowEngine(symbol="EURUSD")
    assert engine.flow_state == FlowState.UNKNOWN

    bar = make_bar()
    rec = engine.process_bar(
        bar=bar,
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="parent_1",
        parent_version=1,
    )
    assert rec.previous_flow_state == FlowState.UNKNOWN
    assert rec.flow_state in (FlowState.LONG_EMERGING, FlowState.BALANCED)


def test_hysteresis_and_dwell_time():
    engine = FlowEngine(
        symbol="EURUSD",
        dominance_threshold=Decimal("0.60"),
        emerging_threshold=Decimal("0.30"),
        min_persistence_bars=2,
        min_dwell_bars=2,
    )

    # 1. First bullish bar
    ev1 = FlowEvidence(
        long_strength=Decimal("0.65"),
        short_strength=Decimal("0.10"),
        imbalance=Decimal("0.55"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("1"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000060,
    )
    rec1 = engine.process_bar(
        bar=make_bar(ts=1700000000),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev1,
    )
    # Transitions from UNKNOWN -> LONG_EMERGING
    assert rec1.flow_state == FlowState.LONG_EMERGING

    # 2. Second bullish bar satisfying dominance threshold, but persistence = 1 < 2
    ev2 = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.10"),
        imbalance=Decimal("0.60"),
        directional_displacement=Decimal("2.0"),
        directional_efficiency=Decimal("0.9"),
        structure_progression=Decimal("0.6"),
        persistence=Decimal("1"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000120,
    )
    rec2 = engine.process_bar(
        bar=make_bar(ts=1700000060),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev2,
    )
    assert rec2.flow_state == FlowState.LONG_EMERGING

    # 3. Third bar satisfying persistence >= 2 and dwell >= 2
    ev3 = FlowEvidence(
        long_strength=Decimal("0.75"),
        short_strength=Decimal("0.10"),
        imbalance=Decimal("0.65"),
        directional_displacement=Decimal("2.5"),
        directional_efficiency=Decimal("0.95"),
        structure_progression=Decimal("0.7"),
        persistence=Decimal("2"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000180,
    )
    rec3 = engine.process_bar(
        bar=make_bar(ts=1700000120),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev3,
    )
    assert rec3.flow_state == FlowState.LONG_DOMINANT


def test_weakening_does_not_imply_reversal():
    engine = FlowEngine(symbol="EURUSD")
    engine.flow_state = FlowState.LONG_DOMINANT

    # Weakening long strength
    ev_weak = FlowEvidence(
        long_strength=Decimal("0.25"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.05"),
        directional_displacement=Decimal("0.1"),
        directional_efficiency=Decimal("0.1"),
        structure_progression=Decimal("0.0"),
        persistence=Decimal("0"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000060,
    )
    rec = engine.process_bar(
        bar=make_bar(ts=1700000000),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev_weak,
    )
    assert rec.flow_state == FlowState.LONG_WEAKENING
    assert rec.flow_state != FlowState.SHORT_DOMINANT

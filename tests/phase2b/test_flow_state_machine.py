"""Tests for Flow State Machine Transitions, Hysteresis, Dwell, and Transition Confirmation."""

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


def test_transition_confirmation_bars_behavior():
    # Set transition_confirm_bars = 2, min_dwell_bars = 1
    engine = FlowEngine(
        symbol="EURUSD",
        dominance_threshold=Decimal("0.60"),
        emerging_threshold=Decimal("0.30"),
        min_persistence_bars=1,
        min_dwell_bars=1,
        transition_confirm_bars=2,
    )

    ev_long = FlowEvidence(
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

    # First bar: Candidate is LONG_EMERGING, confirmation counter = 1 < 2 -> state remains UNKNOWN
    rec1 = engine.process_bar(
        bar=make_bar(ts=1700000000),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev_long,
    )
    assert rec1.flow_state == FlowState.UNKNOWN
    assert engine.transition_candidate == FlowState.LONG_EMERGING
    assert engine.transition_counter == 1

    # Second bar: Candidate is LONG_EMERGING again, confirmation counter = 2 >= 2 -> commits transition to LONG_EMERGING
    rec2 = engine.process_bar(
        bar=make_bar(ts=1700000060),
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev_long,
    )
    assert rec2.flow_state == FlowState.LONG_EMERGING
    assert engine.transition_candidate is None
    assert engine.transition_counter == 0


def test_transition_confirmation_interrupted_reset():
    engine = FlowEngine(
        symbol="EURUSD",
        dominance_threshold=Decimal("0.60"),
        emerging_threshold=Decimal("0.30"),
        min_persistence_bars=1,
        min_dwell_bars=1,
        transition_confirm_bars=2,
    )

    ev_long = FlowEvidence(
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

    ev_short = FlowEvidence(
        long_strength=Decimal("0.10"),
        short_strength=Decimal("0.65"),
        imbalance=Decimal("-0.55"),
        directional_displacement=Decimal("-1.5"),
        directional_efficiency=Decimal("-0.8"),
        structure_progression=Decimal("-0.5"),
        persistence=Decimal("1"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000120,
    )

    # Bar 1: Long evidence -> Candidate LONG_EMERGING (counter 1)
    rec1 = engine.process_bar(
        bar=make_bar(ts=1700000000),
        v_local=Decimal("0.0010"),
        root_id="r1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev_long,
    )
    assert rec1.flow_state == FlowState.UNKNOWN
    assert engine.transition_candidate == FlowState.LONG_EMERGING
    assert engine.transition_counter == 1

    # Bar 2: Short evidence interrupts long candidate -> Candidate becomes SHORT_EMERGING (counter resets to 1)
    rec2 = engine.process_bar(
        bar=make_bar(ts=1700000060),
        v_local=Decimal("0.0010"),
        root_id="r1",
        parent_id="p1",
        parent_version=1,
        override_evidence=ev_short,
    )
    assert rec2.flow_state == FlowState.UNKNOWN
    assert engine.transition_candidate == FlowState.SHORT_EMERGING
    assert engine.transition_counter == 1


def test_weakening_does_not_imply_reversal():
    engine = FlowEngine(symbol="EURUSD", min_dwell_bars=1, transition_confirm_bars=1)
    engine.flow_state = FlowState.LONG_DOMINANT
    engine._dwell_counter = 1

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

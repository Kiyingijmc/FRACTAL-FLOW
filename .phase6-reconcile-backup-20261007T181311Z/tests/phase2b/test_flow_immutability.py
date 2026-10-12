"""Tests for Flow Engine Validate-Before-Mutate State Immutability Proofs."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.flow import FlowEngine, FlowEvidence
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar(
    symbol: str = "EURUSD",
    open_p: str = "1.1000",
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1015",
    open_ts: int = 1700000000,
    close_ts: int = 1700000060,
) -> Bar:
    return Bar.create(
        symbol=symbol,
        timeframe=Timeframe.M1,
        open_timestamp=open_ts,
        close_timestamp=close_ts,
        open=Decimal(open_p),
        high=Decimal(high_p),
        low=Decimal(low_p),
        close=Decimal(close_p),
        spread=Decimal("0.0001"),
    )


def snapshot_flow_state(engine: FlowEngine) -> dict:
    return {
        "symbol": engine.symbol,
        "timeframe": engine.timeframe,
        "flow_state": engine.flow_state,
        "previous_flow_state": engine.previous_flow_state,
        "state_version": engine.state_version,
        "_dwell_counter": engine._dwell_counter,
        "_long_persistence_counter": engine._long_persistence_counter,
        "_short_persistence_counter": engine._short_persistence_counter,
        "_transition_candidate": engine._transition_candidate,
        "_transition_counter": engine._transition_counter,
        "_history": list(engine._history),
        "_last_parent_id": engine._last_parent_id,
        "_last_parent_version": engine._last_parent_version,
        "_last_data_version": engine._last_data_version,
        "_last_config_version": engine._last_config_version,
        "_last_timestamp": engine._last_timestamp,
    }


def test_flow_immutability_on_parent_id_discontinuity():
    engine = FlowEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1)

    state_before = snapshot_flow_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    with pytest.raises(ValueError, match="Parent identity discontinuity"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_B", 2)

    state_after = snapshot_flow_state(engine)
    assert state_before == state_after


def test_flow_immutability_on_chronology_violation():
    engine = FlowEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1)

    state_before = snapshot_flow_state(engine)

    bar_past = make_bar(open_ts=1700000000, close_ts=1700000050)
    with pytest.raises(ValueError, match="Chronology violation"):
        engine.process_bar(bar_past, Decimal("0.0010"), "root_1", "parent_A", 2)

    state_after = snapshot_flow_state(engine)
    assert state_before == state_after


def test_flow_immutability_on_provenance_mismatch():
    engine = FlowEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1)

    state_before = snapshot_flow_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    ev_invalid = FlowEvidence(
        long_strength=Decimal("0.70"),
        short_strength=Decimal("0.20"),
        imbalance=Decimal("0.50"),
        directional_displacement=Decimal("1.5"),
        directional_efficiency=Decimal("0.8"),
        structure_progression=Decimal("0.5"),
        persistence=Decimal("3"),
        volatility_context=Decimal("0.0010"),
        timestamp=1700000120,
        symbol="GBPUSD",  # Wrong symbol!
        timeframe="1M",
    )

    with pytest.raises(ValueError, match=r"FlowEvidence provenance mismatch \(symbol\)"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_A", 2, override_evidence=ev_invalid)

    state_after = snapshot_flow_state(engine)
    assert state_before == state_after

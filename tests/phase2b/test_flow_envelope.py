"""Tests for Flow Transition Record and StateEnvelope Provenance / Chronology."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar(ts: int = 1700000000) -> Bar:
    return Bar.create(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=ts,
        close_timestamp=ts + 60,
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0990"),
        close=Decimal("1.1005"),
        spread=Decimal("0.0001"),
    )


def test_state_envelope_conversion_and_lineage():
    engine = FlowEngine(symbol="EURUSD")
    bar = make_bar(1700000000)
    rec = engine.process_bar(
        bar=bar,
        v_local=Decimal("0.0010"),
        root_id="root_100",
        parent_id="p_50",
        parent_version=3,
        config_version=2,
        data_version=1,
    )

    env = rec.to_envelope(object_id="obj_flow_1")
    assert env.object_id == "obj_flow_1"
    assert env.object_type == "FlowState"
    assert env.symbol == "EURUSD"
    assert env.root_id == "root_100"
    assert env.parent_id == "p_50"
    assert env.parent_version == 3
    assert env.version == 1
    assert env.authority == "FLOW"
    assert env.source_timestamp <= env.event_timestamp <= env.processing_timestamp


def test_stale_parent_version_regression_fails_closed():
    engine = FlowEngine(symbol="EURUSD")
    bar1 = make_bar(1700000000)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", parent_version=5)

    bar2 = make_bar(1700000060)
    with pytest.raises(ValueError, match="Parent version regression detected"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "p1", parent_version=4)


def test_chronology_violation_fails_closed():
    engine = FlowEngine(symbol="EURUSD")
    bar1 = make_bar(1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", parent_version=1)

    bar2 = make_bar(1700000000)  # Earlier timestamp
    with pytest.raises(ValueError, match="Chronology violation"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "p1", parent_version=1)

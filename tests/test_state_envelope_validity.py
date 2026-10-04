"""Tests for Timeframe-Aware StateEnvelope Validity Policy and Fail-Closed Boundary."""

import pytest
from decimal import Decimal

from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.structure import StructureEngine


def make_bar(symbol: str = "EURUSD", timeframe: Timeframe = Timeframe.M1, ts: int = 1700000000) -> Bar:
    return Bar.create(
        symbol=symbol,
        timeframe=timeframe,
        open_timestamp=ts,
        close_timestamp=ts + timeframe.seconds,
        open=Decimal("1.1000"),
        high=Decimal("1.1020"),
        low=Decimal("1.0990"),
        close=Decimal("1.1015"),
        spread=Decimal("0.0001"),
    )


def test_state_envelope_timeframe_validity_calculation():
    assert StateEnvelope.calculate_timeframe_validity_seconds("1M") == 300
    assert StateEnvelope.calculate_timeframe_validity_seconds("5M") == 1500
    assert StateEnvelope.calculate_timeframe_validity_seconds("15M") == 4500
    assert StateEnvelope.calculate_timeframe_validity_seconds("30M") == 9000
    assert StateEnvelope.calculate_timeframe_validity_seconds("1H") == 18000
    assert StateEnvelope.calculate_timeframe_validity_seconds("4H") == 72000


def test_state_envelope_invalid_timeframe_fails_closed():
    with pytest.raises(ValueError, match="invalid or unmapped timeframe"):
        StateEnvelope.calculate_timeframe_validity_seconds("99X")

    with pytest.raises(ValueError, match="invalid or unmapped timeframe"):
        StateEnvelope.calculate_timeframe_validity_seconds("")


def test_structure_transition_timeframe_aware_envelope():
    engine = StructureEngine(symbol="EURUSD", timeframe="15M")
    bar = make_bar(timeframe=Timeframe.M15, ts=1700000000)
    rec = engine.process_bar(bar, Decimal("0.0010"), "root_1", "p1", 1)
    env = rec.to_envelope("obj_1", processing_ts=1700000900)

    # 15M timeframe -> 15 * 60 * 5 = 4500 seconds window
    assert env.valid_until == 1700000900 + 4500


def test_flow_transition_timeframe_aware_envelope():
    engine = FlowEngine(symbol="EURUSD", timeframe="1H")
    bar = make_bar(timeframe=Timeframe.H1, ts=1700000000)
    rec = engine.process_bar(bar, Decimal("0.0010"), "root_1", "p1", 1)
    env = rec.to_envelope("obj_1", processing_ts=1700003600)

    # 1H timeframe -> 3600 * 5 = 18000 seconds window
    assert env.valid_until == 1700003600 + 18000

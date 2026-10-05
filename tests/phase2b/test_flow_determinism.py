"""Tests for Flow Engine Replay and Evaluation Determinism."""

from decimal import Decimal

from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar_sequence(count: int = 10) -> list[Bar]:
    bars = []
    base_ts = 1700000000
    for i in range(count):
        val = Decimal(str(i * 5))
        bars.append(
            Bar.create(
                symbol="EURUSD",
                timeframe=Timeframe.M1,
                open_timestamp=base_ts + i * 60,
                close_timestamp=base_ts + i * 60 + 60,
                open=Decimal("1.1000") + val * Decimal("0.0001"),
                high=Decimal("1.1005") + val * Decimal("0.0001"),
                low=Decimal("1.0995") + val * Decimal("0.0001"),
                close=Decimal("1.1002") + val * Decimal("0.0001"),
                spread=Decimal("0.0001"),
            )
        )
    return bars


def test_repeated_replay_determinism():
    bars = make_bar_sequence(10)

    # First run
    engine1 = FlowEngine(symbol="EURUSD")
    results1 = [
        engine1.process_bar(
            bar=b,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
        )
        for b in bars
    ]

    # Second run
    engine2 = FlowEngine(symbol="EURUSD")
    results2 = [
        engine2.process_bar(
            bar=b,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
        )
        for b in bars
    ]

    assert len(results1) == len(results2)
    for r1, r2 in zip(results1, results2):
        assert r1.flow_state == r2.flow_state
        assert r1.previous_flow_state == r2.previous_flow_state
        assert r1.evidence == r2.evidence
        assert r1.state_version == r2.state_version
        assert r1.timestamp == r2.timestamp


def test_envelope_fingerprint_determinism():
    bars = make_bar_sequence(3)
    engine = FlowEngine(symbol="EURUSD")

    envelopes1 = [engine.process_bar(b, Decimal("0.0010"), "root_1", "p1", 1).to_envelope("obj_1") for b in bars]

    engine2 = FlowEngine(symbol="EURUSD")
    envelopes2 = [engine2.process_bar(b, Decimal("0.0010"), "root_1", "p1", 1).to_envelope("obj_1") for b in bars]

    for env1, env2 in zip(envelopes1, envelopes2):
        assert env1.state_id == env2.state_id
        assert env1.state == env2.state
        assert env1.version == env2.version
        assert env1.confidence == env2.confidence

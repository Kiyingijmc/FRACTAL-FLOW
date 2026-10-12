"""Tests for Deterministic Replay and State Serialization Parity across Structure and Flow Engines."""

from decimal import Decimal

from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.structure import StructureEngine


def make_bar(
    open_p: str = "1.1000",
    high_p: str = "1.1200",
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


def test_structure_engine_deterministic_replay():
    # Run 1
    engine1 = StructureEngine(symbol="EURUSD")
    records1 = []
    for i in range(10):
        c_price = str(Decimal("1.1000") + Decimal(i) * Decimal("0.0010"))
        h_price = str(Decimal("1.1200") + Decimal(i) * Decimal("0.0010"))
        bar = make_bar(close_p=c_price, high_p=h_price, ts=1700000000 + i * 60)
        rec = engine1.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=i + 1,
        )
        records1.append(rec)

    # Run 2
    engine2 = StructureEngine(symbol="EURUSD")
    records2 = []
    for i in range(10):
        c_price = str(Decimal("1.1000") + Decimal(i) * Decimal("0.0010"))
        h_price = str(Decimal("1.1200") + Decimal(i) * Decimal("0.0010"))
        bar = make_bar(close_p=c_price, high_p=h_price, ts=1700000000 + i * 60)
        rec = engine2.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=i + 1,
        )
        records2.append(rec)

    assert len(records1) == len(records2) == 10
    assert records1 == records2


def test_flow_engine_deterministic_replay():
    # Run 1
    engine1 = FlowEngine(symbol="EURUSD")
    records1 = []
    for i in range(10):
        c_price = str(Decimal("1.1000") + Decimal(i) * Decimal("0.0010"))
        h_price = str(Decimal("1.1200") + Decimal(i) * Decimal("0.0010"))
        bar = make_bar(close_p=c_price, high_p=h_price, ts=1700000000 + i * 60)
        rec = engine1.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=i + 1,
        )
        records1.append(rec)

    # Run 2
    engine2 = FlowEngine(symbol="EURUSD")
    records2 = []
    for i in range(10):
        c_price = str(Decimal("1.1000") + Decimal(i) * Decimal("0.0010"))
        h_price = str(Decimal("1.1200") + Decimal(i) * Decimal("0.0010"))
        bar = make_bar(close_p=c_price, high_p=h_price, ts=1700000000 + i * 60)
        rec = engine2.process_bar(
            bar=bar,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=i + 1,
        )
        records2.append(rec)

    assert len(records1) == len(records2) == 10
    assert records1 == records2

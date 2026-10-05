"""Tests for Structure Engine Chronology Enforcement, Out-of-Order Bar Rejection, and State Immutability."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.structure import StructureEngine


def make_bar(
    open_p: str = "1.1000",
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1015",
    open_ts: int = 1700000000,
    close_ts: int = 1700000060,
) -> Bar:
    return Bar.create(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=open_ts,
        close_timestamp=close_ts,
        open=Decimal(open_p),
        high=Decimal(high_p),
        low=Decimal(low_p),
        close=Decimal(close_p),
        spread=Decimal("0.0001"),
    )


def test_structure_chronology_monotonic_acceptance():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    bar3 = make_bar(open_ts=1700000120, close_ts=1700000180)

    rec1 = engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 1)
    rec2 = engine.process_bar(bar2, Decimal("0.0010"), "root_1", "p1", 2)
    rec3 = engine.process_bar(bar3, Decimal("0.0010"), "root_1", "p1", 3)

    assert rec1.timestamp == 1700000060
    assert rec2.timestamp == 1700000120
    assert rec3.timestamp == 1700000180


def test_structure_chronology_out_of_order_rejection_and_atomic_immutability():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120, high_p="1.1100")  # Extreme high
    bar_past = make_bar(open_ts=1700000000, close_ts=1700000050, high_p="1.1500")  # Out of order!

    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 1)
    engine.process_bar(bar2, Decimal("0.0010"), "root_1", "p1", 2)

    version_before = engine.state_version
    swing_before = engine.swing_state
    break_before = engine.break_state
    damage_before = engine.damage_state
    high_before = engine.last_extreme_high
    low_before = engine.last_extreme_low
    protected_high_before = engine.protected_high
    protected_low_before = engine.protected_low
    persistence_before = engine.persistence_counter

    with pytest.raises(ValueError, match="Chronology violation"):
        engine.process_bar(bar_past, Decimal("0.0010"), "root_1", "p1", 3)

    # Prove complete atomic immutability
    assert engine.state_version == version_before
    assert engine.swing_state == swing_before
    assert engine.break_state == break_before
    assert engine.damage_state == damage_before
    assert engine.last_extreme_high == high_before
    assert engine.last_extreme_low == low_before
    assert engine.protected_high == protected_high_before
    assert engine.protected_low == protected_low_before
    assert engine.persistence_counter == persistence_before


def test_structure_chronology_duplicate_timestamp_idempotency():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)

    rec1 = engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 1)
    # Equal timestamp (replay/idempotent processing) is allowed
    rec2 = engine.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 2)

    assert rec1.timestamp == 1700000060
    assert rec2.timestamp == 1700000060
    assert rec1 == rec2
    assert engine.state_version == 1


def test_structure_chronology_causal_prefix_invariance():
    # Sequence S1: T0 -> T1 -> T2
    engine1 = StructureEngine(symbol="EURUSD")
    bar0 = make_bar(open_ts=1700000000, close_ts=1700000060, high_p="1.1020", low_p="1.0990", close_p="1.1010")
    bar1 = make_bar(open_ts=1700000060, close_ts=1700000120, high_p="1.1030", low_p="1.0990", close_p="1.1020")
    bar2_a = make_bar(open_ts=1700000120, close_ts=1700000180, high_p="1.1040", low_p="1.0990", close_p="1.1030")

    r0_1 = engine1.process_bar(bar0, Decimal("0.0010"), "root_1", "p1", 1)
    r1_1 = engine1.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 2)
    r2_1 = engine1.process_bar(bar2_a, Decimal("0.0010"), "root_1", "p1", 3)

    # Sequence S2 with future mutation at T2: T0 -> T1 -> T2_mutated (large breakdown causing structural damage)
    engine2 = StructureEngine(symbol="EURUSD")
    bar2_b = make_bar(open_ts=1700000120, close_ts=1700000180, high_p="1.1040", low_p="1.0800", close_p="1.0810")

    r0_2 = engine2.process_bar(bar0, Decimal("0.0010"), "root_1", "p1", 1)
    r1_2 = engine2.process_bar(bar1, Decimal("0.0010"), "root_1", "p1", 2)
    r2_2 = engine2.process_bar(bar2_b, Decimal("0.0010"), "root_1", "p1", 3)

    # Prefix outputs at T0 and T1 must be identical
    assert r0_1 == r0_2
    assert r1_1 == r1_2
    # Future output at T2 differs
    assert r2_1 != r2_2

"""Tests for Structure Engine Validate-Before-Mutate State Immutability Proofs."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.structure import StructureEngine


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


def snapshot_engine_state(engine: StructureEngine) -> dict:
    return {
        "symbol": engine.symbol,
        "swing_state": engine.swing_state,
        "previous_swing_state": engine.previous_swing_state,
        "break_state": engine.break_state,
        "previous_break_state": engine.previous_break_state,
        "damage_state": engine.damage_state,
        "previous_damage_state": engine.previous_damage_state,
        "state_version": engine.state_version,
        "protected_high": engine.protected_high,
        "protected_low": engine.protected_low,
        "last_extreme_high": engine.last_extreme_high,
        "last_extreme_low": engine.last_extreme_low,
        "persistence_counter": engine.persistence_counter,
        "_last_bar": engine._last_bar,
        "_last_parent_id": engine._last_parent_id,
        "_last_parent_version": engine._last_parent_version,
        "_last_data_version": engine._last_data_version,
        "_last_config_version": engine._last_config_version,
        "_last_timestamp": engine._last_timestamp,
    }


def test_structure_immutability_on_parent_id_discontinuity():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1)

    state_before = snapshot_engine_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    with pytest.raises(ValueError, match="Parent identity discontinuity"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_B", 2)  # Discontinuous parent!

    state_after = snapshot_engine_state(engine)
    assert state_before == state_after


def test_structure_immutability_on_parent_version_regression():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 5)

    state_before = snapshot_engine_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    with pytest.raises(ValueError, match="Parent version regression"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_A", 4)  # Regressed version!

    state_after = snapshot_engine_state(engine)
    assert state_before == state_after


def test_structure_immutability_on_data_version_regression():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1, data_version=3)

    state_before = snapshot_engine_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    with pytest.raises(ValueError, match="Stale data version detected"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_A", 2, data_version=2)

    state_after = snapshot_engine_state(engine)
    assert state_before == state_after


def test_structure_immutability_on_config_version_mismatch():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060)
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1, config_version=1)

    state_before = snapshot_engine_state(engine)

    bar2 = make_bar(open_ts=1700000060, close_ts=1700000120)
    with pytest.raises(ValueError, match="Configuration version mismatch"):
        engine.process_bar(bar2, Decimal("0.0010"), "root_1", "parent_A", 2, config_version=2)

    state_after = snapshot_engine_state(engine)
    assert state_before == state_after


def test_structure_immutability_on_duplicate_conflicting_timestamp():
    engine = StructureEngine(symbol="EURUSD")
    bar1 = make_bar(open_ts=1700000000, close_ts=1700000060, close_p="1.1015")
    engine.process_bar(bar1, Decimal("0.0010"), "root_1", "parent_A", 1)

    state_before = snapshot_engine_state(engine)

    bar1_conflicting = make_bar(
        open_ts=1700000000, close_ts=1700000060, high_p="1.1100", close_p="1.1090"
    )
    with pytest.raises(ValueError, match="Duplicate timestamp conflict"):
        engine.process_bar(bar1_conflicting, Decimal("0.0010"), "root_1", "parent_A", 2)

    state_after = snapshot_engine_state(engine)
    assert state_before == state_after

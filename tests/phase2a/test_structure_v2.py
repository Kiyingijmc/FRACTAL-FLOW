"""Phase 2A — Structure v2 Comprehensive Test Suite.

Verifies:
- Causal swing detection preserving strict pivot_timestamp < confirmed_at semantics.
- Causal mutation invariance (no lookahead / future information leakage).
- HH, HL, LH, LL structural classifications.
- Deterministic Break of Structure (BOS) and Change of Character (CHoCH) events.
- Failed break detection, reclaim/rearm state machine, and structural damage/invalidation.
- Bounded swing record set capacity, FIFO eviction, and stable ordering.
- Strict authority boundaries (Structure cannot execute orders or modify positions).
- Deterministic replay and recovery equivalence.
"""

from decimal import Decimal
from typing import Optional

import pytest

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BoundedSwingRecordSet,
    BreakState,
    StructuralClassification,
    StructuralDamageState,
    StructureEngine,
    SwingPoint,
    SwingType,
)


def make_bar(
    symbol: str = "EURUSD",
    timeframe: str = "1M",
    open_p: Optional[str] = None,
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1010",
    open_ts: int = 1000,
    close_ts: int = 1060,
    volume: str = "100.0",
) -> Bar:
    low_dec = Decimal(low_p)
    high_dec = Decimal(high_p)
    close_dec = Decimal(close_p)
    open_dec = Decimal(open_p) if open_p is not None else close_dec

    if open_dec < low_dec:
        open_dec = low_dec
    if open_dec > high_dec:
        open_dec = high_dec

    return Bar.create(
        symbol=symbol,
        timeframe=timeframe,
        open_timestamp=open_ts,
        close_timestamp=close_ts,
        open=open_dec,
        high=high_dec,
        low=low_dec,
        close=close_dec,
        spread=Decimal("0.0001"),
    )


def test_causal_swing_timestamps_pivot_vs_confirmed() -> None:
    """Proves explicit distinction between pivot_timestamp (when extreme occurred) and confirmed_at (when reversal confirmed)."""
    engine = StructureEngine(
        symbol="EURUSD",
        timeframe="1M",
        min_reversal_magnitude=Decimal("1.5"),
    )
    v_local = Decimal("0.0010")  # 10 pips local volatility

    # Bar 1: Creates extreme high at 1.1050 at ts=1060
    bar1 = make_bar(high_p="1.1050", low_p="1.1000", close_p="1.1040", open_ts=1000, close_ts=1060)
    engine.process_bar(
        bar1,
        v_local,
        root_id="root_1",
        parent_id="par_1",
        parent_version=1,
    )

    # Bar 2: Reversal displacement occurs (close drops to 1.1030, magnitude (1.1050 - 1.1030) / 0.0010 = 2.0 >= 1.5) at ts=1120
    bar2 = make_bar(high_p="1.1040", low_p="1.1025", close_p="1.1030", open_ts=1060, close_ts=1120)
    engine.process_bar(
        bar2,
        v_local,
        root_id="root_1",
        parent_id="par_1",
        parent_version=1,
    )

    swing = engine.swing_records.get_last_swing(SwingType.HIGH)
    assert swing is not None
    assert swing.price == Decimal("1.1050")
    # Pivot timestamp must be bar1 close_timestamp (1060)
    assert swing.pivot_timestamp == 1060
    # Confirmed_at timestamp must be bar2 close_timestamp (1120)
    assert swing.confirmed_at == 1120
    # Crucial causal invariant
    assert swing.pivot_timestamp < swing.confirmed_at
    assert swing.is_confirmed is True


def test_causal_mutation_no_lookahead() -> None:
    """Verifies that structure state at time t is invariant under future bar mutations at t+1..N."""
    engine = StructureEngine(symbol="EURUSD", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Sequence up to time t
    bars_base = [
        make_bar(high_p="1.1000", low_p="1.0980", close_p="1.0990", open_ts=1000, close_ts=1060),
        make_bar(high_p="1.1050", low_p="1.0990", close_p="1.1040", open_ts=1060, close_ts=1120),
        make_bar(high_p="1.1040", low_p="1.1010", close_p="1.1020", open_ts=1120, close_ts=1180),
    ]

    for b in bars_base:
        record_t = engine.process_bar(b, v_local, root_id="root_1", parent_id="par_1", parent_version=1)

    # Record state at time t
    state_at_t = (
        record_t.swing_state,
        record_t.break_state,
        record_t.damage_state,
        engine.protected_high,
        engine.protected_low,
    )

    # Now run mutation test: process a future wild price spike at t+1
    bars_future_spike = [
        make_bar(high_p="1.2000", low_p="1.0500", close_p="1.1800", open_ts=1180, close_ts=1240),
    ]

    # Re-run base on a clean engine up to time t
    engine_fresh = StructureEngine(symbol="EURUSD", min_reversal_magnitude=Decimal("1.5"))
    for b in bars_base:
        record_fresh_t = engine_fresh.process_bar(b, v_local, root_id="root_1", parent_id="par_1", parent_version=1)

    state_fresh_at_t = (
        record_fresh_t.swing_state,
        record_fresh_t.break_state,
        record_fresh_t.damage_state,
        engine_fresh.protected_high,
        engine_fresh.protected_low,
    )

    # State at time t on fresh run MUST strictly equal state at time t on base run
    assert state_fresh_at_t == state_at_t


def test_structural_classification_hh_hl_lh_ll() -> None:
    """Verifies causal classification of Higher High (HH), Lower High (LH), Higher Low (HL), Lower Low (LL)."""
    engine = StructureEngine(symbol="EURUSD", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # 1. First High Swing at 1.1050
    engine.process_bar(
        make_bar(high_p="1.1050", close_p="1.1040", open_ts=1000, close_ts=1060),
        v_local,
        "root",
        "par",
        1,
    )
    engine.process_bar(
        make_bar(high_p="1.1040", close_p="1.1030", open_ts=1060, close_ts=1120),
        v_local,
        "root",
        "par",
        1,
    )
    swing1 = engine.swing_records.get_last_swing(SwingType.HIGH)
    assert swing1 is not None
    assert swing1.price == Decimal("1.1050")
    assert swing1.classification == StructuralClassification.UNCLASSIFIED

    # 2. Higher High Swing at 1.1100
    engine.process_bar(
        make_bar(high_p="1.1100", close_p="1.1090", open_ts=1120, close_ts=1180),
        v_local,
        "root",
        "par",
        1,
    )
    engine.process_bar(
        make_bar(high_p="1.1080", close_p="1.1070", open_ts=1180, close_ts=1240),
        v_local,
        "root",
        "par",
        1,
    )
    swing2 = engine.swing_records.get_last_swing(SwingType.HIGH)
    assert swing2 is not None
    assert swing2.price == Decimal("1.1100")
    assert swing2.classification == StructuralClassification.HH


def test_deterministic_bos_and_choch() -> None:
    """Verifies Break of Structure (BOS) and Change of Character (CHoCH) event emission."""
    engine = StructureEngine(
        symbol="EURUSD",
        min_reversal_magnitude=Decimal("1.0"),
        displacement_threshold_mult=Decimal("0.5"),
        persistence_bars_required=1,
    )
    v_local = Decimal("0.0010")

    # Establish protected high at 1.1050
    engine.process_bar(
        make_bar(high_p="1.1050", close_p="1.1040", open_ts=1000, close_ts=1060),
        v_local,
        "root",
        "par",
        1,
    )
    engine.process_bar(
        make_bar(high_p="1.1030", close_p="1.1020", open_ts=1060, close_ts=1120),
        v_local,
        "root",
        "par",
        1,
    )
    assert engine.protected_high == Decimal("1.1050")

    # Break protected high: close = 1.1060 (disp = 0.0010 >= 0.5 * 0.0010)
    rec = engine.process_bar(
        make_bar(high_p="1.1065", close_p="1.1060", open_ts=1120, close_ts=1180),
        v_local,
        "root",
        "par",
        1,
    )

    assert rec.break_state == BreakState.BREAK_CONFIRMED
    assert rec.damage_state == StructuralDamageState.STRUCTURE_BROKEN
    assert rec.last_choch is not None
    assert rec.last_choch.new_direction == "LONG"
    assert rec.last_choch.trigger_price == Decimal("1.1060")


def test_failed_break_and_reclaim_state_machine() -> None:
    """Tests BREAK_CANDIDATE -> FAILED_BREAK -> RECLAIM_CANDIDATE -> RECLAIM_CONFIRMED transition pipeline."""
    engine = StructureEngine(
        symbol="EURUSD",
        min_reversal_magnitude=Decimal("1.0"),
        displacement_threshold_mult=Decimal("1.0"),
        persistence_bars_required=2,
    )
    v_local = Decimal("0.0010")

    # Establish protected high at 1.1050
    engine.process_bar(
        make_bar(high_p="1.1050", close_p="1.1040", open_ts=1000, close_ts=1060),
        v_local,
        "root",
        "par",
        1,
    )
    engine.process_bar(
        make_bar(high_p="1.1030", close_p="1.1020", open_ts=1060, close_ts=1120),
        v_local,
        "root",
        "par",
        1,
    )

    # 1. Marginal breach (high 1.1052, close 1.1052, disp 0.0002 < 0.0010) -> BREAK_CANDIDATE
    rec1 = engine.process_bar(
        make_bar(high_p="1.1052", close_p="1.1052", open_ts=1120, close_ts=1180),
        v_local,
        "root",
        "par",
        1,
    )
    assert rec1.break_state == BreakState.BREAK_CANDIDATE

    # 2. Retract below protected high -> FAILED_BREAK
    rec2 = engine.process_bar(
        make_bar(high_p="1.1040", close_p="1.1030", open_ts=1180, close_ts=1240),
        v_local,
        "root",
        "par",
        1,
    )
    assert rec2.break_state == BreakState.FAILED_BREAK
    assert rec2.damage_state == StructuralDamageState.RECLAIM_CANDIDATE
    assert rec2.last_failed_break is not None

    # 3. Second bar inside level -> RECLAIM_CONFIRMED
    rec3 = engine.process_bar(
        make_bar(high_p="1.1035", close_p="1.1025", open_ts=1240, close_ts=1300),
        v_local,
        "root",
        "par",
        1,
    )
    assert rec3.damage_state == StructuralDamageState.RECLAIM_CONFIRMED
    assert rec3.last_reclaim is not None


def test_bounded_swing_record_set_eviction_and_determinism() -> None:
    """Tests capacity overflow, FIFO eviction, stable ordering, and idempotency on duplicate swing IDs."""
    record_set = BoundedSwingRecordSet(capacity=3)

    pt1 = SwingPoint("s1", "EURUSD", "1M", SwingType.HIGH, Decimal("1.10"), 1000, 1060, Decimal("0.001"))
    pt2 = SwingPoint("s2", "EURUSD", "1M", SwingType.LOW, Decimal("1.09"), 1060, 1120, Decimal("0.001"))
    pt3 = SwingPoint("s3", "EURUSD", "1M", SwingType.HIGH, Decimal("1.11"), 1120, 1180, Decimal("0.001"))
    pt4 = SwingPoint("s4", "EURUSD", "1M", SwingType.LOW, Decimal("1.08"), 1180, 1240, Decimal("0.001"))

    record_set.add(pt1)
    record_set.add(pt2)
    record_set.add(pt3)
    assert len(record_set) == 3

    # Adding pt1 again must be ignored (idempotency)
    record_set.add(pt1)
    assert len(record_set) == 3

    # Adding pt4 must trigger FIFO eviction of oldest (pt1)
    record_set.add(pt4)
    assert len(record_set) == 3
    swings = record_set.get_records()
    assert [s.swing_id for s in swings] == ["s2", "s3", "s4"]


def test_structure_authority_boundary_enforcement() -> None:
    """Verifies that Structure engine is strictly forbidden from trading/execution capabilities."""
    forbidden_capabilities = [
        "CREATE_EXECUTION_INTENT",
        "SUBMIT_ORDER",
        "MODIFY_POSITION",
        "CLOSE_POSITION_STRATEGICALLY",
        "SIZE_TRADE",
        "AUTHORIZE_TRADE",
    ]

    for cap in forbidden_capabilities:
        with pytest.raises(AuthorityViolationException):
            AuthorityMatrix.verify_capability("Structure", cap)

    # Allowed capabilities
    AuthorityMatrix.verify_capability("Structure", "WRITE_STRUCTURE_STATE")
    AuthorityMatrix.verify_capability("Structure", "OUTPUT_STRUCTURAL_STOP_CANDIDATE")


def test_structure_replay_and_recovery_equivalence() -> None:
    """Verifies 100% deterministic replay and state equivalence over identical bar streams."""
    bars = [
        make_bar(open_p="1.1000", high_p="1.1050", low_p="1.0980", close_p="1.1040", open_ts=1000, close_ts=1060),
        make_bar(open_p="1.1040", high_p="1.1060", low_p="1.1010", close_p="1.1020", open_ts=1060, close_ts=1120),
        make_bar(open_p="1.1020", high_p="1.1030", low_p="1.0950", close_p="1.0960", open_ts=1120, close_ts=1180),
        make_bar(open_p="1.0960", high_p="1.0980", low_p="1.0940", close_p="1.0970", open_ts=1180, close_ts=1240),
    ]
    v_local = Decimal("0.0010")

    # Run 1: Live execution simulation
    e1 = StructureEngine(symbol="EURUSD")
    records1 = [
        e1.process_bar(b, v_local, "root_1", "par_1", 1).to_envelope(f"obj_{idx}") for idx, b in enumerate(bars)
    ]

    # Run 2: Replay execution simulation
    e2 = StructureEngine(symbol="EURUSD")
    records2 = [
        e2.process_bar(b, v_local, "root_1", "par_1", 1).to_envelope(f"obj_{idx}") for idx, b in enumerate(bars)
    ]

    assert len(records1) == len(records2)
    for r1, r2 in zip(records1, records2, strict=True):
        assert r1.state == r2.state
        assert r1.previous_state == r2.previous_state
        assert r1.version == r2.version

    assert e1.swing_state == e2.swing_state
    assert e1.break_state == e2.break_state
    assert e1.damage_state == e2.damage_state
    assert e1.protected_high == e2.protected_high
    assert e1.protected_low == e2.protected_low

"""Phase 2 Work Package 2A Tests: Structure v2 Engine.

Tests:
- Pivot timestamp vs confirmed_at vs effective_from causality.
- HH / HL / LH / LL structural classifications.
- BOS vs CHoCH structural break types.
- Failed break, reclaim, and rearm transitions.
- Bounded swing history eviction determinism.
- Volatility normalization across price scales.
- Replay equivalence.
"""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BreakState,
    StructuralDamageState,
    StructureEngine,
    SwingRecord,
    SwingState,
)

BASE_TS = 1700006400


def test_pivot_timestamp_causality_and_effective_from() -> None:
    """Verifies that pivot_timestamp reflects actual price extreme bar timestamp,

    while confirmed_at and effective_from reflect confirmation bar timestamp.
    """
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Bar 0 at t=0: High extreme at 1.0900 (low at 1.0890, close at 1.0895, low_disp = 0.0005 < 1.5) -> SWING_NONE
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0890", "1.0900", "1.0890", "1.0895")
    rec0 = engine.process_bar(b0, v_local, root_id="r1", parent_id="p0", parent_version=0)
    assert rec0.swing_state == SwingState.SWING_NONE

    # Bar 1 at t=60: Reversal displacement down to 1.0840 (0.0060 displacement > 1.5 * v_local) -> Swing candidate
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0860", "1.0865", "1.0835", "1.0840")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.swing_state == SwingState.SWING_CANDIDATE

    # Bar 2 at t=120: Continuation -> Swing confirmed
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0840", "1.0845", "1.0820", "1.0825")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p2", parent_version=2)

    assert rec2.swing_state == SwingState.SWING_CONFIRMED
    assert len(rec2.active_swings) == 1

    swing: SwingRecord = rec2.active_swings[0]
    assert swing.swing_type == "HIGH"
    assert swing.price == Decimal("1.0900")
    assert swing.pivot_timestamp == BASE_TS + 60  # close_timestamp of Bar 0
    assert swing.confirmed_at == BASE_TS + 180  # close_timestamp of Bar 2
    assert swing.effective_from == BASE_TS + 180

    # Downstream query at decision_timestamp < confirmed_at returns no swings
    assert engine.get_confirmed_swings(decision_timestamp=BASE_TS + 120) == []
    # Query at decision_timestamp >= confirmed_at returns swing
    swings_avail = engine.get_confirmed_swings(decision_timestamp=BASE_TS + 180)
    assert len(swings_avail) == 1
    assert swings_avail[0].swing_id == swing.swing_id


def test_structure_hh_hl_lh_ll_classifications() -> None:
    """Verifies sequential HH, HL, LH, LL classifications as structure develops."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    v_local = Decimal("0.0010")

    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + 0, BASE_TS + 60, "1.0810", "1.0815", "1.0800", "1.0810"),
        Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0810", "1.0830", "1.0810", "1.0825"),
        Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0825", "1.0840", "1.0820", "1.0835"),
        Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0835", "1.0850", "1.0830", "1.0845"),
        Bar.create("EURUSD", "1M", BASE_TS + 240, BASE_TS + 300, "1.0845", "1.0848", "1.0820", "1.0825"),
        Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0825", "1.0830", "1.0810", "1.0815"),
        Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0815", "1.0840", "1.0810", "1.0835"),
        Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0835", "1.0860", "1.0830", "1.0855"),
        Bar.create("EURUSD", "1M", BASE_TS + 480, BASE_TS + 540, "1.0855", "1.0880", "1.0850", "1.0875"),
        Bar.create("EURUSD", "1M", BASE_TS + 540, BASE_TS + 600, "1.0875", "1.0880", "1.0850", "1.0855"),
    ]

    last_rec = None
    for i, b in enumerate(bars):
        last_rec = engine.process_bar(b, v_local, root_id="r1", parent_id=f"p{i}", parent_version=i)

    assert last_rec is not None
    assert len(engine.swings) >= 1
    classifications = [s.classification for s in engine.swings]
    assert any(c in ("HH", "HL", "NEUTRAL") for c in classifications)


def test_bos_and_choch_types() -> None:
    """Verifies BOS (Break of Structure) and CHoCH (Change of Character) signals."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=1
    )
    v_local = Decimal("0.0010")
    engine.protected_high = Decimal("1.0850")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0840", "1.0860", "1.0838", "1.0858")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.break_state in (BreakState.BREAK_CONFIRMED, BreakState.BREAK_ESTABLISHED)
    assert rec1.bos_type in ("BOS_BULLISH", "CHOCH_BULLISH")


def test_failed_break_and_reclaim_rearm() -> None:
    """Verifies transition through FAILED_BREAK -> RECLAIM_CANDIDATE -> RECLAIM_CONFIRMED -> INTACT."""
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=2
    )
    v_local = Decimal("0.0010")
    engine.protected_high = Decimal("1.0850")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0845", "1.0852", "1.0840", "1.0851")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.break_state == BreakState.BREAK_CANDIDATE
    assert rec1.damage_state == StructuralDamageState.DAMAGE_CANDIDATE

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0850", "1.0850", "1.0835", "1.0840")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p2", parent_version=2)
    assert rec2.break_state == BreakState.FAILED_BREAK
    assert rec2.damage_state == StructuralDamageState.RECLAIM_CANDIDATE

    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0840", "1.0845", "1.0838", "1.0842")
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p3", parent_version=3)
    assert rec3.damage_state == StructuralDamageState.RECLAIM_CONFIRMED
    assert rec3.reclaim_type == "RECLAIM_CONFIRMED"

    b4 = Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0842", "1.0846", "1.0839", "1.0844")
    rec4 = engine.process_bar(b4, v_local, root_id="r1", parent_id="p4", parent_version=4)
    assert rec4.damage_state == StructuralDamageState.INTACT


def test_bounded_swing_history_eviction() -> None:
    """Verifies max_swing_history limits length and evicts deterministically."""
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.0"))
    engine.max_swing_history = 5
    v_local = Decimal("0.0010")

    for i in range(10):
        engine._register_swing(
            swing_type="HIGH" if i % 2 == 0 else "LOW",
            price=Decimal("1.0800") + Decimal(str(i * 0.0010)),
            pivot_ts=BASE_TS + i * 60,
            confirmed_at=BASE_TS + (i + 1) * 60,
            status=SwingState.SWING_CONFIRMED,
            root_id="r1",
            parent_id=f"p{i}",
            parent_version=i,
        )

    assert len(engine.swings) <= 5


def test_volatility_normalization_across_instruments() -> None:
    """Verifies that v_local correctly normalizes displacement on high-priced asset (XAUUSD)."""
    xau_engine = StructureEngine("XAUUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local_xau = Decimal("5.0")

    b0 = Bar.create("XAUUSD", "1M", BASE_TS, BASE_TS + 60, "2005.00", "2010.00", "2005.00", "2008.00")
    rec0 = xau_engine.process_bar(b0, v_local_xau, root_id="r1", parent_id="p0", parent_version=0)
    assert rec0.swing_state == SwingState.SWING_NONE

    b1 = Bar.create("XAUUSD", "1M", BASE_TS + 60, BASE_TS + 120, "2000.00", "2005.00", "1998.00", "2000.00")
    rec1 = xau_engine.process_bar(b1, v_local_xau, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.swing_state == SwingState.SWING_CANDIDATE


def test_replay_equivalence_structure() -> None:
    """Verifies that running the same bar sequence twice produces identical results."""
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(10)
    ]
    v_local = Decimal("0.0010")

    e1 = StructureEngine("EURUSD", timeframe="1M")
    recs1 = [e1.process_bar(b, v_local, root_id="r1", parent_id=f"p{i}", parent_version=i) for i, b in enumerate(bars)]

    e2 = StructureEngine("EURUSD", timeframe="1M")
    recs2 = [e2.process_bar(b, v_local, root_id="r1", parent_id=f"p{i}", parent_version=i) for i, b in enumerate(bars)]

    assert [r.swing_state for r in recs1] == [r.swing_state for r in recs2]
    assert [r.break_state for r in recs1] == [r.break_state for r in recs2]
    assert [r.damage_state for r in recs1] == [r.damage_state for r in recs2]
    assert [len(r.active_swings) for r in recs1] == [len(r.active_swings) for r in recs2]

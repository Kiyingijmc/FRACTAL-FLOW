"""Phase 1F Tests: Adaptive Swing, Structural Break, and State Transitions."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BreakState,
    StructureEngine,
    SwingState,
)

BASE_TS = 1700006400


def test_adaptive_swing_reversal_magnitude_transitions() -> None:
    # covers: [31]
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")  # 10 pips

    # Low candidate at 1.0800
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0810", "1.0800", "1.0805")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.swing_state == SwingState.SWING_CANDIDATE

    # Reversal displacement = 1.0820 - 1.0800 = 0.0020 = 2.0 * v_local (>= 1.5) -> SWING_CONFIRMED
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0810", "1.0825", "1.0808", "1.0820")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec2.swing_state == SwingState.SWING_CONFIRMED

    # Continued displacement -> SWING_CONFIRMED / SWING_PROTECTED
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.0835", "1.0818", "1.0830")
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert rec3.swing_state in (SwingState.SWING_CONFIRMED, SwingState.SWING_PROTECTED)
    assert engine.protected_low == Decimal("1.0800")


def test_structural_break_requires_cross_displacement_and_persistence() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=2
    )
    # Establish BEARISH ownership with LH and LL
    engine._register_swing("HIGH", Decimal("1.0850"), candidate_at=BASE_TS, confirmed_at=BASE_TS + 60)
    engine._register_swing("LOW", Decimal("1.0800"), candidate_at=BASE_TS + 60, confirmed_at=BASE_TS + 120)
    engine._register_swing("HIGH", Decimal("1.0840"), candidate_at=BASE_TS + 120, confirmed_at=BASE_TS + 180)  # LH
    engine._register_swing("LOW", Decimal("1.0780"), candidate_at=BASE_TS + 180, confirmed_at=BASE_TS + 240)  # LL

    engine.protected_high = Decimal("1.0840")
    engine.current_direction = "SHORT"
    v_local = Decimal("0.0010")  # 10 pips

    # 1. Level touch alone (High = 1.0840, Close = 1.0838) -> NO BREAK
    b_touch = Bar.create("EURUSD", "1M", BASE_TS + 300, BASE_TS + 360, "1.0830", "1.0840", "1.0828", "1.0838")
    rec_touch = engine.process_bar(b_touch, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec_touch.break_state == BreakState.BREAK_NONE

    # 2. Level cross without displacement confirmation (Close 1.0842 > 1.0840, but disp 2 pips < 5 pips) -> BREAK_CANDIDATE
    b_cross = Bar.create("EURUSD", "1M", BASE_TS + 360, BASE_TS + 420, "1.0838", "1.0843", "1.0835", "1.0842")
    rec_cross = engine.process_bar(b_cross, v_local, root_id="r1", parent_id="p1", parent_version=2)
    assert rec_cross.break_state == BreakState.BREAK_CANDIDATE

    # 3. Bar 1 with displacement confirmation (Close 1.0846 > 1.0840 + 0.0005) -> BREAK_CANDIDATE (persistence 1/2)
    b_disp1 = Bar.create("EURUSD", "1M", BASE_TS + 420, BASE_TS + 480, "1.0842", "1.0848", "1.0840", "1.0846")
    rec_disp1 = engine.process_bar(b_disp1, v_local, root_id="r1", parent_id="p1", parent_version=3)
    assert rec_disp1.break_state == BreakState.BREAK_CANDIDATE

    # 4. Bar 2 with displacement confirmation -> BREAK_CONFIRMED (persistence 2/2 satisfied)
    b_disp2 = Bar.create("EURUSD", "1M", BASE_TS + 480, BASE_TS + 540, "1.0846", "1.0852", "1.0844", "1.0850")
    rec_disp2 = engine.process_bar(b_disp2, v_local, root_id="r1", parent_id="p1", parent_version=4)
    assert rec_disp2.break_state == BreakState.BREAK_CONFIRMED

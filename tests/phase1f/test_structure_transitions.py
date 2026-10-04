"""Phase 1F Tests: Adaptive Swing, Structural Break, and State Transitions."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import (
    BreakState,
    StructuralDamageState,
    StructureEngine,
    SwingState,
)

BASE_TS = 1700006400


def test_adaptive_swing_reversal_magnitude_transitions() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")  # 10 pips

    # Low extreme at 1.0800
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0810", "1.0800", "1.0805")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.swing_state == SwingState.SWING_NONE

    # Reversal displacement = 1.0820 - 1.0800 = 0.0020 = 2.0 * v_local (>= 1.5) -> SWING_CANDIDATE
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0810", "1.0825", "1.0808", "1.0820")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec2.swing_state == SwingState.SWING_CANDIDATE

    # Continued displacement -> SWING_CONFIRMED
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.0835", "1.0818", "1.0830")
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec3.swing_state == SwingState.SWING_CONFIRMED
    assert engine.protected_low == Decimal("1.0800")


def test_structural_break_requires_cross_displacement_and_persistence() -> None:
    engine = StructureEngine(
        "EURUSD", timeframe="1M", displacement_threshold_mult=Decimal("0.5"), persistence_bars_required=2
    )
    engine.protected_high = Decimal("1.0850")
    v_local = Decimal("0.0010")  # 10 pips

    # 1. Level touch alone (High = 1.0850, Close = 1.0848) -> NO BREAK
    b_touch = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0840", "1.0850", "1.0838", "1.0848")
    rec_touch = engine.process_bar(b_touch, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec_touch.break_state == BreakState.BREAK_NONE

    # 2. Level cross without displacement confirmation (Close 1.0852 > 1.0850, but disp 2 pips < 5 pips) -> BREAK_CANDIDATE
    b_cross = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0848", "1.0853", "1.0845", "1.0852")
    rec_cross = engine.process_bar(b_cross, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec_cross.break_state == BreakState.BREAK_CANDIDATE

    # 3. Bar 1 with displacement confirmation (Close 1.0856 > 1.0850 + 0.0005) -> BREAK_CANDIDATE (persistence 1/2)
    b_disp1 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0852", "1.0858", "1.0850", "1.0856")
    rec_disp1 = engine.process_bar(b_disp1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec_disp1.break_state == BreakState.BREAK_CANDIDATE

    # 4. Bar 2 with displacement confirmation -> BREAK_CONFIRMED (persistence 2/2 satisfied)
    b_disp2 = Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0856", "1.0862", "1.0854", "1.0860")
    rec_disp2 = engine.process_bar(b_disp2, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec_disp2.break_state == BreakState.BREAK_CONFIRMED
    assert rec_disp2.damage_state == StructuralDamageState.STRUCTURE_BROKEN

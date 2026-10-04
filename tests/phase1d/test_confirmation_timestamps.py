"""Phase 1D Tests: Confirmation Timestamps for Future-Confirmed Structures.

Verifies that retrospectively confirmed structural swings produced by StructureEngine
are timestamped at the actual confirmation time (when confirmed),
never at the earlier extreme timestamp, preventing lookahead bias in state tracking.
"""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine, SwingState

BASE_TS = 1700006400


def test_structure_engine_swing_confirmation_timestamp_equals_confirmation_time() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))
    v_local = Decimal("0.0010")

    # Bar 0 (T=0): Extreme Low at 1.0800
    b0 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0810", "1.0800", "1.0805")
    rec0 = engine.process_bar(b0, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec0.swing_state == SwingState.SWING_NONE

    # Bar 1 (T=60s): Displacement occurs -> SWING_CANDIDATE
    b1 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0805", "1.0825", "1.0805", "1.0820")
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)

    # Bar 2 (T=120s): Reversal confirmed -> SWING_CONFIRMED
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0820", "1.0835", "1.0818", "1.0830")
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec2.swing_state == SwingState.SWING_CONFIRMED

    # Invariant assertion: Confirmation event timestamp = T=180 (b2.close_timestamp), NOT T=60 (b0.close_timestamp)
    t_extreme = b0.close_timestamp  # BASE_TS + 60
    t_confirmation = b2.close_timestamp  # BASE_TS + 180

    assert rec2.timestamp == t_confirmation
    assert rec2.timestamp > t_extreme
    assert engine.last_extreme_low == Decimal("1.0800")

"""Phase 1H Tests: Architectural Invariant Verification (Invariants 31, 32, 35)."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine, SwingState

BASE_TS = 1700006400


def test_invariant_32_fixed_three_candle_fractals_not_used_in_structure() -> None:
    """Invariant 32: Fixed three-candle fractals are not the core structure engine.

    Proves that StructureEngine uses volatility-normalized reversal displacement (V_local), not fixed candle count fractals.
    """
    engine = StructureEngine("EURUSD", timeframe="1M", min_reversal_magnitude=Decimal("1.5"))

    # Three-candle pattern with small displacement < 1.5 * V_local
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0852", "1.0848", "1.0850")
    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0850", "1.0854", "1.0849", "1.0852")
    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0852", "1.0853", "1.0849", "1.0850")

    v_local = Decimal("0.0020")  # 20 pips
    rec1 = engine.process_bar(b1, v_local, root_id="r1", parent_id="p1", parent_version=1)
    rec2 = engine.process_bar(b2, v_local, root_id="r1", parent_id="p1", parent_version=1)
    rec3 = engine.process_bar(b3, v_local, root_id="r1", parent_id="p1", parent_version=1)

    # 3-candle pattern with sub-threshold displacement produces NO CONFIRMED SWING
    assert len(engine.swings) == 0
    assert rec3.swing_state != SwingState.SWING_CONFIRMED


def test_invariant_35_structural_stops_are_primary() -> None:
    """Invariant 35: Structural stops are primary.

    Proves that structural stops are anchored to protected levels rather than arbitrary ATR multipliers alone.
    """
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine.protected_low = Decimal("1.0800")

    stop_candidate = engine.get_structural_stop_candidate("LONG", atr_14=Decimal("0.0010"))
    assert stop_candidate is not None
    assert stop_candidate.protected_level_price == Decimal("1.0800")
    assert stop_candidate.recommended_stop_price == Decimal("1.0795")

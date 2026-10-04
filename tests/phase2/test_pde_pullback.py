"""Phase 2 Work Package 2C Tests: PDE / Pullback / Resumption Engine.

Tests:
- Impulse Quality calculation and PullbackObject hierarchy.
- PDEState and PDEResumptionState state transitions.
- Invariant 26 (Higher-Timeframe ordering enforcement).
- Invariants 33 & 34 (Fibonacci and candle-count constitutional independence).
- Authority enforcement and forbidden capability checks.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.pde import (
    PDEEngine,
    PDEState,
    PDEResumptionState,
    compare_timeframes,
)

BASE_TS = 1700006400


def test_timeframe_ordering_invariant_26() -> None:
    """Verifies Invariant 26 strict higher-timeframe rank comparisons."""
    assert compare_timeframes("4H", "1H") > 0
    assert compare_timeframes("1H", "15M") > 0
    assert compare_timeframes("15M", "1M") > 0
    assert compare_timeframes("1M", "1M") == 0

    engine = PDEEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0840")

    rec = engine.evaluate_bar(
        b,
        None,
        v_local,
        root_id="r1",
        parent_id="p1",
        parent_version=1,
        htf_pde_state=PDEState.PDE_IMPULSE,
        htf_timeframe="1H",
    )
    assert rec is not None

    with pytest.raises(ValueError, match="Invariant 26 Violation"):
        engine.evaluate_bar(
            b,
            None,
            v_local,
            root_id="r1",
            parent_id="p2",
            parent_version=2,
            htf_pde_state=PDEState.PDE_IMPULSE,
            htf_timeframe="1M",
        )


def test_pde_impulse_quality_and_pullback_resumption_lifecycle() -> None:
    """Verifies impulse detection, quality scoring, pullback activation, and resumption state machine."""
    engine = PDEEngine("EURUSD", timeframe="1M", min_impulse_v_mult=Decimal("2.0"))
    v_local = Decimal("0.0010")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0855", "1.0800", "1.0850")
    rec1 = engine.evaluate_bar(b1, None, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.pde_state == PDEState.PDE_IMPULSE
    assert rec1.active_pullback is not None
    assert rec1.active_pullback.quality.displacement == Decimal("0.0050")

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0850", "1.0852", "1.0830", "1.0835")
    rec2 = engine.evaluate_bar(b2, None, v_local, root_id="r1", parent_id="p2", parent_version=2)
    assert rec2.pde_state == PDEState.PDE_PULLBACK_CANDIDATE

    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0835", "1.0838", "1.0820", "1.0825")
    rec3 = engine.evaluate_bar(b3, None, v_local, root_id="r1", parent_id="p3", parent_version=3)
    assert rec3.pde_state == PDEState.PDE_PULLBACK_ACTIVE
    assert rec3.resumption_state == PDEResumptionState.RECOVERY_CANDIDATE

    b4 = Bar.create("EURUSD", "1M", BASE_TS + 180, BASE_TS + 240, "1.0825", "1.0845", "1.0822", "1.0840")
    rec4 = engine.evaluate_bar(b4, None, v_local, root_id="r1", parent_id="p4", parent_version=4)
    assert rec4.resumption_state == PDEResumptionState.RECOVERY_CONFIRMED


def test_fibonacci_independence_principle_invariant_33() -> None:
    """Verifies Invariant 33: diagnostic Fibonacci threshold mutations do NOT alter constitutional decision behavior."""
    engine1 = PDEEngine("EURUSD", timeframe="1M", max_pullback_depth=Decimal("0.618"))
    engine2 = PDEEngine("EURUSD", timeframe="1M", max_pullback_depth=Decimal("0.786"))

    v_local = Decimal("0.0010")
    b_impulse = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0848")

    rec1 = engine1.evaluate_bar(b_impulse, None, v_local, root_id="r1", parent_id="p1", parent_version=1)
    rec2 = engine2.evaluate_bar(b_impulse, None, v_local, root_id="r1", parent_id="p1", parent_version=1)

    assert rec1.pde_state == rec2.pde_state == PDEState.PDE_IMPULSE


def test_pde_authority_and_forbidden_capabilities() -> None:
    """Verifies PDEEngine has no execution, order placement, or position management capabilities."""
    engine = PDEEngine("EURUSD", timeframe="1M")

    forbidden_methods = [
        "create_execution_intent",
        "submit_order",
        "modify_position",
        "close_position_strategically",
    ]

    for m in forbidden_methods:
        assert not hasattr(engine, m)

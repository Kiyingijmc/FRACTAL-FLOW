"""Phase 2 Work Package 2D Tests: Regime, Role, and Location Engines.

Tests:
- Regime state transitions and chaotic volatility response.
- Role engine directional orthogonality (LONG/SHORT + PULLBACK/COUNTERFLOW).
- Location engine spatial obstacle assessment.
- Ambiguity propagation (UNKNOWN/CHAOTIC -> AMBIGUOUS/UNKNOWN).
- Runtime capability enforcement and forbidden execution methods.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.location import LocationEngine, LocationState
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.regime import RegimeEngine, RegimeState
from src.fractal_flow.domain.role import RoleEngine, RoleState

BASE_TS = 1700006400


def test_regime_engine_transitions_and_volatility_extreme() -> None:
    """Verifies RegimeEngine transitions and CHAOTIC response under extreme volatility."""
    engine = RegimeEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0845")

    rec1 = engine.evaluate(b, "LONG_DOMINANT", v_local, is_vol_extreme=False, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.regime_state == RegimeState.TREND_UP

    rec_chaos = engine.evaluate(b, "LONG_DOMINANT", v_local, is_vol_extreme=True, root_id="r1", parent_id="p2", parent_version=2)
    assert rec_chaos.regime_state == RegimeState.CHAOTIC


def test_role_engine_directional_orthogonality() -> None:
    """Verifies that directional bias and role state are strictly independent dimensions."""
    engine = RoleEngine("EURUSD", timeframe="1M")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0845")

    rec_long_pb = engine.evaluate(
        b,
        direction="LONG",
        regime_state="TREND_UP",
        pde_state="PDE_PULLBACK_ACTIVE",
        break_state="BREAK_NONE",
        damage_state="INTACT",
        root_id="r1",
        parent_id="p1",
        parent_version=1,
    )
    assert rec_long_pb.direction == "LONG"
    assert rec_long_pb.role_state == RoleState.PULLBACK

    rec_short_pb = engine.evaluate(
        b,
        direction="SHORT",
        regime_state="TREND_DOWN",
        pde_state="PDE_PULLBACK_ACTIVE",
        break_state="BREAK_NONE",
        damage_state="INTACT",
        root_id="r1",
        parent_id="p2",
        parent_version=2,
    )
    assert rec_short_pb.direction == "SHORT"
    assert rec_short_pb.role_state == RoleState.PULLBACK


def test_location_engine_obstacle_assessment() -> None:
    """Verifies LocationEngine spatial context calculation."""
    engine = LocationEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0845")

    rec_open = engine.evaluate(
        b,
        protected_high=Decimal("1.1000"),
        protected_low=Decimal("1.0600"),
        v_local=v_local,
        root_id="r1",
        parent_id="p1",
        parent_version=1,
    )
    assert rec_open.location_state == LocationState.OPEN

    rec_blocked = engine.evaluate(
        b,
        protected_high=Decimal("1.1000"),
        protected_low=Decimal("1.0600"),
        v_local=v_local,
        root_id="r1",
        parent_id="p2",
        parent_version=2,
        htf_obstacle_price=Decimal("1.0846"),
    )
    assert rec_blocked.location_state == LocationState.BLOCKED


def test_ambiguity_propagation() -> None:
    """Verifies that UNKNOWN / CHAOTIC inputs propagate explicit AMBIGUOUS state."""
    role_engine = RoleEngine("EURUSD", timeframe="1M")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0845")

    rec = role_engine.evaluate(
        b,
        direction="NEUTRAL",
        regime_state="CHAOTIC",
        pde_state="PDE_NONE",
        break_state="BREAK_NONE",
        damage_state="INTACT",
        root_id="r1",
        parent_id="p1",
        parent_version=1,
    )
    assert rec.role_state == RoleState.AMBIGUOUS


def test_regime_role_location_forbidden_capabilities() -> None:
    """Verifies Regime, Role, and Location engines have no order placement or execution methods."""
    r_eng = RegimeEngine("EURUSD")
    role_eng = RoleEngine("EURUSD")
    loc_eng = LocationEngine("EURUSD")

    forbidden = ["create_execution_intent", "submit_order", "modify_position", "close_position_strategically"]
    for eng in (r_eng, role_eng, loc_eng):
        for m in forbidden:
            assert not hasattr(eng, m)

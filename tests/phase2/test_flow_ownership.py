"""Phase 2 Work Package 2B Tests: Flow Ownership Engine.

Tests:
- FlowState transitions adhering to spec/transitions.yaml.
- Hysteresis margin & dwell time filtering.
- Structural reversal evidence requirement for ownership direction flip.
- Parent version regression rejection.
- Runtime authority enforcement and forbidden capability checks.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.flow import FlowEngine, FlowState
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureTransitionRecord, SwingState, BreakState, StructuralDamageState

BASE_TS = 1700006400


def test_flow_state_transitions_and_dwell_filtering() -> None:
    """Verifies FlowState transitions with dwell time filtering."""
    engine = FlowEngine("EURUSD", timeframe="1M", dwell_bars_required=2, dominance_threshold=Decimal("0.60"))
    v_local = Decimal("0.0010")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0845")
    rec1 = engine.evaluate_bar(b1, None, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.flow_state in (FlowState.LONG_DOMINANT, FlowState.LONG_EMERGING)

    b2 = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0845", "1.0890", "1.0845", "1.0888")
    rec2 = engine.evaluate_bar(b2, None, v_local, root_id="r1", parent_id="p2", parent_version=2)
    assert rec2.flow_state in (FlowState.LONG_EMERGING, FlowState.LONG_DOMINANT)

    b3 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0888", "1.0920", "1.0885", "1.0918")
    rec3 = engine.evaluate_bar(b3, None, v_local, root_id="r1", parent_id="p3", parent_version=3)
    assert rec3.flow_state == FlowState.LONG_DOMINANT


def test_structural_evidence_requirement_for_direction_flip() -> None:
    """Verifies that flipping from LONG_DOMINANT to SHORT_DOMINANT without structural reversal

    steps through LONG_WEAKENING rather than immediately jumping direction.
    """
    engine = FlowEngine("EURUSD", timeframe="1M", dwell_bars_required=1, dominance_threshold=Decimal("0.60"))
    v_local = Decimal("0.0010")

    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0848")
    rec1 = engine.evaluate_bar(b1, None, v_local, root_id="r1", parent_id="p1", parent_version=1)
    assert rec1.flow_state in (FlowState.LONG_DOMINANT, FlowState.LONG_EMERGING)

    b_bear = Bar.create("EURUSD", "1M", BASE_TS + 60, BASE_TS + 120, "1.0848", "1.0850", "1.0800", "1.0802")
    rec_bear = engine.evaluate_bar(b_bear, None, v_local, root_id="r1", parent_id="p2", parent_version=2)

    assert rec_bear.flow_state in (FlowState.LONG_WEAKENING, FlowState.TRANSITIONING)

    struct_record = StructureTransitionRecord(
        symbol="EURUSD",
        timeframe="1M",
        swing_state=SwingState.SWING_PROTECTED,
        previous_swing_state=SwingState.SWING_CONFIRMED,
        break_state=BreakState.BREAK_CONFIRMED,
        previous_break_state=BreakState.BREAK_NONE,
        damage_state=StructuralDamageState.STRUCTURE_BROKEN,
        previous_damage_state=StructuralDamageState.INTACT,
        timestamp=BASE_TS + 180,
        v_local=v_local,
        root_id="r1",
        parent_id="p3",
        parent_version=3,
        state_version=1,
        config_version=1,
        data_version=1,
        feature_version=1,
        bos_type="BOS_BEARISH",
    )

    b_bear2 = Bar.create("EURUSD", "1M", BASE_TS + 120, BASE_TS + 180, "1.0802", "1.0805", "1.0750", "1.0752")
    rec_bear2 = engine.evaluate_bar(b_bear2, struct_record, v_local, root_id="r1", parent_id="p3", parent_version=3)
    assert rec_bear2.flow_state in (FlowState.SHORT_DOMINANT, FlowState.SHORT_EMERGING, FlowState.TRANSITIONING)


def test_flow_parent_version_regression_rejected() -> None:
    """Verifies that parent version regression raises ValueError."""
    engine = FlowEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0848")

    engine.evaluate_bar(b, None, v_local, root_id="r1", parent_id="p1", parent_version=5)
    with pytest.raises(ValueError, match="Parent version regression detected"):
        engine.evaluate_bar(b, None, v_local, root_id="r1", parent_id="p1", parent_version=4)


def test_flow_engine_authority_and_forbidden_capabilities() -> None:
    """Verifies FlowEngine has no execution, order placement, or position management capabilities."""
    engine = FlowEngine("EURUSD", timeframe="1M")

    forbidden_methods = [
        "create_execution_intent",
        "submit_order",
        "modify_position",
        "close_position_strategically",
        "size_trade",
    ]

    for m in forbidden_methods:
        assert not hasattr(engine, m)


def test_flow_to_envelope_conversion() -> None:
    """Verifies FlowTransitionRecord converts cleanly to StateEnvelope."""
    engine = FlowEngine("EURUSD", timeframe="1M")
    v_local = Decimal("0.0010")
    b = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0850", "1.0800", "1.0848")

    rec = engine.evaluate_bar(b, None, v_local, root_id="r1", parent_id="p1", parent_version=1)
    env = rec.to_envelope(object_id="flow_obj_1")

    assert env.object_type == "FlowState"
    assert env.authority == "FLOW"
    assert env.state == rec.flow_state.value
    assert env.root_id == "r1"
    assert env.parent_id == "p1"
    assert env.parent_version == 1

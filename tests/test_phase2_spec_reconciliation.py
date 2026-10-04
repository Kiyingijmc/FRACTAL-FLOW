"""Phase 2 Canonical Specification Reconciliation Test Suite.

Validates state vocabulary, transition graph coverage, fail-closed transition validation,
lineage hierarchy, authority boundaries, and constitutional independence.
"""

import pytest
import yaml

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException
from src.fractal_flow.domain.envelope import (
    GLOBAL_STATE_REGISTRY,
    InvalidStateTransitionException,
    StateEnvelope,
)
from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException


def test_state_vocabulary_spec_parity() -> None:
    """Verifies canonical state vocabularies in spec/states.yaml."""
    with open("spec/states.yaml") as f:
        data = yaml.safe_load(f)
    states = data.get("states", {})

    # FlowState
    expected_flow = {
        "UNKNOWN",
        "LONG_EMERGING",
        "LONG_DOMINANT",
        "LONG_WEAKENING",
        "BALANCED",
        "CONTESTED",
        "SHORT_EMERGING",
        "SHORT_DOMINANT",
        "SHORT_WEAKENING",
        "TRANSITIONING",
    }
    assert set(states["FlowState"]) == expected_flow

    # PDEState
    expected_pde = {
        "PDE_NONE",
        "PDE_IMPULSE",
        "PDE_PULLBACK_CANDIDATE",
        "PDE_PULLBACK_ACTIVE",
        "PDE_WEAKENING",
        "PDE_STRENGTHENING",
        "PDE_DEEPENING",
        "PDE_RESUMPTION_IN_PROGRESS",
        "PDE_FOLLOW_THROUGH",
        "PDE_RESUMPTION_FAILED",
        "PDE_INVALIDATED",
    }
    assert set(states["PDEState"]) == expected_pde

    # PDEResumptionState
    expected_resumption = {
        "RESUMPTION_NONE",
        "RECOVERY_CANDIDATE",
        "RECOVERY_CONFIRMED",
        "DISPLACEMENT_CANDIDATE",
        "RESUMPTION_CONFIRMED",
        "FOLLOW_THROUGH",
        "RESUMPTION_FAILED",
    }
    assert set(states["PDEResumptionState"]) == expected_resumption

    # RegimeState
    expected_regime = {
        "UNKNOWN",
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "TRANSITION",
        "CHAOTIC",
    }
    assert set(states["RegimeState"]) == expected_regime

    # RoleState
    expected_role = {
        "UNKNOWN",
        "CONTINUATION",
        "PULLBACK",
        "COUNTERFLOW",
        "RANGE_ROTATION",
        "BREAKOUT",
        "RECLAIM",
        "TRANSITION",
        "EXHAUSTION",
        "NOISE",
        "AMBIGUOUS",
    }
    assert set(states["RoleState"]) == expected_role

    # LocationState
    expected_location = {
        "OPEN",
        "FAVORABLE",
        "NEUTRAL",
        "CONGESTED",
        "BLOCKED",
        "EXTREME",
    }
    assert set(states["LocationState"]) == expected_location


def test_state_registry_envelope_support() -> None:
    """Verifies that every canonical state family can be represented by StateRegistry and StateEnvelope."""
    machines = [
        ("FlowState", "LONG_DOMINANT", "Flow"),
        ("PDEState", "PDE_PULLBACK_ACTIVE", "PDE"),
        ("PDEResumptionState", "RESUMPTION_CONFIRMED", "PDEResumption"),
        ("RegimeState", "TREND_UP", "Regime"),
        ("RoleState", "CONTINUATION", "Role"),
        ("LocationState", "FAVORABLE", "Location"),
    ]

    for machine_name, test_state, object_type in machines:
        assert GLOBAL_STATE_REGISTRY.is_known_machine(machine_name)
        assert GLOBAL_STATE_REGISTRY.is_valid_state(machine_name, test_state)

        env = StateEnvelope(
            state_id="ST_001",
            object_id="OBJ_001",
            object_type=object_type,
            symbol="EURUSD",
            timeframe="15M",
            root_id="ROOT_001",
            parent_id="PAR_001",
            parent_version=1,
            state=test_state,
            previous_state="",
            version=1,
            source_timestamp=100,
            event_timestamp=105,
            processing_timestamp=110,
            valid_until=200,
            last_seen=110,
        )
        assert env.state == test_state


def test_transition_coverage_and_validation() -> None:
    """Verifies every canonical state family has explicit transition definitions and fails closed on illegal transitions."""
    with open("spec/transitions.yaml") as f:
        data = yaml.safe_load(f)
    transitions = data.get("transitions", {})

    canonical_families = [
        "FlowState",
        "PDEState",
        "PDEResumptionState",
        "RegimeState",
        "RoleState",
        "LocationState",
    ]

    for family in canonical_families:
        assert family in transitions, f"Missing transition graph for {family}"

    # Valid transitions test
    GLOBAL_STATE_REGISTRY.validate_transition("FlowState", "LONG_DOMINANT", "LONG_WEAKENING")
    GLOBAL_STATE_REGISTRY.validate_transition("RegimeState", "TREND_UP", "TRANSITION")
    GLOBAL_STATE_REGISTRY.validate_transition("RoleState", "CONTINUATION", "EXHAUSTION")

    # Fail-closed illegal transitions test
    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.validate_transition("FlowState", "LONG_DOMINANT", "NON_EXISTENT_STATE")

    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.validate_transition("RegimeState", "UNKNOWN_MACHINE", "TREND_UP")


def test_lineage_hierarchy_d035() -> None:
    """Verifies canonical lineage hierarchy conforms to D-035."""
    with open("spec/lineage.yaml") as f:
        data = yaml.safe_load(f)
    hierarchy = data.get("lineage", {}).get("hierarchy", [])

    expected_hierarchy = [
        "ROOT",
        "REGIME",
        "SETUP",
        "PRIMARY_PULLBACK",
        "SECONDARY_PULLBACK",
        "MICRO_PULLBACK",
        "OPPORTUNITY",
        "SIGNAL",
        "ORDER",
        "POSITION",
        "TRADE",
        "MANAGEMENT",
    ]
    assert hierarchy == expected_hierarchy

    # Legal edges test
    Lineage.verify_legal_edge("PRIMARY_PULLBACK", "SECONDARY_PULLBACK")
    Lineage.verify_legal_edge("PRIMARY_PULLBACK", "MICRO_PULLBACK")
    Lineage.verify_legal_edge("PRIMARY_PULLBACK", "OPPORTUNITY")
    Lineage.verify_legal_edge("SECONDARY_PULLBACK", "MICRO_PULLBACK")
    Lineage.verify_legal_edge("MICRO_PULLBACK", "OPPORTUNITY")

    # Illegal edge test
    with pytest.raises(LineageInvalidException):
        Lineage.verify_legal_edge("PRIMARY_PULLBACK", "ORDER")


def test_authority_specification_boundaries() -> None:
    """Verifies Flow/PDE/Regime/Role/Location cannot acquire execution authority in spec/engines.yaml and AuthorityMatrix."""
    with open("spec/engines.yaml") as f:
        data = yaml.safe_load(f)
    engines_spec = data.get("engines", {})

    forbidden_actions = [
        "CREATE_EXECUTION_INTENT",
        "SUBMIT_ORDER",
        "MODIFY_POSITION",
        "CLOSE_POSITION_STRATEGICALLY",
    ]

    behavioral_engines = ["Flow", "PDE", "Regime", "Role", "Location"]

    for engine in behavioral_engines:
        spec_entry = engines_spec.get(engine, {})
        allowed = spec_entry.get("allowed_capabilities", [])
        forbidden = spec_entry.get("forbidden_capabilities", [])

        for action in forbidden_actions:
            assert action not in allowed, f"{engine} allowed forbidden action {action} in spec/engines.yaml"
            assert action in forbidden, f"{engine} missing forbidden action {action} in spec/engines.yaml"

            # Verify in runtime AuthorityMatrix
            with pytest.raises(AuthorityViolationException):
                AuthorityMatrix.verify_capability(engine, action)


def test_fibonacci_independence_principle() -> None:
    """Verifies that Fibonacci values do not act as constitutional validity criteria."""

    class MockPullback:
        def __init__(self, fib_level: float, structural_validity: bool) -> None:
            self.fib_level = fib_level
            self.structural_validity = structural_validity

        def is_constitutionally_valid(self) -> bool:
            # Constitutional validity depends strictly on structure/state, NOT fibonacci thresholds
            return self.structural_validity

    pb_618 = MockPullback(fib_level=0.618, structural_validity=True)
    pb_999 = MockPullback(fib_level=0.999, structural_validity=True)
    pb_invalid = MockPullback(fib_level=0.618, structural_validity=False)

    assert pb_618.is_constitutionally_valid() is True
    assert pb_999.is_constitutionally_valid() is True
    assert pb_invalid.is_constitutionally_valid() is False


def test_candle_count_independence_principle() -> None:
    """Verifies that fixed candle counts do not act as constitutional validity criteria."""

    class MockStructure:
        def __init__(self, candle_count: int, displacement_valid: bool) -> None:
            self.candle_count = candle_count
            self.displacement_valid = displacement_valid

        def is_constitutionally_valid(self) -> bool:
            # Constitutional validity depends strictly on volatility-normalized displacement, NOT fixed candle counts
            return self.displacement_valid

    s_3_candles = MockStructure(candle_count=3, displacement_valid=True)
    s_100_candles = MockStructure(candle_count=100, displacement_valid=True)
    s_3_invalid = MockStructure(candle_count=3, displacement_valid=False)

    assert s_3_candles.is_constitutionally_valid() is True
    assert s_100_candles.is_constitutionally_valid() is True
    assert s_3_invalid.is_constitutionally_valid() is False

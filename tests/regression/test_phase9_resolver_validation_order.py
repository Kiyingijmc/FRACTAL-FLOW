"""Phase 9 regression tests for fail-closed resolver validation order."""

import pytest

from src.fractal_flow.domain.envelope import (
    GLOBAL_STATE_REGISTRY,
    InvalidStateTransitionException,
)


def test_resolver_rejects_unknown_machine_even_for_equal_states() -> None:
    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.resolve_transition("UNKNOWN_MACHINE", "UNKNOWN_STATE", "UNKNOWN_STATE")


def test_resolver_rejects_unknown_equal_state_for_known_machine() -> None:
    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.resolve_transition("RegimeState", "NOT_A_REGIME_STATE", "NOT_A_REGIME_STATE")


def test_resolver_preserves_valid_equal_state_noop() -> None:
    assert GLOBAL_STATE_REGISTRY.resolve_transition("RegimeState", "CHAOTIC", "CHAOTIC") == ()


def test_resolver_preserves_valid_shortest_legal_route() -> None:
    assert GLOBAL_STATE_REGISTRY.resolve_transition("RegimeState", "CHAOTIC", "TREND_UP") == ("TRANSITION", "TREND_UP")

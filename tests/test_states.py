"""Tests for State Envelopes, Transition Validation, and Reason Codes."""

import pytest
from src.fractal_flow.domain.envelope import StateEnvelope, InvalidStateTransitionException
from src.fractal_flow.domain.reason_codes import ReasonCode


def test_valid_state_transitions() -> None:
    env = StateEnvelope(
        state_id="s1",
        object_id="p1",
        object_type="PDE",
        symbol="EURUSD",
        timeframe="15M",
        root_id="r1",
        parent_id="par1",
        parent_version=1,
        state="PDE_NONE",
        previous_state="PDE_NONE",
        version=1,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        valid_until=1000,
        last_seen=100,
    )
    env.transition_to("PDE_IMPULSE")
    assert env.state == "PDE_IMPULSE"
    assert env.previous_state == "PDE_NONE"
    assert env.version == 2


def test_illegal_state_transition_fails_closed() -> None:
    env = StateEnvelope(
        state_id="s1",
        object_id="p1",
        object_type="PDE",
        symbol="EURUSD",
        timeframe="15M",
        root_id="r1",
        parent_id="par1",
        parent_version=1,
        state="PDE_INVALIDATED",
        previous_state="PDE_DEEPENING",
        version=5,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        valid_until=1000,
        last_seen=100,
    )
    with pytest.raises(InvalidStateTransitionException) as exc_info:
        env.transition_to("PDE_PULLBACK_ACTIVE")
    assert "Illegal state transition" in str(exc_info.value)
    assert env.state == "PDE_INVALIDATED"  # Unchanged


def test_reason_code_values() -> None:
    assert ReasonCode.NEWS_LOCKDOWN == "NEWS_LOCKDOWN"
    assert ReasonCode.PARENT_INVALID == "PARENT_INVALID"
    assert ReasonCode.EXECUTION_UNKNOWN == "EXECUTION_UNKNOWN"

"""Tests for State Envelopes, Fail-Closed Transition Validation, and Reason Codes."""

import pytest
from src.fractal_flow.domain.envelope import StateEnvelope, InvalidStateTransitionException, StateRegistry
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


def test_unknown_object_type_fails_closed() -> None:
    with pytest.raises(ValueError) as exc:
        StateEnvelope(
            state_id="s1",
            object_id="p1",
            object_type="UNKNOWN_OBJECT",
            symbol="EURUSD",
            timeframe="15M",
            root_id="r1",
            parent_id="par1",
            parent_version=1,
            state="SOME_STATE",
            previous_state="SOME_STATE",
            version=1,
            source_timestamp=100,
            event_timestamp=100,
            processing_timestamp=100,
            valid_until=1000,
            last_seen=100,
        )
    assert "maps to unknown machine" in str(exc.value)


def test_unknown_current_state_fails_closed() -> None:
    with pytest.raises(ValueError) as exc:
        StateEnvelope(
            state_id="s1",
            object_id="p1",
            object_type="PDE",
            symbol="EURUSD",
            timeframe="15M",
            root_id="r1",
            parent_id="par1",
            parent_version=1,
            state="INVALID_PDE_STATE",
            previous_state="PDE_NONE",
            version=1,
            source_timestamp=100,
            event_timestamp=100,
            processing_timestamp=100,
            valid_until=1000,
            last_seen=100,
        )
    assert "Invalid canonical current state" in str(exc.value)


def test_unknown_target_state_transition_fails_closed() -> None:
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
    with pytest.raises(InvalidStateTransitionException) as exc:
        env.transition_to("NONEXISTENT_TARGET_STATE")
    assert "Unknown target state" in str(exc.value)


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

"""Tests for StateRegistry Fail-Closed Startup Validation."""

import pytest
from src.fractal_flow.domain.envelope import StateRegistry


def test_stateregistry_successful_canonical_startup():
    registry = StateRegistry(states_path="spec/states.yaml", transitions_path="spec/transitions.yaml")
    assert registry.is_known_machine("FlowState")
    assert registry.is_valid_state("FlowState", "LONG_DOMINANT")


def test_stateregistry_missing_states_spec_file_raises():
    with pytest.raises(FileNotFoundError, match="states specification file not found"):
        StateRegistry(states_path="spec/non_existent_states.yaml", transitions_path="spec/transitions.yaml")


def test_stateregistry_missing_transitions_spec_file_raises():
    with pytest.raises(FileNotFoundError, match="transitions specification file not found"):
        StateRegistry(states_path="spec/states.yaml", transitions_path="spec/non_existent_transitions.yaml")


def test_stateregistry_malformed_yaml_raises(tmp_path):
    bad_states = tmp_path / "bad_states.yaml"
    bad_states.write_text("states: [unclosed_list")

    with pytest.raises(ValueError, match="malformed states specification"):
        StateRegistry(states_path=str(bad_states), transitions_path="spec/transitions.yaml")


def test_stateregistry_invalid_schema_root_raises(tmp_path):
    invalid_states = tmp_path / "invalid_states.yaml"
    invalid_states.write_text("invalid_root: True")

    with pytest.raises(ValueError, match="missing or invalid 'states' root dict"):
        StateRegistry(states_path=str(invalid_states), transitions_path="spec/transitions.yaml")

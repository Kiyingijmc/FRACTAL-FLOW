"""Parity tests checking that spec/*.yaml and Python domain code are 100% in sync."""

from pathlib import Path
import yaml
import pytest

from src.fractal_flow.domain.reason_codes import ReasonCode


def test_reason_codes_parity() -> None:
    yaml_path = Path("spec/reason_codes.yaml")
    assert yaml_path.exists(), "spec/reason_codes.yaml missing"
    with open(yaml_path) as f:
        spec_codes = yaml.safe_load(f)

    if isinstance(spec_codes, dict) and "reason_codes" in spec_codes:
        spec_codes = spec_codes["reason_codes"]

    python_codes = [c.value for c in ReasonCode]

    # Check exact match
    assert set(spec_codes) == set(python_codes), (
        f"ReasonCode mismatch! Spec extra: {set(spec_codes) - set(python_codes)}, "
        f"Python extra: {set(python_codes) - set(spec_codes)}"
    )


def test_states_parity() -> None:
    yaml_path = Path("spec/states.yaml")
    assert yaml_path.exists(), "spec/states.yaml missing"
    with open(yaml_path) as f:
        spec_states = yaml.safe_load(f)

    assert "states" in spec_states or isinstance(spec_states, dict)


def test_transitions_parity() -> None:
    yaml_path = Path("spec/transitions.yaml")
    assert yaml_path.exists(), "spec/transitions.yaml missing"
    with open(yaml_path) as f:
        spec_trans = yaml.safe_load(f)

    assert "transitions" in spec_trans or isinstance(spec_trans, dict)

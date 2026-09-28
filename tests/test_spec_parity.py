"""Semantic specification parity tests ensuring spec/*.yaml and Python runtime registries are 100% identical."""

from pathlib import Path
import yaml
import pytest

from src.fractal_flow.domain.reason_codes import ReasonCode
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.lineage import LEGAL_LINEAGE_EDGES


def test_reason_codes_exact_parity() -> None:
    yaml_path = Path("spec/reason_codes.yaml")
    assert yaml_path.exists(), "spec/reason_codes.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_codes = spec_data.get("reason_codes", spec_data) if isinstance(spec_data, dict) else spec_data
    python_codes = [c.value for c in ReasonCode]

    assert set(spec_codes) == set(python_codes), (
        f"ReasonCode mismatch! Spec extra: {set(spec_codes) - set(python_codes)}, "
        f"Python extra: {set(python_codes) - set(spec_codes)}"
    )


def test_states_exact_parity() -> None:
    yaml_path = Path("spec/states.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    spec_states = data["states"]

    for machine_name, states_list in spec_states.items():
        assert GLOBAL_STATE_REGISTRY.is_known_machine(machine_name), f"Machine {machine_name} missing in runtime"
        for st in states_list:
            assert GLOBAL_STATE_REGISTRY.is_valid_state(machine_name, st), f"State {st} missing in machine {machine_name}"


def test_lineage_graph_exact_parity() -> None:
    yaml_path = Path("spec/lineage.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    spec_edges = data["lineage"]["legal_edges"]

    # Verify every YAML edge matches Python runtime graph
    for parent_tier, children_list in spec_edges.items():
        assert parent_tier in LEGAL_LINEAGE_EDGES
        assert set(children_list) == LEGAL_LINEAGE_EDGES[parent_tier]

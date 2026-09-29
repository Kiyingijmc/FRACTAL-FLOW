"""Semantic specification parity tests ensuring spec/*.yaml and Python runtime registries are 100% identically mapped bidirectionally."""

from pathlib import Path
import yaml

from src.fractal_flow.domain.reason_codes import ReasonCode
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.lineage import LEGAL_LINEAGE_EDGES
from src.fractal_flow.domain.entry import EntryModel, OrderType


def test_reason_codes_exact_parity() -> None:
    yaml_path = Path("spec/reason_codes.yaml")
    assert yaml_path.exists(), "spec/reason_codes.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_codes = set(
        spec_data.get("reason_codes", spec_data)
        if isinstance(spec_data, dict)
        else spec_data
    )
    python_codes = set(c.value for c in ReasonCode)

    assert spec_codes == python_codes, (
        f"ReasonCode mismatch! Spec extra: {spec_codes - python_codes}, "
        f"Python extra: {python_codes - spec_codes}"
    )


def test_entry_models_exact_parity() -> None:
    yaml_path = Path("spec/entry_models.yaml")
    assert yaml_path.exists(), "spec/entry_models.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_models = set(
        spec_data.get("entry_models", spec_data)
        if isinstance(spec_data, dict)
        else spec_data
    )
    python_models = set(m.value for m in EntryModel)

    assert spec_models == python_models, (
        f"EntryModel mismatch! Spec extra: {spec_models - python_models}, "
        f"Python extra: {python_models - spec_models}"
    )


def test_order_types_exact_parity() -> None:
    yaml_path = Path("spec/order_types.yaml")
    assert yaml_path.exists(), "spec/order_types.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_types = set(
        spec_data.get("order_types", spec_data)
        if isinstance(spec_data, dict)
        else spec_data
    )
    python_types = set(ot.value for ot in OrderType)

    assert spec_types == python_types, (
        f"OrderType mismatch! Spec extra: {spec_types - python_types}, "
        f"Python extra: {python_types - spec_types}"
    )


def test_states_bidirectional_parity() -> None:
    yaml_path = Path("spec/states.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    spec_states = data["states"]

    # 1. Spec -> Runtime check
    for machine_name, states_list in spec_states.items():
        assert GLOBAL_STATE_REGISTRY.is_known_machine(machine_name), (
            f"Machine {machine_name} missing in runtime"
        )
        for st in states_list:
            assert GLOBAL_STATE_REGISTRY.is_valid_state(machine_name, st), (
                f"State {st} missing in machine {machine_name}"
            )

    # 2. Runtime -> Spec check
    runtime_machines = set(GLOBAL_STATE_REGISTRY._states.keys())
    spec_machines = set(spec_states.keys())
    assert runtime_machines == spec_machines, (
        f"State machine mismatch! Spec extra: {spec_machines - runtime_machines}, "
        f"Runtime extra: {runtime_machines - spec_machines}"
    )


def test_transitions_destinations_are_valid_canonical_states() -> None:
    yaml_path = Path("spec/transitions.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        trans_data = yaml.safe_load(f)
    spec_transitions = trans_data["transitions"]

    for machine_name, trans_map in spec_transitions.items():
        assert GLOBAL_STATE_REGISTRY.is_known_machine(machine_name), (
            f"Transition machine '{machine_name}' missing from states spec"
        )
        for source_state, destinations in trans_map.items():
            assert GLOBAL_STATE_REGISTRY.is_valid_state(machine_name, source_state), (
                f"Source state '{source_state}' in transition table is not a valid canonical state for '{machine_name}'"
            )
            for dest_state in destinations:
                assert GLOBAL_STATE_REGISTRY.is_valid_state(machine_name, dest_state), (
                    f"Destination state '{dest_state}' in transition table is not a valid canonical state for '{machine_name}'"
                )


def test_lineage_graph_bidirectional_parity() -> None:
    yaml_path = Path("spec/lineage.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    spec_edges = data["lineage"]["legal_edges"]

    spec_parents = set(spec_edges.keys())
    runtime_parents = set(LEGAL_LINEAGE_EDGES.keys())
    assert spec_parents == runtime_parents, (
        f"Lineage graph parent mismatch! {spec_parents ^ runtime_parents}"
    )

    for parent_tier, children_list in spec_edges.items():
        assert set(children_list) == LEGAL_LINEAGE_EDGES[parent_tier], (
            f"Lineage graph children mismatch for tier '{parent_tier}'"
        )

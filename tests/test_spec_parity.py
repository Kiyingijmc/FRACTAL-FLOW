"""Semantic specification parity tests ensuring spec/*.yaml and Python runtime registries are 100% identically mapped bidirectionally."""

from pathlib import Path

import yaml

from src.fractal_flow.domain.entry import EntryModel, OrderType
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.lineage import LEGAL_LINEAGE_EDGES
from src.fractal_flow.domain.reason_codes import ReasonCode


def test_reason_codes_exact_parity() -> None:
    yaml_path = Path("spec/reason_codes.yaml")
    assert yaml_path.exists(), "spec/reason_codes.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_codes = set(spec_data.get("reason_codes", spec_data) if isinstance(spec_data, dict) else spec_data)
    python_codes = set(c.value for c in ReasonCode)

    assert spec_codes == python_codes, (
        f"ReasonCode mismatch! Spec extra: {spec_codes - python_codes}, Python extra: {python_codes - spec_codes}"
    )


def test_entry_models_exact_parity() -> None:
    yaml_path = Path("spec/entry_models.yaml")
    assert yaml_path.exists(), "spec/entry_models.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_models = set(spec_data.get("entry_models", spec_data) if isinstance(spec_data, dict) else spec_data)
    python_models = set(m.value for m in EntryModel)

    assert spec_models == python_models, (
        f"EntryModel mismatch! Spec extra: {spec_models - python_models}, Python extra: {python_models - spec_models}"
    )


def test_order_types_exact_parity() -> None:
    yaml_path = Path("spec/order_types.yaml")
    assert yaml_path.exists(), "spec/order_types.yaml missing"
    with open(yaml_path) as f:
        spec_data = yaml.safe_load(f)

    spec_types = set(spec_data.get("order_types", spec_data) if isinstance(spec_data, dict) else spec_data)
    python_types = set(ot.value for ot in OrderType)

    assert spec_types == python_types, (
        f"OrderType mismatch! Spec extra: {spec_types - python_types}, Python extra: {python_types - spec_types}"
    )


def test_states_exact_parity() -> None:
    """Canonical test symbol verifying state registry parity against spec/states.yaml."""
    yaml_path = Path("spec/states.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    spec_states = data["states"]

    # 1. Spec -> Runtime check
    for machine_name, states_list in spec_states.items():
        assert GLOBAL_STATE_REGISTRY.is_known_machine(machine_name), f"Machine {machine_name} missing in runtime"
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


def test_states_bidirectional_parity() -> None:
    test_states_exact_parity()


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
    assert spec_parents == runtime_parents, f"Lineage graph parent mismatch! {spec_parents ^ runtime_parents}"

    for parent_tier, children_list in spec_edges.items():
        assert set(children_list) == LEGAL_LINEAGE_EDGES[parent_tier], (
            f"Lineage graph children mismatch for tier '{parent_tier}'"
        )


def test_artifact_and_invariant_consistency() -> None:
    yaml_path = Path("spec/invariants.yaml")
    assert yaml_path.exists()
    with open(yaml_path) as f:
        inv_data = yaml.safe_load(f)
    invariants = inv_data["invariants"]

    assert len(invariants) == 42, f"Expected 42 invariants, got {len(invariants)}"

    status_counts = {}
    for inv in invariants:
        st = inv["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    assert sum(status_counts.values()) == 42
    assert (
        status_counts.get("ENFORCED", 0)
        + status_counts.get("INTEGRATION_VERIFIED", 0)
        + status_counts.get("SPECIFIED_ONLY", 0)
        == 42
    )


def test_phase1_evidence_manifest_parity() -> None:
    """Verifies spec/phase1_evidence.yaml machine manifest parity against spec/invariants.yaml and code references."""
    evidence_path = Path("spec/phase1_evidence.yaml")
    assert evidence_path.exists(), "spec/phase1_evidence.yaml missing"
    with open(evidence_path) as f:
        ev_data = yaml.safe_load(f)

    assert "phase1_evidence" in ev_data
    evidence = ev_data["phase1_evidence"]
    assert len(evidence) == 42, f"Expected 42 entries in evidence manifest, got {len(evidence)}"

    invariants_path = Path("spec/invariants.yaml")
    with open(invariants_path) as f:
        inv_data = yaml.safe_load(f)
    invariants_map = {inv["id"]: inv for inv in inv_data["invariants"]}

    for item in evidence:
        item_id = item["id"]
        assert item_id in invariants_map, f"Evidence item ID {item_id} missing from spec/invariants.yaml"
        inv = invariants_map[item_id]

        # Check required fields
        for field in ("title", "status", "implementation_refs", "test_refs", "evidence_type", "limitation", "scope"):
            assert field in item, f"Evidence item {item_id} missing required field '{field}'"

        # Check status agreement between evidence and invariants spec
        assert item["status"] == inv["status"], (
            f"Status mismatch for invariant {item_id}: evidence='{item['status']}' vs invariants='{inv['status']}'"
        )

        # Check implementation refs exist on disk
        for impl_ref in item["implementation_refs"]:
            ref_path = Path(impl_ref)
            assert ref_path.exists(), f"Evidence item {item_id} implementation_ref '{impl_ref}' does not exist on disk!"

"""Tests for PGVF Invariant Registry Engine."""

import pytest

from tools.pfgv.errors import InvariantViolationError
from tools.pfgv.invariants import InvariantRegistry


def test_valid_invariant_registry_loading() -> None:
    registry = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    assert len(registry.invariants) >= 10
    inv1 = registry.get("PGVF-001")
    assert inv1.name == "agent_non_authority"
    assert inv1.severity == "P0"
    assert inv1.blocking is True


def test_all_initial_invariants_registered() -> None:
    registry = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    expected_ids = [f"PGVF-{i:03d}" for i in range(1, 11)]
    verified = registry.verify_required_invariants(expected_ids)
    assert len(verified) == 10


def test_missing_required_invariant_fails() -> None:
    registry = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    with pytest.raises(InvariantViolationError, match="Invariant 'PGVF-999' not found"):
        registry.verify_required_invariants(["PGVF-999"])


def test_non_blocking_required_invariant_fails() -> None:
    bad_data = {
        "invariants": {
            "PGVF-001": {
                "id": "PGVF-001",
                "name": "agent_non_authority",
                "severity": "P0",
                "category": "governance",
                "statement": "stmt",
                "blocking": False,  # Non-blocking!
                "authority": "gov",
                "positive_tests": ["p1"],
                "negative_tests": ["n1"],
                "required_evidence": ["e1"],
                "mutation_tests": ["m1"],
            }
        }
    }
    registry = InvariantRegistry.from_dict(bad_data)
    with pytest.raises(InvariantViolationError, match="required invariants must be blocking"):
        registry.verify_required_invariants(["PGVF-001"])


def test_invariant_registry_hash_determinism() -> None:
    reg1 = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    reg2 = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    assert reg1.compute_hash() == reg2.compute_hash()

"""Governance Integrity Tests - Testing the Governance System Against Itself."""

import copy

import pytest

from tools.pfgv.authority import AuthorityModel
from tools.pfgv.contract import PhaseContract
from tools.pfgv.errors import AuthorityError, InvariantViolationError, ScopeViolationError
from tools.pfgv.evidence import EvidenceRecord
from tools.pfgv.invariants import InvariantRegistry
from tools.pfgv.scope import ScopePolicy


def test_agent_cannot_self_authorize_status_as_verified() -> None:
    """PGVF-001 / PGVF-010: Proves that an agent assertion (E0) claiming VERIFIED cannot pass independent verification acceptance."""
    agent_assertion_evidence = EvidenceRecord.from_dict(
        {
            "evidence_id": "EV-AGENT-SELF-APPROVAL",
            "type": "agent_assertion",
            "producer": "jules_agent",
            "producer_version": "1.0",
            "target_commit": "74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d",
            "target_tree": "abc123tree",
            "timestamp": "2025-10-04T00:00:00Z",
            "source": "agent_self_attestation",
            "claim": {"status": "VERIFIED", "all_passed": True},
            "result": "PASS",
            "verification_level": "E0",  # E0 Agent Assertion
        }
    )

    contract = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")
    required_level = contract.minimum_verification_level  # "E2" or "E3"

    # Agent assertion fails minimum verification level check
    assert not agent_assertion_evidence.satisfies_level(required_level)


def test_agent_cannot_remove_required_invariant_without_detection() -> None:
    """PGVF-004 / PGVF-010: Proves that removing a required invariant from the registry is detected and rejected."""
    raw_registry = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    contract = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")

    # Simulate agent deleting PGVF-001 from invariants dictionary
    tampered_data = copy.deepcopy(raw_registry._raw_dict)
    del tampered_data["invariants"]["PGVF-001"]

    tampered_registry = InvariantRegistry.from_dict(tampered_data)

    # Registry hash changes
    assert tampered_registry.compute_hash() != raw_registry.compute_hash()

    # Verification against contract required invariants fails
    with pytest.raises(InvariantViolationError, match="Invariant 'PGVF-001' not found"):
        tampered_registry.verify_required_invariants(contract.required_invariants)


def test_agent_cannot_flip_blocking_flag_to_false_without_detection() -> None:
    """PGVF-010: Proves that weakening an invariant by changing blocking=True to blocking=False fails verification."""
    raw_registry = InvariantRegistry.from_file("docs/governance/PHASE_INVARIANTS.yaml")
    contract = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")

    tampered_data = copy.deepcopy(raw_registry._raw_dict)
    tampered_data["invariants"]["PGVF-001"]["blocking"] = False

    tampered_registry = InvariantRegistry.from_dict(tampered_data)

    # Verification fails because required invariants must be blocking
    with pytest.raises(InvariantViolationError, match="required invariants must be blocking"):
        tampered_registry.verify_required_invariants(contract.required_invariants)


def test_agent_cannot_bypass_scope_or_authority_silently() -> None:
    """PGVF-007 / PGVF-008: Proves that unauthorized production edits or execution authority expansion are blocked."""
    scope_policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    authority_model = AuthorityModel.from_file("docs/governance/AUTHORITY_MODEL.yaml")

    # Forbidden path edit
    with pytest.raises(ScopeViolationError):
        scope_policy.validate_changes(changed_files=["src/fractal_flow/domain/models.py"])

    # Undeclared authority addition
    tampered_auth = AuthorityModel.from_dict(
        {
            "phase_0_authority": {
                "informational": ["read_codebase"],
                "strategy": [],
                "risk": [],
                "execution": ["unauthorized_order_send"],
                "governance": ["validate_contract"],
                "verification": [],
            }
        }
    )
    contract = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")
    with pytest.raises(AuthorityError):
        authority_model.verify_no_undeclared_expansion(tampered_auth, contract.authority_map)


def test_governance_kernel_determinism() -> None:
    """Determinism Requirement: Identical inputs must yield identical output across multiple evaluations."""
    contract_file = "docs/governance/PHASE_EXECUTION_CONTRACT.md"
    invariants_file = "docs/governance/PHASE_INVARIANTS.yaml"
    scope_file = "docs/governance/SCOPE_POLICY.yaml"
    authority_file = "docs/governance/AUTHORITY_MODEL.yaml"

    results = []
    for _ in range(5):
        c = PhaseContract.from_file(contract_file)
        i = InvariantRegistry.from_file(invariants_file)
        s = ScopePolicy.from_file(scope_file)
        a = AuthorityModel.from_file(authority_file)

        results.append((c.compute_hash(), i.compute_hash(), s.compute_hash(), a.compute_hash()))

    # All 5 iterations must be strictly equal
    assert len(set(results)) == 1

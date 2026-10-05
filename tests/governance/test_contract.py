"""Tests for PGVF Contract Validation Engine."""

import pytest

from tools.pfgv.contract import PhaseContract
from tools.pfgv.errors import ContractError


def test_valid_contract_loading() -> None:
    contract = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")
    assert contract.phase_id == "PGVF-PHASE-0"
    assert contract.phase_name == "Governance Kernel"
    assert contract.minimum_verification_level == "E2"
    assert "PGVF-001" in contract.required_invariants
    assert contract.compute_hash() is not None
    assert len(contract.compute_hash()) == 64


def test_contract_missing_required_field_fails() -> None:
    bad_data = {
        "phase": {"id": "P0", "name": "Test"},  # missing version & description
        "intent": {"objectives": ["obj1"]},
        "allowed": {"paths": [], "capabilities": [], "symbols": []},
        "forbidden": {"paths": [], "capabilities": [], "symbols": []},
        "required_invariants": [],
        "required_gates": [],
        "required_evidence": [],
        "authority": {
            "informational": [],
            "strategy": [],
            "risk": [],
            "execution": [],
            "governance": [],
            "verification": [],
        },
        "verification": {"minimum_level": "E2"},
        "closure": {"required": []},
    }
    with pytest.raises(ContractError, match="Missing or invalid phase field 'version'"):
        PhaseContract.from_dict(bad_data)


def test_contract_malformed_authority_block_fails() -> None:
    bad_data = {
        "phase": {"id": "P0", "name": "Test", "version": "1.0", "description": "desc"},
        "intent": {"objectives": ["obj1"]},
        "allowed": {"paths": [], "capabilities": [], "symbols": []},
        "forbidden": {"paths": [], "capabilities": [], "symbols": []},
        "required_invariants": [],
        "required_gates": [],
        "required_evidence": [],
        "authority": "NOT_A_DICT",
        "verification": {"minimum_level": "E2"},
        "closure": {"required": []},
    }
    with pytest.raises(ContractError, match="Missing or malformed 'authority' block"):
        PhaseContract.from_dict(bad_data)


def test_contract_hash_determinism() -> None:
    contract1 = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")
    contract2 = PhaseContract.from_file("docs/governance/PHASE_EXECUTION_CONTRACT.md")
    assert contract1.compute_hash() == contract2.compute_hash()


def test_contract_nonexistent_file_fails() -> None:
    with pytest.raises(ContractError, match="Contract file not found"):
        PhaseContract.from_file("docs/governance/NONEXISTENT.md")

"""Tests for PGVF Authority Model Engine."""

import pytest

from tools.pfgv.authority import AuthorityModel
from tools.pfgv.errors import AuthorityError


def test_authority_model_loading() -> None:
    model = AuthorityModel.from_file("docs/governance/AUTHORITY_MODEL.yaml")
    assert "validate_contract" in model.get_domain("governance")
    assert model.compute_hash() is not None


def test_unchanged_authority_delta() -> None:
    model1 = AuthorityModel.from_file("docs/governance/AUTHORITY_MODEL.yaml")
    model2 = AuthorityModel.from_file("docs/governance/AUTHORITY_MODEL.yaml")
    delta = model1.compute_delta(model2)
    assert not delta.has_changes
    assert not delta.added
    assert not delta.removed


def test_declared_authority_expansion_delta() -> None:
    before = AuthorityModel.from_dict(
        {
            "phase_0_authority": {
                "informational": ["read_codebase"],
                "strategy": [],
                "risk": [],
                "execution": [],
                "governance": ["validate_contract"],
                "verification": [],
            }
        }
    )
    after = AuthorityModel.from_dict(
        {
            "phase_0_authority": {
                "informational": ["read_codebase"],
                "strategy": [],
                "risk": [],
                "execution": [],
                "governance": ["validate_contract", "validate_invariants"],
                "verification": [],
            }
        }
    )
    delta = before.compute_delta(after)
    assert delta.has_changes
    assert delta.added["governance"] == ["validate_invariants"]


def test_undeclared_authority_expansion_fails() -> None:
    before = AuthorityModel.from_file("docs/governance/AUTHORITY_MODEL.yaml")
    after = AuthorityModel.from_dict(
        {
            "phase_0_authority": {
                "informational": ["read_codebase"],
                "strategy": [],
                "risk": [],
                "execution": ["place_live_order"],  # Undeclared execution capability!
                "governance": ["validate_contract"],
                "verification": [],
            }
        }
    )
    allowed_contract_authority = {
        "informational": ["read_codebase"],
        "strategy": [],
        "risk": [],
        "execution": [],  # None allowed in contract
        "governance": ["validate_contract"],
        "verification": [],
    }
    with pytest.raises(AuthorityError, match="Undeclared authority expansion in domain 'execution'"):
        before.verify_no_undeclared_expansion(after, allowed_contract_authority)


def test_malformed_authority_model_fails() -> None:
    bad_data = {"phase_0_authority": {"governance": "NOT_A_LIST"}}
    with pytest.raises(AuthorityError, match="must be a list or capability dictionary"):
        AuthorityModel.from_dict(bad_data)

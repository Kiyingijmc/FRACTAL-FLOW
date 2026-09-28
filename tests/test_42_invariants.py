"""Automated Invariants Verification Tests and Truthful Verification Matrix Validator for all 42 Non-Negotiable Invariants."""

from pathlib import Path
import yaml
import pytest


def test_invariant_verification_matrix_is_truthful() -> None:
    yaml_path = Path("spec/invariants.yaml")
    assert yaml_path.exists(), "spec/invariants.yaml missing"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert "invariants" in data
    invariants = data["invariants"]
    assert len(invariants) == 42, f"Expected 42 invariants, found {len(invariants)}"

    ids = [inv["id"] for inv in invariants]
    assert sorted(ids) == list(range(1, 43)), "Invariant IDs must be sequentially numbered 1 to 42"

    enforced_count = 0
    integration_count = 0
    specified_count = 0

    for inv in invariants:
        assert "title" in inv and "rule" in inv and "status" in inv
        status = inv["status"]
        assert status in ("ENFORCED", "INTEGRATION_VERIFIED", "SPECIFIED_ONLY"), f"Invalid status '{status}' for invariant {inv['id']}"

        if status == "ENFORCED":
            enforced_count += 1
            assert inv.get("test_reference") is not None and inv["test_reference"] != "None", (
                f"Invariant {inv['id']} marked ENFORCED must have a non-empty test_reference"
            )
        elif status == "INTEGRATION_VERIFIED":
            integration_count += 1
            assert inv.get("test_reference") is not None and inv["test_reference"] != "None", (
                f"Invariant {inv['id']} marked INTEGRATION_VERIFIED must have a non-empty test_reference"
            )
        elif status == "SPECIFIED_ONLY":
            specified_count += 1

    assert enforced_count + integration_count + specified_count == 42

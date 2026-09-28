"""Automated Invariants Verification Tests for all 42 Non-Negotiable Invariants."""

from pathlib import Path
import yaml
import pytest


def test_all_42_invariants_cataloged() -> None:
    yaml_path = Path("spec/invariants.yaml")
    assert yaml_path.exists(), "spec/invariants.yaml missing"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert "invariants" in data
    invariants = data["invariants"]
    assert len(invariants) == 42, f"Expected 42 invariants, found {len(invariants)}"

    ids = [inv["id"] for inv in invariants]
    assert sorted(ids) == list(range(1, 43)), "Invariant IDs must be sequentially numbered 1 to 42"

    for inv in invariants:
        assert "title" in inv and "rule" in inv and "status" in inv
        assert inv["status"] in ("ENFORCED", "SPECIFIED_ONLY")

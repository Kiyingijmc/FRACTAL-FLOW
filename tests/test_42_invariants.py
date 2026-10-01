"""Automated Invariants Verification Tests and Mechanical Evidence Validator for all 42 Non-Negotiable Invariants."""

import ast
from pathlib import Path
import yaml


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

    referenced_symbols: dict[str, list[int]] = {}

    for inv in invariants:
        inv_id = inv["id"]
        assert "title" in inv and "rule" in inv and "status" in inv
        status = inv["status"]
        assert status in ("ENFORCED", "INTEGRATION_VERIFIED", "SPECIFIED_ONLY"), (
            f"Invalid status '{status}' for invariant {inv_id}"
        )

        ref = inv.get("test_reference")

        if status in ("ENFORCED", "INTEGRATION_VERIFIED"):
            if status == "ENFORCED":
                enforced_count += 1
            else:
                integration_count += 1

            assert ref is not None and ref != "None", (
                f"Invariant {inv_id} marked {status} must have a non-empty test_reference"
            )

            referenced_symbols.setdefault(ref, []).append(inv_id)

            # Mechanical Verification: Resolve file and test symbol
            parts = ref.split("::")
            file_path_str = parts[0]
            test_symbol = parts[1] if len(parts) > 1 else None

            test_file = Path(file_path_str)
            assert test_file.exists(), (
                f"Invariant {inv_id} test reference file '{file_path_str}' does not exist on disk!"
            )

            # AST parse test file to confirm test function exists and starts with test_
            tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=file_path_str)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

            assert test_symbol is not None, f"Invariant {inv_id} test reference '{ref}' missing '::function_name'"
            assert test_symbol in functions, (
                f"Invariant {inv_id} references symbol '{test_symbol}' which does not exist in '{file_path_str}'!"
            )
            assert test_symbol.startswith("test_"), (
                f"Invariant {inv_id} reference '{test_symbol}' is not a pytest-collectible test function!"
            )

        elif status == "SPECIFIED_ONLY":
            specified_count += 1

    assert enforced_count + integration_count + specified_count == 42

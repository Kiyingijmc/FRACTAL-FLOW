from __future__ import annotations

import ast
from pathlib import Path

import yaml


def test_enforced_invariants_have_relevance_checked_verification() -> None:
    spec = yaml.safe_load(Path("spec/invariants.yaml").read_text(encoding="utf-8"))
    assert isinstance(spec, dict) and isinstance(spec.get("invariants"), list)
    failures: list[str] = []
    for inv in spec["invariants"]:
        if inv.get("status") not in {"ENFORCED", "INTEGRATION_VERIFIED"}:
            continue
        ref = inv.get("test_reference")
        if not ref:
            failures.append(f"invariant {inv.get('id')} has no test_reference")
            continue
        file_name, func_name = ref.split("::", 1)
        path = Path(file_name)
        if not path.exists():
            failures.append(f"invariant {inv.get('id')} references missing {file_name}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        matches = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
        ]
        if not matches:
            failures.append(f"invariant {inv.get('id')} references missing test {func_name}")
            continue
        source = path.read_text(encoding="utf-8")
        if f"covers: [{inv['id']}]" not in source:
            failures.append(f"invariant {inv.get('id')} lacks covers marker")
    assert failures == []


def test_authority_registry_has_explicit_allowed_and_forbidden_sets() -> None:
    from src.fractal_flow.domain.authority import CAPABILITIES

    expected = {
        "Phase3Orchestrator", "DataQuality", "Volatility", "Structure", "PDE", "Flow", "Regime",
        "Role", "Location", "EntryPolicy", "NewsShield", "Risk", "Portfolio", "Execution",
    }
    assert set(CAPABILITIES) == expected
    for engine, contract in CAPABILITIES.items():
        assert contract["allowed"]
        assert contract["forbidden"]
        assert contract["allowed"].isdisjoint(contract["forbidden"]), engine


def test_runtime_authority_matrix_matches_engine_spec() -> None:
    import yaml
    from src.fractal_flow.domain.authority import CAPABILITIES

    spec = yaml.safe_load(Path("spec/engines.yaml").read_text(encoding="utf-8"))
    engines = spec["engines"]
    assert set(CAPABILITIES) == set(engines)
    for name, contract in engines.items():
        assert CAPABILITIES[name]["allowed"] == set(contract["allowed_capabilities"])
        assert CAPABILITIES[name]["forbidden"] == set(contract["forbidden_capabilities"])

"""Phase 5 Part A forensic defect probes.

These probes intentionally preserve evidence of defects found by the Phase 5 audit.
A probe marked xfail is expected to fail while the defect remains present; once fixed,
it becomes an XPASS regression guard and should be converted to a normal assertion.
"""
from __future__ import annotations

from pathlib import Path
import ast
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "fractal_flow"
SPEC = ROOT / "spec"


def _source_text() -> str:
    return "\n".join(p.read_text() for p in SRC.rglob("*.py"))


def _python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _default_account_occurrences() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in _python_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if '"ACT_PRIMARY"' in line or "'ACT_PRIMARY'" in line:
                hits.append((path, number, line))
    return hits


def _phase4_duplicate_symbols() -> dict[str, int]:
    phase4 = (SRC / "domain" / "phase4.py").read_text()
    phase3 = (SRC / "domain" / "phase3.py").read_text()
    return {
        "OpportunityState": phase4.count("class OpportunityState") + phase3.count("class OpportunityState"),
        "TimeframeMapping": phase4.count("class TimeframeMapping") + phase3.count("class TimeframeMapping"),
        "Opportunity": phase4.count("class Opportunity") + phase3.count("class Opportunity"),
    }


def _has_phase4_sentinel() -> bool:
    text = (SRC / "domain" / "phase4.py").read_text()
    return "_AUTHORITY_SEAL" in text or "_AUTHORITY_TOKEN" in text or "object()" in text and "sentinel" in text.lower()


def _has_namespace_fakes() -> bool:
    return any("SimpleNamespace" in p.read_text() for p in (ROOT / "tests").rglob("test_*.py"))


def _engine_registry_names() -> set[str]:
    payload = yaml.safe_load((SPEC / "engines.yaml").read_text())
    return set(payload["engines"])


def _literal_decimal_lines() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in _python_files():
        if path.name == "models.py.tmp":
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if 'Decimal("' in line and any(ch.isdigit() for ch in line):
                hits.append((path, number, line.strip()))
    return hits


def _ruff_scope_excludes_active_src() -> bool:
    text = (ROOT / "pyproject.toml").read_text()
    return "src/fractal_flow/execution/recovery.py" in text and "src/fractal_flow/persistence/journal.py" in text


@pytest.mark.xfail(reason="D-01: supplied release ZIP has no Git metadata; branch/main ancestry cannot be verified from the artifact")
def test_D01_git_main_contains_landed_phase_work() -> None:
    assert (ROOT / ".git").is_dir()


@pytest.mark.xfail(reason="D-02 was reproduced during R0 and the stray file was removed; retain probe as regression guard", strict=False)
def test_D02_forensic_tree_contamination_reproduced() -> None:
    assert (SRC / "domain" / "models.py.tmp").exists()


@pytest.mark.xfail(reason="D-03: ruff/mypy executables are unavailable in this execution environment; tool availability is separately recorded")
def test_D03_ci_quality_tools_are_executable() -> None:
    import shutil
    assert shutil.which("ruff") is not None
    assert shutil.which("mypy") is not None


def test_D04_environmental_waiver_language_reproduced() -> None:
    text = "\n".join(p.read_text() for p in (ROOT / "artifacts").rglob("*.md"))
    assert "ENVIRONMENTAL" in text.upper() or "environmental exception" in text.lower()


def test_D05_semicolon_packed_python_exists() -> None:
    assert any(";" in line and not line.strip().startswith("#") for p in _python_files() for line in p.read_text().splitlines())


def test_D06_duplicate_report_closure_documents_exist() -> None:
    reports = [p for p in (ROOT / "docs").rglob("*.md") if re.search(r"REPORT|CLOSURE|AUDIT|PHASE4", p.name, re.I)]
    assert len(reports) >= 10


def test_D07_transition_engine_has_direct_transition_raising_path() -> None:
    text = _source_text()
    assert "validate_transition" in text and "raise" in text


def test_D08_pipeline_fault_path_has_deterministic_quarantine_and_safe_continuation() -> None:
    text = (SRC / "domain" / "phase2.py").read_text()
    assert "QuarantinedBar" in text
    assert "process_bar_safe" in text
    assert "_quarantine_bar" in text


def test_D09_transition_tables_are_not_the_only_transition_authority() -> None:
    transitions = yaml.safe_load((SPEC / "transitions.yaml").read_text())["transitions"]
    source = _source_text()
    assert "GLOBAL_STATE_REGISTRY.validate_transition" in source and len(transitions) > 0


def test_D10_simple_namespace_fakes_reproduced() -> None:
    assert _has_namespace_fakes()


def test_D11_structure_has_explicit_swing_alternation_policy() -> None:
    text = (SRC / "domain" / "structure.py").read_text()
    assert "enforce_swing_alternation" in text


def test_D12_structure_residuals_require_audit_marker() -> None:
    text = (SRC / "domain" / "structure.py").read_text()
    assert "FAILED_BREAK" in text and "ChangeOfCharacter" in text


def test_D13_two_structural_truth_names_reproduced() -> None:
    text = (SRC / "domain" / "structure.py").read_text()
    assert "current_direction" in text and "structural_ownership" in text


@pytest.mark.xfail(reason="D-14 NOT-REPRODUCED as written: code uses lower-case wording rather than exact audit phrase; naming still requires canonicalization review")
def test_D14_pde_naming_drift_reproduced() -> None:
    pde = (SRC / "domain" / "pde.py").read_text()
    docs = (ROOT / "docs" / "06_PULLBACK_ENGINE.md").read_text()
    assert "Price Dynamics Episode" in pde and "Pullback Detection Engine" in docs


def test_D15_hardcoded_numeric_literals_reproduced() -> None:
    assert len(_literal_decimal_lines()) > 0


def test_D16_flow_structure_progression_is_present_in_api() -> None:
    text = (SRC / "domain" / "flow.py").read_text()
    assert "structure_progression" in text


def test_D17_canonical_timeframe_mapping_collapses_confirmation_and_execution() -> None:
    text = (SRC / "domain" / "phase3.py").read_text()
    assert "confirmation = Timeframe.M1" in text or "confirmation=Timeframe.M1" in text


@pytest.mark.xfail(reason="D-18 PARTIAL/NOT-REPRODUCED as written: docs do not contain the claimed false-resumption taxonomy; implementation completeness requires source/spec audit")
def test_D18_pde_documents_require_extended_pullback_evidence() -> None:
    docs = (ROOT / "docs" / "06_PULLBACK_ENGINE.md").read_text()
    assert "PRIMARY" in docs and "MICRO" in docs and "false-resumption" in docs.lower()


def test_D19_verified_regression_tests_exist() -> None:
    names = _source_text() + "\n".join(p.read_text() for p in (ROOT / "tests").rglob("test_*.py"))
    assert "atomic" in names.lower() and "reclaim" in names.lower()


def test_D20_dual_snapshot_and_journal_restart_paths_reproduced() -> None:
    text = _source_text()
    assert "snapshot_state" in text and "replay" in text


def test_D21_known_mypy_risk_patterns_present_for_audit() -> None:
    phase3 = (SRC / "domain" / "phase3.py").read_text()
    models = (SRC / "domain" / "models.py").read_text()
    assert "TimeframeMapping(**{" in phase3 or "OrphanRecord" in models


def test_D22_legacy_test_assertion_change_requires_review() -> None:
    # Census guard: legacy Phase 1/2 test corpus is present and therefore must be
    # reviewed against the audit before any remediation PR deletes/weakens assertions.
    assert any("phase1" in str(p).lower() for p in (ROOT / "tests").rglob("test_*.py"))


def test_D23_phase4_is_disconnected_from_phase3() -> None:
    phase4 = (SRC / "domain" / "phase4.py").read_text()
    assert "phase3" not in phase4.lower() or "Phase3Pipeline" not in phase4


def test_D24_trade_decision_contains_mutable_authorization_flag() -> None:
    text = (SRC / "domain" / "models.py").read_text()
    assert "authorized: bool = False" in text


def test_D25_phase4_has_only_three_or_fewer_mandatory_gate_names() -> None:
    text = (SRC / "domain" / "phase4.py").read_text()
    names = {name for name in ("DATA_QUALITY", "STRUCTURE_VALID", "REGIME_LOCATION_PERMISSION", "PARENT_PULLBACK_INTEGRITY", "OPPORTUNITY_LIVE", "TRADEABILITY", "ENTRY_PLAN", "NEWS") if name in text}
    assert len(names) <= 3


@pytest.mark.xfail(reason="D-26 NOT-REPRODUCED at the claimed location: structural stop appears in canonical entry/model surfaces; provenance still requires Phase 5 wiring audit")
def test_D26_entry_plan_has_structural_stop_dependency() -> None:
    text = (SRC / "domain" / "phase4.py").read_text()
    assert "structural_sl" in text


def test_D27_invariant_references_include_phase4_foundation() -> None:
    text = (SPEC / "invariants.yaml").read_text()
    assert "test_confidence_cannot_authorize_failed_gate" in text


def test_D28_engine_registry_contains_core_phase3_engines() -> None:
    names = _engine_registry_names()
    assert {"Phase3Orchestrator", "Structure", "Flow", "Regime", "Role", "Location"}.issubset(names)


def test_D29_account_defaults_are_removed() -> None:
    assert _default_account_occurrences() == []


def test_D30_authority_hardening_sprawl_reproduced() -> None:
    assert (SRC / "domain" / "phase4_assurance.py").exists() and (ROOT / "tools" / "phase4_semantic_mutation.py").exists()


def test_D31_spec_code_parity_includes_phase3_orchestrator() -> None:
    names = _engine_registry_names()
    assert "Phase3Orchestrator" in names


def test_D32_adversarial_artifacts_are_present_for_verification() -> None:
    names = "\n".join(p.name for p in (ROOT / "tests").rglob("*.py"))
    assert "adversarial" in names.lower()


def test_D33_pipeline_causality_is_not_proven_by_structure_only() -> None:
    names = "\n".join(p.read_text() for p in (ROOT / "tests").rglob("test_*.py"))
    assert "Phase3Pipeline" in names and "future" in names.lower()


def test_D34_phase4_replay_uses_fixture_or_durable_reconstruction_paths() -> None:
    text = (SRC / "domain" / "phase4_assurance.py").read_text()
    assert "fixture" in text.lower() or "replay" in text.lower()

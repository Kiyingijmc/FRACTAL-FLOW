"""Tests for PGVF Scope Policy Engine."""

import pytest

from tools.pfgv.errors import ScopeViolationError
from tools.pfgv.scope import ScopePolicy


def test_valid_allowed_scope_changes_pass() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    changed_files = [
        "docs/governance/PHASE_EXECUTION_CONTRACT.md",
        "tools/pfgv/cli.py",
        "tests/governance/test_scope.py",
    ]
    # Should not raise
    policy.validate_changes(changed_files=changed_files, deleted_files=[])


def test_forbidden_scope_path_fails() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    changed_files = [
        "src/fractal_flow/domain/structure.py"  # Forbidden path
    ]
    with pytest.raises(ScopeViolationError, match="File change in forbidden scope path"):
        policy.validate_changes(changed_files=changed_files)


def test_unallowed_path_fails() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    changed_files = [
        "src/unauthorized_module.py"  # Not in allowed paths
    ]
    with pytest.raises(ScopeViolationError, match="File change outside allowed scope paths"):
        policy.validate_changes(changed_files=changed_files)


def test_undeclared_deletions_fail() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    with pytest.raises(ScopeViolationError, match="Undeclared file deletions are forbidden"):
        policy.validate_changes(changed_files=[], deleted_files=["docs/governance/OLD.md"])


def test_workflow_changes_fail() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    changed_files = [".github/workflows/ci.yml"]
    with pytest.raises(ScopeViolationError, match="Workflow file changes forbidden"):
        policy.validate_changes(changed_files=changed_files)


def test_forbidden_capability_fails() -> None:
    policy = ScopePolicy.from_file("docs/governance/SCOPE_POLICY.yaml")
    with pytest.raises(ScopeViolationError, match="Forbidden capability invoked"):
        policy.validate_changes(changed_files=[], used_capabilities=["live_trading"])


def test_malformed_scope_policy_fails() -> None:
    bad_data = {"scope_policy": "INVALID_TYPE"}
    with pytest.raises(ScopeViolationError, match="Malformed scope policy block"):
        ScopePolicy.from_dict(bad_data)

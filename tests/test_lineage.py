"""Tests for Lineage Chain Integrity, Stale Versioning, and Orphan Prevention."""

import pytest
from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException


def test_lineage_chain_integrity_validation() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=1,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
        parent_is_valid=True,
    )
    # Should not raise
    lineage.validate_child_action(expected_parent_version=1)


def test_orphaned_signal_never_executes() -> None:
    lineage = Lineage(
        root_id="",
        parent_id="",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=True,
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action()
    assert "Orphaned object" in str(exc_info.value)


def test_invalid_parent_version_blocks_child_action() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=1,  # Stale version
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=True,
    )
    # Latest parent version is 2
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(expected_parent_version=2)
    assert "Parent version mismatch" in str(exc_info.value)


def test_invalid_parent_state_blocks_child() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=False,  # Parent state invalidated
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action()
    assert "Parent opp_456 (OPPORTUNITY) is invalid/expired" in str(exc_info.value)


def test_tier_order_verification() -> None:
    Lineage.verify_tier_order("PRIMARY_PULLBACK", "OPPORTUNITY")
    with pytest.raises(LineageInvalidException):
        Lineage.verify_tier_order("SIGNAL", "PRIMARY_PULLBACK")

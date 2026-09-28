"""Tests for Lineage Chain Integrity, Strict Version Identity, and Legal Edge Validation."""

import pytest
from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException


def test_lineage_exact_version_accepted() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
        parent_is_valid=True,
    )
    lineage.validate_child_action(authoritative_parent_version=2)


def test_stale_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=True,
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=2)
    assert "Parent version mismatch" in str(exc_info.value)


def test_future_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=3,  # Future version relative to authoritative parent version 2
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=True,
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=2)
    assert "Parent version mismatch" in str(exc_info.value)


def test_zero_or_negative_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=0,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
        parent_is_valid=True,
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=0)
    assert "Version must be positive" in str(exc_info.value)


def test_illegal_lineage_edge_skipped_parent_rejected() -> None:
    """ROOT -> POSITION skipping intermediate tiers is forbidden."""
    lineage = Lineage(
        root_id="root_123",
        parent_id="root_123",
        parent_version=1,
        parent_tier="ROOT",
        current_tier="POSITION",
        parent_is_valid=True,
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=1)
    assert "Illegal lineage edge" in str(exc_info.value)


def test_legal_lineage_edges_all_valid() -> None:
    Lineage.verify_legal_edge("ROOT", "REGIME")
    Lineage.verify_legal_edge("PRIMARY_PULLBACK", "MICRO_PULLBACK")
    Lineage.verify_legal_edge("OPPORTUNITY", "SIGNAL")
    Lineage.verify_legal_edge("ORDER", "POSITION")
    Lineage.verify_legal_edge("POSITION", "MANAGEMENT")

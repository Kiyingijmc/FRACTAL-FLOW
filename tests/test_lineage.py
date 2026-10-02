"""Tests for Lineage Chain Integrity, Strict Version Identity, and Legal Edge Validation."""

from dataclasses import dataclass
import pytest

from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException


@dataclass
class MockParent:
    id: str
    version: int
    validity: bool = True


def test_lineage_exact_version_accepted() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    lineage.validate_child_action(authoritative_parent_version=2)


def test_child_carries_lineage_ids() -> None:
    """Invariant #12: Every child object carries parent_id, parent_version, and root_id."""
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    assert lineage.root_id == "root_123"
    assert lineage.parent_id == "pullback_456"
    assert lineage.parent_version == 2


def test_lineage_with_authoritative_parent_object() -> None:
    parent_obj = MockParent(id="pullback_456", version=2, validity=True)
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    lineage.validate_child_action(authoritative_parent=parent_obj)

    # Invalid parent object fails
    invalid_parent = MockParent(id="pullback_456", version=2, validity=False)
    with pytest.raises(LineageInvalidException) as exc:
        lineage.validate_child_action(authoritative_parent=invalid_parent)
    assert "marked invalid" in str(exc.value)


def test_stale_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
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

"""Canonical Lineage Chain and Governance Model."""

from dataclasses import dataclass
from typing import Optional, List


class LineageInvalidException(Exception):
    """Raised when lineage validation or parent checks fail."""
    pass


# Hierarchy order from highest (ROOT) to lowest
LINEAGE_HIERARCHY: List[str] = [
    "ROOT",
    "REGIME",
    "SETUP",
    "PRIMARY_PULLBACK",
    "SECONDARY_PULLBACK",
    "MICRO_PULLBACK",
    "OPPORTUNITY",
    "SIGNAL",
    "ORDER",
    "POSITION",
    "TRADE",
    "MANAGEMENT",
]


@dataclass(frozen=True)
class LineageNode:
    tier: str
    node_id: str
    version: int
    is_valid: bool = True


@dataclass
class Lineage:
    root_id: str
    parent_id: str
    parent_version: int
    parent_tier: str
    current_tier: str
    parent_is_valid: bool = True

    def validate_child_action(self, expected_parent_version: Optional[int] = None) -> None:
        """Validates that child node can execute based on parent state and version."""
        if not self.parent_is_valid:
            raise LineageInvalidException(
                f"Parent {self.parent_id} ({self.parent_tier}) is invalid/expired. Child cannot execute."
            )

        if expected_parent_version is not None and self.parent_version < expected_parent_version:
            raise LineageInvalidException(
                f"Parent version mismatch: child has parent_version={self.parent_version}, "
                f"latest parent_version={expected_parent_version}. Stale parent blocks child."
            )

        if not self.root_id or not self.parent_id:
            raise LineageInvalidException("Lineage missing root_id or parent_id. Orphaned object cannot execute.")

    @staticmethod
    def verify_tier_order(parent_tier: str, child_tier: str) -> None:
        """Verifies parent tier precedes child tier in legal lineage hierarchy."""
        if parent_tier not in LINEAGE_HIERARCHY or child_tier not in LINEAGE_HIERARCHY:
            raise LineageInvalidException(f"Invalid tier name: {parent_tier} or {child_tier}")

        p_idx = LINEAGE_HIERARCHY.index(parent_tier)
        c_idx = LINEAGE_HIERARCHY.index(child_tier)

        if p_idx >= c_idx:
            raise LineageInvalidException(
                f"Illegal lineage sequence: parent tier '{parent_tier}' (index {p_idx}) "
                f"must strictly precede child tier '{child_tier}' (index {c_idx})"
            )

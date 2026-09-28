"""Canonical Lineage Chain and Governance Model."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Set


class LineageInvalidException(Exception):
    """Raised when lineage validation or parent checks fail."""
    pass


# Legal directed lineage graph edges
LEGAL_LINEAGE_EDGES: Dict[str, Set[str]] = {
    "ROOT": {"REGIME", "DATA", "FEATURE", "STRUCTURE", "FLOW", "PULLBACK"},
    "REGIME": {"SETUP", "OPPORTUNITY"},
    "SETUP": {"PRIMARY_PULLBACK"},
    "PRIMARY_PULLBACK": {"SECONDARY_PULLBACK", "MICRO_PULLBACK", "OPPORTUNITY"},
    "SECONDARY_PULLBACK": {"MICRO_PULLBACK", "OPPORTUNITY"},
    "MICRO_PULLBACK": {"OPPORTUNITY"},
    "OPPORTUNITY": {"SIGNAL", "DECISION"},
    "SIGNAL": {"ORDER", "DECISION"},
    "DECISION": {"AUTHORIZATION", "ORDER"},
    "AUTHORIZATION": {"ORDER", "EXECUTION"},
    "ORDER": {"EXECUTION", "POSITION"},
    "EXECUTION": {"POSITION"},
    "POSITION": {"TRADE", "MANAGEMENT", "CLOSURE", "RECONCILIATION"},
    "TRADE": {"MANAGEMENT", "JOURNAL"},
    "MANAGEMENT": {"CLOSURE", "JOURNAL"},
    "CLOSURE": {"RECONCILIATION", "JOURNAL"},
    "RECONCILIATION": {"JOURNAL"},
}


@dataclass
class Lineage:
    root_id: str
    parent_id: str
    parent_version: int
    parent_tier: str
    current_tier: str
    parent_is_valid: bool = True

    def validate_child_action(self, authoritative_parent_version: Optional[int] = None) -> None:
        """Validates child node execution using strict version identity and parent checks."""
        if not self.root_id or not self.parent_id:
            raise LineageInvalidException("Lineage missing root_id or parent_id. Orphaned object cannot execute.")

        if not self.parent_is_valid:
            raise LineageInvalidException(
                f"Parent {self.parent_id} ({self.parent_tier}) is invalid/expired. Child cannot execute."
            )

        if self.parent_version <= 0:
            raise LineageInvalidException(
                f"Invalid parent version {self.parent_version}. Version must be positive."
            )

        if authoritative_parent_version is not None:
            if self.parent_version != authoritative_parent_version:
                raise LineageInvalidException(
                    f"Parent version mismatch: child parent_version={self.parent_version}, "
                    f"authoritative parent_version={authoritative_parent_version}. Strict version identity required."
                )

        # Validate legal lineage edge
        self.verify_legal_edge(self.parent_tier, self.current_tier)

    @staticmethod
    def verify_legal_edge(parent_tier: str, child_tier: str) -> None:
        """Verifies parent_tier -> child_tier is an explicitly authorized legal lineage edge."""
        allowed_children = LEGAL_LINEAGE_EDGES.get(parent_tier, set())
        if child_tier not in allowed_children:
            raise LineageInvalidException(
                f"Illegal lineage edge: '{parent_tier}' -> '{child_tier}' is not an authorized parent-child edge."
            )

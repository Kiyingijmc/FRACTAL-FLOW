"""Canonical Lineage Chain and Governance Model."""

from dataclasses import dataclass
from typing import Optional, Dict, Set
from pathlib import Path
import yaml


class LineageInvalidException(Exception):
    """Raised when lineage validation or parent checks fail."""

    pass


def load_spec_lineage_edges(
    yaml_path: str = "spec/lineage.yaml",
) -> Dict[str, Set[str]]:
    path = Path(yaml_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f)
            raw_edges = (
                data.get("lineage", {}).get("legal_edges", {})
                if isinstance(data, dict)
                else {}
            )
            return {k: set(v) for k, v in raw_edges.items()}
    return {}


# Dynamic loading of legal lineage edges directly from canonical spec/lineage.yaml
LEGAL_LINEAGE_EDGES: Dict[str, Set[str]] = load_spec_lineage_edges()


@dataclass
class Lineage:
    root_id: str
    parent_id: str
    parent_version: int
    parent_tier: str
    current_tier: str
    parent_is_valid: bool = True

    def validate_child_action(
        self, authoritative_parent_version: Optional[int] = None
    ) -> None:
        """Validates child node execution using strict version identity and parent checks."""
        if not self.root_id or not self.parent_id:
            raise LineageInvalidException(
                "Lineage missing root_id or parent_id. Orphaned object cannot execute."
            )

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

"""Canonical Lineage Chain and Governance Model."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml


class LineageInvalidException(Exception):
    """Raised when lineage validation or parent checks fail."""


@runtime_checkable
class ValidatableParent(Protocol):
    """Protocol for domain parent objects that maintain validity state."""

    @property
    def validity(self) -> bool: ...


def load_spec_lineage_edges(
    yaml_path: str = "spec/lineage.yaml",
) -> dict[str, set[str]]:
    path = Path(yaml_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f)
            raw_edges = data.get("lineage", {}).get("legal_edges", {}) if isinstance(data, dict) else {}
            return {k: set(v) for k, v in raw_edges.items()}
    return {}


# Dynamic loading of legal lineage edges directly from canonical spec/lineage.yaml
LEGAL_LINEAGE_EDGES: dict[str, set[str]] = load_spec_lineage_edges()


@dataclass
class Lineage:
    root_id: str
    parent_id: str
    parent_version: int
    parent_tier: str
    current_tier: str

    def validate_child_action(
        self,
        authoritative_parent_version: int | None = None,
        authoritative_parent: Any | None = None,
    ) -> None:
        """Validates child node execution using strict version identity, independent parent verification, and legal edges."""
        if not self.root_id or not self.parent_id:
            raise LineageInvalidException("Lineage missing root_id or parent_id. Orphaned object cannot execute.")

        if self.parent_version <= 0:
            raise LineageInvalidException(f"Invalid parent version {self.parent_version}. Version must be positive.")

        # Independent parent state & version verification
        if authoritative_parent is not None:
            # Verify parent object validity attribute if present
            if hasattr(authoritative_parent, "validity") and not getattr(authoritative_parent, "validity"):
                raise LineageInvalidException(
                    f"Parent {self.parent_id} ({self.parent_tier}) object is marked invalid. Child cannot execute."
                )
            if hasattr(authoritative_parent, "is_valid") and not getattr(authoritative_parent, "is_valid"):
                raise LineageInvalidException(
                    f"Parent {self.parent_id} ({self.parent_tier}) object is marked invalid. Child cannot execute."
                )
            # Verify parent object version attribute if present
            if hasattr(authoritative_parent, "version"):
                parent_obj_ver = getattr(authoritative_parent, "version")
                if self.parent_version != parent_obj_ver:
                    raise LineageInvalidException(
                        f"Parent version mismatch with parent object: child parent_version={self.parent_version}, "
                        f"parent object version={parent_obj_ver}."
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

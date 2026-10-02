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


@dataclass(frozen=True)
class AuthoritativeParentSeal:
    """Immutable provenance seal wrapping an authoritative parent object resolved from an authoritative registry."""

    parent: Any
    resolver_id: str
    resolved_at_version: int


class AuthoritativeParentResolver:
    """Authoritative Parent Resolver maintaining registered parent states and issuing provenance seals."""

    def __init__(self, resolver_id: str = "GLOBAL_AUTHORITATIVE_PARENT_RESOLVER") -> None:
        self.resolver_id = resolver_id
        self._registry: dict[tuple[str, int], Any] = {}

    def register_parent(self, parent_id: str, version: int, parent_obj: Any) -> None:
        """Registers an authoritative parent object at a specific version."""
        self._registry[(parent_id, version)] = parent_obj

    def resolve_authoritative_parent(self, parent_id: str, version: int) -> AuthoritativeParentSeal:
        """Resolves an authoritative parent from registry and returns a sealed AuthoritativeParentSeal.

        Raises LineageInvalidException if parent cannot be resolved.
        """
        key = (parent_id, version)
        if key not in self._registry:
            raise LineageInvalidException(
                f"Authoritative parent '{parent_id}' version {version} cannot be resolved by {self.resolver_id}."
            )
        return AuthoritativeParentSeal(
            parent=self._registry[key],
            resolver_id=self.resolver_id,
            resolved_at_version=version,
        )

    def verify_seal(self, seal: Any) -> bool:
        """Verifies that an AuthoritativeParentSeal originated from this resolver instance and wraps an active, valid parent."""
        if not isinstance(seal, AuthoritativeParentSeal):
            return False
        if seal.resolver_id != self.resolver_id:
            return False
        parent_id_attr = (
            getattr(seal.parent, "id", None)
            or getattr(seal.parent, "parent_id", None)
            or getattr(seal.parent, "canonical_id", None)
            or getattr(seal.parent, "decision_id", None)
            or getattr(seal.parent, "opportunity_id", None)
            or getattr(seal.parent, "signal_id", None)
        )
        if parent_id_attr is None:
            return False
        key = (str(parent_id_attr), seal.resolved_at_version)
        if key not in self._registry or self._registry[key] is not seal.parent:
            return False

        # Additional verification of parent validity and state keywords
        p_obj = seal.parent
        if hasattr(p_obj, "validity") and not bool(getattr(p_obj, "validity")):
            return False
        if hasattr(p_obj, "is_valid") and not bool(getattr(p_obj, "is_valid")):
            return False
        if hasattr(p_obj, "state"):
            p_state = str(getattr(p_obj, "state"))
            invalid_keywords = ("INVALID", "EXPIRED", "STALE", "CANCELLED", "REVOKED")
            if any(kw in p_state for kw in invalid_keywords):
                return False

        return True


# Global singleton instance for system-wide authoritative parent resolution
GLOBAL_PARENT_RESOLVER = AuthoritativeParentResolver()


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
        """Validates child node execution using strict version identity, independent parent verification, and legal edges.

        Distinguishes structural lineage validation (checking graph structural properties) from authoritative
        lineage verification (verifying against an independently resolved authoritative parent object).
        """
        if not self.root_id or not self.parent_id:
            raise LineageInvalidException("Lineage missing root_id or parent_id. Orphaned object cannot execute.")

        if self.parent_version <= 0:
            raise LineageInvalidException(f"Invalid parent version {self.parent_version}. Version must be positive.")

        # Independent parent state & version verification
        if authoritative_parent is not None:
            # Verify parent identity matching if parent ID attribute is present
            parent_id_attr = (
                getattr(authoritative_parent, "id", None)
                or getattr(authoritative_parent, "parent_id", None)
                or getattr(authoritative_parent, "canonical_id", None)
                or getattr(authoritative_parent, "decision_id", None)
                or getattr(authoritative_parent, "opportunity_id", None)
                or getattr(authoritative_parent, "signal_id", None)
            )
            if parent_id_attr is not None and str(parent_id_attr) != self.parent_id:
                raise LineageInvalidException(
                    f"Parent ID mismatch: lineage parent_id='{self.parent_id}', "
                    f"authoritative parent ID='{parent_id_attr}'."
                )

            # Verify root identity matching if root ID attribute is present
            root_id_attr = getattr(authoritative_parent, "root_id", None)
            if root_id_attr is not None and str(root_id_attr) != self.root_id:
                raise LineageInvalidException(
                    f"Root ID mismatch: lineage root_id='{self.root_id}', "
                    f"authoritative parent root_id='{root_id_attr}'."
                )

            # Verify parent tier matching if tier attribute is present
            tier_attr = getattr(authoritative_parent, "tier", None) or getattr(
                authoritative_parent, "parent_tier", None
            )
            if tier_attr is not None and str(tier_attr) != self.parent_tier:
                raise LineageInvalidException(
                    f"Parent tier mismatch: lineage parent_tier='{self.parent_tier}', "
                    f"authoritative parent tier='{tier_attr}'."
                )

            # Verify parent object validity attribute if present
            if hasattr(authoritative_parent, "validity") and not bool(getattr(authoritative_parent, "validity")):
                raise LineageInvalidException(
                    f"Parent {self.parent_id} ({self.parent_tier}) object is marked invalid. Child cannot execute."
                )
            if hasattr(authoritative_parent, "is_valid") and not bool(getattr(authoritative_parent, "is_valid")):
                raise LineageInvalidException(
                    f"Parent {self.parent_id} ({self.parent_tier}) object is marked invalid. Child cannot execute."
                )
            if hasattr(authoritative_parent, "state"):
                parent_state = str(getattr(authoritative_parent, "state"))
                invalid_keywords = ("INVALID", "EXPIRED", "STALE", "CANCELLED", "REVOKED")
                if any(kw in parent_state for kw in invalid_keywords):
                    raise LineageInvalidException(f"Parent {self.parent_id} is in invalid state '{parent_state}'.")

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

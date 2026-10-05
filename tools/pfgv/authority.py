"""PGVF Authority Model and Delta Computation Engine."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Union

import yaml

from tools.pfgv.errors import AuthorityError

AUTHORITY_DOMAINS = ("informational", "strategy", "risk", "execution", "governance", "verification")


@dataclass(frozen=True)
class AuthorityDelta:
    """Represents differences between before and after authority models."""

    added: Dict[str, List[str]]
    removed: Dict[str, List[str]]
    has_changes: bool


@dataclass(frozen=True)
class AuthorityModel:
    """Immutable representation of authority allocations across canonical governance domains."""

    authority_map: Dict[str, List[str]]
    raw_dict: Dict[str, Any]

    def get_domain(self, domain: str) -> List[str]:
        return list(self.authority_map.get(domain, []))

    def compute_hash(self) -> str:
        """Computes deterministic SHA256 hash of authority model."""
        canonical_json = json.dumps(self.raw_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthorityModel":
        if not isinstance(data, dict):
            raise AuthorityError("Authority model payload must be a dictionary")

        source = data.get("phase_0_authority", data.get("authority", data.get("authority_domains", data)))
        if not isinstance(source, dict):
            raise AuthorityError("Malformed authority block")

        authority_map: Dict[str, List[str]] = {}
        for domain in AUTHORITY_DOMAINS:
            entry = source.get(domain, [])
            if isinstance(entry, dict):
                caps = entry.get("capabilities", [])
            elif isinstance(entry, list):
                caps = entry
            else:
                raise AuthorityError(f"Authority domain '{domain}' must be a list or capability dictionary")

            if not isinstance(caps, list):
                raise AuthorityError(f"Capabilities for domain '{domain}' must be a list")

            authority_map[domain] = [str(c) for c in caps]

        return cls(authority_map=authority_map, raw_dict=data)

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "AuthorityModel":
        path = Path(filepath)
        if not path.exists():
            raise AuthorityError(f"Authority model file not found: {filepath}")

        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise AuthorityError(f"Could not parse valid YAML authority model from {filepath}")

        return cls.from_dict(parsed)

    def compute_delta(self, after: "AuthorityModel") -> AuthorityDelta:
        """Computes structural authority delta between self (before) and after."""
        added: Dict[str, List[str]] = {}
        removed: Dict[str, List[str]] = {}
        has_changes = False

        for domain in AUTHORITY_DOMAINS:
            before_set: Set[str] = set(self.get_domain(domain))
            after_set: Set[str] = set(after.get_domain(domain))

            added_caps = sorted(list(after_set - before_set))
            removed_caps = sorted(list(before_set - after_set))

            if added_caps:
                added[domain] = added_caps
                has_changes = True
            if removed_caps:
                removed[domain] = removed_caps
                has_changes = True

        return AuthorityDelta(added=added, removed=removed, has_changes=has_changes)

    def verify_no_undeclared_expansion(
        self,
        after: "AuthorityModel",
        contract_allowed_authority: Dict[str, List[str]],
    ) -> None:
        """Verifies that authority changes in 'after' do not contain undeclared authority expansions.

        Fails closed with AuthorityError if undeclared authority addition is detected.
        """
        delta = self.compute_delta(after)
        if not delta.has_changes:
            return

        for domain, added_caps in delta.added.items():
            allowed = set(contract_allowed_authority.get(domain, []))
            for cap in added_caps:
                if cap not in allowed:
                    raise AuthorityError(
                        f"Undeclared authority expansion in domain '{domain}': '{cap}' is not allowed in contract"
                    )

"""PGVF Invariant Registry Schema and Verification Engine."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from tools.pfgv.errors import InvariantViolationError


@dataclass(frozen=True)
class Invariant:
    """Immutable PGVF Invariant entry."""

    id: str
    name: str
    severity: str
    category: str
    statement: str
    blocking: bool
    authority: str
    positive_tests: List[str]
    negative_tests: List[str]
    required_evidence: List[str]
    mutation_tests: List[str]
    raw_dict: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Invariant":
        if not isinstance(data, dict):
            raise InvariantViolationError("Invariant definition must be a dictionary")

        req_str_fields = ("id", "name", "severity", "category", "statement", "authority")
        for field in req_str_fields:
            val = data.get(field)
            if not isinstance(val, str) or not val.strip():
                raise InvariantViolationError(f"Missing or invalid invariant field '{field}'")

        blocking = data.get("blocking")
        if not isinstance(blocking, bool):
            raise InvariantViolationError(f"Invariant '{data.get('id')}' field 'blocking' must be a boolean")

        req_list_fields = ("positive_tests", "negative_tests", "required_evidence", "mutation_tests")
        list_vals: Dict[str, List[str]] = {}
        for field in req_list_fields:
            val = data.get(field)
            if not isinstance(val, list):
                raise InvariantViolationError(f"Invariant '{data.get('id')}' field '{field}' must be a list")
            list_vals[field] = list(val)

        return cls(
            id=data["id"],
            name=data["name"],
            severity=data["severity"],
            category=data["category"],
            statement=data["statement"],
            blocking=blocking,
            authority=data["authority"],
            positive_tests=list_vals["positive_tests"],
            negative_tests=list_vals["negative_tests"],
            required_evidence=list_vals["required_evidence"],
            mutation_tests=list_vals["mutation_tests"],
            raw_dict=data,
        )


class InvariantRegistry:
    """Registry holding all canonical invariants for a phase."""

    def __init__(self, invariants: Dict[str, Invariant], raw_dict: Dict[str, Any]) -> None:
        self._invariants = dict(invariants)
        self._raw_dict = dict(raw_dict)

    @property
    def invariants(self) -> Dict[str, Invariant]:
        return dict(self._invariants)

    def get(self, invariant_id: str) -> Invariant:
        if invariant_id not in self._invariants:
            raise InvariantViolationError(f"Invariant '{invariant_id}' not found in registry")
        return self._invariants[invariant_id]

    def compute_hash(self) -> str:
        """Computes deterministic SHA256 hash of invariant registry."""
        canonical_json = json.dumps(self._raw_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def verify_required_invariants(self, required_ids: List[str]) -> List[Invariant]:
        """Verifies that all required invariant IDs exist and are valid.

        Fails closed if any required invariant is missing or non-blocking when required.
        """
        verified: List[Invariant] = []
        for inv_id in required_ids:
            inv = self.get(inv_id)
            if not inv.blocking:
                raise InvariantViolationError(
                    f"Required invariant '{inv_id}' has blocking=False; required invariants must be blocking"
                )
            verified.append(inv)
        return verified

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvariantRegistry":
        if not isinstance(data, dict):
            raise InvariantViolationError("Invariant registry payload must be a dictionary")

        inv_map = data.get("invariants")
        if not isinstance(inv_map, dict):
            raise InvariantViolationError("Invariant registry must contain an 'invariants' dictionary block")

        parsed: Dict[str, Invariant] = {}
        for k, v in inv_map.items():
            if not isinstance(v, dict):
                raise InvariantViolationError(f"Invariant entry '{k}' must be a dictionary")
            # Ensure id matches dictionary key if present
            if "id" not in v:
                v["id"] = k
            inv = Invariant.from_dict(v)
            parsed[inv.id] = inv

        return cls(invariants=parsed, raw_dict=data)

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "InvariantRegistry":
        path = Path(filepath)
        if not path.exists():
            raise InvariantViolationError(f"Invariant registry file not found: {filepath}")

        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise InvariantViolationError(f"Could not parse valid YAML invariant registry from {filepath}")

        return cls.from_dict(parsed)

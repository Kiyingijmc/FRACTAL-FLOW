"""PGVF Phase Contract Model and Validation."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from tools.pfgv.errors import ContractError


@dataclass(frozen=True)
class PhaseContract:
    """Immutable machine-readable phase contract."""

    phase_id: str
    phase_name: str
    phase_version: str
    description: str
    objectives: List[str]
    allowed_paths: List[str]
    allowed_capabilities: List[str]
    allowed_symbols: List[str]
    forbidden_paths: List[str]
    forbidden_capabilities: List[str]
    forbidden_symbols: List[str]
    required_invariants: List[str]
    required_gates: List[str]
    required_evidence: List[str]
    authority_map: Dict[str, List[str]]
    minimum_verification_level: str
    closure_required: List[str]
    raw_dict: Dict[str, Any]

    def compute_hash(self) -> str:
        """Computes a deterministic SHA256 hash of the canonical contract dictionary."""
        canonical_json = json.dumps(self.raw_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseContract":
        """Parses and validates a phase contract from a raw dictionary.

        Fails closed on missing or malformed required fields.
        """
        if not isinstance(data, dict):
            raise ContractError("Contract payload must be a dictionary")

        phase = data.get("phase")
        if not isinstance(phase, dict):
            raise ContractError("Missing or malformed 'phase' block in contract")

        for key in ("id", "name", "version", "description"):
            val = phase.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ContractError(f"Missing or invalid phase field '{key}' in contract")

        intent = data.get("intent")
        if not isinstance(intent, dict) or "objectives" not in intent:
            raise ContractError("Missing or malformed 'intent' block in contract")
        objectives = intent.get("objectives")
        if not isinstance(objectives, list):
            raise ContractError("Contract 'objectives' must be a list")

        allowed = data.get("allowed")
        if not isinstance(allowed, dict):
            raise ContractError("Missing or malformed 'allowed' block in contract")
        for key in ("paths", "capabilities", "symbols"):
            if not isinstance(allowed.get(key), list):
                raise ContractError(f"Contract 'allowed.{key}' must be a list")

        forbidden = data.get("forbidden")
        if not isinstance(forbidden, dict):
            raise ContractError("Missing or malformed 'forbidden' block in contract")
        for key in ("paths", "capabilities", "symbols"):
            if not isinstance(forbidden.get(key), list):
                raise ContractError(f"Contract 'forbidden.{key}' must be a list")

        req_invariants = data.get("required_invariants")
        if not isinstance(req_invariants, list):
            raise ContractError("Contract 'required_invariants' must be a list")

        req_gates = data.get("required_gates")
        if not isinstance(req_gates, list):
            raise ContractError("Contract 'required_gates' must be a list")

        req_evidence = data.get("required_evidence")
        if not isinstance(req_evidence, list):
            raise ContractError("Contract 'required_evidence' must be a list")

        authority = data.get("authority")
        if not isinstance(authority, dict):
            raise ContractError("Missing or malformed 'authority' block in contract")
        expected_authority_keys = ("informational", "strategy", "risk", "execution", "governance", "verification")
        authority_map: Dict[str, List[str]] = {}
        for key in expected_authority_keys:
            val = authority.get(key, [])
            if not isinstance(val, list):
                raise ContractError(f"Authority category '{key}' must be a list")
            authority_map[key] = list(val)

        verification = data.get("verification")
        if not isinstance(verification, dict):
            raise ContractError("Missing or malformed 'verification' block in contract")
        min_level = verification.get("minimum_level")
        if not isinstance(min_level, str) or not min_level.strip():
            raise ContractError("Missing or invalid 'verification.minimum_level' in contract")

        closure = data.get("closure")
        if not isinstance(closure, dict):
            raise ContractError("Missing or malformed 'closure' block in contract")
        closure_req = closure.get("required")
        if not isinstance(closure_req, list):
            raise ContractError("Contract 'closure.required' must be a list")

        return cls(
            phase_id=phase["id"],
            phase_name=phase["name"],
            phase_version=phase["version"],
            description=phase["description"],
            objectives=list(objectives),
            allowed_paths=list(allowed["paths"]),
            allowed_capabilities=list(allowed["capabilities"]),
            allowed_symbols=list(allowed["symbols"]),
            forbidden_paths=list(forbidden["paths"]),
            forbidden_capabilities=list(forbidden["capabilities"]),
            forbidden_symbols=list(forbidden["symbols"]),
            required_invariants=list(req_invariants),
            required_gates=list(req_gates),
            required_evidence=list(req_evidence),
            authority_map=authority_map,
            minimum_verification_level=min_level,
            closure_required=list(closure_req),
            raw_dict=data,
        )

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "PhaseContract":
        """Loads and parses a contract from a Markdown (embedded YAML block) or YAML file."""
        path = Path(filepath)
        if not path.exists():
            raise ContractError(f"Contract file not found: {filepath}")

        text = path.read_text(encoding="utf-8")
        data: Dict[str, Any] = {}

        if "```yaml" in text:
            # Extract YAML code block from markdown
            parts = text.split("```yaml")
            if len(parts) > 1:
                yaml_content = parts[1].split("```")[0]
                parsed = yaml.safe_load(yaml_content)
                if isinstance(parsed, dict):
                    data = parsed
        else:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, dict):
                data = parsed

        if not data:
            raise ContractError(f"Could not parse valid YAML contract from {filepath}")

        return cls.from_dict(data)

"""PGVF Scope Policy Engine."""

import fnmatch
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from tools.pfgv.errors import ScopeViolationError


@dataclass(frozen=True)
class ScopePolicy:
    """Immutable scope policy definition."""

    allowed_paths: List[str]
    allowed_symbols: List[str]
    allowed_capabilities: List[str]
    forbidden_paths: List[str]
    forbidden_symbols: List[str]
    forbidden_capabilities: List[str]
    allow_deletions: bool
    allow_new_dependencies: bool
    allow_workflow_changes: bool
    raw_dict: Dict[str, Any]

    def compute_hash(self) -> str:
        """Computes deterministic SHA256 hash of scope policy."""
        canonical_json = json.dumps(self.raw_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScopePolicy":
        if not isinstance(data, dict):
            raise ScopeViolationError("Scope policy payload must be a dictionary")

        policy = data.get("scope_policy", data)
        if not isinstance(policy, dict):
            raise ScopeViolationError("Malformed scope policy block")

        allowed = policy.get("allowed")
        if not isinstance(allowed, dict):
            raise ScopeViolationError("Missing or malformed 'allowed' block in scope policy")
        for key in ("paths", "symbols", "capabilities"):
            if not isinstance(allowed.get(key), list):
                raise ScopeViolationError(f"Scope policy 'allowed.{key}' must be a list")

        forbidden = policy.get("forbidden")
        if not isinstance(forbidden, dict):
            raise ScopeViolationError("Missing or malformed 'forbidden' block in scope policy")
        for key in ("paths", "symbols", "capabilities"):
            if not isinstance(forbidden.get(key), list):
                raise ScopeViolationError(f"Scope policy 'forbidden.{key}' must be a list")

        allow_deletions = policy.get("allow_deletions", False)
        allow_deps = policy.get("allow_new_dependencies", False)
        allow_workflows = policy.get("allow_workflow_changes", False)

        if not isinstance(allow_deletions, bool):
            raise ScopeViolationError("scope_policy.allow_deletions must be a boolean")
        if not isinstance(allow_deps, bool):
            raise ScopeViolationError("scope_policy.allow_new_dependencies must be a boolean")
        if not isinstance(allow_workflows, bool):
            raise ScopeViolationError("scope_policy.allow_workflow_changes must be a boolean")

        return cls(
            allowed_paths=list(allowed["paths"]),
            allowed_symbols=list(allowed["symbols"]),
            allowed_capabilities=list(allowed["capabilities"]),
            forbidden_paths=list(forbidden["paths"]),
            forbidden_symbols=list(forbidden["symbols"]),
            forbidden_capabilities=list(forbidden["capabilities"]),
            allow_deletions=allow_deletions,
            allow_new_dependencies=allow_deps,
            allow_workflow_changes=allow_workflows,
            raw_dict=data,
        )

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "ScopePolicy":
        path = Path(filepath)
        if not path.exists():
            raise ScopeViolationError(f"Scope policy file not found: {filepath}")

        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise ScopeViolationError(f"Could not parse valid YAML scope policy from {filepath}")

        return cls.from_dict(parsed)

    def _normalize_path(self, file_path: str) -> str:
        """Normalizes a file path, resolving path traversal dots and slashes."""
        p = file_path.replace("\\", "/")
        if p.startswith("/"):
            p = p.lstrip("/")
        norm = os.path.normpath(p).replace("\\", "/")
        if norm.startswith("../") or norm == "..":
            raise ScopeViolationError(f"Path traversal attempt detected: {file_path}")
        return norm

    def _matches_patterns(self, file_path: str, patterns: List[str]) -> bool:
        """Helper to match a file path against a list of glob patterns or prefix matches."""
        norm_path = self._normalize_path(file_path)
        for pattern in patterns:
            norm_pat = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm_path, norm_pat):
                return True
            if norm_pat.endswith("/**"):
                prefix = norm_pat[:-3]
                if norm_path.startswith(prefix + "/") or norm_path == prefix:
                    return True
        return False

    def validate_changes(
        self,
        changed_files: List[str],
        deleted_files: Optional[List[str]] = None,
        used_capabilities: Optional[List[str]] = None,
    ) -> None:
        """Validates changed files, deleted files, and capabilities against scope policy.

        Fails closed on any violation.
        """
        deleted_files = deleted_files or []
        used_capabilities = used_capabilities or []

        # 1. Check deletions
        if deleted_files and not self.allow_deletions:
            raise ScopeViolationError(f"Undeclared file deletions are forbidden by policy: {deleted_files}")

        # 2. Check workflow changes
        if not self.allow_workflow_changes:
            for file_path in changed_files:
                norm = file_path.replace("\\", "/")
                if norm.startswith(".github/workflows/"):
                    raise ScopeViolationError(f"Workflow file changes forbidden by policy: {file_path}")

        # 3. Check forbidden paths
        for file_path in changed_files:
            if self._matches_patterns(file_path, self.forbidden_paths):
                raise ScopeViolationError(f"File change in forbidden scope path: {file_path}")

        # 4. Check allowed paths (if allowed_paths is non-empty)
        if self.allowed_paths:
            for file_path in changed_files:
                if not self._matches_patterns(file_path, self.allowed_paths):
                    raise ScopeViolationError(
                        f"File change outside allowed scope paths: {file_path} (allowed patterns: {self.allowed_paths})"
                    )

        # 5. Check forbidden capabilities
        if used_capabilities:
            for cap in used_capabilities:
                if cap in self.forbidden_capabilities:
                    raise ScopeViolationError(f"Forbidden capability invoked: {cap}")

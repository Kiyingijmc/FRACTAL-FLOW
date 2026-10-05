"""PGVF Evidence Model, Trust Engine, and Contradiction Analyzer."""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from tools.pfgv.errors import ContradictionError, EvidenceError


class VerificationLevel(IntEnum):
    """PGVF Evidence Verification Trust Hierarchy (E0 to E6)."""

    E0 = 0  # Agent Assertion
    E1 = 1  # Agent-Generated Test
    E2 = 2  # Repository-Local Verification
    E3 = 3  # Independent Verification
    E4 = 4  # Exact-Head CI
    E5 = 5  # Adversarial Verification
    E6 = 6  # Post-Merge Verification


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable PGVF evidence record."""

    evidence_id: str
    type: str
    producer: str
    producer_version: str
    target_commit: str
    target_tree: str
    timestamp: str
    source: str
    claim: Dict[str, Any]
    result: str
    verification_level: VerificationLevel
    metadata: Dict[str, Any]
    raw_dict: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceRecord":
        if not isinstance(data, dict):
            raise EvidenceError("Evidence record payload must be a dictionary")

        req_fields = (
            "evidence_id",
            "type",
            "producer",
            "producer_version",
            "target_commit",
            "target_tree",
            "timestamp",
            "source",
            "result",
        )
        for field_name in req_fields:
            val = data.get(field_name)
            if not isinstance(val, str) or not val.strip():
                raise EvidenceError(f"Missing or invalid evidence field '{field_name}'")

        claim = data.get("claim", {})
        if not isinstance(claim, dict):
            raise EvidenceError("Evidence field 'claim' must be a dictionary")

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise EvidenceError("Evidence field 'metadata' must be a dictionary")

        raw_level = data.get("verification_level", "E0")
        try:
            if isinstance(raw_level, int):
                level = VerificationLevel(raw_level)
            else:
                level = VerificationLevel[str(raw_level).upper()]
        except (KeyError, ValueError):
            raise EvidenceError(f"Invalid verification level: {raw_level}")

        return cls(
            evidence_id=data["evidence_id"],
            type=data["type"],
            producer=data["producer"],
            producer_version=data["producer_version"],
            target_commit=data["target_commit"],
            target_tree=data["target_tree"],
            timestamp=data["timestamp"],
            source=data["source"],
            claim=claim,
            result=data["result"].upper(),
            verification_level=level,
            metadata=metadata,
            raw_dict=data,
        )

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "EvidenceRecord":
        path = Path(filepath)
        if not path.exists():
            raise EvidenceError(f"Evidence file not found: {filepath}")

        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise EvidenceError(f"Could not parse valid YAML evidence from {filepath}")

        return cls.from_dict(parsed)

    def verify_provenance(self, expected_commit: Optional[str] = None, expected_tree: Optional[str] = None) -> None:
        """Verifies evidence provenance and target commit/tree match.

        Fails closed with EvidenceError if provenance is invalid or target does not match.
        """
        if not self.evidence_id or not self.producer or not self.timestamp:
            raise EvidenceError(f"Evidence {self.evidence_id} fails provenance check: missing essential metadata")

        if expected_commit and self.target_commit != expected_commit:
            raise EvidenceError(
                f"Evidence {self.evidence_id} target_commit mismatch: expected {expected_commit}, got {self.target_commit}"
            )

        if expected_tree and self.target_tree != expected_tree:
            raise EvidenceError(
                f"Evidence {self.evidence_id} target_tree mismatch: expected {expected_tree}, got {self.target_tree}"
            )

    def satisfies_level(self, minimum_required_level: Union[str, VerificationLevel]) -> bool:
        """Checks if this evidence record satisfies the required verification level."""
        if isinstance(minimum_required_level, str):
            req = VerificationLevel[minimum_required_level.upper()]
        else:
            req = minimum_required_level

        return self.verification_level >= req


@dataclass(frozen=True)
class Contradiction:
    """Data model representing a detected evidence contradiction."""

    id: str
    claim_key: str
    evidence_a: EvidenceRecord
    evidence_b: EvidenceRecord
    severity: str
    status: str  # UNRESOLVED or RESOLVED


class ContradictionAnalyzer:
    """Analyzes evidence collections for contradictions and conflicting claims."""

    def __init__(self) -> None:
        self._contradictions: List[Contradiction] = []

    def analyze(self, records: List[EvidenceRecord]) -> List[Contradiction]:
        """Scans evidence records for contradictory claims or results."""
        self._contradictions.clear()

        # Group claims by type or claim_key
        by_type: Dict[str, List[EvidenceRecord]] = {}
        for rec in records:
            by_type.setdefault(rec.type, []).append(rec)

        for ev_type, items in by_type.items():
            if len(items) < 2:
                continue

            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    rec_a = items[i]
                    rec_b = items[j]

                    # 1. Check result contradiction (PASS vs FAIL)
                    if rec_a.result != rec_b.result:
                        c = Contradiction(
                            id=f"CTR-{len(self._contradictions) + 1:03d}",
                            claim_key=f"{ev_type}.result",
                            evidence_a=rec_a,
                            evidence_b=rec_b,
                            severity="P0",
                            status="UNRESOLVED",
                        )
                        self._contradictions.append(c)

                    # 2. Check numerical/claim key conflicts
                    for key in rec_a.claim:
                        if key in rec_b.claim and rec_a.claim[key] != rec_b.claim[key]:
                            c = Contradiction(
                                id=f"CTR-{len(self._contradictions) + 1:03d}",
                                claim_key=f"{ev_type}.claim.{key}",
                                evidence_a=rec_a,
                                evidence_b=rec_b,
                                severity="P0",
                                status="UNRESOLVED",
                            )
                            self._contradictions.append(c)

        return list(self._contradictions)

    def verify_no_unresolved_contradictions(self, records: List[EvidenceRecord]) -> None:
        """Verifies that no unresolved contradictions exist in the evidence set.

        Fails closed with ContradictionError if any unresolved contradiction is found.
        """
        contradictions = self.analyze(records)
        unresolved = [c for c in contradictions if c.status == "UNRESOLVED"]
        if unresolved:
            ctr_desc = "; ".join(
                f"[{c.id}] {c.claim_key}: '{c.evidence_a.evidence_id}' vs '{c.evidence_b.evidence_id}'"
                for c in unresolved
            )
            raise ContradictionError(f"Unresolved blocking contradictions detected: {ctr_desc}")

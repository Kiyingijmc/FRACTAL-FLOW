"""Tests for PGVF Evidence Engine and Contradiction Analyzer."""

import pytest

from tools.pfgv.errors import ContradictionError, EvidenceError
from tools.pfgv.evidence import ContradictionAnalyzer, EvidenceRecord, VerificationLevel


def test_valid_evidence_record_loading() -> None:
    data = {
        "evidence_id": "EV-001",
        "type": "test_result",
        "producer": "pytest_runner",
        "producer_version": "8.0",
        "target_commit": "74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d",
        "target_tree": "abc123tree",
        "timestamp": "2025-10-04T00:00:00Z",
        "source": "local_test_suite",
        "claim": {"passed_tests": 411, "failed_tests": 0},
        "result": "PASS",
        "verification_level": "E2",
        "metadata": {"coverage": 87.9},
    }
    ev = EvidenceRecord.from_dict(data)
    assert ev.evidence_id == "EV-001"
    assert ev.verification_level == VerificationLevel.E2
    ev.verify_provenance(expected_commit="74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d", expected_tree="abc123tree")


def test_mismatched_target_commit_fails_provenance() -> None:
    data = {
        "evidence_id": "EV-001",
        "type": "test_result",
        "producer": "pytest_runner",
        "producer_version": "8.0",
        "target_commit": "74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d",
        "target_tree": "abc123tree",
        "timestamp": "2025-10-04T00:00:00Z",
        "source": "local_test_suite",
        "result": "PASS",
    }
    ev = EvidenceRecord.from_dict(data)
    with pytest.raises(EvidenceError, match="target_commit mismatch"):
        ev.verify_provenance(expected_commit="DIFFERENT_COMMIT_SHA")


def test_agent_assertion_e0_cannot_satisfy_independent_acceptance() -> None:
    data = {
        "evidence_id": "EV-AGENT-001",
        "type": "agent_assertion",
        "producer": "jules_agent",
        "producer_version": "1.0",
        "target_commit": "74d42bc073f0ece4a3cc86c35dbb93fe08c5f26d",
        "target_tree": "abc123tree",
        "timestamp": "2025-10-04T00:00:00Z",
        "source": "agent_prompt_reply",
        "claim": {"statement": "I have verified my own code"},
        "result": "PASS",
        "verification_level": "E0",  # Agent Assertion
    }
    ev = EvidenceRecord.from_dict(data)
    assert not ev.satisfies_level(VerificationLevel.E3)  # Cannot satisfy Independent Verification E3


def test_contradiction_analyzer_detects_conflicting_claims() -> None:
    ev1 = EvidenceRecord.from_dict(
        {
            "evidence_id": "EV-001",
            "type": "test_result",
            "producer": "local_runner",
            "producer_version": "1.0",
            "target_commit": "74d42bc",
            "target_tree": "tree1",
            "timestamp": "2025-10-04T00:00:00Z",
            "source": "host",
            "claim": {"test_count": 411},
            "result": "PASS",
            "verification_level": "E2",
        }
    )
    ev2 = EvidenceRecord.from_dict(
        {
            "evidence_id": "EV-002",
            "type": "test_result",
            "producer": "independent_runner",
            "producer_version": "1.0",
            "target_commit": "74d42bc",
            "target_tree": "tree1",
            "timestamp": "2025-10-04T00:00:01Z",
            "source": "remote_host",
            "claim": {"test_count": 384},  # Contradictory test_count!
            "result": "PASS",
            "verification_level": "E3",
        }
    )

    analyzer = ContradictionAnalyzer()
    with pytest.raises(ContradictionError, match="Unresolved blocking contradictions detected"):
        analyzer.verify_no_unresolved_contradictions([ev1, ev2])

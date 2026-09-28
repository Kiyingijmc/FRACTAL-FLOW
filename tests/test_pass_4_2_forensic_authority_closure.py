"""Pass 4.2 Forensic Authority Closure Verification Test Suite.

Comprehensive adversarial test suite proving that callers cannot forge recovery evidence,
manipulate broker query authority, bypass orphan tracking, corrupt snapshot equivalence,
or pass invalid deal chains to authorize strategic execution.
"""

import pytest
import time
import uuid
import json
from dataclasses import replace

from src.fractal_flow.domain.models import (
    ExecutionIntent,
    Position,
    BrokerOrder,
    BrokerDeal,
    OrderSide,
    DealEntryRole,
)
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationReport,
    ReconciliationMismatchType,
    BrokerQueryResult,
    BrokerQueryQuality,
    BrokerQueryProvider,
    OrphanStatus,
)
from src.fractal_flow.execution.recovery import (
    RecoveryEngine,
    RecoveryState,
    RecoveryEvidence,
    RecoveryEvidenceError,
    RecoveryEvidenceAssembler,
    JournalRecoveryValidator,
    SnapshotRecoveryValidator,
    RiskLedgerRecoveryValidator,
    IntentRecoveryValidator,
    BrokerReconciliationValidator,
    ConfigurationValidator,
    ProtectiveMonitoringValidator,
    EvidenceProvenance,
    JournalRecoveryEvidence,
    SnapshotRecoveryEvidence,
    RiskLedgerRecoveryEvidence,
    IntentRecoveryEvidence,
    BrokerReconciliationEvidence,
    ConfigurationEvidence,
    ProtectiveMonitoringEvidence,
)
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalRecord
from src.fractal_flow.persistence.snapshot import SnapshotEngine, AggregateSnapshot, SnapshotCorruptionException
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository, IdempotencyConflictException
from src.fractal_flow.domain.event import Event


# --- Helper functions for valid evidence creation ---

def _create_valid_journal(tmp_path) -> DurableEventJournal:
    j_path = str(tmp_path / "journal.log")
    return DurableEventJournal(j_path)


def _create_assembled_evidence(session_id: str, recon_report: ReconciliationReport, journal_head_seq: int = 0) -> RecoveryEvidence:
    p_j = EvidenceProvenance(source_component="JournalRecoveryValidator", source_operation="validate", source_session=session_id, source_sequence=journal_head_seq, result="SUCCESS")
    p_s = EvidenceProvenance(source_component="SnapshotRecoveryValidator", source_operation="validate", source_session=session_id, result="SUCCESS")
    p_r = EvidenceProvenance(source_component="RiskLedgerRecoveryValidator", source_operation="reconstruct", source_session=session_id, result="SUCCESS")
    p_i = EvidenceProvenance(source_component="IntentRecoveryValidator", source_operation="reconstruct", source_session=session_id, result="SUCCESS")
    p_b = EvidenceProvenance(source_component="BrokerReconciliationValidator", source_operation="reconcile", source_session=session_id, result="SUCCESS")
    p_c = EvidenceProvenance(source_component="ConfigurationValidator", source_operation="validate", source_session=session_id, result="SUCCESS")
    p_p = EvidenceProvenance(source_component="ProtectiveMonitoringValidator", source_operation="validate", source_session=session_id, result="SUCCESS")

    j_ev = JournalRecoveryEvidence(valid=True, head_sequence=journal_head_seq, provenance=p_j)
    s_ev = SnapshotRecoveryEvidence(valid=True, provenance=p_s)
    r_ev = RiskLedgerRecoveryEvidence(valid=True, provenance=p_r)
    i_ev = IntentRecoveryEvidence(valid=True, provenance=p_i)
    b_ev = BrokerReconciliationValidator.reconcile(recon_report, session_id)
    c_ev = ConfigurationEvidence(valid=True, config_id="cfg_1", identity_matched=True, provenance=p_c)
    p_ev = ProtectiveMonitoringEvidence(valid=True, active=True, provenance=p_p)

    return RecoveryEvidenceAssembler.assemble(
        journal=j_ev,
        snapshot=s_ev,
        risk=r_ev,
        intents=i_ev,
        broker=b_ev,
        config=c_ev,
        protective=p_ev,
        session_id=session_id,
    )


# --- 1. Evidence Forgery Tests ---

def test_caller_cannot_forge_authoritative_evidence() -> None:
    engine = RecoveryEngine()
    engine.trigger_system_restart()
    engine.start_reconciliation()

    # Calling create_authoritative_evidence should return evidence marked UNAUTHORIZED_FACTORY
    forged_evidence = RecoveryEvidence.create_authoritative_evidence(session_id=engine.session_id)

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(forged_evidence)

    assert engine.state == RecoveryState.SAFE
    assert engine.can_authorize_strategic_action() is False


# --- 2. Orphan Propagation & Authorization Blocking ---

def test_orphan_count_flows_into_recovery_evidence() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )
    orphan_pos = Position(
        position_id="POS_ORPHAN", intent_id="intent_untracked", order_id="ORD_ORPHAN",
        symbol="EURUSD", side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )

    query_res = BrokerQueryResult(
        status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000,
        broker_positions={"POS_ORPHAN": orphan_pos},
    )

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
    )

    assert report.orphaned_count == 1
    broker_ev = BrokerReconciliationValidator.reconcile(report, session_id="session_1")
    assert broker_ev.orphaned_count == 1
    assert broker_ev.valid is False


def test_orphaned_broker_position_blocks_strategic_authorization(tmp_path) -> None:
    engine = RecoveryEngine()
    engine.trigger_system_restart()
    engine.start_reconciliation()

    orphan_pos = Position(
        position_id="POS_ORPHAN", intent_id="intent_untracked", order_id="ORD_ORPHAN",
        symbol="EURUSD", side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    query_res = BrokerQueryResult(
        status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000,
        broker_positions={"POS_ORPHAN": orphan_pos},
    )
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res)

    b_ev = BrokerReconciliationValidator.reconcile(report, engine.session_id)
    p_j = EvidenceProvenance(source_component="JournalRecoveryValidator", source_session=engine.session_id, result="SUCCESS")
    p_s = EvidenceProvenance(source_component="SnapshotRecoveryValidator", source_session=engine.session_id, result="SUCCESS")
    p_r = EvidenceProvenance(source_component="RiskLedgerRecoveryValidator", source_session=engine.session_id, result="SUCCESS")
    p_i = EvidenceProvenance(source_component="IntentRecoveryValidator", source_session=engine.session_id, result="SUCCESS")
    p_c = EvidenceProvenance(source_component="ConfigurationValidator", source_session=engine.session_id, result="SUCCESS")
    p_p = EvidenceProvenance(source_component="ProtectiveMonitoringValidator", source_session=engine.session_id, result="SUCCESS")

    evidence = RecoveryEvidence(
        journal_evidence=JournalRecoveryEvidence(valid=True, provenance=p_j),
        snapshot_evidence=SnapshotRecoveryEvidence(valid=True, provenance=p_s),
        risk_evidence=RiskLedgerRecoveryEvidence(valid=True, provenance=p_r),
        intent_evidence=IntentRecoveryEvidence(valid=True, provenance=p_i),
        broker_evidence=b_ev,
        config_evidence=ConfigurationEvidence(valid=True, config_id="cfg_1", identity_matched=True, provenance=p_c),
        protective_evidence=ProtectiveMonitoringEvidence(valid=True, active=True, provenance=p_p),
    )

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.SAFE


# --- 3. UNKNOWN Broker State Blocking ---

def test_unknown_broker_state_blocks_authorization() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    # Non-authoritative query
    query_res = BrokerQueryResult(
        status="NON_AUTHORITATIVE", authority=BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        query_timestamp=1000,
    )
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={"intent_1": intent}, query_result=query_res)

    assert report.unknown_count == 1
    assert report.authoritative is False

    b_ev = BrokerReconciliationValidator.reconcile(report, "session_1")
    assert b_ev.valid is False


# --- 4. Broker Authority & Query Quality ---

@pytest.mark.parametrize(
    "quality",
    [
        BrokerQueryQuality.QUERY_FAILED,
        BrokerQueryQuality.PARTIAL,
        BrokerQueryQuality.STALE,
        BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
    ],
)
def test_non_authoritative_query_never_becomes_rejection(quality: BrokerQueryQuality) -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    query_res = BrokerQueryResult(status="FAIL", authority=quality, query_timestamp=1000)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={"intent_1": intent}, query_result=query_res)

    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


def test_only_broker_query_authority_can_authorize_rejection() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    auth_query = BrokerQueryResult(status="SUCCESS", authority=BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE, query_timestamp=1000)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={"intent_1": intent}, query_result=auth_query)

    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_REJECTED


def test_authoritative_rejections_cannot_override_query_result() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    non_auth_query = BrokerQueryResult(status="NON_AUTHORITATIVE", authority=BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE, query_timestamp=1000)
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        authoritative_rejections={"intent_1"},  # Attempted override
        query_result=non_auth_query,
    )

    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


# --- 5. Snapshot Semantic Forgery & Replay Equivalence ---

def test_snapshot_self_hash_does_not_make_forged_state_valid(tmp_path) -> None:
    journal = DurableEventJournal(str(tmp_path / "journal.log"))
    evt = Event(
        event_id="e1", event_type="OpportunityDiscovered", aggregate_type="Opportunity",
        aggregate_id="A", root_id="r1", parent_id="p1", aggregate_version=1,
        source_timestamp=100, event_timestamp=100, processing_timestamp=100, payload={"balance": 100},
    )
    journal.append(evt)

    snap_engine = SnapshotEngine(str(tmp_path / "snapshots"))
    forged_payload = {"balance": 999999}  # Forged state payload not matching event log
    forged_hash = AggregateSnapshot.compute_state_hash(forged_payload)
    forged_chk = AggregateSnapshot.compute_checksum("Opportunity", "A", 1, 1, forged_payload, state_hash=forged_hash)

    snap = AggregateSnapshot(
        aggregate_type="Opportunity", aggregate_id="A", aggregate_version=1,
        last_sequence_number=1, state_payload=forged_payload, checksum=forged_chk, state_hash=forged_hash,
    )

    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.validate_snapshot_boundary(snap, journal, "Opportunity", "A")

    assert "not semantically equivalent to deterministic journal replay" in str(exc.value)


def test_corrupt_snapshot_can_fallback_to_verified_full_replay(tmp_path) -> None:
    journal = DurableEventJournal(str(tmp_path / "journal.log"))
    evt = Event(
        event_id="e1", event_type="OpportunityDiscovered", aggregate_type="Opportunity",
        aggregate_id="A", root_id="r1", parent_id="p1", aggregate_version=1,
        source_timestamp=100, event_timestamp=100, processing_timestamp=100, payload={"balance": 100},
    )
    journal.append(evt)

    snap_engine = SnapshotEngine(str(tmp_path / "snapshots"))
    forged_payload = {"balance": 999999}
    forged_hash = AggregateSnapshot.compute_state_hash(forged_payload)
    forged_chk = AggregateSnapshot.compute_checksum("Opportunity", "A", 1, 1, forged_payload, state_hash=forged_hash)
    snap = AggregateSnapshot(
        aggregate_type="Opportunity", aggregate_id="A", aggregate_version=1,
        last_sequence_number=1, state_payload=forged_payload, checksum=forged_chk, state_hash=forged_hash,
    )
    snap_engine._snapshots["Opportunity:A"] = snap

    replayed = snap_engine.replay_journal(journal, "Opportunity", "A")

    assert replayed["balance"] == 100
    assert replayed["_snapshot_valid"] is False
    assert replayed["_snapshot_fallback_used"] is True


# --- 6. Session Binding ---

def test_evidence_from_previous_recovery_session_is_rejected(tmp_path) -> None:
    engine = RecoveryEngine()
    engine.trigger_system_restart()
    old_session = engine.session_id

    query_res = BrokerQueryResult(status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res)
    old_evidence = _create_assembled_evidence(old_session, report)

    # Trigger second restart -> new session ID
    engine.trigger_system_restart()
    engine.start_reconciliation()
    assert engine.session_id != old_session

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(old_evidence)

    assert engine.state == RecoveryState.SAFE


# --- 7. Deal Semantics & Contradictions ---

def test_missing_deal_role_becomes_unknown() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )
    pos = Position(
        position_id="POS_1", intent_id="intent_1", order_id="ORD_1", symbol="EURUSD",
        side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    deal_unknown = BrokerDeal(
        deal_id="D_UNKNOWN", order_id="ORD_1", position_id="POS_1", symbol="EURUSD",
        side="BUY", volume=1.0, price=1.0850, commission=0.0, timestamp=1000,
        entry_role=DealEntryRole.UNKNOWN,
    )

    query_res = BrokerQueryResult(
        status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000,
        broker_positions={"POS_1": pos}, broker_deals={"D_UNKNOWN": deal_unknown},
    )

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
    )

    assert report.results[0].mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


def test_close_before_open_is_unknown() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )
    pos = Position(
        position_id="POS_1", intent_id="intent_1", order_id="ORD_1", symbol="EURUSD",
        side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    close_deal = BrokerDeal(
        deal_id="D_CLOSE", order_id="ORD_1", position_id="POS_1", symbol="EURUSD",
        side="SELL", volume=1.0, price=1.0850, commission=0.0, timestamp=900,  # Earlier timestamp!
        entry_role=DealEntryRole.CLOSE,
    )
    open_deal = BrokerDeal(
        deal_id="D_OPEN", order_id="ORD_1", position_id="POS_1", symbol="EURUSD",
        side="BUY", volume=1.0, price=1.0850, commission=0.0, timestamp=1000,
        entry_role=DealEntryRole.OPEN,
    )

    query_res = BrokerQueryResult(
        status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000,
        broker_positions={"POS_1": pos}, broker_deals={"D_CLOSE": close_deal, "D_OPEN": open_deal},
    )

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
    )

    assert report.results[0].mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


# --- 8. Orphan Protective Management ---

def test_orphan_position_keeps_protective_monitoring_active() -> None:
    orphan_pos = Position(
        position_id="POS_ORPHAN", intent_id="intent_untracked", order_id="ORD_ORPHAN",
        symbol="EURUSD", side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    query_res = BrokerQueryResult(status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000, broker_positions={"POS_ORPHAN": orphan_pos})
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res)

    assert len(report.orphan_records) == 1
    record = report.orphan_records[0]
    assert record.status == OrphanStatus.DETECTED
    assert record.protective_monitoring_active is True


# --- 9. Intent Fingerprint Mutations ---

def test_order_type_mutation_changes_intent_fingerprint(tmp_path) -> None:
    repo = DurableExecutionIntentRepository(str(tmp_path / "intents.db"))
    intent_base = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000, order_type="MARKET",
    )
    repo.save_intent(intent_base)

    intent_mutated = replace(intent_base, intent_id="intent_2", order_type="LIMIT")

    with pytest.raises(IdempotencyConflictException):
        repo.save_intent(intent_mutated)


def test_limit_price_mutation_changes_intent_fingerprint(tmp_path) -> None:
    repo = DurableExecutionIntentRepository(str(tmp_path / "intents.db"))
    intent_base = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000, limit_price=1.0840,
    )
    repo.save_intent(intent_base)

    intent_mutated = replace(intent_base, intent_id="intent_2", limit_price=1.0845)

    with pytest.raises(IdempotencyConflictException):
        repo.save_intent(intent_mutated)


# --- 10. Valid Legitimate Authorization Path ---

def test_legitimate_authoritative_recovery_path(tmp_path) -> None:
    engine = RecoveryEngine()
    engine.trigger_system_restart()
    engine.start_reconciliation()

    query_res = BrokerQueryResult(status="SUCCESS", authority=BrokerQueryQuality.FOUND, query_timestamp=1000)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res)

    evidence = _create_assembled_evidence(session_id=engine.session_id, recon_report=report)

    engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.RECOVERY_COMPLETE
    assert engine.can_authorize_strategic_action() is True

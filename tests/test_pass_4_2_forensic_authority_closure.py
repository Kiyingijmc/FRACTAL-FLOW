"""Pass 4.2 Forensic Authority Closure Verification Test Suite.

Comprehensive adversarial test suite proving that callers cannot forge recovery evidence,
manipulate broker query authority, bypass orphan tracking, corrupt snapshot equivalence,
transplant tokens across modified evidence, or pass invalid deal chains to authorize strategic execution.
"""

import pytest
import time
import uuid
import json
import copy
import sys
from decimal import Decimal
from typing import Any
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
    AuthoritativeBrokerAdapter,
    OrphanRecord,
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
    ProtectiveMonitoringSubsystem,
    EvidenceProvenance,
    JournalRecoveryEvidence,
    SnapshotRecoveryEvidence,
    RiskLedgerRecoveryEvidence,
    IntentRecoveryEvidence,
    BrokerReconciliationEvidence,
    ConfigurationEvidence,
    ProtectiveMonitoringEvidence,
    _AuthorityToken,
    compute_evidence_digest,
    AuthorityBootstrap,
    TrustedRuntimeBootstrap,
    CapabilityRole,
    SealedObservation,
    ValidatorCapability,
    ProducerCapability,
)
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger
from src.fractal_flow.config.config import BaseConfig, compute_effective_config
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalRecord
from src.fractal_flow.persistence.snapshot import SnapshotEngine, AggregateSnapshot, SnapshotCorruptionException
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository, IdempotencyConflictException
from src.fractal_flow.domain.event import Event


# --- Helper functions for valid capability and evidence creation ---

def _setup_test_capabilities(use_production: bool = False) -> tuple[Any, dict[str, ValidatorCapability], dict[str, ProducerCapability]]:
    if use_production:
        prod_boot = TrustedRuntimeBootstrap.bootstrap_production_runtime()
        bootstrap = prod_boot.domain
    else:
        bootstrap = AuthorityBootstrap()
    j_val_cap = bootstrap.get_validator_capability("JournalRecoveryValidator") or bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    s_val_cap = bootstrap.get_validator_capability("SnapshotRecoveryValidator") or bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    r_val_cap = bootstrap.get_validator_capability("RiskLedgerRecoveryValidator") or bootstrap.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    i_val_cap = bootstrap.get_validator_capability("IntentRecoveryValidator") or bootstrap.mint_validator_capability(CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator")
    b_val_cap = bootstrap.get_validator_capability("BrokerReconciliationValidator") or bootstrap.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")
    c_val_cap = bootstrap.get_validator_capability("ConfigurationValidator") or bootstrap.mint_validator_capability(CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator")
    p_val_cap = bootstrap.get_validator_capability("ProtectiveMonitoringValidator") or bootstrap.mint_validator_capability(CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator")

    j_prod_cap = bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    s_prod_cap = bootstrap.get_producer_capability(CapabilityRole.SNAPSHOT) or bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    r_prod_cap = bootstrap.get_producer_capability(CapabilityRole.RISK_LEDGER) or bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    i_prod_cap = bootstrap.get_producer_capability(CapabilityRole.INTENT_REPOSITORY) or bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    b_prod_cap = bootstrap.get_producer_capability(CapabilityRole.BROKER_QUERY) or bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    c_prod_cap = bootstrap.get_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION) or bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, "ConfigSubsystem")
    p_prod_cap = bootstrap.get_producer_capability(CapabilityRole.PROTECTIVE_MONITOR) or bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, "ProtectiveSubsystem")

    bootstrap.finalize()

    val_caps = {
        "JournalRecoveryValidator": j_val_cap,
        "SnapshotRecoveryValidator": s_val_cap,
        "RiskLedgerRecoveryValidator": r_val_cap,
        "IntentRecoveryValidator": i_val_cap,
        "BrokerReconciliationValidator": b_val_cap,
        "ConfigurationValidator": c_val_cap,
        "ProtectiveMonitoringValidator": p_val_cap,
    }
    prod_caps = {
        "Journal": j_prod_cap,
        "Snapshot": s_prod_cap,
        "RiskLedger": r_prod_cap,
        "IntentRepo": i_prod_cap,
        "BrokerQuery": b_prod_cap,
        "Config": c_prod_cap,
        "Protective": p_prod_cap,
    }
    return bootstrap, val_caps, prod_caps


def _query_broker_authoritative(
    producer_cap: ProducerCapability,
    session_id: str,
    orders: dict = None,
    positions: dict = None,
    deals: dict = None,
    authority: BrokerQueryQuality = BrokerQueryQuality.FOUND,
    timestamp: int = 1000,
) -> BrokerQueryResult:
    adapter = AuthoritativeBrokerAdapter(
        capability=producer_cap,
        orders=orders,
        positions=positions,
        deals=deals,
        authority=authority,
    )
    return adapter.query_broker_state(session_id, timestamp)


def _create_assembled_evidence(
    session_id: str,
    recon_report: ReconciliationReport,
    validator_caps: dict[str, ValidatorCapability],
    producer_caps: dict[str, ProducerCapability],
    journal_obj: Any = None,
    snapshot_engine_obj: Any = None,
    risk_ledger_obj: Any = None,
    intent_repo_obj: Any = None,
    config_obj: Any = None,
    protective_subsystem_obj: Any = None,
) -> RecoveryEvidence:
    if journal_obj is None:
        journal_obj = DurableEventJournal()
    if snapshot_engine_obj is None:
        snapshot_engine_obj = SnapshotEngine()
    if risk_ledger_obj is None:
        risk_ledger_obj = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    if intent_repo_obj is None:
        intent_repo_obj = DurableExecutionIntentRepository()
    if config_obj is None:
        base = BaseConfig()
        config_obj = compute_effective_config(base, "EURUSD")
    if protective_subsystem_obj is None:
        protective_subsystem_obj = ProtectiveMonitoringSubsystem()

    j_obs = journal_obj.produce_observation(session_id, producer_caps["Journal"])
    s_obs = snapshot_engine_obj.produce_observation(session_id, producer_caps["Snapshot"])
    r_obs = risk_ledger_obj.produce_observation(session_id, producer_caps["RiskLedger"])
    i_obs = intent_repo_obj.produce_observation(session_id, producer_caps["IntentRepo"])
    c_obs = config_obj.produce_observation(session_id, producer_caps["Config"])
    p_obs = protective_subsystem_obj.produce_observation(session_id, producer_caps["Protective"])

    j_ev = JournalRecoveryValidator.validate(journal_obj, session_id, validator_caps["JournalRecoveryValidator"], observation=j_obs, producer_capability=producer_caps["Journal"])
    s_ev = SnapshotRecoveryValidator.validate(snapshot_engine_obj, session_id, validator_caps["SnapshotRecoveryValidator"], observation=s_obs, producer_capability=producer_caps["Snapshot"])
    r_ev = RiskLedgerRecoveryValidator.reconstruct(risk_ledger_obj, session_id, validator_caps["RiskLedgerRecoveryValidator"], observation=r_obs, producer_capability=producer_caps["RiskLedger"])
    i_ev = IntentRecoveryValidator.reconstruct(intent_repo_obj, session_id, validator_caps["IntentRecoveryValidator"], observation=i_obs, producer_capability=producer_caps["IntentRepo"])
    b_ev = BrokerReconciliationValidator.reconcile(recon_report, session_id, validator_caps["BrokerReconciliationValidator"])
    c_ev = ConfigurationValidator.validate(config_obj, session_id, validator_caps["ConfigurationValidator"], observation=c_obs, producer_capability=producer_caps["Config"])
    p_ev = ProtectiveMonitoringValidator.validate(protective_subsystem_obj, session_id, validator_caps["ProtectiveMonitoringValidator"], observation=p_obs, producer_capability=producer_caps["Protective"])

    return RecoveryEvidenceAssembler.assemble(
        journal=j_ev,
        snapshot=s_ev,
        risk=r_ev,
        intents=i_ev,
        broker=b_ev,
        config=c_ev,
        protective=p_ev,
        session_id=session_id,
        validator_capabilities=validator_caps,
    )


# --- 1. Capability Bootstrap & Role Escalation Tests ---

def test_authority_bootstrap_role_escalation_and_finalization() -> None:
    bootstrap = AuthorityBootstrap()
    risk_cap = bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskSubsystem")

    # Attempting to mint same role twice must be rejected
    with pytest.raises(RecoveryEvidenceError) as exc:
        bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskSubsystem2")
    assert "already been minted" in str(exc.value)

    # Finalize bootstrap
    bootstrap.finalize()

    # Attempting minting post-finalization must be rejected
    with pytest.raises(RecoveryEvidenceError) as exc2:
        bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    assert "finalized" in str(exc2.value)

    # Verify risk_cap holds only role-scoped key, not master key
    assert not hasattr(risk_cap, "_master_key")
    assert risk_cap.role == CapabilityRole.RISK_LEDGER


def test_sealed_observation_signature_verification() -> None:
    bootstrap = AuthorityBootstrap()
    risk_cap = bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedger_1")
    bootstrap.finalize()

    obs = SealedObservation.create(risk_cap, "session_123", 1000, {"balance": Decimal("500.00")})

    # Verify valid signature using role key
    assert obs.verify(risk_cap.authority_domain_id, CapabilityRole.RISK_LEDGER, "session_123", risk_cap._role_key) is True

    # Reject wrong role or wrong session
    assert obs.verify(risk_cap.authority_domain_id, CapabilityRole.JOURNAL, "session_123", risk_cap._role_key) is False
    assert obs.verify(risk_cap.authority_domain_id, CapabilityRole.RISK_LEDGER, "session_wrong", risk_cap._role_key) is False


def test_compute_evidence_digest_strict_type_canonicalization() -> None:
    # Decimal canonicalization
    d1 = {"risk": Decimal("100.00")}
    d2 = {"risk": Decimal("100")}
    assert compute_evidence_digest(d1) == compute_evidence_digest(d2)

    # Fail closed on NaN or infinity
    with pytest.raises(RecoveryEvidenceError) as exc:
        compute_evidence_digest({"nan_val": float("nan")})
    assert "Non-finite float" in str(exc.value)

    # Fail closed on unsupported object
    with pytest.raises(RecoveryEvidenceError) as exc2:
        compute_evidence_digest({"raw_obj": object()})
    assert "Unsupported type" in str(exc2.value)


# --- 2. Cryptographic Token ↔ Evidence Digest Binding & Transplantation Tests ---

def test_validator_capability_required_fails_closed_when_missing() -> None:
    # Calling validator without ValidatorCapability must raise RecoveryEvidenceError
    with pytest.raises(RecoveryEvidenceError) as exc:
        JournalRecoveryValidator.validate(type("MockJournal", (), {"_faulted": False, "_global_sequence": 0})(), "session_1", capability=None)  # type: ignore
    assert "requires a valid JOURNAL_RECOVERY_VALIDATOR capability" in str(exc.value)


def test_token_transplantation_on_modified_evidence_rejected() -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], session_id)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=session_id)

    legitimate = _create_assembled_evidence(session_id, report, validator_caps=val_caps, producer_caps=prod_caps)

    # Attempt transplantation attack: dataclass.replace to tamper with evidence fields while retaining token
    tampered_journal = replace(
        legitimate.journal_evidence,
        head_sequence=9999999,  # Tampered sequence
    )

    tampered_evidence = replace(
        legitimate,
        journal_evidence=tampered_journal,
    )

    with pytest.raises(RecoveryEvidenceError) as exc:
        engine.complete_recovery_with_evidence(tampered_evidence)

    assert engine.state == RecoveryState.SAFE
    assert engine.can_authorize_strategic_action() is False


def test_token_transplantation_valid_flag_tamper_rejected() -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Create invalid evidence from a faulted journal
    faulted_journal = DurableEventJournal()
    faulted_journal._faulted = True
    j_obs = faulted_journal.produce_observation(session_id, prod_caps["Journal"])
    j_ev = JournalRecoveryValidator.validate(faulted_journal, session_id, val_caps["JournalRecoveryValidator"], observation=j_obs, producer_capability=prod_caps["Journal"])
    assert j_ev.valid is False

    # Create legitimate evidence for other subsystems
    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], session_id)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=session_id)
    legitimate_good = _create_assembled_evidence(session_id, report, validator_caps=val_caps, producer_caps=prod_caps)

    # Attempt transplanting authority token from legitimate good evidence onto invalid journal evidence with forced valid=True
    forged_j_ev = replace(
        j_ev,
        valid=True,
        _authority_token=legitimate_good.journal_evidence._authority_token,
    )

    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=forged_j_ev,
            snapshot=legitimate_good.snapshot_evidence,
            risk=legitimate_good.risk_evidence,
            intents=legitimate_good.intent_evidence,
            broker=legitimate_good.broker_evidence,
            config=legitimate_good.config_evidence,
            protective=legitimate_good.protective_evidence,
            session_id=session_id,
                validator_capabilities=val_caps,
        )


def test_subsystem_state_forgery_attacks_rejected() -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    session_id = engine.session_id

    # 1. Faulted Risk Ledger
    faulted_risk = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    faulted_risk._faulted = True
    r_obs = faulted_risk.produce_observation(session_id, prod_caps["RiskLedger"])
    r_ev = RiskLedgerRecoveryValidator.reconstruct(faulted_risk, session_id, val_caps["RiskLedgerRecoveryValidator"], observation=r_obs, producer_capability=prod_caps["RiskLedger"])
    assert r_ev.valid is False

    # 2. Inactive Protective Monitoring
    inactive_prot = ProtectiveMonitoringSubsystem(_active=False)
    p_obs = inactive_prot.produce_observation(session_id, prod_caps["Protective"])
    p_ev = ProtectiveMonitoringValidator.validate(inactive_prot, session_id, val_caps["ProtectiveMonitoringValidator"], observation=p_obs, producer_capability=prod_caps["Protective"])
    assert p_ev.valid is False

    # 3. Manually Constructed ReconciliationReport Lacking Authority Stamp
    unauthenticated_report = ReconciliationReport(
        results=(),
        unknown_count=0,
        orphaned_count=0,
        authoritative=True,
        complete=True,
        query_quality=BrokerQueryQuality.FOUND,
        query_timestamp=1000,
        temporal_boundary=1000,
        broker_orders_seen=0,
        broker_positions_seen=0,
        broker_deals_seen=0,
        generated_at=1000,
    )
    b_ev = BrokerReconciliationValidator.reconcile(unauthenticated_report, session_id, val_caps["BrokerReconciliationValidator"])
    assert b_ev.valid is False


def test_caller_cannot_forge_authoritative_evidence() -> None:
    _, val_caps, _ = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    engine.start_reconciliation()

    # Calling create_authoritative_evidence should return evidence marked UNAUTHORIZED_FACTORY
    forged_evidence = RecoveryEvidence.create_authoritative_evidence(session_id=engine.session_id)

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(forged_evidence)

    assert engine.state == RecoveryState.SAFE
    assert engine.can_authorize_strategic_action() is False


def test_fabricated_seven_validator_bundle_rejected() -> None:
    _, val_caps, _ = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    p_j = EvidenceProvenance(source_component="JournalRecoveryValidator", source_session=session_id, result="SUCCESS")
    p_s = EvidenceProvenance(source_component="SnapshotRecoveryValidator", source_session=session_id, result="SUCCESS")
    p_r = EvidenceProvenance(source_component="RiskLedgerRecoveryValidator", source_session=session_id, result="SUCCESS")
    p_i = EvidenceProvenance(source_component="IntentRecoveryValidator", source_session=session_id, result="SUCCESS")
    p_b = EvidenceProvenance(source_component="BrokerReconciliationValidator", source_session=session_id, result="SUCCESS")
    p_c = EvidenceProvenance(source_component="ConfigurationValidator", source_session=session_id, result="SUCCESS")
    p_p = EvidenceProvenance(source_component="ProtectiveMonitoringValidator", source_session=session_id, result="SUCCESS")

    j_ev = JournalRecoveryEvidence(valid=True, provenance=p_j)
    s_ev = SnapshotRecoveryEvidence(valid=True, provenance=p_s)
    r_ev = RiskLedgerRecoveryEvidence(valid=True, provenance=p_r)
    i_ev = IntentRecoveryEvidence(valid=True, provenance=p_i)
    b_ev = BrokerReconciliationEvidence(valid=True, unresolved_unknown_count=0, orphaned_count=0, provenance=p_b)
    c_ev = ConfigurationEvidence(valid=True, config_id="cfg_1", identity_matched=True, provenance=p_c)
    p_ev = ProtectiveMonitoringEvidence(valid=True, active=True, provenance=p_p)

    with pytest.raises(RecoveryEvidenceError) as exc:
        RecoveryEvidenceAssembler.assemble(
            journal=j_ev, snapshot=s_ev, risk=r_ev, intents=i_ev,
            broker=b_ev, config=c_ev, protective=p_ev, session_id=session_id,
            validator_capabilities=val_caps,
        )
    assert "forged" in str(exc.value).lower()


def test_copy_or_deepcopy_strips_authority_token() -> None:
    _, val_caps, _ = _setup_test_capabilities()
    cap = val_caps["JournalRecoveryValidator"]
    tok = cap.sign_token("session_1", "digest_123")
    assert tok is not None
    assert copy.copy(tok) is None
    assert copy.deepcopy(tok) is None


# --- 3. Orphan Lifecycle & Transition Matrix Tests ---

def test_orphan_legal_state_machine_transitions() -> None:
    orphan = OrphanRecord(
        orphan_id="ORPHAN_1", object_type="POSITION", object_id="POS_1",
        symbol="EURUSD", volume=1.0, status=OrphanStatus.DETECTED,
    )

    # DETECTED -> RECONCILING
    orphan_recon = orphan.transition(OrphanStatus.RECONCILING, reason="Reconciliation initiated")
    assert orphan_recon.status == OrphanStatus.RECONCILING

    # RECONCILING -> REATTACHED
    orphan_reattached = orphan_recon.transition(OrphanStatus.REATTACHED, reason="Matched local intent")
    assert orphan_reattached.status == OrphanStatus.REATTACHED
    assert orphan_reattached.is_resolved_or_quarantined() is True


def test_orphan_illegal_state_machine_transitions_rejected() -> None:
    orphan = OrphanRecord(
        orphan_id="ORPHAN_1", object_type="POSITION", object_id="POS_1",
        symbol="EURUSD", volume=1.0, status=OrphanStatus.DETECTED,
    )

    # Illegal transition: DETECTED -> RECOVERED directly (must go through RECONCILING)
    with pytest.raises(ValueError) as exc:
        orphan.transition(OrphanStatus.RECOVERED, reason="Direct recovery attempt")
    assert "Illegal orphan status transition" in str(exc.value)


def test_orphan_record_details_mutation_rejected() -> None:
    orphan = OrphanRecord(
        orphan_id="ORPHAN_1", object_type="POSITION", object_id="POS_1",
        symbol="EURUSD", volume=1.0, status=OrphanStatus.DETECTED,
        details={"key": "value"},
    )

    # Attempting in-place dictionary mutation must fail because details is MappingProxyType
    with pytest.raises(TypeError):
        orphan.details["key"] = "tampered"  # type: ignore


# --- 4. Orphan Propagation & Authorization Blocking ---

def test_orphan_count_flows_into_recovery_evidence() -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
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

    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], "session_1", positions={"POS_ORPHAN": orphan_pos})

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
        session_id="session_1",
    )

    assert report.orphaned_count == 1
    broker_ev = BrokerReconciliationValidator.reconcile(report, session_id="session_1", capability=val_caps["BrokerReconciliationValidator"])
    assert broker_ev.orphaned_count == 1
    assert broker_ev.valid is False


def test_orphaned_broker_position_blocks_strategic_authorization(tmp_path) -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    engine.start_reconciliation()

    orphan_pos = Position(
        position_id="POS_ORPHAN", intent_id="intent_untracked", order_id="ORD_ORPHAN",
        symbol="EURUSD", side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], engine.session_id, positions={"POS_ORPHAN": orphan_pos})
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=engine.session_id)

    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    j_obs = journal.produce_observation(engine.session_id, prod_caps["Journal"])
    s_obs = snap_engine.produce_observation(engine.session_id, prod_caps["Snapshot"])
    r_obs = risk_ledger.produce_observation(engine.session_id, prod_caps["RiskLedger"])
    i_obs = intent_repo.produce_observation(engine.session_id, prod_caps["IntentRepo"])
    c_obs = config.produce_observation(engine.session_id, prod_caps["Config"])
    p_obs = protective.produce_observation(engine.session_id, prod_caps["Protective"])

    j_ev = JournalRecoveryValidator.validate(journal, engine.session_id, val_caps["JournalRecoveryValidator"], observation=j_obs, producer_capability=prod_caps["Journal"])
    s_ev = SnapshotRecoveryValidator.validate(snap_engine, engine.session_id, val_caps["SnapshotRecoveryValidator"], observation=s_obs, producer_capability=prod_caps["Snapshot"])
    r_ev = RiskLedgerRecoveryValidator.reconstruct(risk_ledger, engine.session_id, val_caps["RiskLedgerRecoveryValidator"], observation=r_obs, producer_capability=prod_caps["RiskLedger"])
    i_ev = IntentRecoveryValidator.reconstruct(intent_repo, engine.session_id, val_caps["IntentRecoveryValidator"], observation=i_obs, producer_capability=prod_caps["IntentRepo"])
    b_ev = BrokerReconciliationValidator.reconcile(report, engine.session_id, val_caps["BrokerReconciliationValidator"])
    c_ev = ConfigurationValidator.validate(config, engine.session_id, val_caps["ConfigurationValidator"], observation=c_obs, producer_capability=prod_caps["Config"])
    p_ev = ProtectiveMonitoringValidator.validate(protective, engine.session_id, val_caps["ProtectiveMonitoringValidator"], observation=p_obs, producer_capability=prod_caps["Protective"])

    evidence = RecoveryEvidence(
        journal_evidence=j_ev, snapshot_evidence=s_ev, risk_evidence=r_ev, intent_evidence=i_ev,
        broker_evidence=b_ev, config_evidence=c_ev, protective_evidence=p_ev
    )

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.SAFE


# --- 5. UNKNOWN Broker State Blocking ---

def test_unknown_broker_state_blocks_authorization() -> None:
    _, val_caps, _ = _setup_test_capabilities()
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    query_res = BrokerQueryResult(
        status="NON_AUTHORITATIVE", authority=BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
        query_timestamp=1000,
    )
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={"intent_1": intent}, query_result=query_res)

    assert report.unknown_count == 1
    assert report.authoritative is False

    b_ev = BrokerReconciliationValidator.reconcile(report, "session_1", capability=val_caps["BrokerReconciliationValidator"])
    assert b_ev.valid is False


# --- 6. Broker Authority & Query Quality ---

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
    _, _, prod_caps = _setup_test_capabilities()
    intent = ExecutionIntent(
        intent_id="intent_1", decision_id="dec_1", opportunity_id="opp_1", root_id="root_1",
        idempotency_key="key_1", symbol="EURUSD", side=OrderSide.BUY, requested_volume=1.0,
        entry_price=1.0850, sl=1.0820, tp_plan={}, effective_config_id="cfg_1", lineage_version=1,
        broker_constraint_snapshot={}, quote_timestamp=1000, spread_pips=1.0, status="EXEC_SUBMITTED",
        created_at=1000, updated_at=1000,
    )

    auth_query = _query_broker_authoritative(prod_caps["BrokerQuery"], "session_1", authority=BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE)
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


# --- 7. Snapshot Semantic Forgery & Replay Equivalence ---

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


# --- 8. Session Binding ---

def test_evidence_from_previous_recovery_session_is_rejected(tmp_path) -> None:
    _, val_caps, prod_caps = _setup_test_capabilities()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    old_session = engine.session_id

    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], old_session)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=old_session)
    old_evidence = _create_assembled_evidence(old_session, report, validator_caps=val_caps, producer_caps=prod_caps)

    # Trigger second restart -> new session ID
    engine.trigger_system_restart()
    engine.start_reconciliation()
    assert engine.session_id != old_session

    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(old_evidence)

    assert engine.state == RecoveryState.SAFE


# --- 9. Deal Semantics & Contradictions ---

def test_missing_deal_role_becomes_unknown() -> None:
    _, _, prod_caps = _setup_test_capabilities()
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

    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], "session_1", positions={"POS_1": pos}, deals={"D_UNKNOWN": deal_unknown})

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
    )

    assert report.results[0].mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


def test_close_before_open_is_unknown() -> None:
    _, _, prod_caps = _setup_test_capabilities()
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

    query_res = _query_broker_authoritative(
        prod_caps["BrokerQuery"], "session_1",
        positions={"POS_1": pos}, deals={"D_CLOSE": close_deal, "D_OPEN": open_deal},
    )

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={"intent_1": intent},
        query_result=query_res,
    )

    assert report.results[0].mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert report.results[0].resolved_execution_state == ExecutionState.EXEC_UNKNOWN


# --- 10. Orphan Protective Management ---

def test_orphan_position_keeps_protective_monitoring_active() -> None:
    _, _, prod_caps = _setup_test_capabilities()
    orphan_pos = Position(
        position_id="POS_ORPHAN", intent_id="intent_untracked", order_id="ORD_ORPHAN",
        symbol="EURUSD", side="BUY", requested_volume=1.0, filled_volume=1.0, remaining_volume=0.0,
        entry_price=1.0850, current_sl=1.0820, lifecycle_state="POS_ACTIVE", health_state="HEALTH_HEALTHY", opened_at=1000,
    )
    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], "session_1", positions={"POS_ORPHAN": orphan_pos})
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res)

    assert len(report.orphan_records) == 1
    record = report.orphan_records[0]
    assert record.status == OrphanStatus.DETECTED
    assert record.protective_monitoring_active is True


# --- 11. Intent Fingerprint Mutations ---

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


# --- 12. Valid Legitimate Authorization Path ---

def test_legitimate_authoritative_recovery_path(tmp_path) -> None:
    _, val_caps, prod_caps = _setup_test_capabilities(use_production=True)
    prod_boot = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    engine = prod_boot.create_recovery_engine()
    engine.trigger_system_restart()
    engine.start_reconciliation()

    query_res = _query_broker_authoritative(prod_caps["BrokerQuery"], engine.session_id)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=engine.session_id)

    evidence = _create_assembled_evidence(session_id=engine.session_id, recon_report=report, validator_caps=val_caps, producer_caps=prod_caps)

    engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.RECOVERY_COMPLETE
    assert engine.can_authorize_strategic_action() is True

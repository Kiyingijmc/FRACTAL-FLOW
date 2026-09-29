"""Dedicated Adversarial Authority Provenance Hardening Test Suite.

Exhaustive negative and positive test matrix for Pass 4.2 authority provenance hardening,
covering capability attacks, subsystem forgery, token/evidence transplantation,
snapshot business field canonicalization, orphan deep immutability, REVERSAL deal accounting,
and recovery gate independent verification.
"""

import pytest
import copy
from dataclasses import replace

from src.fractal_flow.domain.models import (
    ExecutionIntent,
    Position,
    BrokerDeal,
    OrderSide,
    DealEntryRole,
)
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationMismatchType,
    BrokerQueryResult,
    BrokerQueryQuality,
    AuthoritativeBrokerAdapter,
    OrphanRecord,
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
    _RecoveryAuthorityBundle,
    AuthorityBootstrap,
    CapabilityRole,
    SealedObservation,
    ValidatorCapability,
    ProducerCapability,
)
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger, LedgerOperation
from src.fractal_flow.config.config import BaseConfig, compute_effective_config
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import (
    SnapshotEngine,
    SnapshotCorruptionException,
)
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository
from src.fractal_flow.domain.event import Event


def _bootstrap_all() -> tuple[
    AuthorityBootstrap, dict[str, ValidatorCapability], dict[str, ProducerCapability]
]:
    bootstrap = AuthorityBootstrap()
    val_caps = {
        "JournalRecoveryValidator": bootstrap.mint_validator_capability(
            CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
        ),
        "SnapshotRecoveryValidator": bootstrap.mint_validator_capability(
            CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator"
        ),
        "RiskLedgerRecoveryValidator": bootstrap.mint_validator_capability(
            CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator"
        ),
        "IntentRecoveryValidator": bootstrap.mint_validator_capability(
            CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator"
        ),
        "BrokerReconciliationValidator": bootstrap.mint_validator_capability(
            CapabilityRole.BROKER_RECONCILIATION_VALIDATOR,
            "BrokerReconciliationValidator",
        ),
        "ConfigurationValidator": bootstrap.mint_validator_capability(
            CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator"
        ),
        "ProtectiveMonitoringValidator": bootstrap.mint_validator_capability(
            CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR,
            "ProtectiveMonitoringValidator",
        ),
    }
    prod_caps = {
        "Journal": bootstrap.mint_producer_capability(
            CapabilityRole.JOURNAL, "JournalSubsystem"
        ),
        "Snapshot": bootstrap.mint_producer_capability(
            CapabilityRole.SNAPSHOT, "SnapshotSubsystem"
        ),
        "RiskLedger": bootstrap.mint_producer_capability(
            CapabilityRole.RISK_LEDGER, "RiskSubsystem"
        ),
        "IntentRepo": bootstrap.mint_producer_capability(
            CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem"
        ),
        "BrokerQuery": bootstrap.mint_producer_capability(
            CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem"
        ),
        "Config": bootstrap.mint_producer_capability(
            CapabilityRole.EFFECTIVE_CONFIGURATION, "ConfigSubsystem"
        ),
        "Protective": bootstrap.mint_producer_capability(
            CapabilityRole.PROTECTIVE_MONITOR, "ProtectiveSubsystem"
        ),
    }
    bootstrap.finalize()
    return bootstrap, val_caps, prod_caps


# --- 1. CAPABILITY ATTACKS ---


def test_direct_validator_capability_construction_rejected() -> None:
    with pytest.raises(RecoveryEvidenceError) as exc:
        ValidatorCapability(
            authority_domain_id="ATTACKER_DOMAIN",
            role=CapabilityRole.JOURNAL_RECOVERY_VALIDATOR,
            validator_id="JournalRecoveryValidator",
            _role_key=b"attacker_key_32_bytes_long_12345",
        )
    assert "Direct instantiation of ValidatorCapability is forbidden" in str(exc.value)


def test_direct_producer_capability_construction_rejected() -> None:
    with pytest.raises(RecoveryEvidenceError) as exc:
        ProducerCapability(
            authority_domain_id="ATTACKER_DOMAIN",
            role=CapabilityRole.JOURNAL,
            producer_id="FakeJournalProducer",
            _role_key=b"attacker_key_32_bytes_long_12345",
        )
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)


def test_cross_validator_capability_transplantation_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    journal = DurableEventJournal()
    session_id = "sess_cross_val"
    j_obs = journal.produce_observation(session_id, prod_caps["Journal"])

    # Attempt using Snapshot validator capability for JournalRecoveryValidator
    with pytest.raises(RecoveryEvidenceError) as exc:
        JournalRecoveryValidator.validate(
            journal,
            session_id,
            capability=val_caps["SnapshotRecoveryValidator"],  # Wrong capability!
            observation=j_obs,
            producer_capability=prod_caps["Journal"],
        )
    assert "requires a valid JOURNAL_RECOVERY_VALIDATOR capability" in str(exc.value)


def test_capability_copy_and_deepcopy_return_none() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    v_cap = val_caps["JournalRecoveryValidator"]
    p_cap = prod_caps["Journal"]

    assert copy.copy(v_cap) is None
    assert copy.deepcopy(v_cap) is None
    assert copy.copy(p_cap) is None
    assert copy.deepcopy(p_cap) is None


# --- 2. JOURNAL ATTACKS ---


def test_fake_duck_typed_journal_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_fake_j"

    fake_journal = type(
        "FakeJournal", (), {"_faulted": False, "_global_sequence": 100}
    )()
    obs = SealedObservation.create(
        prod_caps["Journal"],
        session_id,
        1000,
        {"faulted": False, "global_sequence": 100, "journal_path": ""},
    )

    ev = JournalRecoveryValidator.validate(
        fake_journal,
        session_id,
        capability=val_caps["JournalRecoveryValidator"],
        observation=obs,
        producer_capability=prod_caps["Journal"],
    )
    assert ev.valid is False
    assert "DurableEventJournal" in ev.provenance.failure_reason


def test_tampered_journal_sequence_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_tamper_j"
    journal = DurableEventJournal()

    # Produce observation for initial sequence 0
    obs = journal.produce_observation(session_id, prod_caps["Journal"])

    # Tamper with live sequence
    journal._global_sequence = 9999

    ev = JournalRecoveryValidator.validate(
        journal,
        session_id,
        capability=val_caps["JournalRecoveryValidator"],
        observation=obs,
        producer_capability=prod_caps["Journal"],
    )
    assert ev.valid is False
    assert "contradicts sealed observation" in ev.provenance.failure_reason


# --- 3. RISK LEDGER ATTACKS ---


def test_fake_risk_ledger_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_fake_r"

    fake_risk = type(
        "FakeRisk", (), {"entries": [], "remaining_risk": 500.0, "_faulted": False}
    )()
    obs = SealedObservation.create(
        prod_caps["RiskLedger"],
        session_id,
        1000,
        {
            "budget_id": "b1",
            "opportunity_id": "o1",
            "entries_count": 0,
            "total_risk": "500",
            "remaining_risk": "500",
            "allocated_risk": "0",
            "reserved_risk": "0",
            "consumed_risk": "0",
            "faulted": False,
        },
    )

    ev = RiskLedgerRecoveryValidator.reconstruct(
        fake_risk,
        session_id,
        capability=val_caps["RiskLedgerRecoveryValidator"],
        observation=obs,
        producer_capability=prod_caps["RiskLedger"],
    )
    assert ev.valid is False
    assert "OpportunityRiskLedger" in ev.provenance.failure_reason


def test_tampered_remaining_risk_and_entries_count_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_risk_tamper"
    ledger = OpportunityRiskLedger("b1", "o1", 500.0, 1.0)
    obs = ledger.produce_observation(session_id, prod_caps["RiskLedger"])

    # Tamper with ledger entries
    ledger.record_operation("e1", LedgerOperation.RESERVE, 100.0, 0.2, "r1", "c1", 1000)

    ev = RiskLedgerRecoveryValidator.reconstruct(
        ledger,
        session_id,
        capability=val_caps["RiskLedgerRecoveryValidator"],
        observation=obs,
        producer_capability=prod_caps["RiskLedger"],
    )
    assert ev.valid is False
    assert "contradicts sealed observation" in ev.provenance.failure_reason


# --- 4. INTENT REPOSITORY ATTACKS ---


def test_plain_object_intent_repo_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_fake_repo"

    obs = SealedObservation.create(
        prod_caps["IntentRepo"],
        session_id,
        1000,
        {"db_path": "", "intents_count": 0, "idempotency_keys_count": 0},
    )

    ev = IntentRecoveryValidator.reconstruct(
        object(),
        session_id,
        capability=val_caps["IntentRecoveryValidator"],
        observation=obs,
        producer_capability=prod_caps["IntentRepo"],
    )
    assert ev.valid is False
    assert "DurableExecutionIntentRepository" in ev.provenance.failure_reason


# --- 5. CONFIGURATION ATTACKS ---


def test_raw_string_config_authority_rejected() -> None:
    _, val_caps, _ = _bootstrap_all()
    session_id = "sess_raw_str_cfg"

    ev = ConfigurationValidator.validate(
        "cfg_12345",
        session_id,
        capability=val_caps["ConfigurationValidator"],
    )
    assert ev.valid is False
    assert "Raw string identity assertion rejected" in ev.provenance.failure_reason


def test_effective_config_id_mismatch_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_cfg_mismatch"

    config = compute_effective_config(BaseConfig(), "EURUSD")
    obs = config.produce_observation(session_id, prod_caps["Config"])

    ev = ConfigurationValidator.validate(
        config,
        session_id,
        capability=val_caps["ConfigurationValidator"],
        expected_config_id="cfg_EXPECTED_DIFFERENT",
        observation=obs,
        producer_capability=prod_caps["Config"],
    )
    assert ev.valid is False


# --- 6. PROTECTIVE MONITORING ATTACKS ---


def test_raw_boolean_protective_monitoring_rejected() -> None:
    _, val_caps, _ = _bootstrap_all()
    session_id = "sess_bool_prot"

    ev_true = ProtectiveMonitoringValidator.validate(
        True, session_id, capability=val_caps["ProtectiveMonitoringValidator"]
    )
    assert ev_true.valid is False
    assert "Raw boolean assertion rejected" in ev_true.provenance.failure_reason

    ev_false = ProtectiveMonitoringValidator.validate(
        False, session_id, capability=val_caps["ProtectiveMonitoringValidator"]
    )
    assert ev_false.valid is False


def test_fake_active_attribute_object_rejected() -> None:
    _, val_caps, prod_caps = _bootstrap_all()
    session_id = "sess_fake_prot"

    fake_prot = type("FakeProt", (), {"active": True, "is_active": lambda self: True})()
    obs = SealedObservation.create(
        prod_caps["Protective"],
        session_id,
        1000,
        {"subsystem_id": "ProtectiveSubsystem", "active": True, "faulted": False},
    )

    ev = ProtectiveMonitoringValidator.validate(
        fake_prot,
        session_id,
        capability=val_caps["ProtectiveMonitoringValidator"],
        observation=obs,
        producer_capability=prod_caps["Protective"],
    )
    assert ev.valid is False
    assert "ProtectiveMonitoringSubsystem" in ev.provenance.failure_reason


# --- 7. BROKER ATTACKS ---


def test_direct_broker_query_result_claiming_found_downgraded() -> None:
    query_res = BrokerQueryResult(
        status="SUCCESS",
        authority=BrokerQueryQuality.FOUND,
        query_timestamp=1000,
    )
    # Direct construction without issuance key must be downgraded to NOT_FOUND_NON_AUTHORITATIVE
    assert query_res.authority == BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
    assert query_res.status == "NON_AUTHORITATIVE"


def test_tampered_broker_observation_positions_rejected() -> None:
    _, _, prod_caps = _bootstrap_all()
    session_id = "sess_tamper_broker"

    adapter = AuthoritativeBrokerAdapter(
        capability=prod_caps["BrokerQuery"],
        authority=BrokerQueryQuality.FOUND,
    )
    obs = adapter.produce_broker_observation(session_id)

    # Tamper with observation payload
    tampered_payload = dict(obs.frozen_payload)
    tampered_payload["broker_positions"] = {
        "POS_FORGED": Position(
            "POS_FORGED",
            "intent_1",
            "ORD_1",
            "EURUSD",
            "BUY",
            1.0,
            1.0,
            0.0,
            1.085,
            1.082,
            "POS_ACTIVE",
            "HEALTH_HEALTHY",
            1000,
        )
    }

    forged_obs = replace(obs, frozen_payload=tampered_payload)

    with pytest.raises(RecoveryEvidenceError) as exc:
        BrokerQueryResult.from_observation(
            forged_obs, prod_caps["BrokerQuery"], session_id
        )
    assert "SealedObservation verification failed" in str(exc.value)


# --- 8. SNAPSHOT CANONICALIZATION ATTACKS ---


def test_underscore_prefixed_business_field_mutation_fails_snapshot_equivalence(
    tmp_path,
) -> None:
    journal = DurableEventJournal(str(tmp_path / "journal.log"))
    evt = Event(
        event_id="e1",
        event_type="OpportunityDiscovered",
        aggregate_type="Opportunity",
        aggregate_id="A",
        root_id="r1",
        parent_id="p1",
        aggregate_version=1,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        payload={"_business_state": "ORIGINAL_BUSINESS_VAL"},
    )
    journal.append(evt)

    snap_engine = SnapshotEngine(str(tmp_path / "snapshots"))

    # Forged snapshot mutating _business_state
    forged_payload = {"_business_state": "FORGED_BUSINESS_VAL"}
    snap = snap_engine.save_snapshot(
        "Opportunity", "A", version=1, last_seq=1, payload=forged_payload
    )

    # Equivalence verification MUST catch _business_state mutation!
    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.verify_snapshot_equivalence(snap, journal, "Opportunity", "A")
    assert "not semantically equivalent" in str(exc.value)


def test_legitimate_replay_diagnostic_field_excluded_from_snapshot_equivalence(
    tmp_path,
) -> None:
    journal = DurableEventJournal(str(tmp_path / "journal.log"))
    evt = Event(
        event_id="e1",
        event_type="OpportunityDiscovered",
        aggregate_type="Opportunity",
        aggregate_id="A",
        root_id="r1",
        parent_id="p1",
        aggregate_version=1,
        source_timestamp=100,
        event_timestamp=100,
        processing_timestamp=100,
        payload={"balance": 100},
    )
    journal.append(evt)

    snap_engine = SnapshotEngine(str(tmp_path / "snapshots"))
    # Snapshot containing _last_seq replay diagnostic
    snap_payload = {
        "balance": 100,
        "_last_seq": 1,
        "_last_version": 1,
        "_snapshot_valid": True,
    }
    snap = snap_engine.save_snapshot(
        "Opportunity", "A", version=1, last_seq=1, payload=snap_payload
    )

    # Replay equivalence must succeed despite diagnostic fields
    snap_engine.verify_snapshot_equivalence(snap, journal, "Opportunity", "A")


# --- 9. ORPHAN DEEP IMMUTABILITY ATTACKS ---


def test_orphan_record_nested_tuples_and_mappings_immutable() -> None:
    nested_details = {
        "nested_dict": {"k": "v"},
        "nested_list": [1, 2, {"inner": "data"}],
        "nested_tuple": (1, {"inner_t": "data"}),
        "nested_set": {1, 2, 3},
    }
    orphan = OrphanRecord(
        orphan_id="O1",
        object_type="POSITION",
        object_id="P1",
        symbol="EURUSD",
        volume=1.0,
        details=nested_details,
    )

    # Attempt mutating nested dictionary in details
    with pytest.raises(TypeError):
        orphan.details["nested_dict"]["k"] = "tampered"  # type: ignore

    # Attempt mutating nested dictionary inside tuple
    with pytest.raises(TypeError):
        orphan.details["nested_tuple"][1]["inner_t"] = "tampered"  # type: ignore


def test_orphan_record_unsupported_mutable_type_rejected() -> None:
    class MutableObj:
        def __init__(self) -> None:
            self.x = 10

    with pytest.raises(TypeError) as exc:
        OrphanRecord(
            orphan_id="O1",
            object_type="POSITION",
            object_id="P1",
            symbol="EURUSD",
            volume=1.0,
            details={"custom": MutableObj()},
        )
    assert "Unsupported or mutable custom type" in str(exc.value)


# --- 10. REVERSAL DEAL ACCOUNTING EXHAUSTIVE MATRIX ---


def test_reversal_deal_accounting_exhaustive_matrix() -> None:
    intent = ExecutionIntent(
        intent_id="intent_rev",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_rev",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_FILLED",
        created_at=1000,
        updated_at=1000,
    )

    # 1. OPEN -> REVERSAL (Full flip from BUY 1.0 to SELL 1.0)
    pos_flip = Position(
        "POS_REV1",
        "intent_rev",
        "ORD_1",
        "EURUSD",
        "SELL",
        1.0,
        1.0,
        0.0,
        1.085,
        1.082,
        "POS_ACTIVE",
        "HEALTH_HEALTHY",
        1000,
    )
    deal_open = BrokerDeal(
        "D1",
        "ORD_1",
        "POS_REV1",
        "EURUSD",
        "BUY",
        1.0,
        1.085,
        0.0,
        1000,
        DealEntryRole.OPEN,
    )
    deal_rev = BrokerDeal(
        "D2",
        "ORD_2",
        "POS_REV1",
        "EURUSD",
        "SELL",
        2.0,
        1.085,
        0.0,
        1100,
        DealEntryRole.REVERSAL,
    )  # 1.0 close + 1.0 open opposite

    res1 = ReconciliationEngine.reconcile_intent(
        intent, {}, {"POS_REV1": pos_flip}, {"D1": deal_open, "D2": deal_rev}
    )
    assert res1.mismatch_type == ReconciliationMismatchType.MATCH
    assert res1.resolved_execution_state == ExecutionState.EXEC_FILLED

    # 2. REVERSAL without OPEN -> Rejected to EXEC_UNKNOWN
    res2 = ReconciliationEngine.reconcile_intent(
        intent, {}, {"POS_REV1": pos_flip}, {"D2": deal_rev}
    )
    assert res2.mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert res2.resolved_execution_state == ExecutionState.EXEC_UNKNOWN

    # 3. Same-side REVERSAL -> Rejected to EXEC_UNKNOWN
    deal_rev_same = BrokerDeal(
        "D3",
        "ORD_3",
        "POS_REV1",
        "EURUSD",
        "BUY",
        2.0,
        1.085,
        0.0,
        1100,
        DealEntryRole.REVERSAL,
    )
    res3 = ReconciliationEngine.reconcile_intent(
        intent, {}, {"POS_REV1": pos_flip}, {"D1": deal_open, "D3": deal_rev_same}
    )
    assert res3.mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert res3.resolved_execution_state == ExecutionState.EXEC_UNKNOWN


# --- 11. RECOVERY GATE INDEPENDENT VERIFICATION ---


def test_recovery_gate_independently_verifies_authority_chain() -> None:
    bootstrap, val_caps, prod_caps = _bootstrap_all()
    engine = RecoveryEngine(validator_capabilities=val_caps)
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Create another bootstrap instance (simulating attacker keys)
    attacker_bootstrap = AuthorityBootstrap()
    attacker_val_cap = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )
    attacker_bootstrap.finalize()

    # Create journal evidence signed by attacker capability
    journal = DurableEventJournal()
    j_obs = journal.produce_observation(session_id, prod_caps["Journal"])
    forged_j_ev = JournalRecoveryValidator.validate(
        journal,
        session_id,
        attacker_val_cap,
        observation=j_obs,
        producer_capability=prod_caps["Journal"],
    )

    # Legitimate evidence for other components
    adapter = AuthoritativeBrokerAdapter(
        capability=prod_caps["BrokerQuery"], authority=BrokerQueryQuality.FOUND
    )
    query_res = adapter.query_broker_state(session_id)
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={}, query_result=query_res, session_id=session_id
    )

    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    s_obs = snap_engine.produce_observation(session_id, prod_caps["Snapshot"])
    r_obs = risk_ledger.produce_observation(session_id, prod_caps["RiskLedger"])
    i_obs = intent_repo.produce_observation(session_id, prod_caps["IntentRepo"])
    c_obs = config.produce_observation(session_id, prod_caps["Config"])
    p_obs = protective.produce_observation(session_id, prod_caps["Protective"])

    s_ev = SnapshotRecoveryValidator.validate(
        snap_engine,
        session_id,
        val_caps["SnapshotRecoveryValidator"],
        observation=s_obs,
        producer_capability=prod_caps["Snapshot"],
    )
    r_ev = RiskLedgerRecoveryValidator.reconstruct(
        risk_ledger,
        session_id,
        val_caps["RiskLedgerRecoveryValidator"],
        observation=r_obs,
        producer_capability=prod_caps["RiskLedger"],
    )
    i_ev = IntentRecoveryValidator.reconstruct(
        intent_repo,
        session_id,
        val_caps["IntentRecoveryValidator"],
        observation=i_obs,
        producer_capability=prod_caps["IntentRepo"],
    )
    b_ev = BrokerReconciliationValidator.reconcile(
        report, session_id, val_caps["BrokerReconciliationValidator"]
    )
    c_ev = ConfigurationValidator.validate(
        config,
        session_id,
        val_caps["ConfigurationValidator"],
        observation=c_obs,
        producer_capability=prod_caps["Config"],
    )
    p_ev = ProtectiveMonitoringValidator.validate(
        protective,
        session_id,
        val_caps["ProtectiveMonitoringValidator"],
        observation=p_obs,
        producer_capability=prod_caps["Protective"],
    )

    # Attempt assembly with attacker-signed journal token MUST raise RecoveryEvidenceError
    with pytest.raises(RecoveryEvidenceError) as exc:
        RecoveryEvidenceAssembler.assemble(
            journal=forged_j_ev,
            snapshot=s_ev,
            risk=r_ev,
            intents=i_ev,
            broker=b_ev,
            config=c_ev,
            protective=p_ev,
            session_id=session_id,
            validator_capabilities=val_caps,
        )
    assert "invalid, forged, or payload-mismatched" in str(exc.value)

    # Verify un-assembled forged evidence fails RecoveryEngine gate
    unauth_bundle = RecoveryEvidence(
        journal_evidence=forged_j_ev,
        snapshot_evidence=s_ev,
        risk_evidence=r_ev,
        intent_evidence=i_ev,
        broker_evidence=b_ev,
        config_evidence=c_ev,
        protective_evidence=p_ev,
        _authority_bundle=_RecoveryAuthorityBundle(
            journal_token=forged_j_ev._authority_token, session_id=session_id
        ),
    )
    with pytest.raises(RecoveryEvidenceError):
        engine.complete_recovery_with_evidence(unauth_bundle)

    assert engine.state == RecoveryState.SAFE
    assert engine.can_authorize_strategic_action() is False

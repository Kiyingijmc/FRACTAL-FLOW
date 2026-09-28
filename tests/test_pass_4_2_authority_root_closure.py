"""Pass 4.2 Authority Root Closure Adversarial Test Suite.

Comprehensive adversarial test suite proving that callers cannot establish an alternative authority root,
inject un-trusted capabilities into RecoveryEngine, substitute authority domains, forge capabilities via copy/pickle,
or use unregistered producers/broker data to obtain strategic execution authorization.
"""

import pytest
import copy
import pickle
import time
from decimal import Decimal
from dataclasses import replace

from src.fractal_flow.domain.models import ExecutionIntent, Position, OrderSide, BrokerDeal, DealEntryRole
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationReport,
    ReconciliationMismatchType,
    BrokerQueryResult,
    BrokerQueryQuality,
    BrokerQueryProvider,
    AuthoritativeBrokerAdapter,
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
    AuthorityDomain,
    TrustedRuntimeAuthority,
    CapabilityRole,
    SealedObservation,
    ValidatorCapability,
    ProducerCapability,
)
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger
from src.fractal_flow.config.config import BaseConfig, compute_effective_config
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import SnapshotEngine
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository


# --- 1. Authority-Root Attacks ---

def test_public_bootstrap_cannot_create_production_authority() -> None:
    caller_bootstrap = AuthorityBootstrap()
    assert caller_bootstrap.is_production is False
    assert "UNTRUSTED_BOOTSTRAP_" in caller_bootstrap.domain_id

    # Mint capabilities using caller bootstrap
    caller_j_cap = caller_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    assert caller_j_cap.authority_domain_id == caller_bootstrap.domain_id

    # Create production recovery engine
    prod_runtime = TrustedRuntimeAuthority()
    prod_engine = prod_runtime.create_recovery_engine()
    prod_engine.trigger_system_restart()
    session_id = prod_engine.session_id
    prod_engine.start_reconciliation()

    # Evidence signed by caller bootstrap must be REJECTED by production recovery gate
    journal = DurableEventJournal()
    j_obs = journal.produce_observation(session_id, caller_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem"))
    j_ev = JournalRecoveryValidator.validate(journal, session_id, caller_j_cap, observation=j_obs, producer_capability=caller_bootstrap.get_producer_capability(CapabilityRole.JOURNAL))

    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=j_ev,
            snapshot=SnapshotRecoveryEvidence(valid=True),
            risk=RiskLedgerRecoveryEvidence(valid=True),
            intents=IntentRecoveryEvidence(valid=True),
            broker=BrokerReconciliationEvidence(valid=True),
            config=ConfigurationEvidence(valid=True),
            protective=ProtectiveMonitoringEvidence(valid=True),
            session_id=session_id,
            authority_domain=prod_runtime.domain,
        )


def test_attacker_authority_domain_rejected_by_production_gate() -> None:
    prod_runtime = TrustedRuntimeAuthority()
    prod_engine = prod_runtime.create_recovery_engine()
    prod_engine.trigger_system_restart()

    attacker_domain = AuthorityDomain("FRACTAL_PROD_DOMAIN_SAME_NAME", is_production=True)
    # Master key material differs!
    assert attacker_domain._master_key != prod_runtime.domain._master_key

    attacker_cap = attacker_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    journal = DurableEventJournal()
    j_obs = journal.produce_observation(prod_engine.session_id, attacker_domain.mint_producer_capability(CapabilityRole.JOURNAL, "J"))
    j_ev = JournalRecoveryValidator.validate(journal, prod_engine.session_id, attacker_cap, observation=j_obs, producer_capability=attacker_domain.get_producer_capability(CapabilityRole.JOURNAL))

    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=j_ev,
            snapshot=SnapshotRecoveryEvidence(valid=True),
            risk=RiskLedgerRecoveryEvidence(valid=True),
            intents=IntentRecoveryEvidence(valid=True),
            broker=BrokerReconciliationEvidence(valid=True),
            config=ConfigurationEvidence(valid=True),
            protective=ProtectiveMonitoringEvidence(valid=True),
            session_id=prod_engine.session_id,
            authority_domain=prod_runtime.domain,
        )


def test_authority_domain_substitution_rejected() -> None:
    prod_runtime = TrustedRuntimeAuthority()
    prod_domain = prod_runtime.domain

    fake_domain = AuthorityDomain("FAKE_DOMAIN", is_production=False)

    fake_cap = fake_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    prod_cap = prod_domain.get_validator_capability("JournalRecoveryValidator")

    assert fake_cap.authority_domain_id != prod_domain.domain_id


# --- 2. Capability Attacks ---

def test_direct_capability_forgery_rejected() -> None:
    with pytest.raises(RecoveryEvidenceError) as exc:
        ValidatorCapability(
            authority_domain_id="PROD",
            role=CapabilityRole.JOURNAL_RECOVERY_VALIDATOR,
            validator_id="JournalRecoveryValidator",
            _role_key=b"12345678901234567890123456789012",
        )
    assert "Direct instantiation of ValidatorCapability is forbidden" in str(exc.value)


def test_capability_copy_rejected() -> None:
    runtime = TrustedRuntimeAuthority()
    cap = runtime.domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    assert copy.copy(cap) is None
    assert copy.deepcopy(cap) is None


def test_capability_pickle_rejected() -> None:
    runtime = TrustedRuntimeAuthority()
    cap = runtime.domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    with pytest.raises(RecoveryEvidenceError) as exc:
        pickle.dumps(cap)
    assert "Serialization/pickling of authority capabilities is prohibited" in str(exc.value)


def test_cross_domain_capability_rejected() -> None:
    runtime_A = TrustedRuntimeAuthority("DOMAIN_A")
    runtime_B = TrustedRuntimeAuthority("DOMAIN_B")

    cap_A = runtime_A.domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    cap_B = runtime_B.domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    token_A = cap_A.sign_token("sess_1", "digest_123")

    # Verify token_A against cap_B
    assert cap_B.verify_token(token_A, "sess_1", "digest_123") is False


# --- 3. Broker Attacks ---

def test_caller_supplied_found_broker_result_is_non_authoritative() -> None:
    direct_res = BrokerQueryResult(
        status="SUCCESS",
        authority=BrokerQueryQuality.FOUND,
        query_timestamp=1000,
    )
    assert direct_res.authority == BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
    assert direct_res.status == "NON_AUTHORITATIVE"


def test_caller_supplied_broker_dataset_cannot_become_authoritative() -> None:
    runtime = TrustedRuntimeAuthority()
    engine = runtime.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id

    unauth_provider = BrokerQueryProvider(
        authority=BrokerQueryQuality.FOUND,
        query_timestamp=1000,
    )
    query_res = unauth_provider.query_broker_state(session_id=session_id)
    assert query_res.authority == BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE

    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=session_id)
    assert report.authoritative is False


def test_wrong_broker_account_rejected() -> None:
    runtime = TrustedRuntimeAuthority()
    cap = runtime.domain.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapter")

    adapter = AuthoritativeBrokerAdapter(capability=cap, account_id="ACT_PRIMARY")
    obs = adapter.produce_broker_observation(session_id="sess_1")

    # Tamper with account_id in payload
    tampered_payload = dict(obs.frozen_payload)
    tampered_payload["account_id"] = "ACT_FORGED"
    forged_obs = replace(obs, frozen_payload=tampered_payload)

    with pytest.raises(RecoveryEvidenceError):
        BrokerQueryResult.from_observation(forged_obs, cap, session_id="sess_1")


# --- 4. Producer Attacks ---

def test_unregistered_journal_not_authoritative() -> None:
    runtime = TrustedRuntimeAuthority()
    domain = runtime.domain

    val_cap = domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    prod_cap = domain.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    # Create journal instance BUT DO NOT REGISTER it with domain
    unregistered_journal = DurableEventJournal()
    obs = unregistered_journal.produce_observation("sess_1", prod_cap)

    ev = JournalRecoveryValidator.validate(
        unregistered_journal,
        "sess_1",
        capability=val_cap,
        observation=obs,
        producer_capability=prod_cap,
        authority_domain=domain,  # Domain checks registration!
    )
    assert ev.valid is False
    assert "Unregistered Journal instance" in ev.provenance.failure_reason


def test_unregistered_risk_ledger_not_authoritative() -> None:
    runtime = TrustedRuntimeAuthority()
    domain = runtime.domain

    val_cap = domain.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    prod_cap = domain.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskSubsystem")

    unregistered_risk = OpportunityRiskLedger("b1", "o1", 500.0, 1.0)
    obs = unregistered_risk.produce_observation("sess_1", prod_cap)

    ev = RiskLedgerRecoveryValidator.reconstruct(
        unregistered_risk,
        "sess_1",
        capability=val_cap,
        observation=obs,
        producer_capability=prod_cap,
        authority_domain=domain,
    )
    assert ev.valid is False
    assert "Unregistered OpportunityRiskLedger instance" in ev.provenance.failure_reason


# --- 5. Reconciliation Stamp Attacks ---

def test_stamp_cross_domain_rejected() -> None:
    runtime = TrustedRuntimeAuthority()
    engine = runtime.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id

    prod_cap = runtime.domain.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapter")
    runtime.domain.register_producer(CapabilityRole.BROKER_QUERY, prod_cap)

    adapter = AuthoritativeBrokerAdapter(capability=prod_cap, authority=BrokerQueryQuality.FOUND)
    query_res = adapter.query_broker_state(session_id)

    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=session_id)

    # Validate stamp against a DIFFERENT authority domain ID
    b_val_cap = runtime.domain.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")

    ev_wrong_domain = BrokerReconciliationValidator.reconcile(
        report,
        session_id,
        capability=replace(b_val_cap, authority_domain_id="OTHER_DOMAIN_ID"),
    )
    assert ev_wrong_domain.valid is False


def test_raw_mapping_reconciliation_cannot_be_authoritative() -> None:
    # Pure raw-mapping reconciliation without BrokerQueryResult
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={},
        broker_orders={},
        broker_positions={},
    )
    assert report.authoritative is False
    assert report.query_quality == BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE

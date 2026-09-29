"""Pass 4.2 P0 Production Authority Lifecycle & Provenance Closure Test Suite.

Adversarial test suite proving that ordinary callers cannot use publicly reachable production authority objects
(such as prod_bootstrap.domain) to mint capabilities, register producers, retrieve signing capabilities,
or mutate production authority configuration before or after finalization.
"""

import pytest
import copy
import pickle
import time
from decimal import Decimal

from src.fractal_flow.execution.recovery import (
    RecoveryEngine,
    RecoveryState,
    RecoveryEvidence,
    RecoveryEvidenceError,
    AuthorityError,
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
    AuthorityBootstrap,
    AuthorityDomain,
    TrustedRuntimeBootstrap,
    CapabilityRole,
    SealedObservation,
    ValidatorCapability,
    ProducerCapability,
)
from src.fractal_flow.execution.reconciliation import (
    ReconciliationEngine,
    AuthoritativeBrokerAdapter,
    BrokerQueryQuality,
)
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger
from src.fractal_flow.config.config import BaseConfig, compute_effective_config
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import SnapshotEngine
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository


@pytest.fixture(autouse=True)
def _reset_bootstrap() -> None:
    TrustedRuntimeBootstrap._instance = None
    yield
    TrustedRuntimeBootstrap._instance = None


def _provision_full_production_authority(prod_bootstrap: TrustedRuntimeBootstrap) -> None:
    prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.SNAPSHOT) or prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.RISK_LEDGER) or prod_bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.INTENT_REPOSITORY) or prod_bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.BROKER_QUERY) or prod_bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION) or prod_bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, "ConfigSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.PROTECTIVE_MONITOR) or prod_bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, "ProtectiveSubsystem")

    prod_bootstrap.get_validator_capability("JournalRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    prod_bootstrap.get_validator_capability("SnapshotRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    prod_bootstrap.get_validator_capability("RiskLedgerRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    prod_bootstrap.get_validator_capability("IntentRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator")
    prod_bootstrap.get_validator_capability("BrokerReconciliationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")
    prod_bootstrap.get_validator_capability("ConfigurationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator")
    prod_bootstrap.get_validator_capability("ProtectiveMonitoringValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator")

    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    prod_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    prod_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    prod_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    prod_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)


def test_public_production_capability_minting_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    public_domain = prod_bootstrap.domain

    # Attempting to mint producer capability through public domain property MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc:
        public_domain.mint_producer_capability(CapabilityRole.JOURNAL, "MaliciousJournalProducer")
    assert "Public/unauthorized capability minting" in str(exc.value)

    # Attempting to mint validator capability through public domain property MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc2:
        public_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "MaliciousJournalValidator")
    assert "Public/unauthorized capability minting" in str(exc2.value)


def test_public_production_producer_registration_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    public_domain = prod_bootstrap.domain
    fake_journal = DurableEventJournal()

    # Attempting to register producer through public domain property MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc:
        public_domain.register_producer(CapabilityRole.JOURNAL, fake_journal)
    assert "Public/unauthorized producer registration" in str(exc.value)


def test_public_production_capability_retrieval_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    public_domain = prod_bootstrap.domain

    # Attempting to retrieve producer capability through public domain getter MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc:
        public_domain.get_producer_capability(CapabilityRole.JOURNAL)
    assert "Unrestricted public retrieval" in str(exc.value)

    # Attempting to retrieve validator capability through public domain getter MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc2:
        public_domain.get_validator_capability("JournalRecoveryValidator")
    assert "Unrestricted public retrieval" in str(exc2.value)


def test_public_production_finalization_call_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    public_domain = prod_bootstrap.domain

    # Attempting public finalization directly on domain property MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc:
        public_domain.finalize()
    assert "Public/unauthorized finalization" in str(exc.value)


def test_finalization_enforcement_blocks_all_further_mutations_and_retrievals() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Provision standard capabilities via trusted bootstrap
    _provision_full_production_authority(prod_bootstrap)

    # Seal/finalize production bootstrap
    prod_bootstrap.finalize()

    # Post-finalization attempts to mint new capabilities MUST raise RecoveryEvidenceError
    with pytest.raises(RecoveryEvidenceError) as exc:
        prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    assert "finalized" in str(exc.value)

    with pytest.raises(RecoveryEvidenceError) as exc2:
        prod_bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    assert "finalized" in str(exc2.value)

    # Post-finalization attempts to register producers MUST raise AuthorityError
    fake_journal = DurableEventJournal()
    with pytest.raises(AuthorityError) as exc3:
        prod_bootstrap.register_producer(CapabilityRole.JOURNAL, fake_journal)
    assert "finalized" in str(exc3.value)

    # Post-finalization attempts to retrieve capabilities MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc4:
        prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL)
    assert "finalized" in str(exc4.value)

    with pytest.raises(AuthorityError) as exc5:
        prod_bootstrap.get_validator_capability("JournalRecoveryValidator")
    assert "finalized" in str(exc5.value)

    # Re-finalizing MUST raise AuthorityError
    with pytest.raises(AuthorityError) as exc6:
        prod_bootstrap.finalize()
    assert "already finalized" in str(exc6.value)


def test_caller_created_capabilities_rejected_by_recovery_engine() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    engine = prod_bootstrap.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Attacker creates an untrusted bootstrap domain
    untrusted_bootstrap = AuthorityBootstrap("UNTRUSTED_ATTACKER")
    unauth_val = untrusted_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    unauth_prod = untrusted_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    journal = DurableEventJournal()
    untrusted_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)

    obs = journal.produce_observation(session_id, unauth_prod)
    ev = JournalRecoveryValidator.validate(journal, session_id, unauth_val, observation=obs, producer_capability=unauth_prod)

    # Submitting untrusted evidence to production RecoveryEngine MUST fail assembly/validation
    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=ev,
            snapshot=SnapshotRecoveryEvidence(valid=True),
            risk=RiskLedgerRecoveryEvidence(valid=True),
            intents=IntentRecoveryEvidence(valid=True),
            broker=BrokerReconciliationEvidence(valid=True),
            config=ConfigurationEvidence(valid=True),
            protective=ProtectiveMonitoringEvidence(valid=True),
            session_id=session_id,
            validator_capabilities=engine.validator_capabilities,
        )


def test_stale_reference_after_sealing_cannot_mutate_operational_authority() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Provision full authority graph
    _provision_full_production_authority(prod_bootstrap)

    # Caller grabs references prior to finalization
    stale_domain = prod_bootstrap.domain

    # Seal production authority
    prod_bootstrap.finalize()

    # Stale reference MUST NOT allow registration or minting post-seal
    journal = DurableEventJournal()
    with pytest.raises(AuthorityError) as exc:
        stale_domain.register_producer(CapabilityRole.JOURNAL, journal)
    assert "finalized" in str(exc.value)

    with pytest.raises(RecoveryEvidenceError) as exc2:
        stale_domain.mint_producer_capability(CapabilityRole.SNAPSHOT, "Snap")
    assert "finalized" in str(exc2.value)


def test_legitimate_production_recovery_lifecycle_succeeds() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    j_val = prod_bootstrap.get_validator_capability("JournalRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    s_val = prod_bootstrap.get_validator_capability("SnapshotRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    r_val = prod_bootstrap.get_validator_capability("RiskLedgerRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    i_val = prod_bootstrap.get_validator_capability("IntentRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator")
    b_val = prod_bootstrap.get_validator_capability("BrokerReconciliationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")
    c_val = prod_bootstrap.get_validator_capability("ConfigurationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator")
    p_val = prod_bootstrap.get_validator_capability("ProtectiveMonitoringValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator")

    j_prod = prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    s_prod = prod_bootstrap.get_producer_capability(CapabilityRole.SNAPSHOT) or prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    r_prod = prod_bootstrap.get_producer_capability(CapabilityRole.RISK_LEDGER) or prod_bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    i_prod = prod_bootstrap.get_producer_capability(CapabilityRole.INTENT_REPOSITORY) or prod_bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    b_prod = prod_bootstrap.get_producer_capability(CapabilityRole.BROKER_QUERY) or prod_bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    c_prod = prod_bootstrap.get_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION) or prod_bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, "ConfigSubsystem")
    p_prod = prod_bootstrap.get_producer_capability(CapabilityRole.PROTECTIVE_MONITOR) or prod_bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, "ProtectiveSubsystem")

    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    prod_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    prod_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    prod_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    prod_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)

    engine = prod_bootstrap.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Finalize domain after provisioning
    prod_bootstrap.finalize()

    adapter = AuthoritativeBrokerAdapter(capability=b_prod, authority=BrokerQueryQuality.FOUND)
    query_res = adapter.query_broker_state(session_id)
    report = ReconciliationEngine.reconcile_broker_wide(local_intents={}, query_result=query_res, session_id=session_id)

    j_obs = journal.produce_observation(session_id, j_prod)
    s_obs = snap_engine.produce_observation(session_id, s_prod)
    r_obs = risk_ledger.produce_observation(session_id, r_prod)
    i_obs = intent_repo.produce_observation(session_id, i_prod)
    c_obs = config.produce_observation(session_id, c_prod)
    p_obs = protective.produce_observation(session_id, p_prod)

    j_ev = JournalRecoveryValidator.validate(journal, session_id, j_val, observation=j_obs, producer_capability=j_prod, authority_domain=prod_bootstrap.domain)
    s_ev = SnapshotRecoveryValidator.validate(snap_engine, session_id, s_val, observation=s_obs, producer_capability=s_prod, authority_domain=prod_bootstrap.domain)
    r_ev = RiskLedgerRecoveryValidator.reconstruct(risk_ledger, session_id, r_val, observation=r_obs, producer_capability=r_prod, authority_domain=prod_bootstrap.domain)
    i_ev = IntentRecoveryValidator.reconstruct(intent_repo, session_id, i_val, observation=i_obs, producer_capability=i_prod, authority_domain=prod_bootstrap.domain)
    b_ev = BrokerReconciliationValidator.reconcile(report, session_id, b_val)
    c_ev = ConfigurationValidator.validate(config, session_id, c_val, observation=c_obs, producer_capability=c_prod, authority_domain=prod_bootstrap.domain)
    p_ev = ProtectiveMonitoringValidator.validate(protective, session_id, p_val, observation=p_obs, producer_capability=p_prod, authority_domain=prod_bootstrap.domain)

    evidence = RecoveryEvidenceAssembler.assemble(
        journal=j_ev, snapshot=s_ev, risk=r_ev, intents=i_ev,
        broker=b_ev, config=c_ev, protective=p_ev, session_id=session_id,
        validator_capabilities=engine.validator_capabilities,
    )

    engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.RECOVERY_COMPLETE
    assert engine.can_authorize_strategic_action() is True


def test_cross_domain_authority_capabilities_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    other_domain = AuthorityBootstrap("OTHER_DOMAIN")

    other_val = other_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    prod_j_prod = prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    journal = DurableEventJournal()
    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)

    obs = journal.produce_observation("sess_1", prod_j_prod)

    # Validating using validator capability from other domain MUST fail
    ev = JournalRecoveryValidator.validate(
        journal,
        "sess_1",
        capability=other_val,
        observation=obs,
        producer_capability=prod_j_prod,
        authority_domain=prod_bootstrap.domain,
    )

    # Assembly with evidence containing token signed by cross-domain validator capability MUST fail
    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=ev,
            snapshot=SnapshotRecoveryEvidence(valid=True),
            risk=RiskLedgerRecoveryEvidence(valid=True),
            intents=IntentRecoveryEvidence(valid=True),
            broker=BrokerReconciliationEvidence(valid=True),
            config=ConfigurationEvidence(valid=True),
            protective=ProtectiveMonitoringEvidence(valid=True),
            session_id="sess_1",
            validator_capabilities=prod_bootstrap.domain._validator_capabilities,
        )


def test_subclass_and_alternate_domain_bypass_rejected() -> None:
    class SubclassDomain(AuthorityDomain):
        def __init__(self) -> None:
            super().__init__("SPOOFED_ID")

    sub_domain = SubclassDomain()
    assert sub_domain.is_production is False

    # Attempting to mint or register via subclass domain does NOT create production capabilities
    sub_val = sub_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    assert sub_val.authority_domain_id == "SPOOFED_ID"


def test_copy_pickle_deepcopy_resistance_on_authority_objects() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    assert copy.copy(domain) is None
    assert copy.deepcopy(domain) is None
    assert copy.copy(prod_bootstrap) is None
    assert copy.deepcopy(prod_bootstrap) is None

    with pytest.raises(AuthorityError):
        pickle.dumps(domain)

    with pytest.raises(AuthorityError):
        pickle.dumps(prod_bootstrap)

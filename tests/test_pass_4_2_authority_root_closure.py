"""Pass 4.2 Authority Root Closure Adversarial Test Suite.

Comprehensive P0-1 adversarial test suite proving that callers cannot establish an alternative production authority root,
inject un-trusted capabilities into RecoveryEngine, pass is_production=True to public constructors, spoof domain IDs,
subclass authority objects, forge capabilities via copy/pickle, or use unregistered producers/broker datasets to obtain strategic execution authorization.
"""

import pytest
import copy
import pickle
import time

from src.fractal_flow.execution.reconciliation import (
    ReconciliationEngine,
    BrokerQueryResult,
    BrokerQueryQuality,
    AuthoritativeBrokerAdapter,
)
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
    SnapshotRecoveryEvidence,
    RiskLedgerRecoveryEvidence,
    IntentRecoveryEvidence,
    BrokerReconciliationEvidence,
    ConfigurationEvidence,
    ProtectiveMonitoringEvidence,
    AuthorityBootstrap,
    AuthorityDomain,
    TrustedRuntimeBootstrap,
    TrustedRuntimeAuthority,
    CapabilityRole,
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


# --- 1. P0-1 Authority-Root & Production Creation Attacks ---


def test_public_bootstrap_cannot_create_production_authority() -> None:
    caller_bootstrap = AuthorityBootstrap()
    assert caller_bootstrap.is_production is False
    assert "UNTRUSTED_BOOTSTRAP_" in caller_bootstrap.domain_id

    # Mint capabilities using caller bootstrap
    caller_j_cap = caller_bootstrap.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )
    assert caller_j_cap.authority_domain_id == caller_bootstrap.domain_id

    # Create production recovery engine via singular trusted runtime bootstrap
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    prod_engine = prod_bootstrap.create_recovery_engine()
    prod_engine.trigger_system_restart()
    session_id = prod_engine.session_id
    prod_engine.start_reconciliation()

    # Evidence signed by caller bootstrap must be REJECTED by production recovery gate
    journal = DurableEventJournal()
    j_obs = journal.produce_observation(
        session_id,
        caller_bootstrap.mint_producer_capability(
            CapabilityRole.JOURNAL, "JournalSubsystem"
        ),
    )
    j_ev = JournalRecoveryValidator.validate(
        journal,
        session_id,
        caller_j_cap,
        observation=j_obs,
        producer_capability=caller_bootstrap.get_producer_capability(
            CapabilityRole.JOURNAL
        ),
    )

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
            validator_capabilities=prod_bootstrap.domain._validator_capabilities,
        )


def test_public_authority_domain_cannot_grant_production_status() -> None:
    caller_domain = AuthorityDomain("FRACTAL_PROD_DOMAIN_SPOOFED")
    assert caller_domain.is_production is False


def test_standalone_trusted_runtime_authority_cannot_create_production_root() -> None:
    standalone_auth = TrustedRuntimeAuthority()
    assert standalone_auth.domain.is_production is False
    assert "STANDALONE_DOMAIN_" in standalone_auth.domain.domain_id

    engine = standalone_auth.create_recovery_engine()
    assert engine.strategic_authorization_enabled is False


def test_direct_instantiation_of_trusted_runtime_bootstrap_forbidden() -> None:
    with pytest.raises(AuthorityError) as exc:
        TrustedRuntimeBootstrap()
    assert "Direct instantiation of TrustedRuntimeBootstrap is forbidden" in str(
        exc.value
    )


def test_subclass_authority_domain_cannot_claim_production_trust() -> None:
    # Direct setter mutation MUST raise AttributeError
    with pytest.raises(AttributeError):
        caller_domain = AuthorityDomain("ATTACKER")
        caller_domain.is_production = True  # type: ignore

    class EvilPropertyDomain(AuthorityDomain):
        def __init__(self) -> None:
            super().__init__("SPOOFED_PROD_ID")

        @property
        def is_production(self) -> bool:  # Subclass property override attempt
            return True

    evil = EvilPropertyDomain()
    assert evil.is_production is True  # Subclass returning True property

    # When injected into RecoveryEngine, strategic authorization MUST still fail closed
    engine = RecoveryEngine(authority_domain=evil)
    assert engine.is_production_recovery is False
    assert engine.can_authorize_strategic_action() is False


def test_domain_id_spoofing_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    prod_engine = prod_bootstrap.create_recovery_engine()
    prod_engine.trigger_system_restart()

    # Caller creates domain with identical domain_id string
    spoofed_domain = AuthorityDomain(domain_id=prod_bootstrap.domain.domain_id)
    assert spoofed_domain.is_production is False
    assert spoofed_domain._master_key != prod_bootstrap.domain._master_key

    spoofed_cap = spoofed_domain.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )

    journal = DurableEventJournal()
    j_obs = journal.produce_observation(
        prod_engine.session_id,
        spoofed_domain.mint_producer_capability(
            CapabilityRole.JOURNAL, "JournalSubsystem"
        ),
    )
    j_ev = JournalRecoveryValidator.validate(
        journal,
        prod_engine.session_id,
        spoofed_cap,
        observation=j_obs,
        producer_capability=spoofed_domain.get_producer_capability(
            CapabilityRole.JOURNAL
        ),
    )

    # Even though domain_id string matches, signature verification fails because master keys differ
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
            validator_capabilities=prod_bootstrap.domain._validator_capabilities,
        )


# --- 2. Copy, Pickle & Serialization Attacks ---


def test_authority_domain_copy_and_pickle_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    assert copy.copy(domain) is None
    assert copy.deepcopy(domain) is None

    with pytest.raises(AuthorityError) as exc:
        pickle.dumps(domain)
    assert "Serialization/pickling of AuthorityDomain is prohibited" in str(exc.value)


def test_trusted_runtime_bootstrap_copy_and_pickle_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    assert copy.copy(prod_bootstrap) is None
    assert copy.deepcopy(prod_bootstrap) is None

    with pytest.raises(AuthorityError) as exc:
        pickle.dumps(prod_bootstrap)
    assert "Serialization/pickling of TrustedRuntimeBootstrap is prohibited" in str(
        exc.value
    )


def test_trusted_runtime_bootstrap_reset_attempt_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    initial_domain_id = prod_bootstrap.domain.domain_id

    # Attempting reset=True MUST be rejected with AuthorityError
    with pytest.raises(AuthorityError) as exc:
        TrustedRuntimeBootstrap.bootstrap_production_runtime(reset=True)
    assert (
        "Resetting or replacing an active production authority root is forbidden"
        in str(exc.value)
    )

    # Re-querying without reset returns the original unchanged root
    same_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    assert same_bootstrap.domain.domain_id == initial_domain_id


# --- 3. Alternate-Authority Universe Complete Attack ---


def test_alternate_authority_universe_complete_attack_rejected() -> None:
    # Production System
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    prod_engine = prod_bootstrap.create_recovery_engine()
    prod_engine.trigger_system_restart()
    session_id = prod_engine.session_id
    prod_engine.start_reconciliation()

    # Attacker constructs a complete alternative authority universe
    attacker_bootstrap = AuthorityBootstrap("ATTACKER_UNIVERSE")
    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    att_j_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )
    att_s_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator"
    )
    att_r_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator"
    )
    att_i_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator"
    )
    att_b_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator"
    )
    att_c_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator"
    )
    att_p_val = attacker_bootstrap.mint_validator_capability(
        CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator"
    )

    att_j_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.JOURNAL, "JournalSubsystem"
    )
    att_s_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.SNAPSHOT, "SnapshotSubsystem"
    )
    att_r_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.RISK_LEDGER, "RiskSubsystem"
    )
    att_i_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem"
    )
    att_b_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.BROKER_QUERY, "BrokerSubsystem"
    )
    att_c_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.EFFECTIVE_CONFIGURATION, config.effective_config_id
    )
    att_p_prod = attacker_bootstrap.mint_producer_capability(
        CapabilityRole.PROTECTIVE_MONITOR, protective.subsystem_id
    )

    attacker_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    attacker_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    attacker_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    attacker_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    attacker_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    attacker_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)

    adapter = AuthoritativeBrokerAdapter(
        capability=att_b_prod, authority=BrokerQueryQuality.FOUND
    )
    query_res = adapter.query_broker_state(session_id)
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={}, query_result=query_res, session_id=session_id
    )

    j_obs = journal.produce_observation(session_id, att_j_prod)
    s_obs = snap_engine.produce_observation(session_id, att_s_prod)
    r_obs = risk_ledger.produce_observation(session_id, att_r_prod)
    i_obs = intent_repo.produce_observation(session_id, att_i_prod)
    c_obs = config.produce_observation(session_id, att_c_prod)
    p_obs = protective.produce_observation(session_id, att_p_prod)

    j_ev = JournalRecoveryValidator.validate(
        journal,
        session_id,
        att_j_val,
        observation=j_obs,
        producer_capability=att_j_prod,
        authority_domain=attacker_bootstrap,
    )
    s_ev = SnapshotRecoveryValidator.validate(
        snap_engine,
        session_id,
        att_s_val,
        observation=s_obs,
        producer_capability=att_s_prod,
        authority_domain=attacker_bootstrap,
    )
    r_ev = RiskLedgerRecoveryValidator.reconstruct(
        risk_ledger,
        session_id,
        att_r_val,
        observation=r_obs,
        producer_capability=att_r_prod,
        authority_domain=attacker_bootstrap,
    )
    i_ev = IntentRecoveryValidator.reconstruct(
        intent_repo,
        session_id,
        att_i_val,
        observation=i_obs,
        producer_capability=att_i_prod,
        authority_domain=attacker_bootstrap,
    )
    b_ev = BrokerReconciliationValidator.reconcile(report, session_id, att_b_val)
    c_ev = ConfigurationValidator.validate(
        config,
        session_id,
        att_c_val,
        observation=c_obs,
        producer_capability=att_c_prod,
        authority_domain=attacker_bootstrap,
    )
    p_ev = ProtectiveMonitoringValidator.validate(
        protective,
        session_id,
        att_p_val,
        observation=p_obs,
        producer_capability=att_p_prod,
        authority_domain=attacker_bootstrap,
    )

    # Assembly with attacker's domain MUST fail against production domain
    with pytest.raises(RecoveryEvidenceError):
        RecoveryEvidenceAssembler.assemble(
            journal=j_ev,
            snapshot=s_ev,
            risk=r_ev,
            intents=i_ev,
            broker=b_ev,
            config=c_ev,
            protective=p_ev,
            session_id=session_id,
            validator_capabilities=prod_bootstrap.domain._validator_capabilities,
        )

    # Directly submitting attacker's evidence to production RecoveryEngine MUST place engine in SAFE state
    from src.fractal_flow.execution.recovery import _RecoveryAuthorityBundle

    forged_bundle = _RecoveryAuthorityBundle(
        journal_token=j_ev._authority_token,
        snapshot_token=s_ev._authority_token,
        risk_token=r_ev._authority_token,
        intent_token=i_ev._authority_token,
        broker_token=b_ev._authority_token,
        config_token=c_ev._authority_token,
        protective_token=p_ev._authority_token,
        session_id=session_id,
    )
    forged_evidence = RecoveryEvidence(
        journal_evidence=j_ev,
        snapshot_evidence=s_ev,
        risk_evidence=r_ev,
        intent_evidence=i_ev,
        broker_evidence=b_ev,
        config_evidence=c_ev,
        protective_evidence=p_ev,
        _authority_bundle=forged_bundle,
    )

    with pytest.raises(RecoveryEvidenceError):
        prod_engine.complete_recovery_with_evidence(forged_evidence)

    assert prod_engine.state == RecoveryState.SAFE
    assert prod_engine.can_authorize_strategic_action() is False


# --- 4. Unregistered Producer Attacks ---


def test_unregistered_producer_subsystems_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    j_val = prod_bootstrap.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )
    j_prod = prod_bootstrap.mint_producer_capability(
        CapabilityRole.JOURNAL, "JournalSubsystem"
    )

    # Live journal created BUT NOT registered in domain
    unregistered_journal = DurableEventJournal()
    obs = unregistered_journal.produce_observation("sess_1", j_prod)

    ev = JournalRecoveryValidator.validate(
        unregistered_journal,
        "sess_1",
        capability=j_val,
        observation=obs,
        producer_capability=j_prod,
        authority_domain=domain,  # Domain checks registration!
    )
    assert ev.valid is False
    assert (
        "Unregistered Journal instance in AuthorityDomain"
        in ev.provenance.failure_reason
    )


# --- 5. Legitimate Production Path Continuation ---


def test_legitimate_trusted_runtime_bootstrap_path_succeeds() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain
    engine = prod_bootstrap.create_recovery_engine()

    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Mint or retrieve capabilities on production domain via trusted bootstrap
    j_val = prod_bootstrap.get_validator_capability(
        "JournalRecoveryValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator"
    )
    s_val = prod_bootstrap.get_validator_capability(
        "SnapshotRecoveryValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator"
    )
    r_val = prod_bootstrap.get_validator_capability(
        "RiskLedgerRecoveryValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator"
    )
    i_val = prod_bootstrap.get_validator_capability(
        "IntentRecoveryValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator"
    )
    b_val = prod_bootstrap.get_validator_capability(
        "BrokerReconciliationValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator"
    )
    c_val = prod_bootstrap.get_validator_capability(
        "ConfigurationValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator"
    )
    p_val = prod_bootstrap.get_validator_capability(
        "ProtectiveMonitoringValidator"
    ) or prod_bootstrap.mint_validator_capability(
        CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator"
    )

    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    j_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.JOURNAL
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.JOURNAL, "JournalSubsystem"
    )
    s_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.SNAPSHOT
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.SNAPSHOT, "SnapshotSubsystem"
    )
    r_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.RISK_LEDGER
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem"
    )
    i_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.INTENT_REPOSITORY
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem"
    )
    b_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.BROKER_QUERY
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem"
    )
    c_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.EFFECTIVE_CONFIGURATION
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.EFFECTIVE_CONFIGURATION, config.effective_config_id
    )
    p_prod = prod_bootstrap.get_producer_capability(
        CapabilityRole.PROTECTIVE_MONITOR
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.PROTECTIVE_MONITOR, protective.subsystem_id
    )

    adapter = AuthoritativeBrokerAdapter(
        capability=b_prod, authority=BrokerQueryQuality.FOUND
    )

    # Register producers via trusted bootstrap
    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    prod_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    prod_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    prod_bootstrap.register_producer(CapabilityRole.BROKER_QUERY, adapter)
    prod_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    prod_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)

    prod_bootstrap.finalize()

    adapter = AuthoritativeBrokerAdapter(
        capability=b_prod, authority=BrokerQueryQuality.FOUND
    )
    query_res = adapter.query_broker_state(session_id)
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={}, query_result=query_res, session_id=session_id
    )

    j_obs = journal.produce_observation(session_id, j_prod)
    s_obs = snap_engine.produce_observation(session_id, s_prod)
    r_obs = risk_ledger.produce_observation(session_id, r_prod)
    i_obs = intent_repo.produce_observation(session_id, i_prod)
    c_obs = config.produce_observation(session_id, c_prod)
    p_obs = protective.produce_observation(session_id, p_prod)

    j_ev = JournalRecoveryValidator.validate(
        journal,
        session_id,
        j_val,
        observation=j_obs,
        producer_capability=j_prod,
        authority_domain=domain,
    )
    s_ev = SnapshotRecoveryValidator.validate(
        snap_engine,
        session_id,
        s_val,
        observation=s_obs,
        producer_capability=s_prod,
        authority_domain=domain,
    )
    r_ev = RiskLedgerRecoveryValidator.reconstruct(
        risk_ledger,
        session_id,
        r_val,
        observation=r_obs,
        producer_capability=r_prod,
        authority_domain=domain,
    )
    i_ev = IntentRecoveryValidator.reconstruct(
        intent_repo,
        session_id,
        i_val,
        observation=i_obs,
        producer_capability=i_prod,
        authority_domain=domain,
    )
    b_ev = BrokerReconciliationValidator.reconcile(report, session_id, b_val)
    c_ev = ConfigurationValidator.validate(
        config,
        session_id,
        c_val,
        observation=c_obs,
        producer_capability=c_prod,
        authority_domain=domain,
    )
    p_ev = ProtectiveMonitoringValidator.validate(
        protective,
        session_id,
        p_val,
        observation=p_obs,
        producer_capability=p_prod,
        authority_domain=domain,
    )

    evidence = RecoveryEvidenceAssembler.assemble(
        journal=j_ev,
        snapshot=s_ev,
        risk=r_ev,
        intents=i_ev,
        broker=b_ev,
        config=c_ev,
        protective=p_ev,
        session_id=session_id,
        validator_capabilities=domain._validator_capabilities,
    )

    engine.complete_recovery_with_evidence(evidence)

    assert engine.state == RecoveryState.RECOVERY_COMPLETE
    assert engine.can_authorize_strategic_action() is True


# --- 6. Broker & Stamp Cross-Domain Attacks ---


def test_caller_supplied_found_broker_result_is_non_authoritative() -> None:
    # Caller directly constructs BrokerQueryResult claiming FOUND without an AuthoritativeBrokerAdapter / SealedObservation
    res = BrokerQueryResult(
        broker_positions={},
        broker_orders={},
        broker_deals={},
        completeness=True,
        authority=BrokerQueryQuality.FOUND,
        query_timestamp=int(time.time()),
    )
    assert res.authoritative is False

    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={}, query_result=res, session_id="sess_1"
    )
    assert report.authoritative is False

    val_cap = AuthorityBootstrap().mint_validator_capability(
        CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator"
    )
    ev = BrokerReconciliationValidator.reconcile(report, "sess_1", val_cap)
    assert ev.valid is False


def test_stamp_cross_domain_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain_a = prod_bootstrap.domain
    domain_b = AuthorityDomain("DOMAIN_B")

    b_prod_a = prod_bootstrap.get_producer_capability(
        CapabilityRole.BROKER_QUERY
    ) or prod_bootstrap.mint_producer_capability(
        CapabilityRole.BROKER_QUERY, "BrokerAdapter"
    )
    adapter_a = AuthoritativeBrokerAdapter(
        capability=b_prod_a, authority=BrokerQueryQuality.FOUND
    )
    res_a = adapter_a.query_broker_state("sess_1")

    # Reconciliation report produced under domain_a authority
    report = ReconciliationEngine.reconcile_broker_wide(
        local_intents={}, query_result=res_a, session_id="sess_1"
    )
    assert report.authoritative is True

    # Validator capability from domain_b attempts to validate report stamped by domain_a
    b_val_b = domain_b.mint_validator_capability(
        CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator"
    )
    ev = BrokerReconciliationValidator.reconcile(report, "sess_1", b_val_b)
    assert ev.valid is False


def test_raw_mapping_reconciliation_cannot_be_authoritative() -> None:
    fake_report = {
        "authoritative": True,
        "complete": True,
        "unknown_count": 0,
        "orphaned_count": 0,
    }
    val_cap = AuthorityBootstrap().mint_validator_capability(
        CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator"
    )
    ev = BrokerReconciliationValidator.reconcile(fake_report, "sess_1", val_cap)
    assert ev.valid is False
    assert "authentic ReconciliationReport instance" in ev.provenance.failure_reason


def test_trusted_runtime_bootstrap_concurrency_race() -> None:
    import threading

    results = []

    def _bootstrap_worker() -> None:
        inst = TrustedRuntimeBootstrap.bootstrap_production_runtime()
        results.append(inst)

    threads = [threading.Thread(target=_bootstrap_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    first_domain = results[0].domain
    for item in results:
        assert item.domain is first_domain


# --- 7. TrustedRuntimeBootstrap Subclass Attacks ---


def test_trusted_runtime_bootstrap_subclass_cannot_create_production_root() -> None:
    class EvilBootstrap(TrustedRuntimeBootstrap):
        pass

    with pytest.raises(AuthorityError) as exc:
        EvilBootstrap.bootstrap_production_runtime()
    assert "Subclass invocation" in str(exc.value)


def test_multiple_malicious_subclasses_cannot_create_production_root() -> None:
    class EvilBootstrapA(TrustedRuntimeBootstrap):
        pass

    class EvilBootstrapB(TrustedRuntimeBootstrap):
        pass

    with pytest.raises(AuthorityError):
        EvilBootstrapA.bootstrap_production_runtime()

    with pytest.raises(AuthorityError):
        EvilBootstrapB.bootstrap_production_runtime()


def test_subclass_cannot_create_alternate_production_engine() -> None:
    class EvilBootstrapEngine(TrustedRuntimeBootstrap):
        def create_recovery_engine(
            self, initial_state: RecoveryState = RecoveryState.NORMAL
        ) -> RecoveryEngine:
            fake_domain = AuthorityDomain("EVIL_BOOTSTRAP_DOMAIN")
            return RecoveryEngine(
                authority_domain=fake_domain, initial_state=initial_state
            )

    with pytest.raises(AuthorityError):
        EvilBootstrapEngine.bootstrap_production_runtime()


def test_subclass_cannot_exploit_reset_to_replace_root() -> None:
    class EvilResetBootstrap(TrustedRuntimeBootstrap):
        pass

    with pytest.raises(AuthorityError) as exc:
        EvilResetBootstrap.bootstrap_production_runtime(reset=True)
    assert "Subclass invocation" in str(exc.value)

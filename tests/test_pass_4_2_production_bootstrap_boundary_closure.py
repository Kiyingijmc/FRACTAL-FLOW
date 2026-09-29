"""Pass 4.2 P0 Production Bootstrap Authority Boundary Closure Test Suite.

Adversarial test suite proving that ordinary runtime/application code cannot acquire, reuse, extract,
import, retain, or invoke a production provisioning authority merely through public Python APIs or module state.
"""

import pytest
import copy
import pickle
import threading
import time
from decimal import Decimal
from types import MappingProxyType

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
    compute_evidence_digest,
    AuthorityBootstrap,
    AuthorityDomain,
    TrustedRuntimeBootstrap,
    TrustedRuntimeAuthority,
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
    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    j_prod = prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    s_prod = prod_bootstrap.get_producer_capability(CapabilityRole.SNAPSHOT) or prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    r_prod = prod_bootstrap.get_producer_capability(CapabilityRole.RISK_LEDGER) or prod_bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    i_prod = prod_bootstrap.get_producer_capability(CapabilityRole.INTENT_REPOSITORY) or prod_bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    b_prod = prod_bootstrap.get_producer_capability(CapabilityRole.BROKER_QUERY) or prod_bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    c_prod = prod_bootstrap.get_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION) or prod_bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, config.effective_config_id)
    p_prod = prod_bootstrap.get_producer_capability(CapabilityRole.PROTECTIVE_MONITOR) or prod_bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, protective.subsystem_id)

    adapter = AuthoritativeBrokerAdapter(capability=b_prod, authority=BrokerQueryQuality.FOUND)

    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    prod_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    prod_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    prod_bootstrap.register_producer(CapabilityRole.BROKER_QUERY, adapter)
    prod_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    prod_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)

    prod_bootstrap.get_validator_capability("JournalRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    prod_bootstrap.get_validator_capability("SnapshotRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    prod_bootstrap.get_validator_capability("RiskLedgerRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    prod_bootstrap.get_validator_capability("IntentRecoveryValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator")
    prod_bootstrap.get_validator_capability("BrokerReconciliationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")
    prod_bootstrap.get_validator_capability("ConfigurationValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator")
    prod_bootstrap.get_validator_capability("ProtectiveMonitoringValidator") or prod_bootstrap.mint_validator_capability(CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator")


# --- Attack A: Import the supposedly private provisioning token ---

def test_attack_a_imported_module_state_cannot_mutate_production_authority() -> None:
    # Verify module-level token symbol _BOOTSTRAP_ISSUANCE_TOKEN is no longer exposed in recovery module
    import src.fractal_flow.execution.recovery as rec
    assert not hasattr(rec, "_BOOTSTRAP_ISSUANCE_TOKEN")

    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    # Any attempted forged token passed by an attacker MUST be rejected
    fake_token = object()
    with pytest.raises(AuthorityError) as exc:
        domain.mint_producer_capability(CapabilityRole.JOURNAL, "MaliciousProducer", _provisioning_token=fake_token)
    assert "Public/unauthorized capability minting" in str(exc.value)

    with pytest.raises(AuthorityError) as exc2:
        domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "MaliciousValidator", _provisioning_token=fake_token)
    assert "Public/unauthorized capability minting" in str(exc2.value)


# --- Attack B: Public bootstrap acquisition ---

def test_attack_b_public_bootstrap_acquisition_does_not_grant_reusable_provisioning_authority() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    # Re-querying public production bootstrap handle gives operational handle
    operational_handle = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Operational handle CANNOT be used to mint, register, or retrieve capabilities
    with pytest.raises(RecoveryEvidenceError):
        operational_handle.mint_producer_capability(CapabilityRole.JOURNAL, "AttackerJournal")

    with pytest.raises(RecoveryEvidenceError):
        operational_handle.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "AttackerValidator")

    with pytest.raises(AuthorityError):
        operational_handle.register_producer(CapabilityRole.JOURNAL, DurableEventJournal())

    with pytest.raises(AuthorityError):
        operational_handle.get_producer_capability(CapabilityRole.JOURNAL)

    with pytest.raises(AuthorityError):
        operational_handle.get_validator_capability("JournalRecoveryValidator")


# --- Attack C: Retained bootstrap reference ---

def test_attack_c_retained_bootstrap_reference_inert_after_sealing() -> None:
    retained_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(retained_bootstrap)

    # Complete sealing
    retained_bootstrap.finalize()

    # Post-seal attempts on retained reference MUST fail closed
    with pytest.raises(RecoveryEvidenceError):
        retained_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "PostSealProducer")

    with pytest.raises(RecoveryEvidenceError):
        retained_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "PostSealValidator")

    with pytest.raises(AuthorityError):
        retained_bootstrap.register_producer(CapabilityRole.JOURNAL, DurableEventJournal())

    with pytest.raises(AuthorityError):
        retained_bootstrap.get_producer_capability(CapabilityRole.JOURNAL)

    with pytest.raises(AuthorityError):
        retained_bootstrap.get_validator_capability("JournalRecoveryValidator")

    with pytest.raises(AuthorityError):
        retained_bootstrap.finalize()

    with pytest.raises(AuthorityError):
        TrustedRuntimeBootstrap.bootstrap_production_runtime(reset=True)


# --- Attack D: Stale references ---

def test_attack_d_stale_domain_reference_cannot_mutate_operational_authority() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    stale_domain = prod_bootstrap.domain
    prod_bootstrap.finalize()

    # Stale domain reference operations fail closed
    with pytest.raises(RecoveryEvidenceError):
        stale_domain.mint_producer_capability(CapabilityRole.JOURNAL, "StaleProducer")

    with pytest.raises(RecoveryEvidenceError):
        stale_domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "StaleValidator")

    with pytest.raises(AuthorityError):
        stale_domain.register_producer(CapabilityRole.JOURNAL, DurableEventJournal())

    with pytest.raises(AuthorityError):
        stale_domain.get_producer_capability(CapabilityRole.JOURNAL)

    with pytest.raises(AuthorityError):
        stale_domain.get_validator_capability("JournalRecoveryValidator")

    with pytest.raises(AuthorityError):
        stale_domain.finalize()


# --- Attack E: Extract provisioning authority from operational objects ---

def test_attack_e_cannot_extract_usable_provisioning_material_from_operational_objects() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    engine = prod_bootstrap.create_recovery_engine()
    domain = prod_bootstrap.domain

    # Verify master key is wiped
    assert domain._master_key == b"\x00" * 32

    # Verify provisioning tokens are cleared
    assert getattr(domain, "_provisioning_token", None) is None
    assert getattr(prod_bootstrap, "_provisioning_token", None) is None

    # Verify registries are immutable mapping proxies
    assert isinstance(domain._validator_capabilities, MappingProxyType)
    assert isinstance(domain._producer_capabilities, MappingProxyType)
    assert isinstance(domain._registered_producers, MappingProxyType)

    # Attempting to mutate mapping proxies MUST raise TypeError
    with pytest.raises(TypeError):
        domain._validator_capabilities["JournalRecoveryValidator"] = "FORGED"  # type: ignore

    with pytest.raises(TypeError):
        domain._producer_capabilities[CapabilityRole.JOURNAL] = "FORGED"  # type: ignore

    with pytest.raises(TypeError):
        domain._registered_producers[CapabilityRole.JOURNAL] = "FORGED"  # type: ignore


# --- Attack F: Direct production-domain mutation ---

def test_attack_f_direct_production_domain_mutation_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    with pytest.raises(AuthorityError):
        domain.mint_producer_capability(CapabilityRole.JOURNAL, "DirectProd")

    with pytest.raises(AuthorityError):
        domain.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "DirectVal")

    with pytest.raises(AuthorityError):
        domain.register_producer(CapabilityRole.JOURNAL, DurableEventJournal())

    with pytest.raises(AuthorityError):
        domain.get_producer_capability(CapabilityRole.JOURNAL)

    with pytest.raises(AuthorityError):
        domain.get_validator_capability("JournalRecoveryValidator")

    with pytest.raises(AuthorityError):
        domain.finalize()


# --- Attack G: Cross-domain capability substitution ---

def test_attack_g_cross_domain_capability_substitution_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    engine = prod_bootstrap.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Attacker creates non-production bootstrap
    attacker_bootstrap = AuthorityBootstrap("ATTACKER_DOMAIN")
    att_val = attacker_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    att_prod = attacker_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    journal = DurableEventJournal()
    attacker_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    obs = journal.produce_observation(session_id, att_prod)

    ev = JournalRecoveryValidator.validate(journal, session_id, att_val, observation=obs, producer_capability=att_prod, authority_domain=attacker_bootstrap)

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


# --- Attack H: Caller-created production capabilities ---

def test_attack_h_caller_created_capabilities_rejected() -> None:
    # Direct construction of ProducerCapability is forbidden
    with pytest.raises(RecoveryEvidenceError) as exc:
        ProducerCapability("FRACTAL_PROD_DOMAIN", CapabilityRole.JOURNAL, "FakeJournal", b"1234"*8)
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)

    # Direct construction of ValidatorCapability is forbidden
    with pytest.raises(RecoveryEvidenceError) as exc2:
        ValidatorCapability("FRACTAL_PROD_DOMAIN", CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "FakeVal", b"1234"*8)
    assert "Direct instantiation of ValidatorCapability is forbidden" in str(exc2.value)


# --- Attack I: Bootstrap subclassing ---

def test_attack_i_bootstrap_subclassing_rejected() -> None:
    class EvilBootstrap(TrustedRuntimeBootstrap):
        pass

    with pytest.raises(AuthorityError) as exc:
        EvilBootstrap.bootstrap_production_runtime()
    assert "Subclass invocation" in str(exc.value)

    with pytest.raises(AuthorityError) as exc2:
        EvilBootstrap()
    assert "Direct instantiation" in str(exc2.value)


# --- Attack J: Copy / deepcopy / pickle / serialization ---

def test_attack_j_copy_and_pickle_resistance() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    assert copy.copy(prod_bootstrap) is None
    assert copy.deepcopy(prod_bootstrap) is None
    assert copy.copy(domain) is None
    assert copy.deepcopy(domain) is None

    with pytest.raises(AuthorityError):
        pickle.dumps(prod_bootstrap)

    with pytest.raises(AuthorityError):
        pickle.dumps(domain)


# --- Attack K: Concurrency ---

def test_attack_k_concurrent_production_initialization_race() -> None:
    results = []

    def _worker() -> None:
        inst = TrustedRuntimeBootstrap.bootstrap_production_runtime()
        results.append(inst)

    threads = [threading.Thread(target=_worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 16
    first_instance = results[0]
    for item in results:
        assert item is first_instance
        assert item.domain is first_instance.domain


# --- Authority Completeness Invariant ---

def test_authority_completeness_invariant_fails_closed_when_incomplete() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Mint only subset of required roles
    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    # Finalization MUST fail closed because required capabilities and registered producers are missing
    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.finalize()
    assert "Cannot finalize incomplete production authority domain" in str(exc.value)


# --- Full Production Recovery Lifecycle ---

def test_full_production_recovery_lifecycle_succeeds() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    j_val = prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")
    s_val = prod_bootstrap.mint_validator_capability(CapabilityRole.SNAPSHOT_RECOVERY_VALIDATOR, "SnapshotRecoveryValidator")
    r_val = prod_bootstrap.mint_validator_capability(CapabilityRole.RISK_LEDGER_RECOVERY_VALIDATOR, "RiskLedgerRecoveryValidator")
    i_val = prod_bootstrap.mint_validator_capability(CapabilityRole.INTENT_RECOVERY_VALIDATOR, "IntentRecoveryValidator")
    b_val = prod_bootstrap.mint_validator_capability(CapabilityRole.BROKER_RECONCILIATION_VALIDATOR, "BrokerReconciliationValidator")
    c_val = prod_bootstrap.mint_validator_capability(CapabilityRole.CONFIGURATION_VALIDATOR, "ConfigurationValidator")
    p_val = prod_bootstrap.mint_validator_capability(CapabilityRole.PROTECTIVE_MONITORING_VALIDATOR, "ProtectiveMonitoringValidator")

    journal = DurableEventJournal()
    snap_engine = SnapshotEngine()
    risk_ledger = OpportunityRiskLedger("b1", "o1", 1000.0, 10.0)
    intent_repo = DurableExecutionIntentRepository()
    config = compute_effective_config(BaseConfig(), "EURUSD")
    protective = ProtectiveMonitoringSubsystem()

    j_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    s_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    r_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    i_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    b_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    c_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, config.effective_config_id)
    p_prod = prod_bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, protective.subsystem_id)

    adapter = AuthoritativeBrokerAdapter(capability=b_prod, authority=BrokerQueryQuality.FOUND)

    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal)
    prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, snap_engine)
    prod_bootstrap.register_producer(CapabilityRole.RISK_LEDGER, risk_ledger)
    prod_bootstrap.register_producer(CapabilityRole.INTENT_REPOSITORY, intent_repo)
    prod_bootstrap.register_producer(CapabilityRole.BROKER_QUERY, adapter)
    prod_bootstrap.register_producer(CapabilityRole.EFFECTIVE_CONFIGURATION, config)
    prod_bootstrap.register_producer(CapabilityRole.PROTECTIVE_MONITOR, protective)

    engine = prod_bootstrap.create_recovery_engine()
    engine.trigger_system_restart()
    session_id = engine.session_id
    engine.start_reconciliation()

    # Seal production authority domain
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


# --- Additional Direct Private-Attribute Replacement Attacks ---

def test_direct_private_attribute_replacement_rejected_before_and_after_sealing() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    # Attempt attribute replacement before sealing MUST raise AuthorityError
    with pytest.raises(AuthorityError):
        domain._provisioning_token = object()

    with pytest.raises(AuthorityError):
        domain._master_key = b"\x01" * 32

    with pytest.raises(AuthorityError):
        domain._validator_capabilities = {}

    with pytest.raises(AuthorityError):
        domain._producer_capabilities = {}

    with pytest.raises(AuthorityError):
        domain._registered_producers = {}

    with pytest.raises(AuthorityError):
        domain._minted_roles = set()

    with pytest.raises(AuthorityError):
        domain.domain_id = "SPOOF_DOMAIN_ID"

    with pytest.raises(AuthorityError):
        domain._finalized = True

    with pytest.raises(AuthorityError):
        domain._is_production = False

    with pytest.raises(AuthorityError):
        del domain._finalized

    with pytest.raises(AuthorityError):
        prod_bootstrap._domain = None  # type: ignore

    with pytest.raises(AuthorityError):
        prod_bootstrap._provisioning_token = object()

    with pytest.raises(AuthorityError):
        del prod_bootstrap._is_sealed

    # Now provision and seal authority
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    # Attempt attribute replacement after sealing MUST also raise AuthorityError
    with pytest.raises(AuthorityError):
        domain._provisioning_token = object()

    with pytest.raises(AuthorityError):
        domain._master_key = b"\x01" * 32

    with pytest.raises(AuthorityError):
        domain._validator_capabilities = {}

    with pytest.raises(AuthorityError):
        domain._producer_capabilities = {}

    with pytest.raises(AuthorityError):
        domain._registered_producers = {}

    with pytest.raises(AuthorityError):
        domain._finalized = False

    with pytest.raises(AuthorityError):
        del domain._finalized

    with pytest.raises(AuthorityError):
        prod_bootstrap._is_sealed = False

    # Verify that original authority state remains valid and operational
    assert domain._finalized is True
    assert domain.is_production is True
    assert prod_bootstrap._is_sealed is True


# --- Capability / Producer Mismatch Attacks ---

def test_capability_producer_identity_mismatch_rejected_at_registration() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Mint JOURNAL capability bound to "Journal_Alpha"
    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "Journal_Alpha")

    # Attempting to register producer instance with mismatched identity "Journal_Beta" MUST raise AuthorityError
    class BetaJournal(DurableEventJournal):
        producer_id = "Journal_Beta"

    beta_journal = BetaJournal()
    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.register_producer(CapabilityRole.JOURNAL, beta_journal)
    assert "does not match capability producer_id" in str(exc.value)


def test_producer_registered_under_wrong_role_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    journal = DurableEventJournal()

    # Register journal under SNAPSHOT role
    with pytest.raises(AuthorityError):
        prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, journal)


def test_module_introspection_reveals_no_reusable_sentinels() -> None:
    import src.fractal_flow.execution.recovery as rec

    module_vars = vars(rec)
    module_dir = dir(rec)

    for sentinel_name in (
        "_ISSUANCE_KEY",
        "_PRODUCTION_ROOT_TOKEN",
        "_PRODUCTION_INIT_TOKEN",
        "_BOOTSTRAP_ISSUANCE_TOKEN",
    ):
        assert sentinel_name not in module_vars
        assert sentinel_name not in module_dir
        assert not hasattr(rec, sentinel_name)

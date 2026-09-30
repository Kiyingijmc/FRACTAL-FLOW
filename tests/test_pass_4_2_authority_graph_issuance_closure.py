"""Comprehensive Pass 4.2 Adversarial Authority Matrix Test Suite.

Verifies closure of the Authority Graph, Issuance Boundary, and Adversarial Integrity
across all 20 required attack matrix scenarios (A through T).
"""

import pytest
import copy
import pickle
import threading
from typing import Any

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
    JournalRecoveryEvidence,
    SnapshotRecoveryEvidence,
    RiskLedgerRecoveryEvidence,
    IntentRecoveryEvidence,
    BrokerReconciliationEvidence,
    ConfigurationEvidence,
    ProtectiveMonitoringEvidence,
    AuthorityBootstrap,
    AuthorityDomain,
    TrustedRuntimeBootstrap,
    CapabilityRole,
    SealedObservation,
    ProducerCapability,
    ValidatorCapability,
    ProducerBinding,
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

    b_prod = prod_bootstrap.get_producer_capability(CapabilityRole.BROKER_QUERY) or prod_bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "BrokerAdapterSubsystem")
    adapter = AuthoritativeBrokerAdapter(capability=b_prod, authority=BrokerQueryQuality.FOUND)

    prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL) or prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.SNAPSHOT) or prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.RISK_LEDGER) or prod_bootstrap.mint_producer_capability(CapabilityRole.RISK_LEDGER, "RiskLedgerSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.INTENT_REPOSITORY) or prod_bootstrap.mint_producer_capability(CapabilityRole.INTENT_REPOSITORY, "IntentRepoSubsystem")
    prod_bootstrap.get_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION) or prod_bootstrap.mint_producer_capability(CapabilityRole.EFFECTIVE_CONFIGURATION, config.effective_config_id)
    prod_bootstrap.get_producer_capability(CapabilityRole.PROTECTIVE_MONITOR) or prod_bootstrap.mint_producer_capability(CapabilityRole.PROTECTIVE_MONITOR, protective.subsystem_id)

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


# --- Scenario A: Foreign domain capability ---

def test_scenario_a_foreign_domain_capability_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    # Foreign domain creates capability
    foreign_bootstrap = AuthorityBootstrap("FOREIGN_DOMAIN")
    foreign_cap = foreign_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    # Attempting to register producer with foreign capability or cross-validate MUST fail
    journal = DurableEventJournal()
    foreign_obs = journal.produce_observation("sess_123", foreign_cap)

    val_cap = prod_bootstrap.get_validator_capability("JournalRecoveryValidator")

    ev = JournalRecoveryValidator.validate(
        journal, "sess_123", val_cap, observation=foreign_obs, producer_capability=foreign_cap, authority_domain=prod_bootstrap.domain
    )
    assert ev.valid is False
    assert ev.provenance.result == "FAILED"


# --- Scenario B: Foreign domain producer ---

def test_scenario_b_foreign_domain_producer_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    foreign_bootstrap = AuthorityBootstrap("FOREIGN_DOMAIN")
    foreign_journal = DurableEventJournal()
    foreign_bootstrap.register_producer(CapabilityRole.JOURNAL, foreign_journal)

    # Registering a foreign domain's producer instance without registering it in prod_bootstrap MUST fail validation
    j_cap = prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    val_cap = prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "JournalRecoveryValidator")

    obs = foreign_journal.produce_observation("sess_123", j_cap)

    ev = JournalRecoveryValidator.validate(
        foreign_journal, "sess_123", val_cap, observation=obs, producer_capability=j_cap, authority_domain=prod_bootstrap.domain
    )
    assert ev.valid is False
    assert "Unregistered Journal instance" in str(ev.provenance.failure_reason)


# --- Scenario C: Wrong role ---

def test_scenario_c_wrong_role_registration_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    snap_cap = prod_bootstrap.mint_producer_capability(CapabilityRole.SNAPSHOT, "SnapshotSubsystem")

    class JournalProducer(DurableEventJournal):
        producer_id = "JournalSubsystem"

    journal = JournalProducer()

    # Attempt to register journal producer (with producer_id "JournalSubsystem") under SNAPSHOT role (capability has producer_id "SnapshotSubsystem")
    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.register_producer(CapabilityRole.SNAPSHOT, journal)
    assert "does not match capability producer_id" in str(exc.value)


# --- Scenario D: Wrong producer ID ---

def test_scenario_d_wrong_producer_id_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "Journal_Alpha")

    class BetaJournal(DurableEventJournal):
        producer_id = "Journal_Beta"

    beta_journal = BetaJournal()
    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.register_producer(CapabilityRole.JOURNAL, beta_journal)
    assert "does not match capability producer_id" in str(exc.value)


# --- Scenario E: Wrong producer object ---

def test_scenario_e_wrong_producer_object_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    journal_primary = DurableEventJournal()
    journal_imposter = DurableEventJournal()

    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    prod_bootstrap.register_producer(CapabilityRole.JOURNAL, journal_primary)

    # Imposter object identity check fails
    assert prod_bootstrap.domain.is_registered_producer(CapabilityRole.JOURNAL, journal_primary) is True
    assert prod_bootstrap.domain.is_registered_producer(CapabilityRole.JOURNAL, journal_imposter) is False


# --- Scenario F: Forged issuance evidence ---

def test_scenario_f_forged_issuance_evidence_rejected() -> None:
    # Direct construction attempt without going through AuthorityDomain.mint_producer_capability MUST fail
    with pytest.raises(RecoveryEvidenceError) as exc:
        ProducerCapability("DOMAIN_X", CapabilityRole.JOURNAL, "ProducerX", b"1234" * 8)
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)

    with pytest.raises(RecoveryEvidenceError) as exc2:
        ValidatorCapability("DOMAIN_X", CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "ValX", b"1234" * 8)
    assert "Direct instantiation of ValidatorCapability is forbidden" in str(exc2.value)


# --- Scenario G: Extracted issuance material ---

def test_scenario_g_extracted_issuance_material_nonexistent() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    domain = prod_bootstrap.domain

    assert not hasattr(domain, "_issuance_key")
    assert not hasattr(domain, "_verify_issuance_key")
    assert getattr(domain, "_master_key", None) is not None

    prod_bootstrap.finalize()
    assert domain._master_key == b"\x00" * 32


# --- Scenario H: Post-seal mint ---

def test_scenario_h_post_seal_mint_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    with pytest.raises(RecoveryEvidenceError):
        prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "PostSealJournal")

    with pytest.raises(RecoveryEvidenceError):
        prod_bootstrap.mint_validator_capability(CapabilityRole.JOURNAL_RECOVERY_VALIDATOR, "PostSealVal")


# --- Scenario I: Post-seal registration ---

def test_scenario_i_post_seal_registration_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    with pytest.raises(AuthorityError):
        prod_bootstrap.register_producer(CapabilityRole.JOURNAL, DurableEventJournal())


# --- Scenario J: Post-seal binding replacement ---

def test_scenario_j_post_seal_binding_replacement_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    with pytest.raises(TypeError):
        prod_bootstrap.domain._producer_bindings[CapabilityRole.JOURNAL] = "REPLACEMENT"  # type: ignore


# --- Scenario K: Registry mutation ---

def test_scenario_k_registry_mutation_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    with pytest.raises(TypeError):
        prod_bootstrap.domain._registered_producers[CapabilityRole.JOURNAL] = "MUTATED"  # type: ignore


# --- Scenario L: Registry replacement ---

def test_scenario_l_registry_replacement_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    with pytest.raises(AuthorityError):
        domain._registered_producers = {}

    with pytest.raises(AuthorityError):
        domain._producer_capabilities = {}


# --- Scenario M: Copy / deepcopy reconstruction ---

def test_scenario_m_copy_deepcopy_reconstruction_returns_none() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    assert copy.copy(prod_bootstrap) is None
    assert copy.deepcopy(prod_bootstrap) is None
    assert copy.copy(domain) is None
    assert copy.deepcopy(domain) is None


# --- Scenario N: Serialization reconstruction ---

def test_scenario_n_serialization_reconstruction_prohibited() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    domain = prod_bootstrap.domain

    with pytest.raises(AuthorityError):
        pickle.dumps(prod_bootstrap)

    with pytest.raises(AuthorityError):
        pickle.dumps(domain)


# --- Scenario O: Concurrent provisioning ---

def test_scenario_o_concurrent_provisioning_thread_safe() -> None:
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
    first = results[0]
    for item in results:
        assert item is first
        assert item.domain is first.domain


# --- Scenario P: Failed finalization recovery ---

def test_scenario_p_failed_finalization_remains_provisionable() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Provision incomplete graph
    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    # Attempt finalization (fails)
    with pytest.raises(AuthorityError):
        prod_bootstrap.finalize()

    # Domain remains unfinalized and provisionable!
    assert prod_bootstrap.domain._finalized is False
    assert prod_bootstrap._is_sealed is False

    # Continue provisioning missing components
    _provision_full_production_authority(prod_bootstrap)

    # Subsequent finalization succeeds
    prod_bootstrap.finalize()
    assert prod_bootstrap.domain._finalized is True
    assert prod_bootstrap._is_sealed is True


# --- Scenario Q: Retry finalization ---

def test_scenario_q_retry_finalization_prohibited() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)
    prod_bootstrap.finalize()

    # Subsequent finalize attempts fail closed
    with pytest.raises(AuthorityError):
        prod_bootstrap.finalize()

    with pytest.raises(AuthorityError):
        prod_bootstrap.domain.finalize()


# --- Scenario R: Orphan capability ---

def test_scenario_r_orphan_capability_blocks_finalization() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    # Mint capability without registering producer
    prod_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.finalize()
    assert "Cannot finalize incomplete production authority domain" in str(exc.value)


# --- Scenario S: Orphan binding ---

def test_scenario_s_orphan_binding_detected_at_finalization() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    # Manually inject orphan binding
    domain = prod_bootstrap.domain
    fake_binding = ProducerBinding(
        authority_domain_id=domain.domain_id,
        role=CapabilityRole.JOURNAL,
        producer_id="ORPHAN",
        producer_instance=DurableEventJournal(),
        capability=domain._producer_capabilities[CapabilityRole.JOURNAL],
    )
    # _producer_bindings is dict before finalization
    domain._producer_bindings[CapabilityRole.JOURNAL] = fake_binding

    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.finalize()
    assert "ProducerBinding producer instance mismatch" in str(exc.value) or "ProducerBinding identity mismatch" in str(exc.value)


# --- Scenario T: Tampered binding ---

def test_scenario_t_tampered_binding_fields_rejected_at_finalization() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    domain = prod_bootstrap.domain
    original_binding = domain._producer_bindings[CapabilityRole.JOURNAL]

    # Inject binding with mismatched authority_domain_id
    tampered_binding = ProducerBinding(
        authority_domain_id="FOREIGN_DOMAIN",
        role=original_binding.role,
        producer_id=original_binding.producer_id,
        producer_instance=original_binding.producer_instance,
        capability=original_binding.capability,
    )
    domain._producer_bindings[CapabilityRole.JOURNAL] = tampered_binding

    with pytest.raises(AuthorityError) as exc:
        prod_bootstrap.finalize()
    assert "Cross-domain binding substitution detected" in str(exc.value)


# --- Scenario U: Fake AuthorityDomain subclass ---

def test_scenario_u_fake_authority_domain_subclass_rejected() -> None:
    class ForgedDomain(AuthorityDomain):
        def mint_producer_capability(self, role: CapabilityRole, producer_id: str, _provisioning_token: Any = None) -> ProducerCapability:
            return ProducerCapability(
                authority_domain_id=self.domain_id,
                role=role,
                producer_id=producer_id,
                _role_key=b"attacker_key_32_bytes_long_12345",
            )

    attacker = ForgedDomain("ATTACKER_DOMAIN")
    with pytest.raises(RecoveryEvidenceError) as exc:
        attacker.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)


# --- Scenario V: Fake minting frame / stack frame spoofing ---

def test_scenario_v_fake_minting_frame_spoofing_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()

    class ForgedDomain(AuthorityDomain):
        def mint_producer_capability(self, role: CapabilityRole, producer_id: str, _provisioning_token: Any = None) -> ProducerCapability:
            return ProducerCapability(
                authority_domain_id=self.domain_id,
                role=role,
                producer_id=producer_id,
                _role_key=b"attacker_key_32_bytes_long_12345",
            )

    attacker = ForgedDomain("SPOOFED_DOMAIN")

    with pytest.raises(RecoveryEvidenceError) as exc:
        attacker.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)


# --- Scenario W: Fake issuer ---

def test_scenario_w_fake_issuer_rejected() -> None:
    # Attempting to call ProducerCapability._mint from a non-AuthorityDomain or finalized domain fails closed
    fake_domain = object()
    with pytest.raises(RecoveryEvidenceError) as exc:
        ProducerCapability._mint(fake_domain, CapabilityRole.JOURNAL, "JournalSubsystem", b"0" * 32)
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)


# --- Scenario X: Object.__setattr__ bypass regression test ---

def test_scenario_x_object_setattr_cannot_forge_capability_issuance() -> None:
    domain = AuthorityDomain("ATTACKER_DOMAIN")

    # Attacker uses object.__setattr__ to inject arbitrary attributes on AuthorityDomain instance
    ctx = object()
    object.__setattr__(domain, "_active_mint_context", ctx)

    # Calling ProducerCapability directly MUST fail closed
    with pytest.raises(RecoveryEvidenceError) as exc:
        ProducerCapability(
            authority_domain_id=domain.domain_id,
            role=CapabilityRole.JOURNAL,
            producer_id="ATTACKER",
            _role_key=b"attacker-controlled-key",
        )
    assert "Direct instantiation of ProducerCapability is forbidden" in str(exc.value)


# --- Scenario Y: Capability reconstruction from observable state ---

def test_scenario_y_capability_reconstruction_from_observable_fields_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    legitimate_cap = prod_bootstrap.get_producer_capability(CapabilityRole.JOURNAL)
    assert legitimate_cap is not None

    # Attacker attempts to reconstruct capability using observable fields
    with pytest.raises(RecoveryEvidenceError):
        ProducerCapability(
            authority_domain_id=legitimate_cap.authority_domain_id,
            role=legitimate_cap.role,
            producer_id=legitimate_cap.producer_id,
            _role_key=legitimate_cap._role_key,
        )


# --- Scenario Z: Foreign domain / issuer substitution ---

def test_scenario_z_foreign_domain_issuer_substitution_rejected() -> None:
    prod_bootstrap = TrustedRuntimeBootstrap.bootstrap_production_runtime()
    _provision_full_production_authority(prod_bootstrap)

    foreign_bootstrap = AuthorityBootstrap("FOREIGN_DOMAIN")
    foreign_cap = foreign_bootstrap.mint_producer_capability(CapabilityRole.JOURNAL, "JournalSubsystem")

    # Downstream recovery validator rejects foreign domain capability
    journal = DurableEventJournal()
    foreign_obs = journal.produce_observation("sess_123", foreign_cap)
    val_cap = prod_bootstrap.get_validator_capability("JournalRecoveryValidator")

    ev = JournalRecoveryValidator.validate(
        journal, "sess_123", val_cap, observation=foreign_obs, producer_capability=foreign_cap, authority_domain=prod_bootstrap.domain
    )
    assert ev.valid is False
    assert ev.provenance.result == "FAILED"

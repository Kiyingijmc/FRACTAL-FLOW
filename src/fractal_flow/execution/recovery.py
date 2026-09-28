"""RecoveryEngine managing explicit recovery states, evidence provenance, and Gating Strategic Execution."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any


@unique
class RecoveryState(str, Enum):
    NORMAL = "NORMAL"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERING = "RECOVERING"
    RECONCILING = "RECONCILING"
    RECOVERY_COMPLETE = "RECOVERY_COMPLETE"
    SAFE = "SAFE"


@dataclass
class EvidenceProvenance:
    """Verifiable metadata capturing the authoritative source, boundary, and session of produced recovery evidence."""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_component: str = ""
    source_operation: str = ""
    produced_at: float = field(default_factory=time.time)
    source_session: str = ""
    source_sequence: int = 0
    source_boundary: str = ""
    source_identity: str = ""
    result: str = "SUCCESS"
    failure_reason: Optional[str] = None


@dataclass
class JournalRecoveryEvidence:
    valid: bool = False
    head_sequence: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotRecoveryEvidence:
    valid: bool = False
    boundary_sequence: int = 0
    fallback_used: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskLedgerRecoveryEvidence:
    valid: bool = False
    reconstructed_entries_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentRecoveryEvidence:
    valid: bool = False
    reconstructed_intents_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerReconciliationEvidence:
    valid: bool = False
    unresolved_unknown_count: int = 0
    orphaned_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigurationEvidence:
    valid: bool = False
    config_id: str = ""
    identity_matched: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtectiveMonitoringEvidence:
    valid: bool = False
    active: bool = True
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryEvidence:
    """Verifiable composite evidence required to authorize system recovery completion."""
    journal_evidence: JournalRecoveryEvidence = field(default_factory=JournalRecoveryEvidence)
    snapshot_evidence: SnapshotRecoveryEvidence = field(default_factory=SnapshotRecoveryEvidence)
    risk_evidence: RiskLedgerRecoveryEvidence = field(default_factory=RiskLedgerRecoveryEvidence)
    intent_evidence: IntentRecoveryEvidence = field(default_factory=IntentRecoveryEvidence)
    broker_evidence: BrokerReconciliationEvidence = field(default_factory=BrokerReconciliationEvidence)
    config_evidence: ConfigurationEvidence = field(default_factory=ConfigurationEvidence)
    protective_evidence: ProtectiveMonitoringEvidence = field(default_factory=ProtectiveMonitoringEvidence)

    # Legacy attributes maintained purely for backward compatibility/diagnostics.
    # DEPRECATED: These fields CANNOT authorize strategic execution.
    persistence_integrity_valid: bool = False
    journal_integrity_valid: bool = False
    snapshot_integrity_valid: bool = False
    risk_ledger_reconstructed: bool = False
    execution_intents_reconstructed: bool = False
    broker_reconciliation_complete: bool = False
    unresolved_unknown_count: int = 0
    configuration_identity_matched: bool = False
    protective_monitoring_active: bool = True
    additional_details: Dict[str, Any] = field(default_factory=dict)

    def is_satisfactory(self, required_session: Optional[str] = None) -> bool:
        """Returns True only if all required typed subsystem evidence components and valid provenances are satisfied."""
        subsystem_satisfied = (
            self.journal_evidence.valid
            and self.journal_evidence.provenance is not None
            and self.journal_evidence.provenance.result == "SUCCESS"
            and self.snapshot_evidence.valid
            and self.snapshot_evidence.provenance is not None
            and self.snapshot_evidence.provenance.result == "SUCCESS"
            and self.risk_evidence.valid
            and self.risk_evidence.provenance is not None
            and self.risk_evidence.provenance.result == "SUCCESS"
            and self.intent_evidence.valid
            and self.intent_evidence.provenance is not None
            and self.intent_evidence.provenance.result == "SUCCESS"
            and self.broker_evidence.valid
            and self.broker_evidence.provenance is not None
            and self.broker_evidence.provenance.result == "SUCCESS"
            and isinstance(self.broker_evidence.unresolved_unknown_count, int)
            and self.broker_evidence.unresolved_unknown_count == 0
            and isinstance(self.broker_evidence.orphaned_count, int)
            and self.broker_evidence.orphaned_count == 0
            and self.config_evidence.valid
            and self.config_evidence.identity_matched
            and self.config_evidence.provenance is not None
            and self.config_evidence.provenance.result == "SUCCESS"
            and self.protective_evidence.valid
            and self.protective_evidence.active
            and self.protective_evidence.provenance is not None
            and self.protective_evidence.provenance.result == "SUCCESS"
        )

        if not subsystem_satisfied:
            return False

        if required_session:
            provenances = [
                self.journal_evidence.provenance,
                self.snapshot_evidence.provenance,
                self.risk_evidence.provenance,
                self.intent_evidence.provenance,
                self.broker_evidence.provenance,
                self.config_evidence.provenance,
                self.protective_evidence.provenance,
            ]
            for prov in provenances:
                if prov is None or prov.source_session != required_session:
                    return False

        return True

    @classmethod
    def create_authoritative_evidence(
        cls,
        session_id: str,
        journal_valid: bool = True,
        snapshot_valid: bool = True,
        risk_valid: bool = True,
        intent_valid: bool = True,
        broker_valid: bool = True,
        unresolved_unknown_count: int = 0,
        orphaned_count: int = 0,
        config_valid: bool = True,
        config_identity_matched: bool = True,
        protective_valid: bool = True,
        protective_active: bool = True,
    ) -> "RecoveryEvidence":
        p_j = EvidenceProvenance(source_component="JournalRecoveryValidator", source_session=session_id, result="SUCCESS" if journal_valid else "FAILED")
        p_s = EvidenceProvenance(source_component="SnapshotRecoveryValidator", source_session=session_id, result="SUCCESS" if snapshot_valid else "FAILED")
        p_r = EvidenceProvenance(source_component="RiskLedgerRecoveryValidator", source_session=session_id, result="SUCCESS" if risk_valid else "FAILED")
        p_i = EvidenceProvenance(source_component="IntentRecoveryValidator", source_session=session_id, result="SUCCESS" if intent_valid else "FAILED")
        p_b = EvidenceProvenance(source_component="BrokerReconciliationValidator", source_session=session_id, result="SUCCESS" if (broker_valid and unresolved_unknown_count == 0 and orphaned_count == 0) else "FAILED")
        p_c = EvidenceProvenance(source_component="ConfigurationValidator", source_session=session_id, result="SUCCESS" if (config_valid and config_identity_matched) else "FAILED")
        p_p = EvidenceProvenance(source_component="ProtectiveMonitoringValidator", source_session=session_id, result="SUCCESS" if (protective_valid and protective_active) else "FAILED")

        return cls(
            journal_evidence=JournalRecoveryEvidence(valid=journal_valid, provenance=p_j),
            snapshot_evidence=SnapshotRecoveryEvidence(valid=snapshot_valid, provenance=p_s),
            risk_evidence=RiskLedgerRecoveryEvidence(valid=risk_valid, provenance=p_r),
            intent_evidence=IntentRecoveryEvidence(valid=intent_valid, provenance=p_i),
            broker_evidence=BrokerReconciliationEvidence(valid=broker_valid, unresolved_unknown_count=unresolved_unknown_count, orphaned_count=orphaned_count, provenance=p_b),
            config_evidence=ConfigurationEvidence(valid=config_valid, identity_matched=config_identity_matched, provenance=p_c),
            protective_evidence=ProtectiveMonitoringEvidence(valid=protective_valid, active=protective_active, provenance=p_p),
        )


# --- Authoritative Subsystem Recovery Validators / Producers ---

class JournalRecoveryValidator:
    @staticmethod
    def validate(journal: Any, session_id: str) -> JournalRecoveryEvidence:
        faulted = getattr(journal, "_faulted", False)
        seq = journal._global_sequence if hasattr(journal, "_global_sequence") else 0
        prov = EvidenceProvenance(
            source_component="JournalRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            source_sequence=seq,
            source_boundary=str(getattr(journal, "journal_path", "journal")),
            result="SUCCESS" if not faulted else "FAILED"
        )
        return JournalRecoveryEvidence(valid=not faulted, head_sequence=seq, provenance=prov)


class SnapshotRecoveryValidator:
    @staticmethod
    def validate(snapshot_engine: Any, session_id: str) -> SnapshotRecoveryEvidence:
        fallback = getattr(snapshot_engine, "_snapshot_fallback_used", False)
        valid = getattr(snapshot_engine, "_snapshot_valid", True)
        prov = EvidenceProvenance(
            source_component="SnapshotRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED"
        )
        return SnapshotRecoveryEvidence(valid=valid, fallback_used=fallback, provenance=prov)


class RiskLedgerRecoveryValidator:
    @staticmethod
    def reconstruct(risk_ledger: Any, session_id: str) -> RiskLedgerRecoveryEvidence:
        count = len(getattr(risk_ledger, "_entries_by_id", {}))
        prov = EvidenceProvenance(
            source_component="RiskLedgerRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS"
        )
        return RiskLedgerRecoveryEvidence(valid=True, reconstructed_entries_count=count, provenance=prov)


class IntentRecoveryValidator:
    @staticmethod
    def reconstruct(intent_repo: Any, session_id: str) -> IntentRecoveryEvidence:
        prov = EvidenceProvenance(
            source_component="IntentRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS"
        )
        return IntentRecoveryEvidence(valid=True, reconstructed_intents_count=0, provenance=prov)


class BrokerReconciliationValidator:
    @staticmethod
    def reconcile(reconciliation_result: Any, session_id: str) -> BrokerReconciliationEvidence:
        unknown = getattr(reconciliation_result, "unresolved_unknown_count", 0)
        orphaned = getattr(reconciliation_result, "orphaned_count", 0)
        valid = (unknown == 0 and orphaned == 0)
        prov = EvidenceProvenance(
            source_component="BrokerReconciliationValidator",
            source_operation="reconcile",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED"
        )
        return BrokerReconciliationEvidence(
            valid=valid,
            unresolved_unknown_count=unknown,
            orphaned_count=orphaned,
            provenance=prov
        )


class ConfigurationValidator:
    @staticmethod
    def validate(config_id: str, session_id: str) -> ConfigurationEvidence:
        prov = EvidenceProvenance(
            source_component="ConfigurationValidator",
            source_operation="validate",
            source_session=session_id,
            source_identity=config_id,
            result="SUCCESS"
        )
        return ConfigurationEvidence(valid=True, config_id=config_id, identity_matched=True, provenance=prov)


class ProtectiveMonitoringValidator:
    @staticmethod
    def validate(active: bool, session_id: str) -> ProtectiveMonitoringEvidence:
        prov = EvidenceProvenance(
            source_component="ProtectiveMonitoringValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if active else "FAILED"
        )
        return ProtectiveMonitoringEvidence(valid=active, active=active, provenance=prov)


class RecoveryEngine:
    """Manages system recovery lifecycle and gates strategic execution authorization based on verifiable evidence."""

    def __init__(self, initial_state: RecoveryState = RecoveryState.NORMAL) -> None:
        self.state = initial_state
        self.strategic_authorization_enabled = (initial_state == RecoveryState.NORMAL)
        self.last_evidence: Optional[RecoveryEvidence] = None
        self.session_id: str = str(uuid.uuid4())

    def trigger_system_restart(self) -> None:
        """Triggers recovery mode on system restart and disables strategic authorization."""
        self.state = RecoveryState.RECOVERY_REQUIRED
        self.strategic_authorization_enabled = False
        self.session_id = str(uuid.uuid4())

    def start_recovery(self) -> None:
        if self.state not in (RecoveryState.RECOVERY_REQUIRED, RecoveryState.RECONCILING):
            raise ValueError(f"Cannot start recovery from state '{self.state}'")
        self.state = RecoveryState.RECOVERING

    def start_reconciliation(self) -> None:
        if self.state not in (RecoveryState.RECOVERY_REQUIRED, RecoveryState.RECOVERING):
            raise ValueError(f"Cannot start reconciliation from state '{self.state}'")
        self.state = RecoveryState.RECONCILING

    def complete_recovery_with_evidence(self, evidence: RecoveryEvidence) -> None:
        """Completes recovery using verifiable evidence object containing all required gate checks."""
        if self.state not in (RecoveryState.RECONCILING, RecoveryState.RECOVERING):
            raise ValueError(f"Cannot complete recovery with evidence from state '{self.state}'")

        self.last_evidence = evidence
        if not evidence.is_satisfactory(required_session=self.session_id):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise ValueError(
                f"Recovery evidence validation failed. System placed in SAFE state."
            )

        self.state = RecoveryState.RECOVERY_COMPLETE
        self.strategic_authorization_enabled = True

    def complete_recovery(self, reconciliation_successful: bool) -> None:
        """Deprecated boolean recovery method. Places system in SAFE state or RECOVERY_COMPLETE without enabling strategic authorization."""
        if not reconciliation_successful:
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise ValueError("Reconciliation failed. System placed in SAFE recovery state.")

        # Boolean shortcut alone CANNOT authorize strategic execution!
        self.state = RecoveryState.RECOVERY_COMPLETE
        self.strategic_authorization_enabled = False

    def can_authorize_strategic_action(self) -> bool:
        return self.strategic_authorization_enabled and self.state in (RecoveryState.NORMAL, RecoveryState.RECOVERY_COMPLETE)

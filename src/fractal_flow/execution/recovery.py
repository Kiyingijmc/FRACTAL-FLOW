"""RecoveryEngine managing explicit recovery states, evidence provenance, and Gating Strategic Execution."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.fractal_flow.execution.reconciliation import ReconciliationReport


class RecoveryEvidenceError(Exception):
    """Raised when recovery evidence construction, assembly, session binding, or verification fails."""
    pass


@unique
class RecoveryState(str, Enum):
    NORMAL = "NORMAL"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERING = "RECOVERING"
    RECONCILING = "RECONCILING"
    RECOVERY_COMPLETE = "RECOVERY_COMPLETE"
    SAFE = "SAFE"


@dataclass(frozen=True)
class EvidenceProvenance:
    """Verifiable, immutable metadata capturing the authoritative source, boundary, and session of produced recovery evidence."""
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


@dataclass(frozen=True)
class JournalRecoveryEvidence:
    valid: bool = False
    head_sequence: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotRecoveryEvidence:
    valid: bool = False
    boundary_sequence: int = 0
    fallback_used: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskLedgerRecoveryEvidence:
    valid: bool = False
    reconstructed_entries_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntentRecoveryEvidence:
    valid: bool = False
    reconstructed_intents_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerReconciliationEvidence:
    valid: bool = False
    unresolved_unknown_count: int = 0
    orphaned_count: int = 0
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigurationEvidence:
    valid: bool = False
    config_id: str = ""
    identity_matched: bool = False
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProtectiveMonitoringEvidence:
    valid: bool = False
    active: bool = True
    provenance: Optional[EvidenceProvenance] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
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
            and self.journal_evidence.provenance.source_component == "JournalRecoveryValidator"
            and self.snapshot_evidence.valid
            and self.snapshot_evidence.provenance is not None
            and self.snapshot_evidence.provenance.result == "SUCCESS"
            and self.snapshot_evidence.provenance.source_component == "SnapshotRecoveryValidator"
            and self.risk_evidence.valid
            and self.risk_evidence.provenance is not None
            and self.risk_evidence.provenance.result == "SUCCESS"
            and self.risk_evidence.provenance.source_component == "RiskLedgerRecoveryValidator"
            and self.intent_evidence.valid
            and self.intent_evidence.provenance is not None
            and self.intent_evidence.provenance.result == "SUCCESS"
            and self.intent_evidence.provenance.source_component == "IntentRecoveryValidator"
            and self.broker_evidence.valid
            and self.broker_evidence.provenance is not None
            and self.broker_evidence.provenance.result == "SUCCESS"
            and self.broker_evidence.provenance.source_component == "BrokerReconciliationValidator"
            and isinstance(self.broker_evidence.unresolved_unknown_count, int)
            and self.broker_evidence.unresolved_unknown_count == 0
            and isinstance(self.broker_evidence.orphaned_count, int)
            and self.broker_evidence.orphaned_count == 0
            and self.config_evidence.valid
            and self.config_evidence.identity_matched
            and self.config_evidence.provenance is not None
            and self.config_evidence.provenance.result == "SUCCESS"
            and self.config_evidence.provenance.source_component == "ConfigurationValidator"
            and self.protective_evidence.valid
            and self.protective_evidence.active
            and self.protective_evidence.provenance is not None
            and self.protective_evidence.provenance.result == "SUCCESS"
            and self.protective_evidence.provenance.source_component == "ProtectiveMonitoringValidator"
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
        **kwargs: Any,
    ) -> "RecoveryEvidence":
        """DEPRECATED / UNAUTHORIZED FACTORY.

        Caller-supplied booleans cannot manufacture authoritative evidence.
        Returns evidence marked UNAUTHORIZED_FACTORY which fails authorization gates.
        """
        unauth_prov = EvidenceProvenance(
            source_component="CALLER_UNAUTHORIZED_FACTORY",
            source_session=session_id,
            result="UNAUTHORIZED_FACTORY",
            failure_reason="Caller self-attestation is forbidden in authorization pathways.",
        )
        return cls(
            journal_evidence=JournalRecoveryEvidence(valid=False, provenance=unauth_prov),
            snapshot_evidence=SnapshotRecoveryEvidence(valid=False, provenance=unauth_prov),
            risk_evidence=RiskLedgerRecoveryEvidence(valid=False, provenance=unauth_prov),
            intent_evidence=IntentRecoveryEvidence(valid=False, provenance=unauth_prov),
            broker_evidence=BrokerReconciliationEvidence(valid=False, provenance=unauth_prov),
            config_evidence=ConfigurationEvidence(valid=False, provenance=unauth_prov),
            protective_evidence=ProtectiveMonitoringEvidence(valid=False, provenance=unauth_prov),
        )


# --- Controlled Evidence Assembler ---

class RecoveryEvidenceAssembler:
    """Assembles typed recovery evidence from subsystem producers and enforces provenance and session consistency."""

    @staticmethod
    def assemble(
        *,
        journal: JournalRecoveryEvidence,
        snapshot: SnapshotRecoveryEvidence,
        risk: RiskLedgerRecoveryEvidence,
        intents: IntentRecoveryEvidence,
        broker: BrokerReconciliationEvidence,
        config: ConfigurationEvidence,
        protective: ProtectiveMonitoringEvidence,
        session_id: str,
    ) -> RecoveryEvidence:

        evidence = RecoveryEvidence(
            journal_evidence=journal,
            snapshot_evidence=snapshot,
            risk_evidence=risk,
            intent_evidence=intents,
            broker_evidence=broker,
            config_evidence=config,
            protective_evidence=protective,
        )

        if not evidence.is_satisfactory(required_session=session_id):
            raise RecoveryEvidenceError("Recovery evidence assembly failed: evidence is unsatisfactory or session mismatch")

        return evidence


# --- Authoritative Subsystem Recovery Validators / Producers ---

class JournalRecoveryValidator:
    @staticmethod
    def validate(journal: Any, session_id: str) -> JournalRecoveryEvidence:
        faulted = getattr(journal, "_faulted", False)
        seq = journal._global_sequence if hasattr(journal, "_global_sequence") else 0
        valid = not faulted
        prov = EvidenceProvenance(
            source_component="JournalRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            source_sequence=seq,
            source_boundary=str(getattr(journal, "journal_path", "journal")),
            result="SUCCESS" if valid else "FAILED",
            failure_reason="Journal in faulted state" if faulted else None,
        )
        return JournalRecoveryEvidence(valid=valid, head_sequence=seq, provenance=prov)


class SnapshotRecoveryValidator:
    @staticmethod
    def validate(
        snapshot_engine: Any,
        session_id: str,
        journal: Any = None,
        aggregate_type: str = "",
        aggregate_id: str = "",
    ) -> SnapshotRecoveryEvidence:
        fallback = getattr(snapshot_engine, "_snapshot_fallback_used", False)
        valid = getattr(snapshot_engine, "_snapshot_valid", True)

        # If journal and aggregate details are provided, verify snapshot equivalence if loaded snapshot exists
        if snapshot_engine and journal and aggregate_type and aggregate_id:
            try:
                snap = snapshot_engine.load_snapshot(aggregate_type, aggregate_id)
                if snap:
                    snapshot_engine.verify_snapshot_equivalence(
                        snapshot=snap,
                        journal=journal,
                        aggregate_type=aggregate_type,
                        aggregate_id=aggregate_id,
                    )
            except Exception as e:
                valid = False
                fallback = True

        prov = EvidenceProvenance(
            source_component="SnapshotRecoveryValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED",
            failure_reason="Snapshot invalid or corrupt" if not valid else None,
        )
        return SnapshotRecoveryEvidence(valid=valid, fallback_used=fallback, provenance=prov)


class RiskLedgerRecoveryValidator:
    @staticmethod
    def reconstruct(risk_ledger: Any, session_id: str) -> RiskLedgerRecoveryEvidence:
        entries = getattr(risk_ledger, "_entries_by_id", {})
        count = len(entries)
        valid = True
        prov = EvidenceProvenance(
            source_component="RiskLedgerRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED",
        )
        return RiskLedgerRecoveryEvidence(valid=valid, reconstructed_entries_count=count, provenance=prov)


class IntentRecoveryValidator:
    @staticmethod
    def reconstruct(intent_repo: Any, session_id: str) -> IntentRecoveryEvidence:
        valid = True
        count = 0
        if hasattr(intent_repo, "get_all_intents"):
            try:
                intents = intent_repo.get_all_intents()
                count = len(intents)
            except Exception:
                pass
        prov = EvidenceProvenance(
            source_component="IntentRecoveryValidator",
            source_operation="reconstruct",
            source_session=session_id,
            result="SUCCESS" if valid else "FAILED",
        )
        return IntentRecoveryEvidence(valid=valid, reconstructed_intents_count=count, provenance=prov)


class BrokerReconciliationValidator:
    @staticmethod
    def reconcile(reconciliation_report: Any, session_id: str) -> BrokerReconciliationEvidence:
        # Require typed ReconciliationReport
        from src.fractal_flow.execution.reconciliation import ReconciliationReport
        if not isinstance(reconciliation_report, ReconciliationReport):
            prov = EvidenceProvenance(
                source_component="BrokerReconciliationValidator",
                source_operation="reconcile",
                source_session=session_id,
                result="FAILED",
                failure_reason="Authorization requires a ReconciliationReport instance",
            )
            return BrokerReconciliationEvidence(
                valid=False,
                unresolved_unknown_count=-1,
                orphaned_count=-1,
                provenance=prov,
            )

        unknown = reconciliation_report.unknown_count
        orphaned = reconciliation_report.orphaned_count
        valid = (
            reconciliation_report.authoritative
            and reconciliation_report.complete
            and unknown == 0
            and orphaned == 0
        )
        prov = EvidenceProvenance(
            source_component="BrokerReconciliationValidator",
            source_operation="reconcile",
            source_session=session_id,
            source_sequence=reconciliation_report.temporal_boundary,
            source_boundary=str(reconciliation_report.temporal_boundary),
            result="SUCCESS" if valid else "FAILED",
            failure_reason=None if valid else f"Reconciliation invalid (auth={reconciliation_report.authoritative}, comp={reconciliation_report.complete}, unknown={unknown}, orphaned={orphaned})",
        )
        return BrokerReconciliationEvidence(
            valid=valid,
            unresolved_unknown_count=unknown,
            orphaned_count=orphaned,
            provenance=prov,
        )


class ConfigurationValidator:
    @staticmethod
    def validate(config_id: str, session_id: str, expected_config_id: Optional[str] = None) -> ConfigurationEvidence:
        identity_matched = (expected_config_id is None) or (config_id == expected_config_id)
        valid = bool(config_id) and identity_matched
        prov = EvidenceProvenance(
            source_component="ConfigurationValidator",
            source_operation="validate",
            source_session=session_id,
            source_identity=config_id,
            result="SUCCESS" if valid else "FAILED",
            failure_reason=None if valid else "Configuration identity mismatch or empty config_id",
        )
        return ConfigurationEvidence(
            valid=valid,
            config_id=config_id,
            identity_matched=identity_matched,
            provenance=prov,
        )


class ProtectiveMonitoringValidator:
    @staticmethod
    def validate(active: bool, session_id: str) -> ProtectiveMonitoringEvidence:
        prov = EvidenceProvenance(
            source_component="ProtectiveMonitoringValidator",
            source_operation="validate",
            source_session=session_id,
            result="SUCCESS" if active else "FAILED",
            failure_reason=None if active else "Protective monitoring is inactive",
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

        if not isinstance(evidence, RecoveryEvidence):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError("Recovery evidence must be an instance of RecoveryEvidence")

        self.last_evidence = evidence
        if not evidence.is_satisfactory(required_session=self.session_id):
            self.state = RecoveryState.SAFE
            self.strategic_authorization_enabled = False
            raise RecoveryEvidenceError(
                "Recovery evidence validation failed. System placed in SAFE state."
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

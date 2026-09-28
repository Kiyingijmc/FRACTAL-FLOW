"""RecoveryEngine managing explicit recovery states, evidence provenance, and Gating Strategic Execution."""

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
class JournalRecoveryEvidence:
    valid: bool = False
    head_sequence: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotRecoveryEvidence:
    valid: bool = False
    boundary_sequence: int = 0
    fallback_used: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskLedgerRecoveryEvidence:
    valid: bool = False
    reconstructed_entries_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentRecoveryEvidence:
    valid: bool = False
    reconstructed_intents_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerReconciliationEvidence:
    valid: bool = False
    unresolved_unknown_count: int = 0
    orphaned_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigurationEvidence:
    valid: bool = False
    config_id: str = ""
    identity_matched: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtectiveMonitoringEvidence:
    valid: bool = False
    active: bool = True
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

    # Legacy field attributes for backward compatibility
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

    def is_satisfactory(self) -> bool:
        """Returns True only if all required recovery gates and subsystem evidence components are fully satisfied."""
        # Validate legacy boolean gates
        legacy_satisfied = (
            self.persistence_integrity_valid
            and self.journal_integrity_valid
            and self.snapshot_integrity_valid
            and self.risk_ledger_reconstructed
            and self.execution_intents_reconstructed
            and self.broker_reconciliation_complete
            and isinstance(self.unresolved_unknown_count, int)
            and self.unresolved_unknown_count == 0
            and self.configuration_identity_matched
            and self.protective_monitoring_active
        )

        # Validate typed subsystem evidence if provided
        subsystem_satisfied = (
            self.journal_evidence.valid
            and self.snapshot_evidence.valid
            and self.risk_evidence.valid
            and self.intent_evidence.valid
            and self.broker_evidence.valid
            and isinstance(self.broker_evidence.unresolved_unknown_count, int)
            and self.broker_evidence.unresolved_unknown_count == 0
            and self.config_evidence.valid
            and self.config_evidence.identity_matched
            and self.protective_evidence.valid
            and self.protective_evidence.active
        )

        return legacy_satisfied or subsystem_satisfied


class RecoveryEngine:
    """Manages system recovery lifecycle and gates strategic execution authorization based on verifiable evidence."""

    def __init__(self, initial_state: RecoveryState = RecoveryState.NORMAL) -> None:
        self.state = initial_state
        self.strategic_authorization_enabled = (initial_state == RecoveryState.NORMAL)
        self.last_evidence: Optional[RecoveryEvidence] = None

    def trigger_system_restart(self) -> None:
        """Triggers recovery mode on system restart and disables strategic authorization."""
        self.state = RecoveryState.RECOVERY_REQUIRED
        self.strategic_authorization_enabled = False

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
        if not evidence.is_satisfactory():
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

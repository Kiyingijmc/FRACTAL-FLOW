"""RecoveryEngine managing explicit recovery states, evidence-based recovery validation, and Gating Strategic Execution."""

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
class RecoveryEvidence:
    """Verifiable evidence required to authorize system recovery completion."""
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
        """Returns True only if all required recovery gates are fully satisfied."""
        if not isinstance(self.unresolved_unknown_count, int) or self.unresolved_unknown_count != 0:
            return False

        return (
            self.persistence_integrity_valid
            and self.journal_integrity_valid
            and self.snapshot_integrity_valid
            and self.risk_ledger_reconstructed
            and self.execution_intents_reconstructed
            and self.broker_reconciliation_complete
            and self.configuration_identity_matched
            and self.protective_monitoring_active
        )


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
                f"Recovery evidence validation failed (unresolved UNKNOWNs: {evidence.unresolved_unknown_count}, "
                f"reconciliation: {evidence.broker_reconciliation_complete}). System placed in SAFE state."
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

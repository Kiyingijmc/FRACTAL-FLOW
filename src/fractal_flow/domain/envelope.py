"""Canonical State Envelope and State Machine Transition Validator."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


class InvalidStateTransitionException(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


# Allowed state transitions mapped by state machine type
TRANSITION_RULES: Dict[str, Dict[str, List[str]]] = {
    "PDEState": {
        "PDE_NONE": ["PDE_IMPULSE"],
        "PDE_IMPULSE": ["PDE_PULLBACK_CANDIDATE", "PDE_INVALIDATED"],
        "PDE_PULLBACK_CANDIDATE": ["PDE_PULLBACK_ACTIVE", "PDE_INVALIDATED"],
        "PDE_PULLBACK_ACTIVE": ["PDE_WEAKENING", "PDE_STRENGTHENING", "PDE_INVALIDATED"],
        "PDE_WEAKENING": ["PDE_RESUMPTION_IN_PROGRESS", "PDE_STRENGTHENING", "PDE_INVALIDATED"],
        "PDE_STRENGTHENING": ["PDE_DEEPENING", "PDE_WEAKENING", "PDE_INVALIDATED"],
        "PDE_DEEPENING": ["PDE_INVALIDATED"],
        "PDE_RESUMPTION_IN_PROGRESS": ["PDE_FOLLOW_THROUGH", "PDE_RESUMPTION_FAILED", "PDE_INVALIDATED"],
        "PDE_FOLLOW_THROUGH": ["PDE_NONE", "PDE_INVALIDATED"],
        "PDE_RESUMPTION_FAILED": ["PDE_INVALIDATED"],
        "PDE_INVALIDATED": [],
    },
    "NewsState": {
        "NEWS_NORMAL": ["NEWS_WATCH"],
        "NEWS_WATCH": ["NEWS_PREP", "NEWS_NORMAL"],
        "NEWS_PREP": ["NEWS_LOCKDOWN"],
        "NEWS_LOCKDOWN": ["INITIAL_SHOCK"],
        "INITIAL_SHOCK": ["VOLATILITY_DISCOVERY"],
        "VOLATILITY_DISCOVERY": ["POST_NEWS_VALIDATION", "EXTENDED_PROTECTION"],
        "POST_NEWS_VALIDATION": ["RESTRICTED_REENTRY", "EXTENDED_PROTECTION"],
        "RESTRICTED_REENTRY": ["NORMAL_REENTRY", "EXTENDED_PROTECTION"],
        "NORMAL_REENTRY": ["NEWS_NORMAL"],
        "EXTENDED_PROTECTION": ["POST_NEWS_VALIDATION", "NEWS_NORMAL"],
    },
    "ExecutionState": {
        "EXEC_READY": ["EXEC_SUBMITTING", "EXEC_REJECTED"],
        "EXEC_SUBMITTING": ["EXEC_SUBMITTED", "EXEC_UNKNOWN", "EXEC_REJECTED"],
        "EXEC_SUBMITTED": ["EXEC_ACCEPTED", "EXEC_FILLED", "EXEC_REJECTED", "EXEC_UNKNOWN"],
        "EXEC_ACCEPTED": ["EXEC_PARTIAL", "EXEC_FILLED", "EXEC_CANCELLED", "EXEC_UNKNOWN"],
        "EXEC_PARTIAL": ["EXEC_FILLED", "EXEC_CANCELLED", "EXEC_UNKNOWN"],
        "EXEC_FILLED": [],
        "EXEC_REJECTED": [],
        "EXEC_CANCELLED": [],
        "EXEC_UNKNOWN": ["EXEC_RECONCILING"],
        "EXEC_RECONCILING": ["EXEC_ACCEPTED", "EXEC_FILLED", "EXEC_REJECTED", "EXEC_CANCELLED"],
    },
    "OpportunityState": {
        "OPP_DISCOVERED": ["OPP_VALIDATING", "OPP_INVALIDATED"],
        "OPP_VALIDATING": ["OPP_VALID", "OPP_INVALIDATED"],
        "OPP_VALID": ["OPP_TRIGGER_READY", "OPP_DEGRADED", "OPP_INVALIDATED", "OPP_EXPIRED"],
        "OPP_TRIGGER_READY": ["OPP_AUTHORIZED", "OPP_DEGRADED", "OPP_INVALIDATED", "OPP_EXPIRED"],
        "OPP_AUTHORIZED": ["OPP_EXECUTED", "OPP_EXPIRED", "OPP_INVALIDATED"],
        "OPP_EXECUTED": [],
        "OPP_DEGRADED": ["OPP_VALID", "OPP_INVALIDATED", "OPP_EXPIRED"],
        "OPP_INVALIDATED": [],
        "OPP_STALE": ["OPP_EXPIRED"],
        "OPP_EXPIRED": [],
    },
    "PositionLifecycleState": {
        "POS_OPENING": ["POS_ACTIVE", "POS_CLOSING"],
        "POS_ACTIVE": ["POS_PROTECTED", "POS_RUNNER", "POS_DECAYING", "POS_CLOSING"],
        "POS_PROTECTED": ["POS_RUNNER", "POS_DECAYING", "POS_CLOSING"],
        "POS_RUNNER": ["POS_DECAYING", "POS_CLOSING"],
        "POS_DECAYING": ["POS_EXPIRING", "POS_CLOSING"],
        "POS_EXPIRING": ["POS_CLOSING"],
        "POS_CLOSING": ["POS_CLOSED"],
        "POS_CLOSED": [],
    },
    "ReconciliationState": {
        "RECON_NORMAL": ["RECON_SUSPECTED_ORPHAN"],
        "RECON_SUSPECTED_ORPHAN": ["RECON_RECONCILING"],
        "RECON_RECONCILING": ["RECON_RECOVERED", "RECON_QUARANTINED"],
        "RECON_RECOVERED": ["RECON_NORMAL"],
        "RECON_QUARANTINED": ["RECON_NORMAL"],
    },
}


@dataclass
class StateEnvelope:
    state_id: str
    object_id: str
    object_type: str
    symbol: str
    timeframe: str
    root_id: str
    parent_id: str
    parent_version: int
    state: str
    previous_state: str
    version: int
    source_timestamp: int
    event_timestamp: int
    processing_timestamp: int
    valid_until: int
    last_seen: int
    sub_state: Optional[str] = None
    confidence: float = 1.0
    confidence_class: str = "HIGH"
    reason_codes: List[str] = field(default_factory=list)
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    created_at: int = 0
    updated_at: int = 0
    authority: str = "PDE"

    def transition_to(self, new_state: str, machine_type: Optional[str] = None) -> None:
        """Attempts state transition; fails closed if transition is illegal."""
        m_type = machine_type or f"{self.object_type}State"
        if m_type in TRANSITION_RULES:
            allowed = TRANSITION_RULES[m_type].get(self.state, [])
            if new_state not in allowed:
                raise InvalidStateTransitionException(
                    f"Illegal state transition for {m_type} from '{self.state}' to '{new_state}'. Allowed: {allowed}"
                )
        self.previous_state = self.state
        self.state = new_state
        self.version += 1

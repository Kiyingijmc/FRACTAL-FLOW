"""PGVF (Phase Governance & Verification Fabric) Governance Kernel."""

from tools.pfgv.authority import AuthorityDelta, AuthorityModel
from tools.pfgv.contract import PhaseContract
from tools.pfgv.errors import (
    AuthorityError,
    ContractError,
    ContradictionError,
    EvidenceError,
    GovernanceError,
    InvariantViolationError,
    ScopeViolationError,
    StateTransitionError,
)
from tools.pfgv.evidence import Contradiction, ContradictionAnalyzer, EvidenceRecord, VerificationLevel
from tools.pfgv.invariants import Invariant, InvariantRegistry
from tools.pfgv.scope import ScopePolicy
from tools.pfgv.state import FinalizationRecord, PhaseLifecycleState, PhaseStateMachine

__all__ = [
    "GovernanceError",
    "ContractError",
    "StateTransitionError",
    "ScopeViolationError",
    "AuthorityError",
    "EvidenceError",
    "ContradictionError",
    "InvariantViolationError",
    "PhaseContract",
    "PhaseLifecycleState",
    "PhaseStateMachine",
    "FinalizationRecord",
    "Invariant",
    "InvariantRegistry",
    "ScopePolicy",
    "AuthorityModel",
    "AuthorityDelta",
    "EvidenceRecord",
    "VerificationLevel",
    "Contradiction",
    "ContradictionAnalyzer",
]

"""PGVF Phase State Machine and Final-Head Freeze Model."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set

from tools.pfgv.errors import StateTransitionError


class PhaseLifecycleState(Enum):
    """Canonical 18 PGVF phase lifecycle states."""

    DRAFT = auto()
    CONTRACT_LOCKED = auto()
    BASELINE_VERIFIED = auto()
    AUTHORIZED_TO_IMPLEMENT = auto()
    IMPLEMENTING = auto()
    IMPLEMENTATION_SNAPSHOT = auto()
    LOCAL_VERIFICATION = auto()
    INDEPENDENT_VERIFICATION = auto()
    FINAL_HEAD_FROZEN = auto()
    EXACT_HEAD_CI_PENDING = auto()
    EXACT_HEAD_CI_VERIFIED = auto()
    FORENSIC_RECONCILIATION = auto()
    MERGE_AUTHORIZED = auto()
    MERGED = auto()
    POST_MERGE_VERIFICATION = auto()
    CLOSED = auto()
    BLOCKED = auto()
    REMEDIATION_REQUIRED = auto()


# Transition rules definition (Rule A-E)
ALLOWED_TRANSITIONS: Dict[PhaseLifecycleState, Set[PhaseLifecycleState]] = {
    PhaseLifecycleState.DRAFT: {
        PhaseLifecycleState.CONTRACT_LOCKED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.CONTRACT_LOCKED: {
        PhaseLifecycleState.BASELINE_VERIFIED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.BASELINE_VERIFIED: {
        PhaseLifecycleState.AUTHORIZED_TO_IMPLEMENT,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.AUTHORIZED_TO_IMPLEMENT: {
        PhaseLifecycleState.IMPLEMENTING,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.IMPLEMENTING: {
        PhaseLifecycleState.IMPLEMENTATION_SNAPSHOT,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.IMPLEMENTATION_SNAPSHOT: {
        PhaseLifecycleState.LOCAL_VERIFICATION,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.LOCAL_VERIFICATION: {
        PhaseLifecycleState.INDEPENDENT_VERIFICATION,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.INDEPENDENT_VERIFICATION: {
        PhaseLifecycleState.FINAL_HEAD_FROZEN,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.FINAL_HEAD_FROZEN: {
        PhaseLifecycleState.EXACT_HEAD_CI_PENDING,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.EXACT_HEAD_CI_PENDING: {
        PhaseLifecycleState.EXACT_HEAD_CI_VERIFIED,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.EXACT_HEAD_CI_VERIFIED: {
        PhaseLifecycleState.FORENSIC_RECONCILIATION,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.FORENSIC_RECONCILIATION: {
        PhaseLifecycleState.MERGE_AUTHORIZED,
        PhaseLifecycleState.REMEDIATION_REQUIRED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.MERGE_AUTHORIZED: {
        PhaseLifecycleState.MERGED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.MERGED: {
        PhaseLifecycleState.POST_MERGE_VERIFICATION,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.POST_MERGE_VERIFICATION: {
        PhaseLifecycleState.CLOSED,
        PhaseLifecycleState.BLOCKED,
    },
    PhaseLifecycleState.REMEDIATION_REQUIRED: {
        PhaseLifecycleState.IMPLEMENTING,
        PhaseLifecycleState.BLOCKED,
    },
    # Rule B: BLOCKED is terminal for current attempt
    PhaseLifecycleState.BLOCKED: set(),
    # Rule D: CLOSED is terminal
    PhaseLifecycleState.CLOSED: set(),
}


@dataclass(frozen=True)
class FinalizationRecord:
    """Data model representing frozen repository and contract state at finalization."""

    head_sha: str
    tree_sha: str
    contract_hash: str
    invariant_registry_hash: str
    scope_policy_hash: str
    authority_model_hash: str
    created_at: str
    verifier_version: str
    status: str

    def is_valid(
        self,
        current_head_sha: str,
        current_tree_sha: str,
        current_contract_hash: str,
        current_invariant_registry_hash: str,
        current_scope_policy_hash: str,
        current_authority_model_hash: str,
    ) -> bool:
        """Verifies whether repository state and governance artifacts still match finalization freeze."""
        return (
            self.head_sha == current_head_sha
            and self.tree_sha == current_tree_sha
            and self.contract_hash == current_contract_hash
            and self.invariant_registry_hash == current_invariant_registry_hash
            and self.scope_policy_hash == current_scope_policy_hash
            and self.authority_model_hash == current_authority_model_hash
        )


class PhaseStateMachine:
    """PGVF Phase State Machine enforcing lifecycle rules A-E."""

    def __init__(
        self,
        initial_state: PhaseLifecycleState = PhaseLifecycleState.DRAFT,
        finalization: Optional[FinalizationRecord] = None,
    ) -> None:
        self._current_state = initial_state
        self._history: List[PhaseLifecycleState] = [initial_state]
        self._finalization = finalization

    @property
    def current_state(self) -> PhaseLifecycleState:
        return self._current_state

    @property
    def history(self) -> List[PhaseLifecycleState]:
        return list(self._history)

    @property
    def finalization(self) -> Optional[FinalizationRecord]:
        return self._finalization

    def transition_to(
        self,
        target_state: PhaseLifecycleState,
        reason: Optional[str] = None,
        finalization: Optional[FinalizationRecord] = None,
    ) -> None:
        """Transitions the phase state machine to target_state or raises StateTransitionError."""
        # Rule D: CLOSED is terminal
        if self._current_state == PhaseLifecycleState.CLOSED:
            raise StateTransitionError("Phase is CLOSED; closed phases are strictly immutable")

        # Rule B: BLOCKED is terminal
        if self._current_state == PhaseLifecycleState.BLOCKED:
            raise StateTransitionError("Phase is BLOCKED; blocked phases cannot transition out")

        # Rule A: No arbitrary transitions
        allowed = ALLOWED_TRANSITIONS.get(self._current_state, set())
        if target_state not in allowed:
            raise StateTransitionError(f"Invalid state transition: {self._current_state.name} -> {target_state.name}")

        if target_state == PhaseLifecycleState.FINAL_HEAD_FROZEN:
            if finalization is None:
                raise StateTransitionError("FINAL_HEAD_FROZEN requires a valid FinalizationRecord")
            self._finalization = finalization

        self._current_state = target_state
        self._history.append(target_state)

    def check_finalization_invalidation(
        self,
        current_head_sha: str,
        current_tree_sha: str,
        current_contract_hash: str,
        current_invariant_registry_hash: str,
        current_scope_policy_hash: str,
        current_authority_model_hash: str,
    ) -> bool:
        """Rule E: Finalization Invalidation.

        If state is past FINAL_HEAD_FROZEN and state changes, invalidates finalization.
        """
        post_frozen_states = {
            PhaseLifecycleState.FINAL_HEAD_FROZEN,
            PhaseLifecycleState.EXACT_HEAD_CI_PENDING,
            PhaseLifecycleState.EXACT_HEAD_CI_VERIFIED,
            PhaseLifecycleState.FORENSIC_RECONCILIATION,
            PhaseLifecycleState.MERGE_AUTHORIZED,
        }

        if self._current_state in post_frozen_states:
            if self._finalization is None:
                self.transition_to(
                    PhaseLifecycleState.REMEDIATION_REQUIRED,
                    reason="Missing finalization record in post-frozen state",
                )
                return True

            if not self._finalization.is_valid(
                current_head_sha=current_head_sha,
                current_tree_sha=current_tree_sha,
                current_contract_hash=current_contract_hash,
                current_invariant_registry_hash=current_invariant_registry_hash,
                current_scope_policy_hash=current_scope_policy_hash,
                current_authority_model_hash=current_authority_model_hash,
            ):
                self.transition_to(
                    PhaseLifecycleState.REMEDIATION_REQUIRED,
                    reason="Finalization invalidated due to repository or contract mutation after freeze",
                )
                return True

        return False

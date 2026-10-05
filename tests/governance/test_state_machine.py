"""Tests for PGVF Phase State Machine and Finalization Freeze Model."""

import pytest

from tools.pfgv.errors import StateTransitionError
from tools.pfgv.state import FinalizationRecord, PhaseLifecycleState, PhaseStateMachine


def test_valid_lifecycle_transitions() -> None:
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.DRAFT)
    assert sm.current_state == PhaseLifecycleState.DRAFT

    sm.transition_to(PhaseLifecycleState.CONTRACT_LOCKED)
    sm.transition_to(PhaseLifecycleState.BASELINE_VERIFIED)
    sm.transition_to(PhaseLifecycleState.AUTHORIZED_TO_IMPLEMENT)
    sm.transition_to(PhaseLifecycleState.IMPLEMENTING)
    sm.transition_to(PhaseLifecycleState.IMPLEMENTATION_SNAPSHOT)
    sm.transition_to(PhaseLifecycleState.LOCAL_VERIFICATION)
    sm.transition_to(PhaseLifecycleState.INDEPENDENT_VERIFICATION)

    record = FinalizationRecord(
        head_sha="sha1",
        tree_sha="tree1",
        contract_hash="chash1",
        invariant_registry_hash="irhash1",
        scope_policy_hash="sphash1",
        authority_model_hash="amhash1",
        created_at="2025-10-04T00:00:00Z",
        verifier_version="1.0",
        status="FROZEN",
    )
    sm.transition_to(PhaseLifecycleState.FINAL_HEAD_FROZEN, finalization=record)
    assert sm.current_state == PhaseLifecycleState.FINAL_HEAD_FROZEN
    assert len(sm.history) == 9


def test_invalid_state_transition_fails() -> None:
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.DRAFT)
    # Skipping CONTRACT_LOCKED to IMPLEMENTING directly
    with pytest.raises(StateTransitionError, match="Invalid state transition: DRAFT -> IMPLEMENTING"):
        sm.transition_to(PhaseLifecycleState.IMPLEMENTING)


def test_rule_b_blocked_is_terminal() -> None:
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.IMPLEMENTING)
    sm.transition_to(PhaseLifecycleState.BLOCKED)
    assert sm.current_state == PhaseLifecycleState.BLOCKED

    with pytest.raises(StateTransitionError, match="Phase is BLOCKED; blocked phases cannot transition out"):
        sm.transition_to(PhaseLifecycleState.IMPLEMENTING)


def test_rule_c_remediation_required_loop() -> None:
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.IMPLEMENTING)
    sm.transition_to(PhaseLifecycleState.REMEDIATION_REQUIRED)
    assert sm.current_state == PhaseLifecycleState.REMEDIATION_REQUIRED

    sm.transition_to(PhaseLifecycleState.IMPLEMENTING)
    assert sm.current_state == PhaseLifecycleState.IMPLEMENTING


def test_rule_d_closed_is_terminal() -> None:
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.POST_MERGE_VERIFICATION)
    sm.transition_to(PhaseLifecycleState.CLOSED)
    assert sm.current_state == PhaseLifecycleState.CLOSED

    with pytest.raises(StateTransitionError, match="Phase is CLOSED; closed phases are strictly immutable"):
        sm.transition_to(PhaseLifecycleState.DRAFT)


def test_rule_e_finalization_invalidation_on_sha_mismatch() -> None:
    record = FinalizationRecord(
        head_sha="head123",
        tree_sha="tree123",
        contract_hash="chash123",
        invariant_registry_hash="irhash123",
        scope_policy_hash="sphash123",
        authority_model_hash="amhash123",
        created_at="2025-10-04T00:00:00Z",
        verifier_version="1.0",
        status="FROZEN",
    )
    sm = PhaseStateMachine(initial_state=PhaseLifecycleState.FINAL_HEAD_FROZEN, finalization=record)

    # Repository tree modified!
    invalidated = sm.check_finalization_invalidation(
        current_head_sha="head123",
        current_tree_sha="MODIFIED_TREE_SHA",  # Mismatch!
        current_contract_hash="chash123",
        current_invariant_registry_hash="irhash123",
        current_scope_policy_hash="sphash123",
        current_authority_model_hash="amhash123",
    )
    assert invalidated is True
    assert sm.current_state == PhaseLifecycleState.REMEDIATION_REQUIRED

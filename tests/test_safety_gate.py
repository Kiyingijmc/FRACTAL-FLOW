from src.fractal_flow.execution.safety_gate import SafetyGateState


def test_default_gate_is_fail_closed():
    state = SafetyGateState()
    assert state.reconciliation_required and state.protective_only
    assert not state.authenticated
    assert not state.may_dispatch_effectful_command
    assert not state.may_accept_new_exposure


def test_quarantine_disables_auth_and_keeps_reconciliation_required():
    state = SafetyGateState(authenticated=True).quarantine()
    assert not state.authenticated and state.quarantined
    assert state.reconciliation_required and state.protective_only
    assert not state.may_dispatch_effectful_command


def test_reconciliation_requirement_forces_protective_only():
    state = SafetyGateState(True, False, False, False).require_reconciliation()
    assert state.authenticated and state.reconciliation_required
    assert state.protective_only and not state.may_accept_new_exposure


def test_unsafe_inconsistent_state_normalizes_closed():
    state = SafetyGateState(False, True, False, False)
    assert state.protective_only
    assert not state.may_dispatch_effectful_command

from src.fractal_flow.execution.protective_authority import ProtectivePolicy, ProtectiveRecord, ProtectiveState


def policy(deadman=True, ttl=100):
    return ProtectivePolicy("C1", "A", "P1", "1.0", "1.2", ttl, deadman)


def test_strategy_cannot_resume_without_confirmed_protection():
    r = ProtectiveRecord(policy(), ProtectiveState.REQUIRED)
    assert not r.strategy_may_resume
    assert r.mark_confirmed(10).strategy_may_resume


def test_deadman_converts_lost_protection_to_flatten_requirement():
    r = ProtectiveRecord(policy(), ProtectiveState.LOST)
    assert r.evaluate(50).state is ProtectiveState.FLATTEN_REQUIRED


def test_ttl_expiry_is_terminal_for_policy_evaluation():
    r = ProtectiveRecord(policy(ttl=100), ProtectiveState.ARMED, 50)
    assert r.evaluate(100).state is ProtectiveState.EXPIRED

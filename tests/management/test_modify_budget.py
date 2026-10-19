from concurrent.futures import ThreadPoolExecutor

import pytest

from fractal_flow.management.modify_budget import (
    ModifyBudgetError,
    ModifyBudgetPolicy,
    ReservationStatus,
    SQLiteModifyBudget,
)


def test_reservation_is_persisted_across_store_restart(tmp_path):
    db = tmp_path / "budget.sqlite3"
    policy = ModifyBudgetPolicy(max_attempts=2, window_ms=1_000)
    first = SQLiteModifyBudget(db, policy)
    assert first.reserve("broker|acct|lane|pos|EURUSD", "cmd-1", 10_000).status is ReservationStatus.RESERVED
    restarted = SQLiteModifyBudget(db, policy)
    assert restarted.reserve("broker|acct|lane|pos|EURUSD", "cmd-2", 10_100).status is ReservationStatus.RESERVED
    assert restarted.reserve("broker|acct|lane|pos|EURUSD", "cmd-3", 10_200).status is ReservationStatus.RATE_LIMITED


def test_duplicate_action_id_is_denied_not_authorized_for_resend(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(3, 1_000))
    assert budget.reserve("scope", "same-command", 1_000).allowed
    result = budget.reserve("scope", "same-command", 1_001)
    assert result.status is ReservationStatus.DUPLICATE_ACTION
    assert not result.allowed


def test_window_boundary_expires_old_reservation(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(1, 1_000))
    assert budget.reserve("scope", "a", 1_000).allowed
    assert budget.reserve("scope", "b", 2_000).allowed


def test_minimum_interval_enforced(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(10, 10_000, 250))
    assert budget.reserve("scope", "a", 1_000).allowed
    denied = budget.reserve("scope", "b", 1_249)
    assert denied.status is ReservationStatus.RATE_LIMITED
    assert denied.next_eligible_at_ms == 1_250
    assert budget.reserve("scope", "c", 1_250).allowed


def test_clock_rollback_fails_closed_even_after_restart(tmp_path):
    db = tmp_path / "budget.sqlite3"
    policy = ModifyBudgetPolicy(10, 1_000)
    assert SQLiteModifyBudget(db, policy).reserve("scope", "a", 5_000).allowed
    result = SQLiteModifyBudget(db, policy).reserve("scope", "b", 4_999)
    assert result.status is ReservationStatus.CLOCK_ROLLBACK
    assert not result.allowed


def test_scope_isolation_prevents_cross_lane_budget_leak(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(1, 1_000))
    assert budget.reserve("broker|acct|lane-A|pos", "a", 1_000).allowed
    assert budget.reserve("broker|acct|lane-B|pos", "b", 1_001).allowed


def test_concurrent_reservations_cannot_exceed_budget(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(3, 10_000))
    def reserve(i):
        return budget.reserve("scope", f"cmd-{i}", 1_000).status
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(reserve, range(12)))
    assert results.count(ReservationStatus.RESERVED) == 3
    assert results.count(ReservationStatus.RATE_LIMITED) == 9


@pytest.mark.parametrize("policy", [
    ModifyBudgetPolicy(1, 1),
])
def test_policy_valid(policy):
    assert policy.max_attempts == 1


def test_memory_database_rejected_as_not_durable():
    with pytest.raises(ModifyBudgetError):
        SQLiteModifyBudget(":memory:", ModifyBudgetPolicy(1, 1_000))


@pytest.mark.parametrize("now", [-1, True, 1.5])
def test_invalid_clock_rejected(tmp_path, now):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(2, 1_000))
    with pytest.raises(ModifyBudgetError):
        budget.reserve("scope", "cmd", now)


def test_blank_identity_rejected(tmp_path):
    budget = SQLiteModifyBudget(tmp_path / "budget.sqlite3", ModifyBudgetPolicy(2, 1_000))
    with pytest.raises(ModifyBudgetError):
        budget.reserve(" ", "cmd", 1_000)

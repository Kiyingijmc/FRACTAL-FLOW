from decimal import Decimal

import pytest

from src.fractal_flow.management.position_policy import (
    ManagementAction,
    ManagementFacts,
    ManagementPolicyError,
    evaluate_management,
)


def facts(**overrides):
    values = dict(
        position_id="P-1",
        side="LONG",
        lifecycle_state="POS_PROTECTED",
        health_state="HEALTH_HEALTHY",
        ttl_state="TTL_ACTIVE",
        reconciliation_status="RECON_NORMAL",
        current_price=Decimal("1.1100"),
        current_stop=Decimal("1.1000"),
        candidate_stop=Decimal("1.1050"),
        min_stop_distance=Decimal("0.0010"),
    )
    values.update(overrides)
    return ManagementFacts(**values)


def test_valid_long_ratchet_is_advice_only():
    result = evaluate_management(facts())
    assert result.action is ManagementAction.TIGHTEN_STOP
    assert result.stop_candidate == Decimal("1.1050")
    assert result.reduce_only is True


def test_short_ratchet_moves_stop_down_and_keeps_market_distance():
    result = evaluate_management(facts(
        side="SHORT", current_price=Decimal("1.0900"),
        current_stop=Decimal("1.1000"), candidate_stop=Decimal("1.0950"),
    ))
    assert result.action is ManagementAction.TIGHTEN_STOP
    assert result.stop_candidate == Decimal("1.0950")


@pytest.mark.parametrize("candidate", ["1.0990", "1.1090", "1.1091"])
def test_long_loosen_or_market_crossing_candidate_is_rejected(candidate):
    result = evaluate_management(facts(candidate_stop=Decimal(candidate)))
    assert result.action is ManagementAction.HOLD
    assert result.stop_candidate is None


def test_structural_invalidation_precedes_ttl_rescue_and_ratchet():
    result = evaluate_management(facts(
        structural_invalidated=True, ttl_state="TTL_EXPIRED",
        ttl_rescue_viable=True,
    ))
    assert result.action is ManagementAction.CLOSE
    assert result.reason == "HARD_STRUCTURAL_INVALIDATION"


def test_expired_ttl_does_not_close_without_rescue_assessment():
    result = evaluate_management(facts(ttl_state="TTL_EXPIRED", ttl_rescue_viable=None))
    assert result.action is ManagementAction.HOLD
    assert "RESCUE_ASSESSMENT" in result.reason


def test_expired_ttl_closes_only_after_explicit_failed_rescue_assessment():
    result = evaluate_management(facts(
        ttl_state="TTL_EXPIRED", ttl_rescue_viable=False, candidate_stop=None,
    ))
    assert result.action is ManagementAction.CLOSE
    assert result.reason == "TTL_EXPIRED_RESCUE_NOT_VIABLE"


def test_unreconciled_position_never_receives_close_or_reduce_advice():
    result = evaluate_management(facts(
        reconciliation_status="EXEC_UNKNOWN", structural_invalidated=True,
        health_state="HEALTH_CRITICAL", reduction_evidence=True,
    ))
    assert result.action is ManagementAction.HOLD
    assert result.reduce_only is True


def test_orphan_allows_only_safe_protective_ratchet():
    result = evaluate_management(facts(
        reconciliation_status="RECON_SUSPECTED_ORPHAN", is_orphan=True,
    ))
    assert result.action is ManagementAction.TIGHTEN_STOP
    assert result.reason == "ORPHAN_PROTECTIVE_RATCHET_ONLY"


def test_orphan_cannot_be_closed_even_if_structurally_invalidated():
    result = evaluate_management(facts(
        reconciliation_status="RECON_SUSPECTED_ORPHAN", is_orphan=True,
        structural_invalidated=True, candidate_stop=None,
    ))
    assert result.action is ManagementAction.HOLD


def test_reduction_requires_deterioration_and_explicit_evidence():
    result = evaluate_management(facts(
        health_state="HEALTH_DAMAGED", reduction_evidence=True, candidate_stop=None,
    ))
    assert result.action is ManagementAction.REDUCE
    assert result.reduce_only is True


def test_unknown_ttl_state_fails_closed():
    with pytest.raises(ManagementPolicyError, match="unsupported TTL state"):
        facts(ttl_state="STALE")


def test_non_finite_decimal_rejected():
    with pytest.raises(ManagementPolicyError, match="finite"):
        facts(current_price=Decimal("NaN"))


@pytest.mark.parametrize("lifecycle", ["POS_OPENING", "POS_CLOSING", "POS_CLOSED"])
def test_in_flight_or_terminal_lifecycle_never_receives_new_action(lifecycle):
    result = evaluate_management(facts(
        lifecycle_state=lifecycle, structural_invalidated=True,
        ttl_state="TTL_EXPIRED", ttl_rescue_viable=False,
    ))
    assert result.action is ManagementAction.HOLD
    assert result.reason == "POSITION_LIFECYCLE_NOT_MANAGEABLE"

"""Executable Invariant Enforcement Tests verifying genuine architectural enforcement for non-negotiable invariants."""

import pytest

from src.fractal_flow.domain.authority import (
    AuthorityMatrix,
    AuthorityViolationException,
)
from src.fractal_flow.domain.models import Direction, TradeDecision


def test_invariant_4_flow_cannot_open_position() -> None:
    """Invariant #4: Flow cannot open a position."""
    with pytest.raises(AuthorityViolationException) as exc:
        AuthorityMatrix.verify_capability("Flow", "CREATE_EXECUTION_INTENT")
    assert "Authority Violation" in str(exc.value)


def test_invariant_7_execution_cannot_reinterpret_strategy() -> None:
    # covers: [7]
    """Invariant #7: Execution cannot reinterpret strategy."""
    with pytest.raises(AuthorityViolationException) as exc:
        AuthorityMatrix.verify_capability("Execution", "REINTERPRET_STRATEGY")
    assert "Authority Violation" in str(exc.value)


def test_invariant_8_news_shield_cannot_manufacture_trades() -> None:
    """Invariant #8: News Shield cannot manufacture trades."""
    with pytest.raises(AuthorityViolationException) as exc:
        AuthorityMatrix.verify_capability("NewsShield", "CREATE_EXECUTION_INTENT")
    assert "Authority Violation" in str(exc.value)


def test_invariant_9_confidence_cannot_override_validity() -> None:
    # covers: [9]
    """Invariant #9: Confidence score cannot turn an invalid object into a valid decision."""
    decision = TradeDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        direction=Direction.LONG,
        symbol="EURUSD",
        environment="REGIME_TREND_UP",
        role="ROLE_CONTINUATION",
        setup="FF-01",
        pullback_id="pb_1",
        resumption_state="RESUMPTION_CONFIRMED",
        location="LOC_FAVORABLE",
        opportunity_space=0.8,
        tradeability="TRADEABILITY_FAIL_SPREAD",  # Invalid tradeability
        news_state="NEWS_NORMAL",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=1.0850,
        structural_sl=1.0820,
        tp_plan={},
        ttl_ns=300000000000,
        requested_risk=100.0,
        approved_risk=100.0,
        position_size_lots=0.1,
        arbitration_result="ALLOW",
        effective_config_id="cfg_123",
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=3.5,
        authorized=True,  # Attempted manual authorization override
    )
    # Tradeability fail MUST prevent authorization even if authorized=True flag was set
    assert decision.is_authorized() is False


def test_invariant_10_mandatory_validity_gates_unbypassable() -> None:
    # covers: [10]
    """Invariant #10: Mandatory validity gates cannot be bypassed by portfolio deferral."""
    decision = TradeDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        direction=Direction.LONG,
        symbol="EURUSD",
        environment="REGIME_TREND_UP",
        role="ROLE_CONTINUATION",
        setup="FF-01",
        pullback_id="pb_1",
        resumption_state="RESUMPTION_CONFIRMED",
        location="LOC_FAVORABLE",
        opportunity_space=0.8,
        tradeability="TRADEABILITY_PASS",
        news_state="NEWS_NORMAL",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_REJECT",  # Rejected by Portfolio
        entry_price=1.0850,
        structural_sl=1.0820,
        tp_plan={},
        ttl_ns=300000000000,
        requested_risk=100.0,
        approved_risk=0.0,
        position_size_lots=0.0,
        arbitration_result="REJECT",
        effective_config_id="cfg_123",
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        authorized=True,
    )
    assert decision.is_authorized() is False

"""Tests for Entry Domain Foundation and EntryPolicyEngine."""

import pytest
from src.fractal_flow.domain.entry import (
    EntryModel,
    OrderType,
    FillPolicy,
    TimeInForce,
    EntryTrigger,
    EntryTriggerType,
    EntryPlan,
    EntryPolicyEngine,
)
from src.fractal_flow.domain.models import Direction, OrderSide
from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException


def test_entry_policy_engine_model_selection() -> None:
    engine = EntryPolicyEngine()
    constraints = {"supported_order_types": ["MARKET_BUY", "BUY_LIMIT", "BUY_STOP"]}

    # Scalping mode prefers MARKET_CONFIRMATION
    model = engine.evaluate_entry_policy("SCALPING", Direction.LONG, 1.0850, 1.0820, constraints)
    assert model == EntryModel.MARKET_CONFIRMATION

    # Smart Scalping mode prefers PULLBACK_LIMIT
    model_ss = engine.evaluate_entry_policy("SMART_SCALPING", Direction.LONG, 1.0850, 1.0820, constraints)
    assert model_ss == EntryModel.PULLBACK_LIMIT


def test_entry_policy_engine_no_entry_when_unsupported() -> None:
    engine = EntryPolicyEngine()
    # Broker only supports MARKET orders, but FLIPPING prefers RECLAIM_LIMIT and BREAKOUT_STOP
    constraints = {"supported_order_types": ["MARKET_SELL"]}
    model = engine.evaluate_entry_policy("FLIPPING", Direction.LONG, 1.0850, 1.0820, constraints, fallback_allowed=False)
    assert model == EntryModel.NO_ENTRY


def test_entry_policy_authority_boundary() -> None:
    # EntryPolicy can read opportunities and create entry plans
    AuthorityMatrix.verify_capability("EntryPolicy", "READ_OPPORTUNITY")
    AuthorityMatrix.verify_capability("EntryPolicy", "CREATE_ENTRY_PLAN")

    # EntryPolicy cannot submit orders
    with pytest.raises(AuthorityViolationException) as exc:
        AuthorityMatrix.verify_capability("EntryPolicy", "SUBMIT_ORDER")
    assert "Authority Violation" in str(exc.value)

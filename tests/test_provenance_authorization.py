"""Tests for Decision Provenance and News Lockdown Authorization Boundary."""

from decimal import Decimal

from src.fractal_flow.domain.models import (
    Direction,
    ExecutionIntent,
    OrderSide,
    TradeDecision,
)


def test_news_lockdown_blocks_trade_decision_authorization() -> None:
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
        news_state="NEWS_LOCKDOWN",  # Hard lockdown boundary active
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=Decimal("1.0850"),
        structural_sl=Decimal("1.0820"),
        tp_plan={"tp1": 1.0900},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.0"),
        approved_risk=Decimal("100.0"),
        position_size_lots=Decimal("0.1"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_test123",
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,  # Attempted manual authorization during lockdown
    )
    # NEWS_LOCKDOWN must override manual authorized=True flag
    assert decision.is_authorized() is False


def test_provenance_snapshots_preserved() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=Decimal("0.1"),
        entry_price=Decimal("1.0850"),
        sl=Decimal("1.0820"),
        tp_plan={"tp1": 1.0900},
        effective_config_id="cfg_test123",
        lineage_version=1,
        broker_constraint_snapshot={"stops_level": 5.0},
        quote_timestamp=1000,
        spread_pips=Decimal("1.2"),
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )
    assert intent.effective_config_id == "cfg_test123"
    assert intent.broker_constraint_snapshot["stops_level"] == 5.0

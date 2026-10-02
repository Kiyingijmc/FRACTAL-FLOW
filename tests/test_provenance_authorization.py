"""Tests for Decision Provenance and News Lockdown Authorization Boundary."""

from src.fractal_flow.domain.models import ExecutionIntent, TradeDecision


def test_news_lockdown_blocks_trade_decision_authorization() -> None:
    from decimal import Decimal
    from src.fractal_flow.domain.lineage import Lineage
    from src.fractal_flow.domain.murg import (
        GLOBAL_MURG_ISSUER,
        InstrumentDescriptor,
        InstrumentIdentity,
        AssetClass,
        SymbolTradeMode,
        MarketActivationDecision,
        MarketSessionContext,
    )
    from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger, LedgerOperation

    decision = TradeDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        direction="BUY",
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
        tp_plan={"tp1": Decimal("1.0900")},
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

    lineage = Lineage(
        root_id="root_1", parent_id="opp_1", parent_version=1, parent_tier="OPPORTUNITY", current_tier="SIGNAL"
    )
    desc = InstrumentDescriptor(
        identity=InstrumentIdentity("EURUSD", AssetClass.FX_MAJOR, "EUR", "USD", "BROKER", "EURUSD"),
        trade_mode=SymbolTradeMode.FULL,
        execution_mode="MARKET",
        supported_order_types=["MARKET_BUY"],
        supported_fill_policies=["IOC"],
        supported_time_in_force=["GTC"],
        tick_size=0.00001,
        point_size=0.00001,
        pip_size=0.0001,
        tick_value=1.0,
        contract_size=100000.0,
        digits=5,
        min_volume=0.01,
        max_volume=100.0,
        volume_step=0.01,
        stops_level=5.0,
        freeze_level=2.0,
    )
    sess = MarketSessionContext("OPEN", 1000, 10000, True)
    act_dec = MarketActivationDecision("EURUSD", "ACTIVE", [], 90.0, True, True, True)
    murg_ctx = GLOBAL_MURG_ISSUER.issue_context(act_dec, desc, sess, current_time_ns=1000)

    ledger = OpportunityRiskLedger("budget_1", "opp_1", Decimal("500.0"), Decimal("2.0"))
    ledger.record_operation(
        "res_entry_1", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_1", "cause_1", 1000
    )

    from src.fractal_flow.domain.lineage import GLOBAL_PARENT_RESOLVER

    parent_obj = type(
        "Parent", (), {"id": "opp_1", "root_id": "root_1", "tier": "OPPORTUNITY", "version": 1, "validity": True}
    )()
    GLOBAL_PARENT_RESOLVER.register_parent("opp_1", 1, parent_obj)
    seal = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_1", 1)

    # NEWS_LOCKDOWN must override manual authorized=True flag even when all mandatory context is provided
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent_seal=seal,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_1",
            current_time_ns=1000,
        )
        is False
    )


def test_provenance_snapshots_preserved() -> None:
    intent = ExecutionIntent(
        intent_id="intent_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side="BUY",
        requested_volume=0.1,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={"tp1": 1.0900},
        effective_config_id="cfg_test123",
        lineage_version=1,
        broker_constraint_snapshot={"stops_level": 5.0},
        quote_timestamp=1000,
        spread_pips=1.2,
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )
    assert intent.effective_config_id == "cfg_test123"
    assert intent.broker_constraint_snapshot["stops_level"] == 5.0

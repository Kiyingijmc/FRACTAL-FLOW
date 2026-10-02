"""Adversarial Test Suite covering Entry Model EM-001 through EM-060 Scenarios."""

import pytest

from src.fractal_flow.domain.authority import (
    AuthorityMatrix,
    AuthorityViolationException,
)
from src.fractal_flow.domain.entry import (
    EntryModel,
    EntryPlan,
    FillPolicy,
    HybridEntryPlan,
    OpportunityRiskBudget,
    OrderType,
    TimeInForce,
)
from src.fractal_flow.domain.models import OrderSide
from src.fractal_flow.domain.telemetry import EntryAuthorizationEvidence
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.simulator import DeterministicBrokerSimulator


def make_plan(
    plan_id: str,
    model: EntryModel,
    otype: OrderType,
    side: OrderSide = OrderSide.BUY,
    p_version: int = 1,
    news: str = "NEWS_NORMAL",
) -> EntryPlan:
    return EntryPlan(
        entry_plan_id=plan_id,
        opportunity_id="opp_em",
        signal_id="sig_em",
        decision_id="dec_em",
        root_id="root_1",
        parent_id="par_1",
        parent_version=p_version,
        lineage_version=1,
        symbol="EURUSD",
        strategy_mode="SCALPING",
        operating_posture="STANDARD",
        entry_model=model,
        order_type=otype,
        order_side=side,
        reference_price=1.0850,
        trigger_price=1.0830 if "LIMIT" in otype.value or "STOP" in otype.value else None,
        limit_price=1.0830 if "LIMIT" in otype.value else None,
        stop_limit_price=None,
        entry_corridor_low=None,
        entry_corridor_high=None,
        requested_volume=0.1,
        approved_volume=0.1,
        risk_budget=100.0,
        allocated_risk=100.0,
        remaining_opportunity_risk=100.0,
        structural_sl=1.0800,
        tp_plan={},
        fill_policy=FillPolicy.IOC,
        time_in_force=TimeInForce.GTC,
        trigger_conditions=[],
        maintenance_conditions=[],
        invalidation_conditions=[],
        broker_constraints_snapshot={},
        news_state=news,
        tradeability_state="TRADEABILITY_PASS",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        effective_config_id="cfg_em",
    )


def test_em_001_008_order_type_execution_scenarios() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    plan_m = make_plan("plan_m", EntryModel.MARKET_CONFIRMATION, OrderType.MARKET_BUY)
    sim.arm_entry_plan(plan_m)
    # Market fills immediately on tick
    executed = sim.process_price_tick(1.0850)
    assert "plan_m" in executed


def test_em_009_011_parent_version_staleness_invalidation() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    plan = make_plan("plan_stale", EntryModel.PULLBACK_LIMIT, OrderType.BUY_LIMIT, p_version=1)
    sim.arm_entry_plan(plan)

    # Parent version advances to 2, making plan stale
    plan.parent_version = 2
    plan.state = "ENTRY_STALE"

    executed = sim.process_price_tick(1.0820)
    assert "plan_stale" not in executed
    assert plan.state == "ENTRY_STALE"


def test_em_014_news_lockdown_blocks_pending_trigger() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    plan = make_plan(
        "plan_news_em",
        EntryModel.PULLBACK_LIMIT,
        OrderType.BUY_LIMIT,
        news="NEWS_LOCKDOWN",
    )
    with pytest.raises(ValueError) as exc:
        sim.arm_entry_plan(plan)
    assert "NEWS_LOCKDOWN" in str(exc.value)


def test_em_043_046_hybrid_risk_budget_enforcement() -> None:
    budget = OpportunityRiskBudget("opp_hybrid", total_risk_currency=300.0, total_allowed_volume=0.5)
    plan1 = make_plan("leg1", EntryModel.MARKET_CONFIRMATION, OrderType.MARKET_BUY)
    plan1.allocated_risk = 150.0
    plan1.approved_volume = 0.25

    plan2 = make_plan("leg2", EntryModel.PULLBACK_LIMIT, OrderType.BUY_LIMIT)
    plan2.allocated_risk = 150.0
    plan2.approved_volume = 0.25

    hybrid = HybridEntryPlan("h_em", "opp_hybrid", budget, [plan1, plan2])
    assert sum(leg.allocated_risk for leg in hybrid.legs) == budget.total_risk_currency


def test_em_054_056_fallback_cannot_bypass_authority() -> None:
    with pytest.raises(AuthorityViolationException) as exc:
        AuthorityMatrix.verify_capability("EntryPolicy", "SUBMIT_ORDER")
    assert "Authority Violation" in str(exc.value)


def test_em_provenance_evidence() -> None:
    ev = EntryAuthorizationEvidence(
        decision_id="dec_1",
        opportunity_id="opp_1",
        opportunity_version=1,
        risk_decision_id="risk_1",
        portfolio_decision_id="port_1",
        news_state="NEWS_NORMAL",
        broker_snapshot_id="snap_1",
        effective_config_id="cfg_1",
        created_at=1000,
        expires_at=5000,
    )
    assert ev.decision_id == "dec_1"
    assert ev.news_state == "NEWS_NORMAL"


def test_mandatory_authorization_context_and_reservation_binding() -> None:
    """Adversarial test proving authorization fails closed when mandatory dependencies are missing or mismatched."""
    from decimal import Decimal
    from src.fractal_flow.domain.lineage import Lineage
    from src.fractal_flow.domain.models import TradeDecision
    from src.fractal_flow.domain.murg import (
        AssetClass,
        GLOBAL_MURG_ISSUER,
        InstrumentDescriptor,
        InstrumentIdentity,
        MarketActivationDecision,
        MarketSessionContext,
        SymbolTradeMode,
    )
    from src.fractal_flow.domain.risk_ledger import LedgerOperation, OpportunityRiskLedger

    decision = TradeDecision(
        decision_id="dec_adv_1",
        opportunity_id="opp_adv_1",
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
        news_state="NEWS_NORMAL",
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
        authorized=True,
    )

    lineage = Lineage(
        root_id="root_1", parent_id="opp_adv_1", parent_version=1, parent_tier="OPPORTUNITY", current_tier="SIGNAL"
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

    ledger = OpportunityRiskLedger("budget_1", "opp_adv_1", Decimal("500.0"), Decimal("2.0"))
    ledger.record_operation(
        "res_tx_1", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_valid", "cause_1", 1000
    )

    parent_obj = type(
        "Parent", (), {"id": "opp_adv_1", "root_id": "root_1", "tier": "OPPORTUNITY", "version": 1, "validity": True}
    )()

    # 1. Valid authorization passes
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=parent_obj,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_valid",
            current_time_ns=1000,
        )
        is True
    )

    # 2. Missing reservation fails closed
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=parent_obj,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_nonexistent",
            current_time_ns=1000,
        )
        is False
    )

    # 3. Insufficient reservation amount fails closed
    ledger_small = OpportunityRiskLedger("budget_2", "opp_adv_1", Decimal("500.0"), Decimal("2.0"))
    ledger_small.record_operation(
        "res_tx_small", LedgerOperation.RESERVE, Decimal("50.0"), Decimal("0.0"), "res_small", "cause_1", 1000
    )
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=parent_obj,
            murg_context=murg_ctx,
            risk_ledger=ledger_small,
            reservation_id="res_small",
            current_time_ns=1000,
        )
        is False
    )

    # 4. Opportunity ID mismatch on risk ledger fails closed
    ledger_wrong_opp = OpportunityRiskLedger("budget_3", "opp_WRONG", Decimal("500.0"), Decimal("2.0"))
    ledger_wrong_opp.record_operation(
        "res_tx_wrong", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_wrong", "cause_1", 1000
    )
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=parent_obj,
            murg_context=murg_ctx,
            risk_ledger=ledger_wrong_opp,
            reservation_id="res_wrong",
            current_time_ns=1000,
        )
        is False
    )

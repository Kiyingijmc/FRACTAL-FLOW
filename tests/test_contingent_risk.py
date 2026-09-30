"""Tests for Pass 4C Contingent Risk, Hybrid Entries, and Opportunity Budget Allocation."""

from decimal import Decimal

from src.fractal_flow.domain.entry import (
    ContingentExposure,
    EntryModel,
    EntryPlan,
    FillPolicy,
    HybridEntryPlan,
    OpportunityRiskBudget,
    OrderType,
    TimeInForce,
)
from src.fractal_flow.domain.models import OrderSide


def test_opportunity_risk_budget_remaining_calculations() -> None:
    budget = OpportunityRiskBudget(
        opportunity_id="opp_risk",
        total_risk_currency=Decimal("500.0"),
        total_allowed_volume=Decimal("1.0"),
        allocated_risk=Decimal("200.0"),
        allocated_volume=Decimal("0.4"),
    )
    assert budget.remaining_risk == Decimal("300.0")
    assert budget.remaining_volume == Decimal("0.6")


def test_contingent_exposure_worst_case_calculation() -> None:
    exp = ContingentExposure(
        symbol="EURUSD",
        current_open_volume=Decimal("0.5"),
        contingent_pending_volume=Decimal("0.3"),
    )
    assert exp.worst_case_contingent_volume == Decimal("0.8")


def test_hybrid_entry_shared_risk_budget() -> None:
    budget = OpportunityRiskBudget(
        opportunity_id="opp_hybrid",
        total_risk_currency=Decimal("1000.0"),
        total_allowed_volume=Decimal("2.0"),
    )

    leg1 = EntryPlan(
        entry_plan_id="leg_1",
        opportunity_id="opp_hybrid",
        signal_id="sig_1",
        decision_id="dec_1",
        root_id="root_1",
        parent_id="par_1",
        parent_version=1,
        lineage_version=1,
        symbol="EURUSD",
        strategy_mode="SCALPING",
        operating_posture="STANDARD",
        entry_model=EntryModel.MARKET_CONFIRMATION,
        order_type=OrderType.MARKET_BUY,
        order_side=OrderSide.BUY,
        reference_price=Decimal("1.0850"),
        trigger_price=None,
        limit_price=None,
        stop_limit_price=None,
        entry_corridor_low=None,
        entry_corridor_high=None,
        requested_volume=Decimal("0.8"),
        approved_volume=Decimal("0.8"),
        risk_budget=Decimal("400.0"),
        allocated_risk=Decimal("400.0"),
        remaining_opportunity_risk=Decimal("600.0"),
        structural_sl=Decimal("1.0820"),
        tp_plan={},
        fill_policy=FillPolicy.IOC,
        time_in_force=TimeInForce.GTC,
        trigger_conditions=[],
        maintenance_conditions=[],
        invalidation_conditions=[],
        broker_constraints_snapshot={},
        news_state="NEWS_NORMAL",
        tradeability_state="TRADEABILITY_PASS",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        effective_config_id="cfg_h",
    )

    leg2 = EntryPlan(
        entry_plan_id="leg_2",
        opportunity_id="opp_hybrid",
        signal_id="sig_2",
        decision_id="dec_2",
        root_id="root_1",
        parent_id="par_1",
        parent_version=1,
        lineage_version=1,
        symbol="EURUSD",
        strategy_mode="SCALPING",
        operating_posture="STANDARD",
        entry_model=EntryModel.RETEST_LIMIT,
        order_type=OrderType.BUY_LIMIT,
        order_side=OrderSide.BUY,
        reference_price=Decimal("1.0850"),
        trigger_price=Decimal("1.0830"),
        limit_price=Decimal("1.0830"),
        stop_limit_price=None,
        entry_corridor_low=None,
        entry_corridor_high=None,
        requested_volume=Decimal("1.2"),
        approved_volume=Decimal("1.2"),
        risk_budget=Decimal("600.0"),
        allocated_risk=Decimal("600.0"),
        remaining_opportunity_risk=Decimal("0.0"),
        structural_sl=Decimal("1.0800"),
        tp_plan={},
        fill_policy=FillPolicy.IOC,
        time_in_force=TimeInForce.GTC,
        trigger_conditions=[],
        maintenance_conditions=[],
        invalidation_conditions=[],
        broker_constraints_snapshot={},
        news_state="NEWS_NORMAL",
        tradeability_state="TRADEABILITY_PASS",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        effective_config_id="cfg_h",
    )

    hybrid = HybridEntryPlan(
        hybrid_id="h_1",
        opportunity_id="opp_hybrid",
        risk_budget=budget,
        legs=[leg1, leg2],
    )
    total_allocated_risk = sum(leg.allocated_risk for leg in hybrid.legs)
    total_allocated_vol = sum(leg.approved_volume for leg in hybrid.legs)

    assert total_allocated_risk <= hybrid.risk_budget.total_risk_currency
    assert total_allocated_vol <= hybrid.risk_budget.total_allowed_volume

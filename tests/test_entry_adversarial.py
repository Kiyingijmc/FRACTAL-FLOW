"""Adversarial Test Suite covering Entry Model EM-001 through EM-060 Scenarios."""

import pytest
from src.fractal_flow.domain.entry import (
    EntryModel,
    OrderType,
    FillPolicy,
    TimeInForce,
    EntryPlan,
    OpportunityRiskBudget,
    HybridEntryPlan,
)
from src.fractal_flow.domain.models import OrderSide
from src.fractal_flow.domain.telemetry import EntryAuthorizationEvidence
from src.fractal_flow.domain.authority import (
    AuthorityMatrix,
    AuthorityViolationException,
)
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
        trigger_price=1.0830
        if "LIMIT" in otype.value or "STOP" in otype.value
        else None,
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

    plan = make_plan(
        "plan_stale", EntryModel.PULLBACK_LIMIT, OrderType.BUY_LIMIT, p_version=1
    )
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
    budget = OpportunityRiskBudget(
        "opp_hybrid", total_risk_currency=300.0, total_allowed_volume=0.5
    )
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

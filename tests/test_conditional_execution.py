"""Tests for Pass 4B Conditional Execution and Simulator Lifecycle."""

import pytest
from src.fractal_flow.domain.entry import EntryPlan, EntryModel, OrderType, FillPolicy, TimeInForce
from src.fractal_flow.domain.models import OrderSide
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.simulator import DeterministicBrokerSimulator


def make_sample_plan(entry_plan_id: str, order_type: OrderType, trigger_p: float, limit_p: float, news_state: str = "NEWS_NORMAL") -> EntryPlan:
    return EntryPlan(
        entry_plan_id=entry_plan_id,
        opportunity_id="opp_4b",
        signal_id="sig_4b",
        decision_id="dec_4b",
        root_id="root_1",
        parent_id="par_1",
        parent_version=1,
        lineage_version=1,
        symbol="EURUSD",
        strategy_mode="SCALPING",
        operating_posture="STANDARD",
        entry_model=EntryModel.PULLBACK_LIMIT,
        order_type=order_type,
        order_side=OrderSide.BUY,
        reference_price=1.0850,
        trigger_price=trigger_p,
        limit_price=limit_p,
        stop_limit_price=None,
        entry_corridor_low=1.0820,
        entry_corridor_high=1.0850,
        requested_volume=0.1,
        approved_volume=0.1,
        risk_budget=100.0,
        allocated_risk=100.0,
        remaining_opportunity_risk=100.0,
        structural_sl=1.0800,
        tp_plan={"tp1": 1.0900},
        fill_policy=FillPolicy.IOC,
        time_in_force=TimeInForce.GTC,
        trigger_conditions=[],
        maintenance_conditions=[],
        invalidation_conditions=[],
        broker_constraints_snapshot={"min_volume": 0.01},
        news_state=news_state,
        tradeability_state="TRADEABILITY_PASS",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        effective_config_id="cfg_4b",
    )


def test_conditional_limit_order_execution() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    # Buy Limit @ 1.0830
    plan = make_sample_plan("plan_lim", OrderType.BUY_LIMIT, trigger_p=1.0830, limit_p=1.0830)
    sim.arm_entry_plan(plan)
    assert plan.state == "ENTRY_ARMED"

    # Tick @ 1.0840 (not reached)
    executed = sim.process_price_tick(1.0840)
    assert len(executed) == 0

    # Tick @ 1.0825 (Limit touched/crossed)
    executed = sim.process_price_tick(1.0825)
    assert len(executed) == 1
    assert "plan_lim" in executed
    assert plan.state == "ENTRY_FILLED"
    assert len(sim.positions) == 1
    assert list(sim.positions.values())[0].symbol == "EURUSD"


def test_conditional_stop_limit_order_progression() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    # Buy Stop Limit: Trigger @ 1.0860, Limit @ 1.0855
    plan = make_sample_plan("plan_slim", OrderType.BUY_STOP_LIMIT, trigger_p=1.0860, limit_p=1.0855)
    sim.arm_entry_plan(plan)

    # Tick @ 1.0850 -> armed
    sim.process_price_tick(1.0850)
    assert plan.state == "ENTRY_ARMED"

    # Tick @ 1.0865 -> stop triggered
    sim.process_price_tick(1.0865)
    assert plan.state == "STOP_TRIGGERED"

    # Tick @ 1.0850 -> limit activated and filled
    executed = sim.process_price_tick(1.0850)
    assert "plan_slim" in executed
    assert plan.state == "ENTRY_FILLED"


def test_news_lockdown_invalidates_armed_pending_plan() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)

    plan = make_sample_plan("plan_news", OrderType.BUY_LIMIT, trigger_p=1.0830, limit_p=1.0830)
    sim.arm_entry_plan(plan)

    # Mutate plan news_state to NEWS_LOCKDOWN
    plan.news_state = "NEWS_LOCKDOWN"
    sim.process_price_tick(1.0820)

    assert plan.state == "ENTRY_INVALIDATED"
    assert len(sim.positions) == 0

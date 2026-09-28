"""Adversarial Regression Test Suite testing critical security, lineage, execution, and state-machine boundaries."""

import pytest
from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException
from src.fractal_flow.domain.envelope import StateEnvelope, InvalidStateTransitionException, StateRegistry
from src.fractal_flow.domain.models import TradeDecision, ExecutionIntent, OrderSide, Direction
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.simulator import DeterministicBrokerSimulator, SimulationConfig, ExecutionScenario, IdempotencyConflictException


def test_adversarial_stale_and_future_lineage_child() -> None:
    # Authoritative parent version is 3
    stale_child = Lineage("root_1", "par_1", parent_version=2, parent_tier="OPPORTUNITY", current_tier="SIGNAL")
    with pytest.raises(LineageInvalidException) as exc1:
        stale_child.validate_child_action(authoritative_parent_version=3)
    assert "Parent version mismatch" in str(exc1.value)

    future_child = Lineage("root_1", "par_1", parent_version=4, parent_tier="OPPORTUNITY", current_tier="SIGNAL")
    with pytest.raises(LineageInvalidException) as exc2:
        future_child.validate_child_action(authoritative_parent_version=3)
    assert "Parent version mismatch" in str(exc2.value)


def test_adversarial_unknown_state_machine_and_states() -> None:
    reg = StateRegistry()
    with pytest.raises(InvalidStateTransitionException) as exc1:
        reg.validate_transition("UNKNOWN_MACHINE", "STATE_A", "STATE_B")
    assert "Unknown state machine" in str(exc1.value)

    with pytest.raises(InvalidStateTransitionException) as exc2:
        reg.validate_transition("PDEState", "UNKNOWN_STATE", "PDE_IMPULSE")
    assert "Unknown current state" in str(exc2.value)


def test_adversarial_unknown_execution_no_duplicate_exposure() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(
        clock=clock, config=SimulationConfig(scenario=ExecutionScenario.UNKNOWN_AFTER_FILL)
    )
    intent = ExecutionIntent(
        intent_id="intent_adv1",
        decision_id="dec_adv1",
        opportunity_id="opp_adv1",
        root_id="root_1",
        idempotency_key="key_adv1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )

    # Submission results in UNKNOWN due to lost response after fill
    status = sim.submit_intent(intent)
    assert status == ExecutionState.EXEC_UNKNOWN

    # Retry submission with same idempotency key
    retry_status = sim.submit_intent(intent)
    assert retry_status == ExecutionState.EXEC_UNKNOWN

    # Query authoritative broker reconciliation
    recon_status = sim.reconcile_intent("intent_adv1")
    assert recon_status == ExecutionState.EXEC_FILLED

    # Assert exactly 1 position created and total volume is 1.0 lot
    assert len(sim.broker_positions) == 1
    pos = list(sim.broker_positions.values())[0]
    assert pos.filled_volume == 1.0


def test_adversarial_news_lockdown_cannot_be_bypassed() -> None:
    decision = TradeDecision(
        decision_id="dec_adv_news",
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
        opportunity_space=0.9,
        tradeability="TRADEABILITY_PASS",
        news_state="NEWS_LOCKDOWN",  # Hard lockdown
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=1.0850,
        structural_sl=1.0820,
        tp_plan={},
        ttl_ns=300000000000,
        requested_risk=500.0,
        approved_risk=500.0,
        position_size_lots=0.5,
        arbitration_result="ALLOW",
        effective_config_id="cfg_123",
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        authorized=True,  # Attempted bypass
    )
    assert decision.is_authorized() is False

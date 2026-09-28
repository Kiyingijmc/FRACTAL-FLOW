"""Integration Tests for DeterministicBrokerSimulator."""

import pytest
from src.fractal_flow.domain.models import ExecutionIntent, OrderSide
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.simulation.simulator import DeterministicBrokerSimulator, SimulationConfig, ExecutionScenario


def test_broker_simulator_successful_fill() -> None:
    sim = DeterministicBrokerSimulator()
    intent = ExecutionIntent(
        intent_id="intent_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=0.1,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={"tp1": 1.0900},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )
    status = sim.submit_intent(intent)
    assert status == ExecutionState.EXEC_FILLED
    assert len(sim.positions) == 1
    pos = list(sim.positions.values())[0]
    assert pos.symbol == "EURUSD"
    assert pos.current_sl == 1.0820


def test_broker_simulator_network_disconnect_and_reconciliation() -> None:
    sim = DeterministicBrokerSimulator(config=SimulationConfig(scenario=ExecutionScenario.UNKNOWN_BEFORE_RECEIPT))
    intent = ExecutionIntent(
        intent_id="intent_2",
        decision_id="dec_2",
        opportunity_id="opp_2",
        root_id="root_1",
        idempotency_key="key_2",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=0.1,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )
    status = sim.submit_intent(intent)
    assert status == ExecutionState.EXEC_UNKNOWN

    # Reconcile unknown status
    recon_status = sim.reconcile_intent("intent_2")
    assert recon_status == ExecutionState.EXEC_REJECTED  # No position created during disconnect


def test_broker_simulator_stop_loss_tighten_ratchet() -> None:
    sim = DeterministicBrokerSimulator()
    intent = ExecutionIntent(
        intent_id="intent_3",
        decision_id="dec_3",
        opportunity_id="opp_3",
        root_id="root_1",
        idempotency_key="key_3",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=0.1,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )
    sim.submit_intent(intent)
    pos_id = list(sim.positions.keys())[0]

    # Valid stop tightening for Long (move SL higher)
    assert sim.modify_stop_loss(pos_id, 1.0830) is True

    # Invalid stop loosening for Long (attempt to move SL lower) raises ValueError
    with pytest.raises(ValueError) as exc_info:
        sim.modify_stop_loss(pos_id, 1.0810)
    assert "Cannot loosen stop loss" in str(exc_info.value)

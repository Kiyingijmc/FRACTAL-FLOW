"""Tests for Hardened Simulator, Idempotency, Unknown Execution, Partial Fills, and Restart Recovery."""

from decimal import Decimal

import pytest

from src.fractal_flow.domain.models import ExecutionIntent, OrderSide
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.simulator import (
    DeterministicBrokerSimulator,
    ExecutionScenario,
    IdempotencyConflictException,
    SimulationConfig,
)


def make_intent(
    intent_id: str, idempotency_key: str, volume: float = 0.1, price: float = 1.0850
) -> ExecutionIntent:
    return ExecutionIntent(
        intent_id=intent_id,
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key=idempotency_key,
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=Decimal(str(volume)),
        entry_price=Decimal(str(price)),
        sl=Decimal("1.0820"),
        tp_plan={"tp1": Decimal("1.0900")},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={"min_volume": Decimal("0.01")},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        status="EXEC_READY",
        created_at=100,
        updated_at=100,
    )


def test_idempotency_same_payload_returns_existing_state() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)
    intent1 = make_intent("intent_1", "key_1")
    status1 = sim.submit_intent(intent1)
    assert status1 == ExecutionState.EXEC_FILLED

    # Resubmit identical intent with same idempotency key
    intent2 = make_intent("intent_1", "key_1")
    status2 = sim.submit_intent(intent2)
    assert status2 == ExecutionState.EXEC_FILLED
    assert len(sim.positions) == 1  # No duplicate execution created!


def test_idempotency_conflict_raises_exception() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(clock=clock)
    intent1 = make_intent("intent_1", "key_1", volume=0.1)
    sim.submit_intent(intent1)

    # Resubmit with materially different volume on same key
    intent_conflict = make_intent("intent_2", "key_1", volume=0.5)
    with pytest.raises(IdempotencyConflictException) as exc:
        sim.submit_intent(intent_conflict)
    assert "Idempotency Conflict" in str(exc.value)


def test_partial_fill_semantics() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(
        clock=clock,
        config=SimulationConfig(
            scenario=ExecutionScenario.PARTIAL_FILL, partial_fill_ratio=Decimal("0.3")
        ),
    )
    intent = make_intent("intent_pf", "key_pf", volume=1.0)
    status = sim.submit_intent(intent)
    assert status == ExecutionState.EXEC_PARTIAL

    pos = list(sim.positions.values())[0]
    assert pos.requested_volume == Decimal("1.0")
    assert pos.filled_volume == Decimal("0.30")
    assert pos.remaining_volume == Decimal("0.70")
    assert len(pos.deals) == 1


def test_restart_recovery_reconciliation() -> None:
    clock = SimulationClock(1000)
    sim = DeterministicBrokerSimulator(
        clock=clock,
        config=SimulationConfig(scenario=ExecutionScenario.UNKNOWN_BEFORE_RECEIPT),
    )
    intent = make_intent("intent_restart", "key_restart")
    status = sim.submit_intent(intent)
    assert status == ExecutionState.EXEC_UNKNOWN

    # System restarts and reconciles unknown intent
    recon_status = sim.reconcile_intent("intent_restart")
    assert recon_status == ExecutionState.EXEC_REJECTED

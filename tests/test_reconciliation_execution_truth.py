from decimal import Decimal

import src.fractal_flow.execution.reconciliation as reconciliation
from src.fractal_flow.domain.models import (
    BrokerOrder,
    ExecutionIntent,
    OrderSide,
    Position,
)
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.execution.reconciliation import (
    BrokerQueryQuality,
    BrokerQueryResult,
    ReconciliationEngine,
)


def make_intent(status="EXEC_SUBMITTED"):
    return ExecutionIntent(
        intent_id="intent-1",
        decision_id="decision-1",
        opportunity_id="opportunity-1",
        root_id="root-1",
        idempotency_key="idem-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=Decimal("1.0"),
        entry_price=Decimal("1.10000"),
        sl=Decimal("1.09000"),
        tp_plan={},
        effective_config_id="config-1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=100,
        spread_pips=Decimal("1"),
        status=status,
        created_at=100,
        updated_at=100,
    )


def test_broker_rejected_order_is_not_reported_filled():
    intent = make_intent()
    order = BrokerOrder(
        order_id="order-1",
        intent_id=intent.intent_id,
        symbol=intent.symbol,
        side="BUY",
        volume=Decimal("1.0"),
        price=Decimal("1.10000"),
        status="REJECTED",
    )

    result = ReconciliationEngine.reconcile_intent(
        intent, {"order-1": order}, {}
    )

    assert result.resolved_execution_state is ExecutionState.EXEC_REJECTED


def test_fully_filled_entry_remains_filled_after_partial_position_close():
    intent = make_intent(status="EXEC_FILLED")
    position = Position(
        position_id="position-1",
        intent_id=intent.intent_id,
        order_id="order-1",
        symbol=intent.symbol,
        side="BUY",
        requested_volume=Decimal("1.0"),
        filled_volume=Decimal("1.0"),
        remaining_volume=Decimal("0.4"),
        entry_price=Decimal("1.10000"),
        current_sl=Decimal("1.09000"),
        lifecycle_state="OPEN",
        health_state="HEALTHY",
        opened_at=100,
    )

    result = ReconciliationEngine.reconcile_intent(
        intent, {}, {"position-1": position}
    )

    assert result.resolved_execution_state is ExecutionState.EXEC_FILLED


def test_incomplete_authoritative_absence_preserves_unknown():
    intent = make_intent()
    query_result = BrokerQueryResult(
        status="SUCCESS",
        authority=BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE,
        query_timestamp=100,
        completeness=False,
        broker_orders={},
        broker_positions={},
        broker_deals={},
        session_id="session-1",
        observation_digest="test-digest",
        _issuance_key=reconciliation._BROKER_ISSUANCE_KEY,
    )

    result = ReconciliationEngine.reconcile_intent(
        intent, {}, {}, query_result=query_result
    )

    assert result.resolved_execution_state is ExecutionState.EXEC_UNKNOWN

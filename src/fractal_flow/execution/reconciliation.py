"""Authoritative Reconciliation Engine comparing local intents against broker truth."""

from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, List, Optional, Any

from src.fractal_flow.domain.models import ExecutionIntent, Position, BrokerOrder
from src.fractal_flow.execution.execution_state import ExecutionState


@unique
class ReconciliationMismatchType(str, Enum):
    MATCH = "MATCH"
    LOCAL_ONLY = "LOCAL_ONLY"
    BROKER_ONLY = "BROKER_ONLY"
    STATE_MISMATCH = "STATE_MISMATCH"
    VOLUME_MISMATCH = "VOLUME_MISMATCH"
    ORPHANED_BROKER = "ORPHANED_BROKER"


@dataclass(frozen=True)
class ReconciliationResult:
    intent_id: str
    mismatch_type: ReconciliationMismatchType
    resolved_execution_state: ExecutionState
    details: Dict[str, Any]


class ReconciliationEngine:
    """Authoritative reconciliation engine comparing local execution intent state against broker-side order/position truth."""

    @staticmethod
    def reconcile_intent(
        local_intent: ExecutionIntent,
        broker_orders: Dict[str, BrokerOrder],
        broker_positions: Dict[str, Position],
    ) -> ReconciliationResult:
        # Search broker positions directly
        matching_pos = None
        for pos in broker_positions.values():
            if pos.intent_id == local_intent.intent_id:
                matching_pos = pos
                break

        # Search broker orders directly
        matching_order = None
        for ord_obj in broker_orders.values():
            if ord_obj.intent_id == local_intent.intent_id:
                matching_order = ord_obj
                break

        if matching_pos:
            resolved_state = ExecutionState.EXEC_PARTIAL if matching_pos.remaining_volume > 0 else ExecutionState.EXEC_FILLED
            mismatch = ReconciliationMismatchType.MATCH if local_intent.status == resolved_state.value else ReconciliationMismatchType.STATE_MISMATCH
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={"position_id": matching_pos.position_id, "filled_volume": matching_pos.filled_volume},
            )

        if matching_order:
            resolved_state = ExecutionState.EXEC_ACCEPTED if matching_order.status == "ACCEPTED" else ExecutionState.EXEC_FILLED
            mismatch = ReconciliationMismatchType.MATCH if local_intent.status == resolved_state.value else ReconciliationMismatchType.STATE_MISMATCH
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=mismatch,
                resolved_execution_state=resolved_state,
                details={"order_id": matching_order.order_id, "order_status": matching_order.status},
            )

        # Broker has no record of order or position
        return ReconciliationResult(
            intent_id=local_intent.intent_id,
            mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
            resolved_execution_state=ExecutionState.EXEC_REJECTED,
            details={"note": "Broker has no matching order or position record. Resolves to EXEC_REJECTED."},
        )

"""Authoritative Reconciliation Engine comparing local intents against broker truth, preserving UNKNOWN semantics when evidence is non-authoritative."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any

from src.fractal_flow.domain.models import ExecutionIntent, Position, BrokerOrder, BrokerDeal
from src.fractal_flow.execution.execution_state import ExecutionState


@unique
class ReconciliationMismatchType(str, Enum):
    MATCH = "MATCH"
    LOCAL_ONLY = "LOCAL_ONLY"
    BROKER_ONLY = "BROKER_ONLY"
    STATE_MISMATCH = "STATE_MISMATCH"
    VOLUME_MISMATCH = "VOLUME_MISMATCH"
    DEAL_CONTRADICTION = "DEAL_CONTRADICTION"
    ORPHANED_BROKER = "ORPHANED_BROKER"
    UNKNOWN_UNRESOLVED = "UNKNOWN_UNRESOLVED"


@unique
class BrokerQueryQuality(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND_AUTHORITATIVE = "NOT_FOUND_AUTHORITATIVE"
    NOT_FOUND_NON_AUTHORITATIVE = "NOT_FOUND_NON_AUTHORITATIVE"
    QUERY_FAILED = "QUERY_FAILED"


@dataclass(frozen=True)
class ReconciliationResult:
    intent_id: str
    mismatch_type: ReconciliationMismatchType
    resolved_execution_state: ExecutionState
    details: Dict[str, Any]


class ReconciliationEngine:
    """Authoritative reconciliation engine comparing local execution intent state against broker-side order/position/deal truth."""

    @staticmethod
    def reconcile_intent(
        local_intent: ExecutionIntent,
        broker_orders: Dict[str, BrokerOrder],
        broker_positions: Dict[str, Position],
        broker_deals: Optional[Dict[str, BrokerDeal]] = None,
        query_quality: BrokerQueryQuality = BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE,
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

        # Validate Deal Chain if matching position/order and deals provided
        if broker_deals and (matching_pos or matching_order):
            target_order_id = matching_order.order_id if matching_order else (matching_pos.order_id if matching_pos else "")
            target_pos_id = matching_pos.position_id if matching_pos else ""

            related_deals = [
                d for d in broker_deals.values()
                if (target_order_id and d.order_id == target_order_id) or (target_pos_id and d.position_id == target_pos_id)
            ]

            if matching_pos:
                deal_sum_vol = sum(d.volume for d in related_deals)
                if abs(deal_sum_vol - matching_pos.filled_volume) > 0.0001:
                    return ReconciliationResult(
                        intent_id=local_intent.intent_id,
                        mismatch_type=ReconciliationMismatchType.DEAL_CONTRADICTION,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={
                            "note": f"Deal volume sum ({deal_sum_vol}) contradicts position filled volume ({matching_pos.filled_volume})",
                            "position_id": matching_pos.position_id,
                        },
                    )

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
        if query_quality == BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE:
            return ReconciliationResult(
                intent_id=local_intent.intent_id,
                mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
                resolved_execution_state=ExecutionState.EXEC_REJECTED,
                details={"note": "Broker authoritatively confirmed order non-existence / rejection."},
            )

        # Fail-closed: UNKNOWN != REJECTED without authoritative evidence!
        return ReconciliationResult(
            intent_id=local_intent.intent_id,
            mismatch_type=ReconciliationMismatchType.LOCAL_ONLY,
            resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
            details={"note": "Broker record absent but query is non-authoritative. Preserving EXEC_UNKNOWN."},
        )

    @classmethod
    def reconcile_broker_wide(
        cls,
        local_intents: Dict[str, ExecutionIntent],
        broker_orders: Dict[str, BrokerOrder],
        broker_positions: Dict[str, Position],
        broker_deals: Optional[Dict[str, BrokerDeal]] = None,
        authoritative_rejections: Optional[set] = None,
    ) -> List[ReconciliationResult]:
        """Performs full broker-wide multi-directional reconciliation discovering local-only, matched, and orphaned broker objects."""
        results = []
        auth_rejections = authoritative_rejections or set()

        for intent in local_intents.values():
            query_q = (
                BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE
                if intent.intent_id in auth_rejections
                else BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE
            )
            res = cls.reconcile_intent(
                local_intent=intent,
                broker_orders=broker_orders,
                broker_positions=broker_positions,
                broker_deals=broker_deals,
                query_quality=query_q,
            )
            results.append(res)

        for pos in broker_positions.values():
            if pos.intent_id not in local_intents:
                results.append(
                    ReconciliationResult(
                        intent_id=pos.intent_id or f"ORPHAN_POS_{pos.position_id}",
                        mismatch_type=ReconciliationMismatchType.ORPHANED_BROKER,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={"position_id": pos.position_id, "symbol": pos.symbol, "volume": pos.filled_volume},
                    )
                )

        for ord_obj in broker_orders.values():
            if ord_obj.intent_id not in local_intents and not any(p.order_id == ord_obj.order_id for p in broker_positions.values()):
                results.append(
                    ReconciliationResult(
                        intent_id=ord_obj.intent_id or f"ORPHAN_ORD_{ord_obj.order_id}",
                        mismatch_type=ReconciliationMismatchType.ORPHANED_BROKER,
                        resolved_execution_state=ExecutionState.EXEC_UNKNOWN,
                        details={"order_id": ord_obj.order_id, "symbol": ord_obj.symbol, "volume": ord_obj.volume},
                    )
                )

        return results

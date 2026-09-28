"""Deterministic Broker Simulator for Integration Testing without Live MT5 Connection."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time

from src.fractal_flow.domain.models import ExecutionIntent, BrokerOrder, BrokerDeal, Position
from src.fractal_flow.execution.execution_state import ExecutionState


@dataclass
class SimulationConfig:
    auto_accept: bool = True
    auto_fill: bool = True
    delay_ms: int = 0
    reject_probability: float = 0.0
    simulate_network_disconnect: bool = False
    simulate_partial_fill: bool = False
    partial_fill_ratio: float = 0.5


class DeterministicBrokerSimulator:
    """Simulates broker execution behavior deterministically for integration testing."""

    def __init__(self, config: Optional[SimulationConfig] = None) -> None:
        self.config = config or SimulationConfig()
        self.orders: Dict[str, BrokerOrder] = {}
        self.deals: Dict[str, BrokerDeal] = {}
        self.positions: Dict[str, Position] = {}
        self.intent_statuses: Dict[str, ExecutionState] = {}
        self._order_counter = 1000
        self._deal_counter = 5000
        self._pos_counter = 9000

    def submit_intent(self, intent: ExecutionIntent) -> ExecutionState:
        """Processes execution intent submission deterministically."""
        # Save intent status as SUBMITTING
        self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_SUBMITTING

        if self.config.simulate_network_disconnect:
            self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_UNKNOWN
            return ExecutionState.EXEC_UNKNOWN

        if self.config.reject_probability >= 1.0:
            self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_REJECTED
            return ExecutionState.EXEC_REJECTED

        self._order_counter += 1
        order_id = f"ORD_{self._order_counter}"

        if self.config.simulate_partial_fill:
            fill_vol = round(intent.requested_volume * self.config.partial_fill_ratio, 2)
            order = BrokerOrder(
                order_id=order_id,
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=intent.side,
                volume=fill_vol,
                price=intent.entry_price,
                status="PARTIAL",
            )
            self.orders[order_id] = order
            self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_PARTIAL
            return ExecutionState.EXEC_PARTIAL

        if self.config.auto_fill:
            order = BrokerOrder(
                order_id=order_id,
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=intent.side,
                volume=intent.requested_volume,
                price=intent.entry_price,
                status="FILLED",
            )
            self.orders[order_id] = order

            self._deal_counter += 1
            self._pos_counter += 1
            deal_id = f"DEAL_{self._deal_counter}"
            pos_id = f"POS_{self._pos_counter}"

            deal = BrokerDeal(
                deal_id=deal_id,
                order_id=order_id,
                position_id=pos_id,
                symbol=intent.symbol,
                side=intent.side,
                volume=intent.requested_volume,
                price=intent.entry_price,
                commission=1.5,
            )
            self.deals[deal_id] = deal

            pos = Position(
                position_id=pos_id,
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=intent.side,
                volume=intent.requested_volume,
                entry_price=intent.entry_price,
                current_sl=intent.sl,
                lifecycle_state="POS_ACTIVE",
                health_state="HEALTH_HEALTHY",
                opened_at=int(time.time() * 1e9),
            )
            self.positions[pos_id] = pos
            self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_FILLED
            return ExecutionState.EXEC_FILLED

        self.intent_statuses[intent.intent_id] = ExecutionState.EXEC_ACCEPTED
        return ExecutionState.EXEC_ACCEPTED

    def modify_stop_loss(self, position_id: str, new_sl: float) -> bool:
        """Modifies position stop loss."""
        pos = self.positions.get(position_id)
        if not pos:
            return False
        # Tighten stop validation: Long SL can only increase, Short SL can only decrease
        if pos.side == "BUY" and new_sl < pos.current_sl:
            raise ValueError(
                f"Cannot loosen stop loss for Long position {position_id}: {pos.current_sl} -> {new_sl}"
            )
        if pos.side == "SELL" and new_sl > pos.current_sl:
            raise ValueError(
                f"Cannot loosen stop loss for Short position {position_id}: {pos.current_sl} -> {new_sl}"
            )
        pos.current_sl = new_sl
        return True

    def close_position(self, position_id: str) -> bool:
        """Closes an active position."""
        pos = self.positions.get(position_id)
        if not pos:
            return False
        pos.lifecycle_state = "POS_CLOSED"
        return True

    def reconcile_intent(self, intent_id: str) -> ExecutionState:
        """Reconciles intent status after simulated network disconnect."""
        status = self.intent_statuses.get(intent_id, ExecutionState.EXEC_UNKNOWN)
        if status == ExecutionState.EXEC_UNKNOWN:
            # Reconcile by checking matching order/position
            for pos in self.positions.values():
                if pos.intent_id == intent_id:
                    self.intent_statuses[intent_id] = ExecutionState.EXEC_FILLED
                    return ExecutionState.EXEC_FILLED
            self.intent_statuses[intent_id] = ExecutionState.EXEC_REJECTED
            return ExecutionState.EXEC_REJECTED
        return status

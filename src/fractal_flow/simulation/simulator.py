"""Hardened Deterministic Broker Simulator modeling realistic execution scenarios, conditional execution, and authoritative broker state."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, overload
from decimal import Decimal
from enum import Enum, unique

from src.fractal_flow.domain.models import (
    ExecutionIntent,
    BrokerOrder,
    BrokerDeal,
    Position,
)
from src.fractal_flow.domain.entry import EntryPlan, OrderType
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.simulation.clock import SimulationClock


@overload
def _to_decimal(val: None) -> None: ...


@overload
def _to_decimal(val: Union[Decimal, float, int, str]) -> Decimal: ...


def _to_decimal(val: Union[Decimal, float, int, str, None]) -> Optional[Decimal]:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


class IdempotencyConflictException(Exception):
    """Raised when an intent with an existing idempotency_key has materially different parameters."""

    pass


@unique
class ExecutionScenario(str, Enum):
    NORMAL = "NORMAL"
    REJECT = "REJECT"
    UNKNOWN_BEFORE_RECEIPT = "UNKNOWN_BEFORE_RECEIPT"
    UNKNOWN_AFTER_ACCEPT = "UNKNOWN_AFTER_ACCEPT"
    UNKNOWN_AFTER_FILL = "UNKNOWN_AFTER_FILL"
    UNKNOWN_AFTER_PARTIAL_FILL = "UNKNOWN_AFTER_PARTIAL_FILL"
    PARTIAL_FILL = "PARTIAL_FILL"


@dataclass
class SimulationConfig:
    scenario: ExecutionScenario = ExecutionScenario.NORMAL
    partial_fill_ratio: Decimal = field(default_factory=lambda: Decimal("0.5"))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "partial_fill_ratio", _to_decimal(self.partial_fill_ratio)
        )


class DeterministicBrokerSimulator:
    """Simulates broker execution behavior deterministically for Market, Limit, Stop, and Stop-Limit conditional orders."""

    def __init__(
        self,
        clock: Optional[SimulationClock] = None,
        config: Optional[SimulationConfig] = None,
    ) -> None:
        self.clock = clock or SimulationClock()
        self.config = config or SimulationConfig()

        # Authoritative Broker-Side State
        self.broker_orders: Dict[str, BrokerOrder] = {}
        self.broker_deals: Dict[str, BrokerDeal] = {}
        self.broker_positions: Dict[str, Position] = {}
        self.broker_intent_statuses: Dict[str, ExecutionState] = {}
        self.pending_entry_plans: Dict[str, EntryPlan] = {}

        # Client-Observed State & Idempotency Store
        self.client_intent_statuses: Dict[str, ExecutionState] = {}
        self.idempotency_records: Dict[str, ExecutionIntent] = {}

        self._order_counter = 1000
        self._deal_counter = 5000
        self._pos_counter = 9000

    @property
    def orders(self) -> Dict[str, BrokerOrder]:
        return self.broker_orders

    @property
    def deals(self) -> Dict[str, BrokerDeal]:
        return self.broker_deals

    @property
    def positions(self) -> Dict[str, Position]:
        return self.broker_positions

    @property
    def intent_statuses(self) -> Dict[str, ExecutionState]:
        return self.client_intent_statuses

    def _side_str(self, side_obj: Any) -> str:
        return side_obj.value if hasattr(side_obj, "value") else str(side_obj)

    def arm_entry_plan(self, plan: EntryPlan) -> str:
        """Arms a conditional pending entry plan for continuous evaluation."""
        if plan.news_state == "NEWS_LOCKDOWN":
            plan.state = "ENTRY_INVALIDATED"
            raise ValueError("Cannot arm entry plan during NEWS_LOCKDOWN")
        plan.state = "ENTRY_ARMED"
        self.pending_entry_plans[plan.entry_plan_id] = plan
        return plan.state

    def process_price_tick(self, current_price: Union[Decimal, float]) -> List[str]:
        """Evaluates armed conditional entry plans against incoming market price tick."""
        curr_price_dec = _to_decimal(current_price)
        executed_plans = []
        for plan_id, plan in list(self.pending_entry_plans.items()):
            if plan.state not in ("ENTRY_ARMED", "STOP_TRIGGERED", "LIMIT_ACTIVATED"):
                continue

            # Continuous Conditional Validation Checks
            if plan.news_state == "NEWS_LOCKDOWN":
                plan.state = "ENTRY_INVALIDATED"
                continue

            if plan.expires_at > 0 and self.clock.now_ns() >= plan.expires_at:
                plan.state = "ENTRY_EXPIRED"
                continue

            # Evaluate conditional triggers based on OrderType
            triggered = False

            limit_price_dec = _to_decimal(plan.limit_price)
            trigger_price_dec = _to_decimal(plan.trigger_price)

            if plan.order_type in (OrderType.MARKET_BUY, OrderType.MARKET_SELL):
                triggered = True

            elif plan.order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT):
                if limit_price_dec is not None:
                    if (
                        plan.order_type == OrderType.BUY_LIMIT
                        and curr_price_dec <= limit_price_dec
                    ):
                        triggered = True
                    elif (
                        plan.order_type == OrderType.SELL_LIMIT
                        and curr_price_dec >= limit_price_dec
                    ):
                        triggered = True

            elif plan.order_type in (OrderType.BUY_STOP, OrderType.SELL_STOP):
                if trigger_price_dec is not None:
                    if (
                        plan.order_type == OrderType.BUY_STOP
                        and curr_price_dec >= trigger_price_dec
                    ):
                        triggered = True
                    elif (
                        plan.order_type == OrderType.SELL_STOP
                        and curr_price_dec <= trigger_price_dec
                    ):
                        triggered = True

            elif plan.order_type in (
                OrderType.BUY_STOP_LIMIT,
                OrderType.SELL_STOP_LIMIT,
            ):
                if plan.state == "ENTRY_ARMED" and trigger_price_dec is not None:
                    # Check stop trigger
                    if (
                        plan.order_type == OrderType.BUY_STOP_LIMIT
                        and curr_price_dec >= trigger_price_dec
                    ) or (
                        plan.order_type == OrderType.SELL_STOP_LIMIT
                        and curr_price_dec <= trigger_price_dec
                    ):
                        plan.state = "STOP_TRIGGERED"
                if (
                    plan.state in ("STOP_TRIGGERED", "LIMIT_ACTIVATED")
                    and limit_price_dec is not None
                ):
                    # Check limit fill activation
                    if (
                        plan.order_type == OrderType.BUY_STOP_LIMIT
                        and curr_price_dec <= limit_price_dec
                    ) or (
                        plan.order_type == OrderType.SELL_STOP_LIMIT
                        and curr_price_dec >= limit_price_dec
                    ):
                        plan.state = "LIMIT_ACTIVATED"
                        triggered = True

            if triggered:
                # Convert EntryPlan into ExecutionIntent and submit
                intent = ExecutionIntent(
                    intent_id=f"intent_plan_{plan.entry_plan_id}",
                    decision_id=plan.decision_id,
                    opportunity_id=plan.opportunity_id,
                    root_id=plan.root_id,
                    idempotency_key=f"key_plan_{plan.entry_plan_id}",
                    symbol=plan.symbol,  # Use actual symbol from plan!
                    side=plan.order_side,
                    requested_volume=_to_decimal(plan.approved_volume),
                    entry_price=curr_price_dec,
                    sl=_to_decimal(plan.structural_sl),
                    tp_plan=plan.tp_plan,
                    effective_config_id=plan.effective_config_id,
                    lineage_version=plan.lineage_version,
                    broker_constraint_snapshot=plan.broker_constraints_snapshot,
                    quote_timestamp=self.clock.now_ns(),
                    spread_pips=Decimal("1.0"),
                    status="EXEC_READY",
                    created_at=self.clock.now_ns(),
                    updated_at=self.clock.now_ns(),
                    entry_plan_id=plan.entry_plan_id,
                    entry_model=plan.entry_model.value,
                    order_type=plan.order_type.value,
                    fill_policy=plan.fill_policy.value,
                    time_in_force=plan.time_in_force.value,
                    trigger_price=trigger_price_dec,
                    limit_price=limit_price_dec,
                    stop_limit_price=_to_decimal(plan.stop_limit_price),
                )
                exec_state = self.submit_intent(intent)

                # Align plan state with execution submission result
                if exec_state == ExecutionState.EXEC_FILLED:
                    plan.state = "ENTRY_FILLED"
                    executed_plans.append(plan_id)
                elif exec_state == ExecutionState.EXEC_PARTIAL:
                    plan.state = "PARTIAL_FILL"
                    executed_plans.append(plan_id)
                elif exec_state == ExecutionState.EXEC_REJECTED:
                    plan.state = "ENTRY_REJECTED"
                elif exec_state == ExecutionState.EXEC_UNKNOWN:
                    plan.state = "ENTRY_UNKNOWN"

        return executed_plans

    def submit_intent(self, intent: ExecutionIntent) -> ExecutionState:
        """Processes execution intent with strict idempotency and scenario modeling."""
        side_val = self._side_str(intent.side)

        req_vol_dec = _to_decimal(intent.requested_volume)
        entry_price_dec = _to_decimal(intent.entry_price)
        sl_dec = _to_decimal(intent.sl)

        # Canonical Idempotency Enforcement
        if intent.idempotency_key in self.idempotency_records:
            existing = self.idempotency_records[intent.idempotency_key]
            existing_side_val = self._side_str(existing.side)
            if (
                existing.symbol != intent.symbol
                or existing_side_val != side_val
                or _to_decimal(existing.requested_volume) != req_vol_dec
                or _to_decimal(existing.entry_price) != entry_price_dec
                or existing.decision_id != intent.decision_id
                or _to_decimal(existing.sl) != sl_dec
                or existing.effective_config_id != intent.effective_config_id
            ):
                raise IdempotencyConflictException(
                    f"Idempotency Conflict: Key '{intent.idempotency_key}' already used with different parameters."
                )
            return self.client_intent_statuses.get(
                existing.intent_id, ExecutionState.EXEC_SUBMITTED
            )

        self.idempotency_records[intent.idempotency_key] = intent

        scenario = self.config.scenario

        if scenario == ExecutionScenario.REJECT:
            self.broker_intent_statuses[intent.intent_id] = ExecutionState.EXEC_REJECTED
            self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_REJECTED
            return ExecutionState.EXEC_REJECTED

        if scenario == ExecutionScenario.UNKNOWN_BEFORE_RECEIPT:
            self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_UNKNOWN
            return ExecutionState.EXEC_UNKNOWN

        self._order_counter += 1
        order_id = f"ORD_{self._order_counter}"

        if scenario == ExecutionScenario.UNKNOWN_AFTER_ACCEPT:
            order = BrokerOrder(
                order_id=order_id,
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=side_val,
                volume=req_vol_dec,
                price=entry_price_dec,
                status="ACCEPTED",
            )
            self.broker_orders[order_id] = order
            self.broker_intent_statuses[intent.intent_id] = ExecutionState.EXEC_ACCEPTED
            self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_UNKNOWN
            return ExecutionState.EXEC_UNKNOWN

        if scenario in (
            ExecutionScenario.PARTIAL_FILL,
            ExecutionScenario.UNKNOWN_AFTER_PARTIAL_FILL,
        ):
            partial_ratio_dec = _to_decimal(self.config.partial_fill_ratio)
            fill_vol = (req_vol_dec * partial_ratio_dec).quantize(Decimal("0.01"))
            rem_vol = req_vol_dec - fill_vol

            order = BrokerOrder(
                order_id=order_id,
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=side_val,
                volume=fill_vol,
                price=entry_price_dec,
                status="PARTIAL",
            )
            self.broker_orders[order_id] = order

            self._deal_counter += 1
            self._pos_counter += 1
            deal_id = f"DEAL_{self._deal_counter}"
            pos_id = f"POS_{self._pos_counter}"

            deal = BrokerDeal(
                deal_id=deal_id,
                order_id=order_id,
                position_id=pos_id,
                symbol=intent.symbol,
                side=side_val,
                volume=fill_vol,
                price=entry_price_dec,
                commission=Decimal("1.5"),
                timestamp=self.clock.now_ns(),
            )
            self.broker_deals[deal_id] = deal

            pos = Position(
                position_id=pos_id,
                intent_id=intent.intent_id,
                order_id=order_id,
                symbol=intent.symbol,
                side=side_val,
                requested_volume=req_vol_dec,
                filled_volume=fill_vol,
                remaining_volume=rem_vol,
                entry_price=entry_price_dec,
                current_sl=sl_dec,
                lifecycle_state="POS_ACTIVE",
                health_state="HEALTH_HEALTHY",
                opened_at=self.clock.now_ns(),
                deals=[deal],
            )
            self.broker_positions[pos_id] = pos
            self.broker_intent_statuses[intent.intent_id] = ExecutionState.EXEC_PARTIAL

            if scenario == ExecutionScenario.UNKNOWN_AFTER_PARTIAL_FILL:
                self.client_intent_statuses[intent.intent_id] = (
                    ExecutionState.EXEC_UNKNOWN
                )
                return ExecutionState.EXEC_UNKNOWN

            self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_PARTIAL
            return ExecutionState.EXEC_PARTIAL

        # Normal or Unknown After Fill/Accept
        order = BrokerOrder(
            order_id=order_id,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=side_val,
            volume=req_vol_dec,
            price=entry_price_dec,
            status="FILLED",
        )
        self.broker_orders[order_id] = order

        self._deal_counter += 1
        self._pos_counter += 1
        deal_id = f"DEAL_{self._deal_counter}"
        pos_id = f"POS_{self._pos_counter}"

        deal = BrokerDeal(
            deal_id=deal_id,
            order_id=order_id,
            position_id=pos_id,
            symbol=intent.symbol,
            side=side_val,
            volume=req_vol_dec,
            price=entry_price_dec,
            commission=Decimal("1.5"),
            timestamp=self.clock.now_ns(),
        )
        self.broker_deals[deal_id] = deal

        pos = Position(
            position_id=pos_id,
            intent_id=intent.intent_id,
            order_id=order_id,
            symbol=intent.symbol,
            side=side_val,
            requested_volume=req_vol_dec,
            filled_volume=req_vol_dec,
            remaining_volume=Decimal("0.0"),
            entry_price=entry_price_dec,
            current_sl=sl_dec,
            lifecycle_state="POS_ACTIVE",
            health_state="HEALTH_HEALTHY",
            opened_at=self.clock.now_ns(),
            deals=[deal],
        )
        self.broker_positions[pos_id] = pos
        self.broker_intent_statuses[intent.intent_id] = ExecutionState.EXEC_FILLED

        if scenario == ExecutionScenario.UNKNOWN_AFTER_FILL:
            self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_UNKNOWN
            return ExecutionState.EXEC_UNKNOWN

        self.client_intent_statuses[intent.intent_id] = ExecutionState.EXEC_FILLED
        return ExecutionState.EXEC_FILLED

    def modify_stop_loss(self, position_id: str, new_sl: Union[Decimal, float]) -> bool:
        """Modifies position stop loss with protective ratchet checks."""
        pos = self.broker_positions.get(position_id)
        if not pos:
            return False

        new_sl_dec = _to_decimal(new_sl)

        if pos.lifecycle_state == "POS_CLOSED":
            raise ValueError(
                f"Cannot modify stop loss on closed position {position_id}"
            )

        if pos.side in ("BUY", "LONG") and new_sl_dec < _to_decimal(pos.current_sl):
            raise ValueError(
                f"Cannot loosen stop loss for Long position {position_id}: {pos.current_sl} -> {new_sl_dec}"
            )
        if pos.side in ("SELL", "SHORT") and new_sl_dec > _to_decimal(pos.current_sl):
            raise ValueError(
                f"Cannot loosen stop loss for Short position {position_id}: {pos.current_sl} -> {new_sl_dec}"
            )
        pos.current_sl = new_sl_dec
        return True

    def close_position(
        self,
        position_id: str,
        exit_price: Optional[Union[Decimal, float]] = None,
        close_volume: Optional[Union[Decimal, float]] = None,
    ) -> bool:
        """Closes an active position with partial closing support and instrument-native PnL calculation."""
        pos = self.broker_positions.get(position_id)
        if not pos or pos.lifecycle_state == "POS_CLOSED":
            return False

        rem_vol_dec = _to_decimal(pos.remaining_volume)
        filled_vol_dec = _to_decimal(pos.filled_volume)
        entry_price_dec = _to_decimal(pos.entry_price)

        vol_to_close_dec = (
            _to_decimal(close_volume)
            if close_volume is not None
            else (rem_vol_dec if rem_vol_dec > Decimal("0") else filled_vol_dec)
        )

        max_allowed_close = (
            rem_vol_dec if rem_vol_dec > Decimal("0") else filled_vol_dec
        )
        if vol_to_close_dec > max_allowed_close:
            raise ValueError(
                f"Cannot close volume {vol_to_close_dec} exceeding active position volume {filled_vol_dec}"
            )

        close_price_dec = (
            _to_decimal(exit_price) if exit_price is not None else entry_price_dec
        )

        contract_size = Decimal("100000.0")
        if pos.intent_id in self.idempotency_records:
            snap = self.idempotency_records[pos.intent_id].broker_constraint_snapshot
            if "contract_size" in snap:
                contract_size = Decimal(str(snap["contract_size"]))

        price_diff = (
            close_price_dec - entry_price_dec
            if pos.side in ("BUY", "LONG")
            else entry_price_dec - close_price_dec
        )
        pnl = (price_diff * vol_to_close_dec * contract_size).quantize(Decimal("0.01"))

        self._deal_counter += 1
        close_deal = BrokerDeal(
            deal_id=f"DEAL_{self._deal_counter}",
            order_id=f"CLOSE_ORD_{pos.position_id}",
            position_id=pos.position_id,
            symbol=pos.symbol,
            side="SELL" if pos.side in ("BUY", "LONG") else "BUY",
            volume=vol_to_close_dec,
            price=close_price_dec,
            commission=Decimal("1.5"),
            timestamp=self.clock.now_ns(),
        )
        self.broker_deals[close_deal.deal_id] = close_deal
        pos.deals.append(close_deal)
        pos.realized_pnl = _to_decimal(pos.realized_pnl) + pnl

        new_remaining = filled_vol_dec - vol_to_close_dec
        if new_remaining == Decimal("0.0"):
            pos.lifecycle_state = "POS_CLOSED"
            pos.remaining_volume = Decimal("0.0")
        else:
            pos.lifecycle_state = "POS_ACTIVE"
            pos.remaining_volume = new_remaining

        return True

    def reconcile_intent(self, intent_id: str) -> ExecutionState:
        """Queries authoritative broker state to reconcile client-observed UNKNOWN state."""
        broker_status = self.broker_intent_statuses.get(
            intent_id, ExecutionState.EXEC_UNKNOWN
        )
        if broker_status == ExecutionState.EXEC_UNKNOWN:
            for pos in self.broker_positions.values():
                if pos.intent_id == intent_id:
                    status = (
                        ExecutionState.EXEC_PARTIAL
                        if _to_decimal(pos.remaining_volume) > Decimal("0")
                        else ExecutionState.EXEC_FILLED
                    )
                    self.client_intent_statuses[intent_id] = status
                    return status
            self.client_intent_statuses[intent_id] = ExecutionState.EXEC_REJECTED
            return ExecutionState.EXEC_REJECTED

        self.client_intent_statuses[intent_id] = broker_status
        return broker_status

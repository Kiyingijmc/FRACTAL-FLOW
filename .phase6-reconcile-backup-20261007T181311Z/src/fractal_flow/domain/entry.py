"""Canonical Entry Model Domain Types, Authoritative State Machine, Validators, and Policy Engine for FRACTAL FLOW."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Optional, List, Dict, Any, Union, ClassVar, overload
from decimal import Decimal

from src.fractal_flow.domain.models import Direction, OrderSide
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger, LedgerOperation, AccountingInvariantException


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


@unique
class EntryModel(str, Enum):
    MARKET_CONFIRMATION = "MARKET_CONFIRMATION"
    PULLBACK_LIMIT = "PULLBACK_LIMIT"
    RETEST_LIMIT = "RETEST_LIMIT"
    RECLAIM_LIMIT = "RECLAIM_LIMIT"
    BREAKOUT_STOP = "BREAKOUT_STOP"
    STOP_LIMIT_BREAKOUT = "STOP_LIMIT_BREAKOUT"
    MOMENTUM_MARKET = "MOMENTUM_MARKET"
    CONFIRMATION_REENTRY = "CONFIRMATION_REENTRY"
    HYBRID = "HYBRID"
    NO_ENTRY = "NO_ENTRY"


@unique
class OrderType(str, Enum):
    MARKET_BUY = "MARKET_BUY"
    MARKET_SELL = "MARKET_SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"
    BUY_STOP_LIMIT = "BUY_STOP_LIMIT"
    SELL_STOP_LIMIT = "SELL_STOP_LIMIT"


@unique
class FillPolicy(str, Enum):
    FOK = "FOK"
    IOC = "IOC"
    RETURN = "RETURN"
    BOC = "BOC"


@unique
class TimeInForce(str, Enum):
    GTC = "GTC"
    DAY = "DAY"
    SPECIFIED = "SPECIFIED"
    SPECIFIED_DAY = "SPECIFIED_DAY"


@unique
class EntryTriggerType(str, Enum):
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    PRICE_TOUCH = "PRICE_TOUCH"
    PRICE_CROSS = "PRICE_CROSS"
    PRICE_IN_CORRIDOR = "PRICE_IN_CORRIDOR"
    STRUCTURAL_LEVEL_REACHED = "STRUCTURAL_LEVEL_REACHED"


@dataclass(frozen=True)
class ActiveMarketContext:
    canonical_id: str
    activation_state: str
    entry_analysis_enabled: bool
    is_tradable_session: bool
    broker_constraints: Dict[str, Any]
    producer_id: str = "MURG_AUTHORITY_ROOT"
    broker: str = "GENERIC_BROKER"
    generation: int = 1
    issued_at_ns: int = 0
    expires_at_ns: int = 0
    provenance_token: str = ""


@dataclass(frozen=True)
class EntryTrigger:
    trigger_type: EntryTriggerType
    target_price: Decimal
    secondary_price: Optional[Decimal] = None
    required_states: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_price", _to_decimal(self.target_price))
        if self.secondary_price is not None:
            object.__setattr__(self, "secondary_price", _to_decimal(self.secondary_price))


class OpportunityRiskBudget:
    """Read-only projection and state-delegating view over OpportunityRiskLedger.

    Ensures OpportunityRiskLedger remains the single authoritative mutable risk state machine.
    """

    def __init__(
        self,
        opportunity_id: str,
        total_risk_currency: Union[Decimal, float, int, str],
        total_allowed_volume: Union[Decimal, float, int, str],
        allocated_risk: Union[Decimal, float, int, str] = Decimal("0.0"),
        allocated_volume: Union[Decimal, float, int, str] = Decimal("0.0"),
        reserved_risk: Union[Decimal, float, int, str] = Decimal("0.0"),
        ledger: Optional[OpportunityRiskLedger] = None,
    ) -> None:
        self.opportunity_id = opportunity_id
        self.total_risk_currency = _to_decimal(total_risk_currency) or Decimal("0.0")
        self.total_allowed_volume = _to_decimal(total_allowed_volume) or Decimal("0.0")

        if ledger is not None:
            self._ledger = ledger
        else:
            self._ledger = OpportunityRiskLedger(
                budget_id=opportunity_id,
                opportunity_id=opportunity_id,
                total_risk=self.total_risk_currency,
                total_volume=self.total_allowed_volume,
            )
            init_res = _to_decimal(reserved_risk) or Decimal("0.0")
            init_alloc_risk = _to_decimal(allocated_risk) or Decimal("0.0")
            init_alloc_vol = _to_decimal(allocated_volume) or Decimal("0.0")

            if init_res > Decimal("0.0"):
                self._ledger.record_operation(
                    entry_id=f"init_res_{opportunity_id}",
                    operation=LedgerOperation.RESERVE,
                    amount=init_res,
                    volume=Decimal("0.0"),
                    reference_id=f"res_{opportunity_id}",
                    causation_id="init",
                    timestamp=0,
                )
            if init_alloc_risk > Decimal("0.0") or init_alloc_vol > Decimal("0.0"):
                ref = f"res_{opportunity_id}" if init_res > Decimal("0.0") else f"alloc_{opportunity_id}"
                self._ledger.record_operation(
                    entry_id=f"init_alloc_{opportunity_id}",
                    operation=LedgerOperation.ALLOCATE,
                    amount=init_alloc_risk,
                    volume=init_alloc_vol,
                    reference_id=ref,
                    causation_id="init",
                    timestamp=0,
                )

    @property
    def ledger(self) -> OpportunityRiskLedger:
        return self._ledger

    @property
    def allocated_risk(self) -> Decimal:
        return self._ledger.allocated_risk

    @property
    def allocated_volume(self) -> Decimal:
        return self._ledger.allocated_volume

    @property
    def reserved_risk(self) -> Decimal:
        return self._ledger.reserved_risk

    @property
    def remaining_risk(self) -> Decimal:
        return self._ledger.remaining_risk

    @property
    def remaining_volume(self) -> Decimal:
        return self._ledger.remaining_volume

    def reserve(self, amount: Union[Decimal, float, int, str], reference_id: Optional[str] = None) -> None:
        amt_dec = _to_decimal(amount) or Decimal("0.0")
        if amt_dec <= Decimal("0.0"):
            raise ValueError("Reservation amount must be positive")
        ref_id = reference_id or f"res_{self.opportunity_id}_{len(self._ledger.entries) + 1}"
        import time

        ts = int(time.time())
        try:
            self._ledger.record_operation(
                entry_id=f"entry_{ref_id}_{ts}_{len(self._ledger.entries)}",
                operation=LedgerOperation.RESERVE,
                amount=amt_dec,
                volume=Decimal("0.0"),
                reference_id=ref_id,
                causation_id="budget_reserve",
                timestamp=ts,
            )
        except AccountingInvariantException as e:
            raise ValueError(str(e)) from e

    def allocate(
        self,
        amount: Union[Decimal, float, int, str],
        volume: Union[Decimal, float, int, str],
        reference_id: Optional[str] = None,
    ) -> None:
        amt_dec = _to_decimal(amount) or Decimal("0.0")
        vol_dec = _to_decimal(volume) or Decimal("0.0")
        if amt_dec < Decimal("0.0") or vol_dec < Decimal("0.0"):
            raise ValueError("Allocation amount and volume must be non-negative")
        ref_id = reference_id or f"alloc_{self.opportunity_id}_{len(self._ledger.entries) + 1}"
        import time

        ts = int(time.time())
        try:
            self._ledger.record_operation(
                entry_id=f"entry_{ref_id}_{ts}_{len(self._ledger.entries)}",
                operation=LedgerOperation.ALLOCATE,
                amount=amt_dec,
                volume=vol_dec,
                reference_id=ref_id,
                causation_id="budget_allocate",
                timestamp=ts,
            )
        except AccountingInvariantException as e:
            raise ValueError(str(e)) from e

    def release(
        self,
        amount: Union[Decimal, float, int, str],
        volume: Union[Decimal, float, int, str],
        reference_id: Optional[str] = None,
    ) -> None:
        amt_dec = _to_decimal(amount) or Decimal("0.0")
        vol_dec = _to_decimal(volume) or Decimal("0.0")
        ref_id = reference_id or f"rel_{self.opportunity_id}_{len(self._ledger.entries) + 1}"
        import time

        ts = int(time.time())
        try:
            self._ledger.record_operation(
                entry_id=f"entry_{ref_id}_{ts}_{len(self._ledger.entries)}",
                operation=LedgerOperation.RELEASE,
                amount=amt_dec,
                volume=vol_dec,
                reference_id=ref_id,
                causation_id="budget_release",
                timestamp=ts,
            )
        except AccountingInvariantException as e:
            raise ValueError(str(e)) from e


@dataclass(frozen=True)
class EntryAllocation:
    leg_id: str
    entry_model: EntryModel
    allocated_risk: Decimal
    allocated_volume: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "allocated_risk", _to_decimal(self.allocated_risk))
        object.__setattr__(self, "allocated_volume", _to_decimal(self.allocated_volume))


@dataclass
class EntryPlan:
    entry_plan_id: str
    opportunity_id: str
    signal_id: str
    decision_id: str
    root_id: str
    parent_id: str
    parent_version: int
    lineage_version: int
    symbol: str
    strategy_mode: str
    operating_posture: str
    entry_model: EntryModel
    order_type: OrderType
    order_side: OrderSide
    reference_price: Decimal
    trigger_price: Optional[Decimal]
    limit_price: Optional[Decimal]
    stop_limit_price: Optional[Decimal]
    entry_corridor_low: Optional[Decimal]
    entry_corridor_high: Optional[Decimal]
    requested_volume: Decimal
    approved_volume: Decimal
    risk_budget: Decimal
    allocated_risk: Decimal
    remaining_opportunity_risk: Decimal
    structural_sl: Decimal
    tp_plan: Dict[str, Any]
    fill_policy: FillPolicy
    time_in_force: TimeInForce
    trigger_conditions: List[EntryTrigger]
    maintenance_conditions: List[str]
    invalidation_conditions: List[str]
    broker_constraints_snapshot: Dict[str, Any]
    news_state: str
    tradeability_state: str
    risk_state: str
    portfolio_state: str
    effective_config_id: str
    configuration_version: int = 1
    state: str = "ENTRY_CREATED"
    created_at: int = 0
    updated_at: int = 0
    expires_at: int = 0

    def __post_init__(self) -> None:
        self.reference_price = _to_decimal(self.reference_price)
        self.trigger_price = _to_decimal(self.trigger_price)
        self.limit_price = _to_decimal(self.limit_price)
        self.stop_limit_price = _to_decimal(self.stop_limit_price)
        self.entry_corridor_low = _to_decimal(self.entry_corridor_low)
        self.entry_corridor_high = _to_decimal(self.entry_corridor_high)
        self.requested_volume = _to_decimal(self.requested_volume)
        self.approved_volume = _to_decimal(self.approved_volume)
        self.risk_budget = _to_decimal(self.risk_budget)
        self.allocated_risk = _to_decimal(self.allocated_risk)
        self.remaining_opportunity_risk = _to_decimal(self.remaining_opportunity_risk)
        self.structural_sl = _to_decimal(self.structural_sl)


@dataclass
class HybridEntryPlan:
    hybrid_id: str
    opportunity_id: str
    risk_budget: OpportunityRiskBudget
    legs: List[EntryPlan]

    def validate_budget_limits(self) -> None:
        total_leg_risk = sum(_to_decimal(leg.allocated_risk) for leg in self.legs)
        total_leg_vol = sum(_to_decimal(leg.approved_volume) for leg in self.legs)

        if total_leg_risk > self.risk_budget.total_risk_currency:
            raise ValueError(
                f"Hybrid plan total risk {total_leg_risk} exceeds opportunity budget {self.risk_budget.total_risk_currency}"
            )
        if total_leg_vol > self.risk_budget.total_allowed_volume:
            raise ValueError(
                f"Hybrid plan total volume {total_leg_vol} exceeds opportunity volume limit {self.risk_budget.total_allowed_volume}"
            )


@dataclass(frozen=True)
class ContingentExposure:
    symbol: str
    current_open_volume: Decimal
    contingent_pending_volume: Decimal
    risk_weighted_exposure: Decimal = field(default_factory=lambda: Decimal("0.0"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_open_volume", _to_decimal(self.current_open_volume))
        object.__setattr__(self, "contingent_pending_volume", _to_decimal(self.contingent_pending_volume))
        object.__setattr__(self, "risk_weighted_exposure", _to_decimal(self.risk_weighted_exposure))

    @property
    def worst_case_contingent_volume(self) -> Decimal:
        return self.current_open_volume + self.contingent_pending_volume


class EntryStateMachine:
    """Authoritative transition service for EntryPlan state transitions."""

    @staticmethod
    def transition(plan: EntryPlan, new_state: str) -> None:
        """Transitions EntryPlan state using StateRegistry fail-closed validation."""
        GLOBAL_STATE_REGISTRY.validate_transition("EntryState", plan.state, new_state)
        plan.state = new_state


class EntryPlanValidator:
    """Validates structural and domain invariants of EntryPlan before arming or submission."""

    @staticmethod
    def validate(plan: EntryPlan) -> None:
        if (
            not plan.entry_plan_id
            or not plan.opportunity_id
            or not plan.decision_id
            or not plan.root_id
            or not plan.parent_id
        ):
            raise ValueError("EntryPlan missing required structural identity fields")

        if plan.parent_version <= 0 or plan.lineage_version <= 0:
            raise ValueError("EntryPlan parent_version and lineage_version must be positive integers")

        app_vol = _to_decimal(plan.approved_volume)
        req_vol = _to_decimal(plan.requested_volume)
        if app_vol <= Decimal("0.0") or app_vol > req_vol:
            raise ValueError(
                f"Approved volume {plan.approved_volume} must be > 0 and <= requested volume {plan.requested_volume}"
            )

        alloc_risk = _to_decimal(plan.allocated_risk)
        risk_budg = _to_decimal(plan.risk_budget)
        if alloc_risk < Decimal("0.0") or alloc_risk > risk_budg:
            raise ValueError(
                f"Allocated risk {plan.allocated_risk} must be non-negative and <= risk_budget {plan.risk_budget}"
            )

        if plan.expires_at > 0 and plan.expires_at < plan.created_at:
            raise ValueError(
                f"EntryPlan expires_at ({plan.expires_at}) cannot be prior to created_at ({plan.created_at})"
            )


class ConditionalEntryValidator:
    """Revalidates armed EntryPlans continuously prior to execution or trigger activation."""

    @staticmethod
    def revalidate(
        plan: EntryPlan,
        authoritative_parent_version: int,
        current_news_state: str,
        current_tradeability_state: str,
        current_clock_ns: int,
    ) -> bool:
        # Strict parent version equality
        if plan.parent_version != authoritative_parent_version:
            EntryStateMachine.transition(plan, "ENTRY_STALE")
            return False

        # Expiry check
        if plan.expires_at > 0 and current_clock_ns >= plan.expires_at:
            EntryStateMachine.transition(plan, "ENTRY_EXPIRED")
            return False

        # News lockdown
        if current_news_state == "NEWS_LOCKDOWN":
            EntryStateMachine.transition(plan, "ENTRY_INVALIDATED")
            return False

        # Tradeability
        if current_tradeability_state != "TRADEABILITY_PASS":
            EntryStateMachine.transition(plan, "ENTRY_INVALIDATED")
            return False

        return True


class EntryPolicyEngine:
    """Entry Policy Engine selecting entry mechanisms and constructing EntryPlans requiring ActiveMarketContext."""

    PREFERRED_MODELS: ClassVar[Dict[str, List[EntryModel]]] = {
        "SCALPING": [
            EntryModel.MARKET_CONFIRMATION,
            EntryModel.MOMENTUM_MARKET,
            EntryModel.PULLBACK_LIMIT,
        ],
        "SMART_SCALPING": [
            EntryModel.PULLBACK_LIMIT,
            EntryModel.RETEST_LIMIT,
            EntryModel.MARKET_CONFIRMATION,
        ],
        "FLIPPING": [EntryModel.RECLAIM_LIMIT, EntryModel.BREAKOUT_STOP],
        "SMART_OVERTRADING": [EntryModel.CONFIRMATION_REENTRY],
    }

    def evaluate_entry_policy(
        self,
        strategy_mode: str,
        direction: Direction,
        reference_price: Union[Decimal, float],
        structural_sl: Union[Decimal, float],
        market_context: ActiveMarketContext,
        fallback_allowed: bool = True,
    ) -> EntryModel:
        """Determines best entry model ensuring MURG entry analysis is enabled."""
        if not market_context.entry_analysis_enabled or not market_context.is_tradable_session:
            return EntryModel.NO_ENTRY

        preferred = self.PREFERRED_MODELS.get(strategy_mode, [EntryModel.MARKET_CONFIRMATION])
        supported_orders = market_context.broker_constraints.get("supported_order_types", [])

        for model in preferred:
            try:
                required_order = self.map_model_to_order_type(model, direction)
                if not supported_orders or required_order.value in supported_orders:
                    return model
            except ValueError:
                continue

        if fallback_allowed:
            try:
                market_order = self.map_model_to_order_type(EntryModel.MARKET_CONFIRMATION, direction)
                if not supported_orders or market_order.value in supported_orders:
                    return EntryModel.MARKET_CONFIRMATION
            except ValueError:
                pass

        return EntryModel.NO_ENTRY

    @staticmethod
    def map_model_to_order_type(entry_model: EntryModel, direction: Direction) -> OrderType:
        if entry_model == EntryModel.NO_ENTRY:
            raise ValueError("NO_ENTRY model cannot be mapped to an executable OrderType")

        if direction == Direction.LONG:
            if entry_model in (
                EntryModel.MARKET_CONFIRMATION,
                EntryModel.MOMENTUM_MARKET,
                EntryModel.CONFIRMATION_REENTRY,
            ):
                return OrderType.MARKET_BUY
            elif entry_model in (
                EntryModel.PULLBACK_LIMIT,
                EntryModel.RETEST_LIMIT,
                EntryModel.RECLAIM_LIMIT,
            ):
                return OrderType.BUY_LIMIT
            elif entry_model == EntryModel.BREAKOUT_STOP:
                return OrderType.BUY_STOP
            elif entry_model == EntryModel.STOP_LIMIT_BREAKOUT:
                return OrderType.BUY_STOP_LIMIT
        else:  # SHORT
            if entry_model in (
                EntryModel.MARKET_CONFIRMATION,
                EntryModel.MOMENTUM_MARKET,
                EntryModel.CONFIRMATION_REENTRY,
            ):
                return OrderType.MARKET_SELL
            elif entry_model in (
                EntryModel.PULLBACK_LIMIT,
                EntryModel.RETEST_LIMIT,
                EntryModel.RECLAIM_LIMIT,
            ):
                return OrderType.SELL_LIMIT
            elif entry_model == EntryModel.BREAKOUT_STOP:
                return OrderType.SELL_STOP
            elif entry_model == EntryModel.STOP_LIMIT_BREAKOUT:
                return OrderType.SELL_STOP_LIMIT

        raise ValueError(f"Unmapped entry model '{entry_model}' for direction '{direction}'")

"""Canonical Entry Model Domain Types, Authoritative State Machine, Validators, and Policy Engine for FRACTAL FLOW."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Optional, List, Dict, Any, Union, overload
from decimal import Decimal

from src.fractal_flow.domain.models import Direction, OrderSide
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY


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


@dataclass
class OpportunityRiskBudget:
    opportunity_id: str
    total_risk_currency: Decimal
    total_allowed_volume: Decimal
    allocated_risk: Decimal = field(default_factory=lambda: Decimal("0.0"))
    allocated_volume: Decimal = field(default_factory=lambda: Decimal("0.0"))
    reserved_risk: Decimal = field(default_factory=lambda: Decimal("0.0"))

    def __post_init__(self) -> None:
        self.total_risk_currency = _to_decimal(self.total_risk_currency)
        self.total_allowed_volume = _to_decimal(self.total_allowed_volume)
        self.allocated_risk = _to_decimal(self.allocated_risk)
        self.allocated_volume = _to_decimal(self.allocated_volume)
        self.reserved_risk = _to_decimal(self.reserved_risk)

    @property
    def remaining_risk(self) -> Decimal:
        tot = self.total_risk_currency
        alloc = self.allocated_risk
        res = self.reserved_risk
        return max(Decimal("0.0"), tot - alloc - res)

    @property
    def remaining_volume(self) -> Decimal:
        return max(Decimal("0.0"), self.total_allowed_volume - self.allocated_volume)

    def reserve(self, amount: Union[Decimal, float]) -> None:
        amt_dec = _to_decimal(amount)
        if amt_dec <= Decimal("0.0"):
            raise ValueError("Reservation amount must be positive")
        if amt_dec > self.remaining_risk:
            raise ValueError(f"Cannot reserve {amount}: exceeds remaining risk {self.remaining_risk}")
        self.reserved_risk += amt_dec

    def allocate(self, amount: Union[Decimal, float], volume: Union[Decimal, float]) -> None:
        req_risk = _to_decimal(amount)
        req_vol = _to_decimal(volume)
        if req_risk < Decimal("0.0") or req_vol < Decimal("0.0"):
            raise ValueError("Allocation amount and volume must be non-negative")
        if req_risk > self.remaining_risk + self.reserved_risk:
            raise ValueError(
                f"Cannot allocate risk {amount}: exceeds total risk budget {self.total_risk_currency}"
            )
        if req_vol > self.remaining_volume:
            raise ValueError(
                f"Cannot allocate volume {volume}: exceeds total volume budget {self.total_allowed_volume}"
            )

        # If reserved, deduct from reserved first
        if self.reserved_risk >= req_risk:
            self.reserved_risk -= req_risk
        else:
            self.reserved_risk = Decimal("0.0")

        self.allocated_risk += req_risk
        self.allocated_volume += req_vol

    def release(self, amount: Union[Decimal, float], volume: Union[Decimal, float]) -> None:
        rel_risk = _to_decimal(amount)
        rel_vol = _to_decimal(volume)
        self.allocated_risk = max(Decimal("0.0"), self.allocated_risk - rel_risk)
        self.allocated_volume = max(Decimal("0.0"), self.allocated_volume - rel_vol)


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
        object.__setattr__(
            self, "contingent_pending_volume", _to_decimal(self.contingent_pending_volume)
        )
        object.__setattr__(
            self, "risk_weighted_exposure", _to_decimal(self.risk_weighted_exposure)
        )

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
            raise ValueError(
                "EntryPlan parent_version and lineage_version must be positive integers"
            )

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

    PREFERRED_MODELS: Dict[str, List[EntryModel]] = {
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
                market_order = self.map_model_to_order_type(
                    EntryModel.MARKET_CONFIRMATION, direction
                )
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

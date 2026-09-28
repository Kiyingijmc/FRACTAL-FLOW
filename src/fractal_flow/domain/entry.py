"""Canonical Entry Model Domain Types and EntryPolicyEngine for FRACTAL FLOW."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Optional, List, Dict, Any
from decimal import Decimal

from src.fractal_flow.domain.models import Direction, OrderSide
from src.fractal_flow.domain.reason_codes import ReasonCode


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
    target_price: float
    secondary_price: Optional[float] = None
    required_states: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OpportunityRiskBudget:
    opportunity_id: str
    total_risk_currency: float
    total_allowed_volume: float
    allocated_risk: float = 0.0
    allocated_volume: float = 0.0

    @property
    def remaining_risk(self) -> float:
        return max(0.0, float(Decimal(str(self.total_risk_currency)) - Decimal(str(self.allocated_risk))))

    @property
    def remaining_volume(self) -> float:
        return max(0.0, float(Decimal(str(self.total_allowed_volume)) - Decimal(str(self.allocated_volume))))


@dataclass(frozen=True)
class EntryAllocation:
    leg_id: str
    entry_model: EntryModel
    allocated_risk: float
    allocated_volume: float


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
    reference_price: float
    trigger_price: Optional[float]
    limit_price: Optional[float]
    stop_limit_price: Optional[float]
    entry_corridor_low: Optional[float]
    entry_corridor_high: Optional[float]
    requested_volume: float
    approved_volume: float
    risk_budget: float
    allocated_risk: float
    remaining_opportunity_risk: float
    structural_sl: float
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


@dataclass
class HybridEntryPlan:
    hybrid_id: str
    opportunity_id: str
    risk_budget: OpportunityRiskBudget
    legs: List[EntryPlan]


@dataclass(frozen=True)
class ContingentExposure:
    symbol: str
    current_open_volume: float
    contingent_pending_volume: float

    @property
    def worst_case_contingent_volume(self) -> float:
        return float(Decimal(str(self.current_open_volume)) + Decimal(str(self.contingent_pending_volume)))


class EntryPolicyEngine:
    """Entry Policy Engine selecting entry mechanisms and constructing EntryPlans requiring ActiveMarketContext."""

    PREFERRED_MODELS: Dict[str, List[EntryModel]] = {
        "SCALPING": [EntryModel.MARKET_CONFIRMATION, EntryModel.MOMENTUM_MARKET, EntryModel.PULLBACK_LIMIT],
        "SMART_SCALPING": [EntryModel.PULLBACK_LIMIT, EntryModel.RETEST_LIMIT, EntryModel.MARKET_CONFIRMATION],
        "FLIPPING": [EntryModel.RECLAIM_LIMIT, EntryModel.BREAKOUT_STOP],
        "SMART_OVERTRADING": [EntryModel.CONFIRMATION_REENTRY],
    }

    def evaluate_entry_policy(
        self,
        strategy_mode: str,
        direction: Direction,
        reference_price: float,
        structural_sl: float,
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
            if entry_model in (EntryModel.MARKET_CONFIRMATION, EntryModel.MOMENTUM_MARKET, EntryModel.CONFIRMATION_REENTRY):
                return OrderType.MARKET_BUY
            elif entry_model in (EntryModel.PULLBACK_LIMIT, EntryModel.RETEST_LIMIT, EntryModel.RECLAIM_LIMIT):
                return OrderType.BUY_LIMIT
            elif entry_model == EntryModel.BREAKOUT_STOP:
                return OrderType.BUY_STOP
            elif entry_model == EntryModel.STOP_LIMIT_BREAKOUT:
                return OrderType.BUY_STOP_LIMIT
        else:  # SHORT
            if entry_model in (EntryModel.MARKET_CONFIRMATION, EntryModel.MOMENTUM_MARKET, EntryModel.CONFIRMATION_REENTRY):
                return OrderType.MARKET_SELL
            elif entry_model in (EntryModel.PULLBACK_LIMIT, EntryModel.RETEST_LIMIT, EntryModel.RECLAIM_LIMIT):
                return OrderType.SELL_LIMIT
            elif entry_model == EntryModel.BREAKOUT_STOP:
                return OrderType.SELL_STOP
            elif entry_model == EntryModel.STOP_LIMIT_BREAKOUT:
                return OrderType.SELL_STOP_LIMIT

        raise ValueError(f"Unmapped entry model '{entry_model}' for direction '{direction}'")

"""Foundational Domain Models for FRACTAL FLOW with Enums and Full Provenance Snapshots."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, unique
from typing import Any


@unique
class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@unique
class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@unique
class DealEntryRole(str, Enum):
    UNKNOWN = "UNKNOWN"
    OPEN = "OPEN"
    INCREASE = "INCREASE"
    CLOSE = "CLOSE"
    DECREASE = "DECREASE"
    REVERSAL = "REVERSAL"


@dataclass(frozen=True)
class MarketObservation:
    symbol: str
    timestamp: int
    bid: Decimal
    ask: Decimal
    volume: Decimal
    timeframe: str = "1M"


@dataclass(frozen=True)
class FeatureSet:
    symbol: str
    timestamp: int
    atr_14: Decimal
    spread_pips: Decimal
    relative_volatility: float  # Statistical metric ratio


@dataclass(frozen=True)
class StructureState:
    symbol: str
    timeframe: str
    swing_state: str
    break_state: str
    version: int


@dataclass(frozen=True)
class FlowState:
    symbol: str
    timeframe: str
    dominant_flow: str
    local_flow: str


@dataclass
class PullbackObject:
    id: str
    parent_id: str
    root_id: str
    symbol: str
    timeframe: str
    direction: Direction
    parent_direction: Direction
    start_time: int
    start_price: Decimal
    impulse_high: Decimal
    impulse_low: Decimal
    impulse_range: Decimal
    current_high: Decimal
    current_low: Decimal
    counter_move: Decimal
    counter_move_norm: Decimal
    retracement_depth: float  # Percentage / ratio metric
    duration: int
    duration_ratio: float  # Ratio metric
    velocity: float  # Statistical rate metric
    acceleration: float  # Statistical rate metric
    efficiency: float  # Ratio metric
    momentum: float  # Indicator metric
    range: Decimal
    structural_damage: float  # Score metric
    weakening_score: float  # Score metric
    resumption_score: float  # Score metric
    false_resumption_risk: float  # Probability score metric
    maturity: str
    state: str
    sub_state: str
    validity: bool
    confidence: float  # Probability score metric
    protected_level: Decimal
    primary_entry_allowed: bool = True
    micro_entry_allowed: bool = False
    reentry_allowed: bool = True
    runner_management_allowed: bool = True


@dataclass
class OpportunityObject:
    opportunity_id: str
    root_id: str
    symbol: str
    session: str
    strategy_mode: str
    posture: str
    environment: str
    environment_tf: str
    location: str
    location_tf: str
    dominant_flow: str
    local_flow: str
    market_role: str
    primary_pullback_id: str
    setup_type: str
    direction: Direction
    structural_edge: float  # Statistical score metric
    opportunity_space: float  # Statistical score metric
    tradeability: str
    execution_quality: float  # Score metric
    entry_profile: str
    risk_class: str
    ttl_class: str
    confidence: float  # Confidence score
    state: str
    entry_allowed: bool
    parent_opportunity_id: str | None = None


@dataclass(frozen=True)
class TradeabilityAssessment:
    opportunity_id: str
    status: str
    spread_pips: Decimal
    allowed_spread_pips: Decimal
    passed: bool


@dataclass(frozen=True)
class RiskAssessment:
    opportunity_id: str
    status: str
    requested_risk: Decimal
    approved_risk: Decimal
    account_feasible: bool


@dataclass(frozen=True)
class PortfolioAssessment:
    opportunity_id: str
    result: str
    currency_exposure_lots: dict[str, Decimal]


@dataclass
class TradeDecision:
    decision_id: str
    opportunity_id: str
    root_id: str
    direction: Direction
    symbol: str
    environment: str
    role: str
    setup: str
    pullback_id: str
    resumption_state: str
    location: str
    opportunity_space: float
    tradeability: str
    news_state: str
    risk_state: str
    portfolio_state: str
    entry_price: Decimal
    structural_sl: Decimal
    tp_plan: dict[str, Any]
    ttl_ns: int
    requested_risk: Decimal
    approved_risk: Decimal
    position_size_lots: Decimal
    arbitration_result: str
    effective_config_id: str
    broker_constraint_snapshot: dict[str, Any]
    quote_timestamp: int
    spread_pips: Decimal
    configuration_version: int = 1
    lineage_version: int = 1
    authorized: bool = False

    def is_authorized(self) -> bool:
        """NEWS_LOCKDOWN is a hard authorization boundary that blocks trade authorization."""
        if self.news_state == "NEWS_LOCKDOWN":
            return False
        return (
            self.authorized
            and self.tradeability == "TRADEABILITY_PASS"
            and self.portfolio_state == "PORTFOLIO_ALLOW"
        )


@dataclass
class ExecutionIntent:
    intent_id: str
    decision_id: str
    opportunity_id: str
    root_id: str
    idempotency_key: str
    symbol: str
    side: OrderSide
    requested_volume: Decimal
    entry_price: Decimal
    sl: Decimal
    tp_plan: dict[str, Any]
    effective_config_id: str
    lineage_version: int
    broker_constraint_snapshot: dict[str, Any]
    quote_timestamp: int
    spread_pips: Decimal
    status: str
    created_at: int
    updated_at: int
    entry_plan_id: str | None = None
    entry_model: str | None = None
    order_type: str | None = None
    fill_policy: str | None = None
    time_in_force: str | None = None
    trigger_price: Decimal | None = None
    limit_price: Decimal | None = None
    stop_limit_price: Decimal | None = None


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    intent_id: str
    symbol: str
    side: str
    volume: Decimal
    price: Decimal
    status: str


@dataclass(frozen=True)
class BrokerDeal:
    deal_id: str
    order_id: str
    position_id: str
    symbol: str
    side: str
    volume: Decimal
    price: Decimal
    commission: Decimal
    timestamp: int
    entry_role: DealEntryRole = DealEntryRole.UNKNOWN


@dataclass
class Position:
    position_id: str
    intent_id: str
    order_id: str
    symbol: str
    side: str
    requested_volume: Decimal
    filled_volume: Decimal
    remaining_volume: Decimal
    entry_price: Decimal
    current_sl: Decimal
    lifecycle_state: str
    health_state: str
    opened_at: int
    deals: list[BrokerDeal] = field(default_factory=list)
    realized_pnl: Decimal = Decimal("0.0")
    unrealized_pnl: Decimal = Decimal("0.0")
    reconciliation_status: str = "RECON_NORMAL"


@dataclass
class PositionManagementState:
    position_id: str
    trailing_sl: Decimal
    tp_level: Decimal
    is_runner: bool


@dataclass
class TTLState:
    object_id: str
    ttl_ns: int
    created_at: int
    expires_at: int
    state: str


@dataclass
class ReconciliationStateRecord:
    object_id: str
    status: str
    matched: bool
    reconstructed_lineage: bool


@dataclass(frozen=True)
class JournalEvent:
    journal_id: str
    timestamp: int
    event_type: str
    entity_id: str
    details: dict[str, Any]

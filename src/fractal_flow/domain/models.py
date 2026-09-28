"""Foundational Domain Models for FRACTAL FLOW."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass(frozen=True)
class MarketObservation:
    symbol: str
    timestamp: int
    bid: float
    ask: float
    volume: float
    timeframe: str = "1M"


@dataclass(frozen=True)
class FeatureSet:
    symbol: str
    timestamp: int
    atr_14: float
    spread_pips: float
    relative_volatility: float


@dataclass(frozen=True)
class StructureState:
    symbol: str
    timeframe: str
    swing_state: str  # SwingState enum
    break_state: str  # BreakState enum
    version: int


@dataclass(frozen=True)
class FlowState:
    symbol: str
    timeframe: str
    dominant_flow: str  # FlowState enum
    local_flow: str


@dataclass
class PullbackObject:
    id: str
    parent_id: str
    root_id: str
    symbol: str
    timeframe: str
    direction: str
    parent_direction: str
    start_time: int
    start_price: float
    impulse_high: float
    impulse_low: float
    impulse_range: float
    current_high: float
    current_low: float
    counter_move: float
    counter_move_norm: float
    retracement_depth: float
    duration: int
    duration_ratio: float
    velocity: float
    acceleration: float
    efficiency: float
    momentum: float
    range: float
    structural_damage: float
    weakening_score: float
    resumption_score: float
    false_resumption_risk: float
    maturity: str
    state: str  # PDEState enum
    sub_state: str  # PDEResumptionState enum
    validity: bool
    confidence: float
    protected_level: float
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
    direction: str
    structural_edge: float
    opportunity_space: float
    tradeability: str
    execution_quality: float
    entry_profile: str
    risk_class: str
    ttl_class: str
    confidence: float
    state: str  # OpportunityState enum
    entry_allowed: bool
    parent_opportunity_id: Optional[str] = None


@dataclass(frozen=True)
class TradeabilityAssessment:
    opportunity_id: str
    status: str  # TradeabilityState enum
    spread_pips: float
    allowed_spread_pips: float
    passed: bool


@dataclass(frozen=True)
class RiskAssessment:
    opportunity_id: str
    status: str  # RiskState enum
    requested_risk: float
    approved_risk: float
    account_feasible: bool


@dataclass(frozen=True)
class PortfolioAssessment:
    opportunity_id: str
    result: str  # PortfolioState enum (ALLOW, DEFER, MERGE, REJECT)
    currency_exposure_lots: Dict[str, float]


@dataclass
class TradeDecision:
    decision_id: str
    opportunity_id: str
    direction: str
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
    entry_price: float
    structural_sl: float
    tp_plan: Dict[str, Any]
    ttl_ns: int
    requested_risk: float
    approved_risk: float
    position_size_lots: float
    arbitration_result: str
    configuration_version: int = 1
    lineage_version: int = 1
    authorized: bool = False


@dataclass
class ExecutionIntent:
    intent_id: str
    decision_id: str
    opportunity_id: str
    idempotency_key: str
    symbol: str
    side: str
    requested_volume: float
    entry_price: float
    sl: float
    tp_plan: Dict[str, Any]
    configuration_version: int
    lineage_version: int
    status: str  # ExecutionState enum
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    intent_id: str
    symbol: str
    side: str
    volume: float
    price: float
    status: str


@dataclass(frozen=True)
class BrokerDeal:
    deal_id: str
    order_id: str
    position_id: str
    symbol: str
    side: str
    volume: float
    price: float
    commission: float


@dataclass
class Position:
    position_id: str
    intent_id: str
    symbol: str
    side: str
    volume: float
    entry_price: float
    current_sl: float
    lifecycle_state: str  # PositionLifecycleState
    health_state: str  # PositionHealthState
    opened_at: int


@dataclass
class PositionManagementState:
    position_id: str
    trailing_sl: float
    tp_level: float
    is_runner: bool


@dataclass
class TTLState:
    object_id: str
    ttl_ns: int
    created_at: int
    expires_at: int
    state: str  # TTLState enum


@dataclass
class ReconciliationStateRecord:
    object_id: str
    status: str  # ReconciliationState enum
    matched: bool
    reconstructed_lineage: bool


@dataclass(frozen=True)
class JournalEvent:
    journal_id: str
    timestamp: int
    event_type: str
    entity_id: str
    details: Dict[str, Any]

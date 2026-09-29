"""EntryAuthorizationEvidence, MURG Telemetry, and Entry Model Research Telemetry for FRACTAL FLOW Pass 4F."""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass(frozen=True)
class EntryAuthorizationEvidence:
    decision_id: str
    opportunity_id: str
    opportunity_version: int
    risk_decision_id: str
    portfolio_decision_id: str
    news_state: str
    broker_snapshot_id: str
    effective_config_id: str
    created_at: int
    expires_at: int


@dataclass
class MURGTelemetry:
    telemetry_id: str
    canonical_id: str
    broker_symbol: str
    activation_state: str
    priority_score: float  # Allocation priority metric
    capacity_multiplier: float  # Capacity scaling multiplier
    entry_analysis_enabled: bool
    position_monitoring_enabled: bool
    pending_order_monitoring_enabled: bool
    timestamp: int


@dataclass
class EntryModelResearchTelemetry:
    telemetry_id: str
    opportunity_id: str
    entry_plan_id: str
    entry_model: str
    order_type: str
    reference_price: Decimal
    entry_price: Decimal
    trigger_price: Optional[Decimal]
    limit_price: Optional[Decimal]
    stop_limit_price: Optional[Decimal]
    planned_risk: Decimal
    allocated_risk: Decimal
    time_to_trigger_ns: int
    time_to_fill_ns: int
    fill_rate: float  # Execution statistical ratio
    slippage_pips: Decimal
    spread_at_entry_pips: Decimal
    mfe_pips: Decimal = Decimal("0.0")
    mae_pips: Decimal = Decimal("0.0")
    realized_r: Decimal = Decimal("0.0")
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

"""EntryAuthorizationEvidence and Entry Model Research Telemetry for FRACTAL FLOW Pass 4D."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


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
class EntryModelResearchTelemetry:
    telemetry_id: str
    opportunity_id: str
    entry_plan_id: str
    entry_model: str
    order_type: str
    reference_price: float
    entry_price: float
    trigger_price: Optional[float]
    limit_price: Optional[float]
    stop_limit_price: Optional[float]
    planned_risk: float
    allocated_risk: float
    time_to_trigger_ns: int
    time_to_fill_ns: int
    fill_rate: float
    slippage_pips: float
    spread_at_entry_pips: float
    mfe_pips: float = 0.0
    mae_pips: float = 0.0
    realized_r: float = 0.0
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

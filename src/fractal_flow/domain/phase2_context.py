"""Canonical same-watermark Phase 2 context and dependency coherence."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from src.fractal_flow.domain.context import CausalWatermark, DataStatus, InstrumentSpec, MarketContextSnapshot
from src.fractal_flow.domain.envelope import StateEnvelope

class DependencyKind(str, Enum):
    HARD = "HARD"
    CONTEXT = "CONTEXT"
    OPTIONAL_EVIDENCE = "OPTIONAL_EVIDENCE"
    AUTHORITY = "AUTHORITY"
    LINEAGE = "LINEAGE"

@dataclass(frozen=True)
class EngineVersionSet:
    structure: int = 0
    flow: int = 0
    regime: int = 0
    pde: int = 0
    role: int = 0
    location: int = 0
    volatility: int = 0
    evidence: int = 0
    data_quality: int = 0

@dataclass(frozen=True)
class DependencyGraph:
    """Explicit informational dependency graph; call order is not authority."""
    edges: tuple[tuple[str, str, DependencyKind], ...] = (
        ("Structure", "Phase2", DependencyKind.CONTEXT),
        ("Flow", "Phase2", DependencyKind.CONTEXT),
        ("Structure", "Regime", DependencyKind.CONTEXT),
        ("Flow", "Regime", DependencyKind.CONTEXT),
        ("Structure", "PDE", DependencyKind.CONTEXT),
        ("Flow", "PDE", DependencyKind.CONTEXT),
        ("Regime", "PDE", DependencyKind.CONTEXT),
        ("Structure", "Location", DependencyKind.CONTEXT),
        ("Regime", "Location", DependencyKind.CONTEXT),
        ("Structure", "Role", DependencyKind.CONTEXT),
        ("Flow", "Role", DependencyKind.CONTEXT),
        ("Regime", "Role", DependencyKind.CONTEXT),
        ("PDE", "Role", DependencyKind.CONTEXT),
        ("Location", "Role", DependencyKind.CONTEXT),
    )

class Phase2ContextBuilder:
    """Builds an atomic context only when all supplied state belongs to one watermark."""
    def build(
        self, root_id: str, symbol: str, timeframe: str, timestamp: int,
        instrument: InstrumentSpec, data_status: DataStatus, volatility: Decimal,
        versions: EngineVersionSet, feature_version: int = 1,
        configuration_version: int = 1, configuration_id: str = "",
        states: dict[str, str] | None = None, component_watermarks: dict[str, int] | None = None, sequence: int = 0,
    ) -> MarketContextSnapshot:
        if timestamp < 0 or sequence < 0:
            raise ValueError("timestamp and sequence must be non-negative")
        if configuration_version <= 0 or feature_version <= 0:
            raise ValueError("configuration_version and feature_version must be positive")
        if not configuration_id:
            raise ValueError("configuration_id is required for Phase 2 context coherence")
        if component_watermarks:
            mismatched = {name: ts for name, ts in component_watermarks.items() if ts != timestamp}
            if mismatched:
                raise ValueError(f"Phase2 component watermark mismatch at {timestamp}: {mismatched}")
        return MarketContextSnapshot(
            root_id=root_id, symbol=symbol, timeframe=timeframe,
            watermark=CausalWatermark(timestamp, sequence), instrument=instrument,
            data_status=data_status, volatility=volatility,
            volatility_valid=volatility > 0 and data_status in (DataStatus.VALID, DataStatus.DEGRADED),
            structure_version=versions.structure, flow_version=versions.flow,
            regime_version=versions.regime, pde_version=versions.pde,
            role_version=versions.role, location_version=versions.location,
            volatility_version=versions.volatility, data_quality_version=versions.data_quality,
            evidence_version=versions.evidence, feature_version=feature_version,
            configuration_version=configuration_version,
            configuration_id=configuration_id,
            valid_until=timestamp + StateEnvelope.calculate_timeframe_validity_seconds(timeframe), states=dict(states or {}),
        )

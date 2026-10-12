"""Domain module initialization."""

from src.fractal_flow.domain.data_quality import DataQualityAssessment, DataQualityEngine, DataQualityState
from src.fractal_flow.domain.flow import FlowEngine, FlowEvidence, FlowState, FlowTransitionRecord
from src.fractal_flow.domain.market import Bar, BarAggregator, Tick, Timeframe, aggregate_ticks_to_bars
from src.fractal_flow.domain.structure import (
    BreakState,
    StructuralBreak,
    StructuralDamageState,
    StructuralStopCandidate,
    StructureEngine,
    StructureTransitionRecord,
    SwingState,
)
from src.fractal_flow.domain.volatility import VolatilityEngine, VolatilityMetrics, VolatilityState

__all__ = [
    "Bar",
    "BarAggregator",
    "BreakState",
    "DataQualityAssessment",
    "DataQualityEngine",
    "DataQualityState",
    "FlowEngine",
    "FlowEvidence",
    "FlowState",
    "FlowTransitionRecord",
    "StructuralBreak",
    "StructuralDamageState",
    "StructuralStopCandidate",
    "StructureEngine",
    "StructureTransitionRecord",
    "SwingState",
    "Tick",
    "Timeframe",
    "VolatilityEngine",
    "VolatilityMetrics",
    "VolatilityState",
    "aggregate_ticks_to_bars",
]

# v2.3 informational substrate
from src.fractal_flow.domain.context import CausalWatermark, DataStatus, InstrumentSpec, MarketContextSnapshot
from src.fractal_flow.domain.evidence import EvidenceAggregator, EvidenceDirection, EvidenceItem, EvidenceSummary
from src.fractal_flow.domain.location import LocationEngine, LocationEvidence, LocationState
from src.fractal_flow.domain.pde import PDEEngine, PDEEvidence, PDEState
from src.fractal_flow.domain.phase2 import Phase2Evaluation, Phase2Pipeline
from src.fractal_flow.domain.regime import RegimeEngine, RegimeEvidence, RegimeState
from src.fractal_flow.domain.role import RoleEngine, RoleEvidence, RoleState
from src.fractal_flow.domain.structure_v23 import StructureEngineV23, StructuralTruth

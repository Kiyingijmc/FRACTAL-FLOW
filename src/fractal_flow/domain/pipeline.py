"""Multi-Timeframe Behavioral Pipeline for FRACTAL FLOW.

Orchestrates the canonical behavioral sequence:
DataQuality -> Volatility -> Structure -> Flow -> PDE -> Regime -> Role -> Location
across timeframes (4H, 1H, 30M, 15M, 5M, 1M) with lineage tracking, version pinning,
and deterministic invalidation cascades.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.fractal_flow.domain.data_quality import DataQualityAssessment, DataQualityEngine
from src.fractal_flow.domain.flow import FlowEngine, FlowTransitionRecord
from src.fractal_flow.domain.location import LocationEngine, LocationTransitionRecord
from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.pde import PDEEngine, PDETransitionRecord
from src.fractal_flow.domain.regime import RegimeEngine, RegimeTransitionRecord
from src.fractal_flow.domain.role import RoleEngine, RoleTransitionRecord
from src.fractal_flow.domain.structure import StructureEngine, StructureTransitionRecord
from src.fractal_flow.domain.volatility import VolatilityEngine, VolatilityMetrics


@dataclass
class BehavioralStateSnapshot:
    symbol: str
    timeframe: str
    dq_record: DataQualityAssessment
    vol_record: VolatilityMetrics
    structure_record: StructureTransitionRecord
    flow_record: FlowTransitionRecord
    pde_record: PDETransitionRecord
    regime_record: RegimeTransitionRecord
    role_record: RoleTransitionRecord
    location_record: LocationTransitionRecord
    timestamp: int
    root_id: str
    version: int


class BehavioralPipeline:
    """Multi-Timeframe Behavioral Pipeline orchestrating all Phase 2 behavioral engines."""

    def __init__(self, symbol: str, timeframes: Optional[list[str]] = None) -> None:
        self.symbol = symbol
        self.timeframes = timeframes or ["4H", "1H", "30M", "15M", "5M", "1M"]

        self.dq_engines: dict[str, DataQualityEngine] = {tf: DataQualityEngine(symbol=symbol) for tf in self.timeframes}
        self.vol_engines: dict[str, VolatilityEngine] = {
            tf: VolatilityEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }
        self.struct_engines: dict[str, StructureEngine] = {
            tf: StructureEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }
        self.flow_engines: dict[str, FlowEngine] = {
            tf: FlowEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }
        self.pde_engines: dict[str, PDEEngine] = {tf: PDEEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes}
        self.regime_engines: dict[str, RegimeEngine] = {
            tf: RegimeEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }
        self.role_engines: dict[str, RoleEngine] = {
            tf: RoleEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }
        self.location_engines: dict[str, LocationEngine] = {
            tf: LocationEngine(symbol=symbol, timeframe=tf) for tf in self.timeframes
        }

        self.pipeline_version = 0

    def process_bar(
        self,
        bar: Bar,
        tick: Tick,
        root_id: str,
        htf_snapshot: Optional[BehavioralStateSnapshot] = None,
        config_version: int = 1,
        data_version: int = 1,
        feature_version: int = 1,
    ) -> BehavioralStateSnapshot:
        """Processes bar through full behavioral pipeline for bar.timeframe."""
        tf = bar.timeframe
        if tf not in self.timeframes:
            raise ValueError(f"Timeframe {tf} not registered in BehavioralPipeline {self.timeframes}")

        self.pipeline_version += 1

        # 1. Data Quality
        dq_rec = self.dq_engines[tf].evaluate_tick(tick)

        # 2. Volatility
        vol_rec = self.vol_engines[tf].update_bar(bar)

        v_local = vol_rec.atr_14 if vol_rec.atr_14 > Decimal("0.0") else Decimal("0.0001")

        # 3. Structure
        struct_rec = self.struct_engines[tf].process_bar(
            bar,
            v_local=v_local,
            root_id=root_id,
            parent_id=f"vol_{vol_rec.version}",
            parent_version=vol_rec.version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        # 4. Flow
        flow_rec = self.flow_engines[tf].evaluate_bar(
            bar,
            structure_record=struct_rec,
            v_local=v_local,
            root_id=root_id,
            parent_id=f"struct_{struct_rec.state_version}",
            parent_version=struct_rec.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        # 5. PDE
        htf_pde_state = htf_snapshot.pde_record.pde_state if htf_snapshot else None
        htf_tf = htf_snapshot.timeframe if htf_snapshot else None

        pde_rec = self.pde_engines[tf].evaluate_bar(
            bar,
            structure_record=struct_rec,
            v_local=v_local,
            root_id=root_id,
            parent_id=f"flow_{flow_rec.state_version}",
            parent_version=flow_rec.state_version,
            htf_pde_state=htf_pde_state,
            htf_timeframe=htf_tf,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        # 6. Regime
        is_vol_extreme = vol_rec.state.value in ("VOL_EXTREME", "VOL_COLLAPSE")
        regime_rec = self.regime_engines[tf].evaluate(
            bar,
            flow_state=flow_rec.flow_state.value,
            v_local=v_local,
            is_vol_extreme=is_vol_extreme,
            root_id=root_id,
            parent_id=f"pde_{pde_rec.state_version}",
            parent_version=pde_rec.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        # 7. Role
        direction = (
            "LONG"
            if "LONG" in flow_rec.flow_state.value
            else ("SHORT" if "SHORT" in flow_rec.flow_state.value else "NEUTRAL")
        )
        role_rec = self.role_engines[tf].evaluate(
            bar,
            direction=direction,
            regime_state=regime_rec.regime_state.value,
            pde_state=pde_rec.pde_state.value,
            break_state=struct_rec.break_state.value,
            damage_state=struct_rec.damage_state.value,
            root_id=root_id,
            parent_id=f"regime_{regime_rec.state_version}",
            parent_version=regime_rec.state_version,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        # 8. Location
        htf_obstacle = getattr(htf_snapshot.structure_record, "protected_high", None) if htf_snapshot else None
        location_rec = self.location_engines[tf].evaluate(
            bar,
            protected_high=getattr(struct_rec, "protected_high", None),
            protected_low=getattr(struct_rec, "protected_low", None),
            v_local=v_local,
            root_id=root_id,
            parent_id=f"role_{role_rec.state_version}",
            parent_version=role_rec.state_version,
            htf_obstacle_price=htf_obstacle,
            config_version=config_version,
            data_version=data_version,
            feature_version=feature_version,
        )

        return BehavioralStateSnapshot(
            symbol=self.symbol,
            timeframe=tf,
            dq_record=dq_rec,
            vol_record=vol_rec,
            structure_record=struct_rec,
            flow_record=flow_rec,
            pde_record=pde_rec,
            regime_record=regime_rec,
            role_record=role_rec,
            location_record=location_rec,
            timestamp=bar.close_timestamp,
            root_id=root_id,
            version=self.pipeline_version,
        )

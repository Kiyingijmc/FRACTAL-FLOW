"""FRACTAL-FLOW v2.3 causal informational pipeline with bounded recovery."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from copy import copy, deepcopy
from contextlib import contextmanager
from typing import Iterator, Any
from decimal import Decimal
import hashlib
import json
from src.fractal_flow.config.config import Phase2EffectiveConfiguration, StructureConfig, build_phase2_effective_config
from src.fractal_flow.domain.context import DataStatus, InstrumentSpec, MarketContextSnapshot
from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.evidence import EvidenceAggregator, EvidenceDirection, EvidenceItem, EvidenceSummary
from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.location import LocationEngine, LocationEvidence
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.pde import PDEEngine, PDEEvidence
from src.fractal_flow.domain.phase2_context import EngineVersionSet, Phase2ContextBuilder
from src.fractal_flow.domain.regime import RegimeEngine, RegimeEvidence
from src.fractal_flow.domain.role import RoleEngine, RoleEvidence
from src.fractal_flow.domain.structure import StructureTransitionRecord
from src.fractal_flow.domain.structure_v23 import StructureEngineV23
from src.fractal_flow.domain.volatility import VolatilityEngine, VolatilityMetrics

@dataclass(frozen=True)
class Phase2Evaluation:
    bar: Bar; volatility: VolatilityMetrics; structure: StructureTransitionRecord; flow: object; regime: RegimeEvidence; pde:PDEEvidence; location:LocationEvidence; role:RoleEvidence; context:MarketContextSnapshot; evidence:EvidenceSummary

class Phase2Pipeline:
    SNAPSHOT_SCHEMA="phase2-pipeline-v2.3.2"

    @staticmethod
    def _compute_configuration_id(symbol: str, timeframe: str, instrument: InstrumentSpec, history_capacity: int) -> str:
        """Compatibility shim returning the canonical Phase 2 effective identity."""
        return build_phase2_effective_config(symbol, timeframe, instrument, history_capacity).effective_config_id

    def __init__(self, symbol: str, timeframe: str = "1M", instrument: InstrumentSpec | None = None,
                 history_capacity: int = 256, configuration: Phase2EffectiveConfiguration | None = None) -> None:
        if history_capacity <= 0:
            raise ValueError("history_capacity must be positive")
        self.symbol = symbol
        self.timeframe = timeframe
        self.instrument = instrument or InstrumentSpec(symbol=symbol, tick_size=Decimal("0.0001"), price_precision=5)
        self.history_capacity = history_capacity
        self.configuration = configuration or build_phase2_effective_config(symbol, timeframe, self.instrument, history_capacity)
        if self.configuration.symbol != symbol or self.configuration.timeframe != timeframe:
            raise ValueError("Phase2EffectiveConfiguration identity does not match pipeline symbol/timeframe")
        instrument_payload = {
            "symbol": self.instrument.symbol, "tick_size": str(self.instrument.tick_size),
            "price_precision": self.instrument.price_precision, "volume_step": str(self.instrument.volume_step),
            "contract_size": str(self.instrument.contract_size), "timezone": self.instrument.timezone,
            "asset_class": self.instrument.asset_class,
        }
        if {k: str(v) for k, v in self.configuration.instrument.items()} != {k: str(v) for k, v in instrument_payload.items()} or self.configuration.history_capacity != history_capacity:
            raise ValueError("Phase2EffectiveConfiguration identity does not match pipeline instrument/history")
        self.configuration_version = self.configuration.version
        self.configuration_id = self.configuration.effective_config_id
        self.data_quality = DataQualityEngine(symbol=symbol)
        self.volatility = VolatilityEngine(symbol=symbol, timeframe=timeframe, **self.configuration.volatility)
        self.structure = StructureEngineV23(symbol=symbol, timeframe=timeframe, config=StructureConfig(**self.configuration.structure))
        self.flow = FlowEngine(symbol=symbol, timeframe=timeframe, **self.configuration.flow)
        self.regime = RegimeEngine(symbol=symbol, timeframe=timeframe, **self.configuration.regime)
        self.pde = PDEEngine(symbol=symbol, timeframe=timeframe, **self.configuration.pde)
        self.location = LocationEngine(symbol=symbol, timeframe=timeframe, **self.configuration.location)
        self.role = RoleEngine(symbol=symbol, timeframe=timeframe)
        self.context_builder = Phase2ContextBuilder()
        self.evidence = EvidenceAggregator()
        self.root_id = f"root:{symbol}:{timeframe}"
        self.feature_version = 1
        self._historical_evaluations: dict[int, Phase2Evaluation] = {}
        self._last_watermark = (-1, -1)
        self._fault_injection_stage: str | None = None

    def _validity_until(self, timestamp: int) -> int:
        from src.fractal_flow.domain.envelope import StateEnvelope
        return timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe)

    _ENGINE_FIELDS = (
        "data_quality", "volatility", "structure", "flow", "regime",
        "pde", "location", "role", "evidence",
    )

    @staticmethod
    def _canonical_state_value(value: Any) -> Any:
        """Convert pipeline state into deterministic JSON-safe primitives for hashing."""
        from enum import Enum
        if isinstance(value, Decimal):
            return {"__decimal__": str(value)}
        if isinstance(value, Enum):
            return {"__enum__": f"{type(value).__module__}.{type(value).__qualname__}", "value": value.value}
        if hasattr(value, "__dataclass_fields__"):
            return Phase2Pipeline._canonical_state_value(asdict(value))
        if isinstance(value, dict):
            return {str(k): Phase2Pipeline._canonical_state_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
        if isinstance(value, (list, tuple)):
            return [Phase2Pipeline._canonical_state_value(v) for v in value]
        if isinstance(value, set):
            values = [Phase2Pipeline._canonical_state_value(v) for v in value]
            return sorted(values, key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")))
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"Unsupported pipeline state value for deterministic hashing: {type(value)!r}")

    def state_hash(self) -> str:
        """Return a deterministic hash of committed pipeline state."""
        canonical = self._canonical_state_value(self.snapshot_state())
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _stage_transaction(self) -> "Phase2Pipeline":
        """Stage engine state with copy-on-write for append/replace-only caches.

        Mutable engine authority is deeply isolated.  Bounded/append-only caches
        whose elements are immutable evidence are copied at the container level,
        preventing quadratic transaction cost while retaining nested mutation
        isolation for authoritative state.
        """
        staged = object.__new__(type(self))
        shallow_caches = {
            "data_quality": {"seen_fingerprints"},
            "volatility": {"_tr_history", "_close_history", "_range_history", "_atr_history"},
            "flow": {"_history"},
            "structure": {"_historical_records"},
        }
        for field in self._ENGINE_FIELDS:
            engine = getattr(self, field)
            engine_copy = copy(engine)
            for key, value in engine.__dict__.items():
                if key in shallow_caches.get(field, set()):
                    if isinstance(value, dict):
                        setattr(engine_copy, key, dict(value))
                    elif isinstance(value, set):
                        setattr(engine_copy, key, set(value))
                    elif isinstance(value, list):
                        setattr(engine_copy, key, list(value))
                    else:
                        setattr(engine_copy, key, value)
                elif field == "structure" and key == "_historical_projections":
                    setattr(engine_copy, key, deepcopy(value))
                else:
                    setattr(engine_copy, key, deepcopy(value))
            setattr(staged, field, engine_copy)
        for field in ("symbol", "timeframe", "instrument", "history_capacity", "configuration",
                      "configuration_version", "configuration_id", "root_id", "feature_version",
                      "context_builder", "_last_watermark", "_fault_injection_stage"):
            setattr(staged, field, getattr(self, field))
        staged._historical_evaluations = dict(self._historical_evaluations)
        return staged

    def _commit_transaction(self, working: "Phase2Pipeline") -> None:
        """Publish a successfully validated working state as the new committed state."""
        for field in self._ENGINE_FIELDS:
            setattr(self, field, getattr(working, field))
        self._last_watermark = working._last_watermark
        self._historical_evaluations = working._historical_evaluations

    def _raise_if_fault_injected(self, stage: str) -> None:
        """Test-only failpoint; production behaviour is unchanged when unset."""
        if self._fault_injection_stage == stage:
            raise RuntimeError(f"injected phase2 failure after stage: {stage}")

    @contextmanager
    def inject_fault_after(self, stage: str) -> Iterator[None]:
        """Inject one deterministic failure after a named pipeline stage.

        This is intentionally a narrow test seam: the failpoint is not part of
        persisted snapshot state and is never published as pipeline state.
        """
        if not stage:
            raise ValueError("stage must be non-empty")
        previous = self._fault_injection_stage
        self._fault_injection_stage = stage
        try:
            yield
        finally:
            self._fault_injection_stage = previous

    @contextmanager
    def _bar_transaction(self) -> Iterator["Phase2Pipeline"]:
        """Stage a bar on an isolated copy and publish only after successful completion."""
        working = self._stage_transaction()
        try:
            yield working
        except Exception:
            # Discard the isolated working state. The committed aggregate was never mutated.
            raise
        else:
            self._commit_transaction(working)

    def process_bar(self, bar: Bar) -> Phase2Evaluation:
        """Process exactly one bar using stage-then-commit atomicity."""
        with self._bar_transaction() as working:
            return working._process_bar_uncommitted(bar)

    def _process_bar_uncommitted(self,bar:Bar)->Phase2Evaluation:
        if not bar.is_closed: raise ValueError("Phase2Pipeline accepts closed bars only")
        watermark=(bar.close_timestamp,bar.sequence)
        if watermark<=self._last_watermark: raise ValueError("Phase2Pipeline rejects duplicate or out-of-order bars")
        dq=self.data_quality.evaluate_bar(bar)
        self._raise_if_fault_injected("data_quality")
        if not dq.exposure_allowed: raise ValueError(f"Phase2Pipeline fail-closed on data quality: {dq.state.value}")
        vol=self.volatility.update_bar(bar); self._raise_if_fault_injected("volatility"); v_local=vol.atr_14
        if v_local<=0: raise ValueError("Phase2Pipeline requires valid local volatility")
        structure=self.structure.process_bar(bar,v_local,self.root_id,"market",max(1,bar.sequence),data_version=bar.data_version)
        self._raise_if_fault_injected("structure")
        flow=self.flow.process_bar(bar,v_local,self.root_id,"market",max(1,bar.sequence),data_version=bar.data_version)
        self._raise_if_fault_injected("flow")
        regime=self.regime.process_bar(bar,v_local,self.root_id,"market",max(1,bar.sequence),data_version=bar.data_version,feature_version=self.feature_version,configuration_version=self.configuration_version)
        self._raise_if_fault_injected("regime")
        pde=self.pde.process_bar(bar,v_local,flow.evidence.imbalance,self.structure.structural_ownership,regime.state.value,self.root_id,"market",max(1,bar.sequence),bar.data_version,self.feature_version,self.configuration_version)
        self._raise_if_fault_injected("pde")
        support=self.structure.protected_low; resistance=self.structure.protected_high
        location=self.location.evaluate(bar.close_timestamp,bar.close,v_local,support,resistance,bar.spread,self.root_id,"market",max(1,bar.sequence),self.configuration_version,bar.data_version,self.feature_version)
        self._raise_if_fault_injected("location")
        role=self.role.evaluate(bar.close_timestamp,self.structure.structural_ownership,flow.flow_state.value,regime.state.value,pde.state.value,location.state.value,True,structure.bos_type,self.root_id,"market",max(1,bar.sequence),self.configuration_version,bar.data_version,self.feature_version,pde.resumption_state.value)
        self._raise_if_fault_injected("role")
        versions=EngineVersionSet(self.structure.state_version,flow.state_version,regime.version,pde.version,role.version,location.version,vol.version,self.evidence.version+1,dq.version)
        states={"structure":self.structure.structural_ownership,"flow":flow.flow_state.value,"regime":regime.state.value,"pde":pde.state.value,"pde_resumption":pde.resumption_state.value,"location":location.state.value,"role":role.state.value,"data_quality":dq.state.value,"volatility":vol.state.value}
        component_watermarks={"structure": structure.timestamp, "flow": flow.timestamp, "regime": regime.timestamp, "pde": pde.timestamp, "role": role.timestamp, "location": location.timestamp, "volatility": vol.timestamp, "data_quality": dq.last_timestamp or bar.close_timestamp}
        context=self.context_builder.build(self.root_id,self.symbol,self.timeframe,bar.close_timestamp,self.instrument,DataStatus.VALID,v_local,versions,self.feature_version,self.configuration_version,self.configuration_id,states,component_watermarks, sequence=bar.sequence)
        items=[
            EvidenceItem("structure", "Structure", "STRUCTURE", EvidenceDirection.LONG if self.structure.structural_ownership=="BULLISH" else EvidenceDirection.SHORT if self.structure.structural_ownership=="BEARISH" else EvidenceDirection.NEUTRAL, Decimal(1),bar.close_timestamp,self._validity_until(bar.close_timestamp),causal_parent=self.root_id,source_version=self.structure.state_version,root_id=self.root_id,parent_id="market",parent_version=max(1,bar.sequence),configuration_version=self.configuration_version,configuration_id=self.configuration_id,data_version=bar.data_version,feature_version=self.feature_version,engine_version=self.structure.state_version,causal_watermark=bar.close_timestamp),
            EvidenceItem("flow", "Flow", "FLOW", EvidenceDirection.LONG if flow.evidence.imbalance>0 else EvidenceDirection.SHORT if flow.evidence.imbalance<0 else EvidenceDirection.NEUTRAL,abs(flow.evidence.imbalance),bar.close_timestamp,self._validity_until(bar.close_timestamp),causal_parent=self.root_id,source_version=flow.state_version,root_id=self.root_id,parent_id="market",parent_version=max(1,bar.sequence),configuration_version=self.configuration_version,configuration_id=self.configuration_id,data_version=bar.data_version,feature_version=self.feature_version,engine_version=flow.state_version,causal_watermark=bar.close_timestamp),
            EvidenceItem("regime", "Regime", "REGIME", EvidenceDirection.LONG if regime.state.value=="TREND_UP" else EvidenceDirection.SHORT if regime.state.value=="TREND_DOWN" else EvidenceDirection.NEUTRAL,regime.efficiency,bar.close_timestamp,regime.valid_until,causal_parent=self.root_id,source_version=regime.version,root_id=self.root_id,parent_id="market",parent_version=max(1,bar.sequence),configuration_version=self.configuration_version,configuration_id=self.configuration_id,data_version=bar.data_version,feature_version=self.feature_version,engine_version=regime.version,causal_watermark=bar.close_timestamp),
            EvidenceItem("pde", "PDE", "EPISODE", EvidenceDirection.LONG if pde.direction=="LONG" else EvidenceDirection.SHORT if pde.direction=="SHORT" else EvidenceDirection.NEUTRAL,pde.recovery_ratio,bar.close_timestamp,pde.valid_until,causal_parent=pde.episode_id,source_version=pde.version,correlation_group="EPISODE",root_id=self.root_id,parent_id="market",parent_version=max(1,bar.sequence),configuration_version=self.configuration_version,configuration_id=self.configuration_id,data_version=bar.data_version,feature_version=self.feature_version,engine_version=pde.version,causal_watermark=bar.close_timestamp),
            EvidenceItem("location", "Location", "LOCATION", EvidenceDirection.NEUTRAL,Decimal(1)/(Decimal(1)+location.normalized_distance),bar.close_timestamp,location.valid_until,causal_parent=self.root_id,source_version=location.version,correlation_group="LOCATION",root_id=self.root_id,parent_id="market",parent_version=max(1,bar.sequence),configuration_version=self.configuration_version,configuration_id=self.configuration_id,data_version=bar.data_version,feature_version=self.feature_version,engine_version=location.version,causal_watermark=bar.close_timestamp),
        ]
        summary=self.evidence.summarize(items,now=bar.close_timestamp)
        self._raise_if_fault_injected("evidence")
        evaluation=Phase2Evaluation(bar,vol,structure,flow,regime,pde,location,role,context,summary)
        self._last_watermark=watermark; self._historical_evaluations[bar.close_timestamp]=deepcopy(evaluation)
        self._raise_if_fault_injected("historical_commit")
        while len(self._historical_evaluations)>self.history_capacity: self._historical_evaluations.pop(min(self._historical_evaluations))
        return evaluation

    def historical_evaluation(self,as_of:int)->Phase2Evaluation|None:
        eligible=[ts for ts in self._historical_evaluations if ts<=as_of]
        return deepcopy(self._historical_evaluations[max(eligible)]) if eligible else None

    def historical_status(self, as_of: int) -> str:
        """Distinguish an unavailable history point from an evicted bounded point."""
        if as_of in self._historical_evaluations:
            return "AVAILABLE"
        if self._historical_evaluations and as_of < min(self._historical_evaluations):
            return "EVICTED"
        return "UNKNOWN"

    def snapshot_state(self)->dict:
        """Bounded, reconstructable pipeline snapshot. Historical evaluations are cache only."""
        return {"schema_version":self.SNAPSHOT_SCHEMA,"symbol":self.symbol,"timeframe":self.timeframe,"instrument":deepcopy(self.instrument),"history_capacity":self.history_capacity,"root_id":self.root_id,"configuration_version":self.configuration_version,"configuration_id":self.configuration_id,"configuration":self.configuration.canonical_payload(),"feature_version":self.feature_version,"last_watermark":self._last_watermark,"data_quality":deepcopy(self.data_quality.__dict__),"volatility":deepcopy(self.volatility.__dict__),"structure":deepcopy(self.structure.snapshot_state()),"flow":deepcopy(self.flow.__dict__),"regime":deepcopy(self.regime.__dict__),"pde":deepcopy(self.pde.__dict__),"location":deepcopy(self.location.__dict__),"role":deepcopy(self.role.__dict__),"evidence":deepcopy(self.evidence.__dict__),"historical_evaluations":deepcopy(self._historical_evaluations)}

    @classmethod
    def from_snapshot_state(cls,payload:dict)->"Phase2Pipeline":
        if payload.get("schema_version")!=cls.SNAPSHOT_SCHEMA: raise ValueError(f"Unsupported Phase2Pipeline snapshot schema: {payload.get('schema_version')!r}")
        configuration_payload = payload.get("configuration")
        if not isinstance(configuration_payload, dict):
            raise ValueError("Phase2 snapshot lacks canonical effective configuration")
        from src.fractal_flow.config.config import Phase2EffectiveConfiguration
        configuration = Phase2EffectiveConfiguration.from_canonical_payload(dict(configuration_payload))
        p=cls(payload["symbol"],payload["timeframe"],payload["instrument"],int(payload["history_capacity"]),configuration=configuration)
        p.root_id=payload["root_id"]; p.configuration_version=int(payload["configuration_version"]); p.configuration_id=str(payload["configuration_id"]); p.feature_version=int(payload["feature_version"]);
        if p.configuration_id != configuration.effective_config_id:
            raise ValueError("Phase2 snapshot configuration identity mismatch")
        p._last_watermark=tuple(payload["last_watermark"])
        p.data_quality.__dict__.update(deepcopy(payload["data_quality"])); p.volatility.__dict__.update(deepcopy(payload["volatility"])); p.structure=StructureEngineV23.from_snapshot_state(deepcopy(payload["structure"])); p.flow.__dict__.update(deepcopy(payload["flow"])); p.regime.__dict__.update(deepcopy(payload["regime"])); p.pde.__dict__.update(deepcopy(payload["pde"])); p.location.__dict__.update(deepcopy(payload["location"])); p.role.__dict__.update(deepcopy(payload["role"])); p.evidence.__dict__.update(deepcopy(payload["evidence"])); p._historical_evaluations=deepcopy(payload.get("historical_evaluations",{})); return p

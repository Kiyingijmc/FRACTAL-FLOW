"""Deterministic contextual regime engine with canonical transition enforcement."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY, StateEnvelope
from src.fractal_flow.domain.market import Bar

@unique
class RegimeState(str, Enum):
    UNKNOWN="UNKNOWN"; TREND_UP="TREND_UP"; TREND_DOWN="TREND_DOWN"; RANGE="RANGE"; TRANSITION="TRANSITION"; CHAOTIC="CHAOTIC"

@dataclass(frozen=True)
class RegimeEvidence:
    state: RegimeState
    efficiency: Decimal
    persistence: Decimal
    volatility_ratio: Decimal
    compression: Decimal
    dispersion: Decimal
    timestamp: int
    version: int
    root_id: str = ""
    parent_id: str = ""
    parent_version: int = 1
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    causal_watermark: int | None = None
    valid_until: int | None = None
    authority: str = "Regime"
    reason_codes: tuple[str, ...] = ()

class RegimeEngine:
    def __init__(self, symbol: str, timeframe: str = "1M", window: int = 10, dwell_bars: int = 2,
                 efficiency_trend: Decimal = Decimal("0.55"), efficiency_range: Decimal = Decimal("0.20"),
                 persistence_trend: Decimal = Decimal("0.35"), compression_range: Decimal = Decimal("0.60"),
                 chaos_dispersion: Decimal = Decimal("2.5"), chaos_volatility_ratio: Decimal = Decimal("2.5")) -> None:
        self.symbol, self.timeframe = symbol, timeframe
        self.window, self.dwell_bars = max(3, window), max(1, dwell_bars)
        self.efficiency_trend, self.efficiency_range = efficiency_trend, efficiency_range
        self.persistence_trend, self.compression_range = persistence_trend, compression_range
        self.chaos_dispersion, self.chaos_volatility_ratio = chaos_dispersion, chaos_volatility_ratio
        self.state=RegimeState.UNKNOWN; self._previous_state=RegimeState.UNKNOWN; self.version=0
        self._last_timestamp=-1; self._last_root_id=""; self._last_parent_id="market"; self._last_parent_version=1; self._last_configuration_version=1; self._last_data_version=1; self._last_feature_version=1
        self._closes:list[Decimal]=[]; self._ranges:list[Decimal]=[]; self._candidate:RegimeState|None=None; self._candidate_count=0; self._last_timestamp=-1

    def _classify(self, efficiency:Decimal, persistence:Decimal, vol_ratio:Decimal, compression:Decimal, dispersion:Decimal)->RegimeState:
        if dispersion >= self.chaos_dispersion or vol_ratio >= self.chaos_volatility_ratio: return RegimeState.CHAOTIC
        if efficiency >= self.efficiency_trend and abs(persistence) >= self.persistence_trend:
            return RegimeState.TREND_UP if self._closes[-1] >= self._closes[0] else RegimeState.TREND_DOWN
        if efficiency <= self.efficiency_range and compression >= self.compression_range: return RegimeState.RANGE
        return RegimeState.TRANSITION

    def to_envelope(self, object_id: str) -> StateEnvelope:
        return StateEnvelope(
            state_id=f"regime_state_{object_id}_{self.version}", object_id=object_id, object_type="RegimeState",
            symbol=self.symbol, timeframe=self.timeframe, root_id=self._last_root_id, parent_id=self._last_parent_id,
            parent_version=self._last_parent_version, state=self.state.value, previous_state=self._previous_state.value,
            version=self.version, source_timestamp=self._last_timestamp, event_timestamp=self._last_timestamp,
            processing_timestamp=self._last_timestamp, valid_until=self._last_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe),
            last_seen=self._last_timestamp, configuration_version=self._last_configuration_version,
            data_version=self._last_data_version, feature_version=self._last_feature_version, authority="REGIME",
        )

    def process_bar(self, bar:Bar, v_local:Decimal, root_id:str="r0", parent_id:str="market", parent_version:int=1,
                    data_version:int=1, feature_version:int=1, configuration_version:int=1)->RegimeEvidence:
        AuthorityMatrix.verify_capability("Regime","WRITE_REGIME_STATE")
        if bar.symbol!=self.symbol or v_local<=0: raise ValueError("RegimeEngine invalid symbol or volatility")
        if bar.close_timestamp<=self._last_timestamp: raise ValueError("RegimeEngine requires strictly increasing bar timestamps")
        self._last_timestamp=bar.close_timestamp; self._last_root_id=root_id; self._last_parent_id=parent_id; self._last_parent_version=parent_version; self._last_configuration_version=configuration_version; self._last_data_version=data_version; self._last_feature_version=feature_version; self._closes.append(bar.close); self._ranges.append(bar.high-bar.low)
        if len(self._closes)>self.window: self._closes.pop(0); self._ranges.pop(0)
        if len(self._closes)<3:
            self.version+=1
            return RegimeEvidence(self.state,Decimal(0),Decimal(0),Decimal(0),Decimal(0),Decimal(0),bar.close_timestamp,self.version,root_id,parent_id,parent_version,configuration_version,data_version,feature_version,bar.close_timestamp,bar.close_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe),"Regime",("WARMUP",))
        deltas=[self._closes[i]-self._closes[i-1] for i in range(1,len(self._closes))]
        path=sum((abs(x) for x in deltas),Decimal(0)); net=self._closes[-1]-self._closes[0]
        efficiency=abs(net)/path if path>0 else Decimal(0)
        persistence=sum((Decimal(1) if x>0 else Decimal(-1) if x<0 else Decimal(0) for x in deltas),Decimal(0))/Decimal(len(deltas))
        mean_range=sum(self._ranges,Decimal(0))/Decimal(len(self._ranges)); vol_ratio=self._ranges[-1]/mean_range if mean_range>0 else Decimal(0)
        short=sum(self._ranges[-min(3,len(self._ranges)):],Decimal(0))/Decimal(min(3,len(self._ranges)))
        compression=max(Decimal(0),min(Decimal(1),Decimal(1)-(short/mean_range if mean_range>0 else Decimal(1))))
        dispersion=abs(persistence)/max(efficiency,Decimal("0.05")) if efficiency>0 else Decimal(0)
        candidate=self._classify(efficiency,persistence,vol_ratio,compression,dispersion)
        if candidate!=self.state:
            if candidate==self._candidate: self._candidate_count+=1
            else: self._candidate,self._candidate_count=candidate,1
            if self._candidate_count>=self.dwell_bars:
                path = GLOBAL_STATE_REGISTRY.resolve_transition("RegimeState", self.state.value, candidate.value)
                for next_state in path:
                    self._previous_state = self.state
                    self.state = RegimeState(next_state)
                self._candidate=None; self._candidate_count=0
        self.version+=1
        return RegimeEvidence(self.state,efficiency,persistence,vol_ratio,compression,dispersion,bar.close_timestamp,self.version,root_id,parent_id,parent_version,configuration_version,data_version,feature_version,bar.close_timestamp,bar.close_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe),"Regime")

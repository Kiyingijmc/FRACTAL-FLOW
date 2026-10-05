"""Geometric location engine. It describes location; it does not authorize risk."""
from enum import Enum, unique
from dataclasses import dataclass
from decimal import Decimal
from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY, StateEnvelope

@unique
class LocationState(str, Enum):
    OPEN="OPEN"; FAVORABLE="FAVORABLE"; NEUTRAL="NEUTRAL"; CONGESTED="CONGESTED"; BLOCKED="BLOCKED"; EXTREME="EXTREME"

@dataclass(frozen=True)
class LocationEvidence:
    state: LocationState; distance_to_support: Decimal; distance_to_resistance: Decimal; normalized_distance: Decimal; timestamp: int; version: int
    root_id: str=""; parent_id: str=""; parent_version:int=1; configuration_version:int=1; data_version:int=1; feature_version:int=1; causal_watermark:int|None=None; valid_until:int|None=None; authority:str="Location"; reason_codes:tuple[str,...]=()

class LocationEngine:
    def to_envelope(self, object_id: str) -> StateEnvelope:
        return StateEnvelope(state_id=f"location_state_{object_id}_{self.version}", object_id=object_id, object_type="LocationState", symbol=self.symbol, timeframe=self.timeframe, root_id=self._root_id, parent_id=self._parent_id, parent_version=self._parent_version, state=self.state.value, previous_state=self._previous_state.value, version=self.version, source_timestamp=self._last_timestamp, event_timestamp=self._last_timestamp, processing_timestamp=self._last_timestamp, valid_until=self._last_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe), last_seen=self._last_timestamp, configuration_version=self._configuration_version, data_version=self._data_version, feature_version=self._feature_version, authority="LOCATION")

    def __init__(self,symbol:str,timeframe:str="1M",congestion_threshold:Decimal=Decimal("0.5"),extreme_threshold:Decimal=Decimal("2.0")):
        self.symbol=symbol; self.timeframe=timeframe; self.congestion_threshold=congestion_threshold; self.extreme_threshold=extreme_threshold; self.state=LocationState.OPEN; self._previous_state=LocationState.OPEN; self.version=0; self._last_timestamp=-1; self._root_id=""; self._parent_id="market"; self._parent_version=1; self._configuration_version=1; self._data_version=1; self._feature_version=1
    def evaluate(self,timestamp:int,price:Decimal,volatility:Decimal,support:Decimal|None,resistance:Decimal|None,spread:Decimal=Decimal("0"),root_id:str="",parent_id:str="market",parent_version:int=1,configuration_version:int=1,data_version:int=1,feature_version:int=1)->LocationEvidence:
        AuthorityMatrix.verify_capability("Location","WRITE_LOCATION_STATE")
        if volatility<=0: raise ValueError("LocationEngine requires positive volatility")
        if timestamp<=self._last_timestamp: raise ValueError("LocationEngine requires strictly increasing timestamps")
        self._last_timestamp=timestamp; self._root_id=root_id; self._parent_id=parent_id; self._parent_version=parent_version; self._configuration_version=configuration_version; self._data_version=data_version; self._feature_version=feature_version
        ds=abs(price-support)/volatility if support is not None else Decimal("999"); dr=abs(resistance-price)/volatility if resistance is not None else Decimal("999"); nearest=min(ds,dr)
        # Spread is descriptive context; BLOCKED is reserved for an extreme local
        # congestion condition rather than treating every wide spread as authority.
        if spread>volatility*Decimal("2") and nearest<=self.congestion_threshold: state=LocationState.BLOCKED; reason="WIDE_SPREAD_AND_CONGESTION"
        elif nearest<=self.congestion_threshold: state=LocationState.CONGESTED; reason="NEAR_STRUCTURAL_LEVEL"
        elif (ds<=self.congestion_threshold and dr>=self.extreme_threshold) or (dr<=self.congestion_threshold and ds>=self.extreme_threshold): state=LocationState.EXTREME; reason="ONE_SIDED_STRUCTURAL_EXTREME"
        elif support is None and resistance is None: state=LocationState.OPEN; reason="NO_STRUCTURAL_BOUNDARY"
        elif nearest>=self.extreme_threshold: state=LocationState.FAVORABLE; reason="DISTANT_FROM_BOUNDARIES"
        else: state=LocationState.NEUTRAL; reason="MID_STRUCTURE"
        if state!=self.state: GLOBAL_STATE_REGISTRY.validate_transition("LocationState",self.state.value,state.value)
        self._previous_state=self.state; self.state=state; self.version+=1
        return LocationEvidence(state,ds,dr,nearest,timestamp,self.version,root_id,parent_id,parent_version,configuration_version,data_version,feature_version,timestamp,timestamp+300,"Location",(reason,))

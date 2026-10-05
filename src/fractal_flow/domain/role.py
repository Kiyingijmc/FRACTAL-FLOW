"""Typed semantic Role projection with explicit precedence and reasons."""
from enum import Enum, unique
from dataclasses import dataclass
from src.fractal_flow.domain.authority import AuthorityMatrix
from src.fractal_flow.domain.envelope import GLOBAL_STATE_REGISTRY, StateEnvelope

@unique
class RoleState(str, Enum):
    UNKNOWN="UNKNOWN"; CONTINUATION="CONTINUATION"; PULLBACK="PULLBACK"; COUNTERFLOW="COUNTERFLOW"; RANGE_ROTATION="RANGE_ROTATION"; BREAKOUT="BREAKOUT"; RECLAIM="RECLAIM"; TRANSITION="TRANSITION"; EXHAUSTION="EXHAUSTION"; NOISE="NOISE"; AMBIGUOUS="AMBIGUOUS"

@dataclass(frozen=True)
class RoleEvidence:
    state: RoleState
    reason: str
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
    authority: str = "Role"
    reason_codes: tuple[str, ...] = ()

class RoleEngine:
    # Semantic conflict-resolution policy. Branch order below is authoritative and
    # this tuple makes the precedence auditable rather than implicit in control flow.
    PRECEDENCE = (
        "DATA_UNAVAILABLE", "LOCATION_BLOCKED", "PDE_PULLBACK",
        "STRUCTURAL_RECLAIM", "STRUCTURAL_BREAK", "CHARACTER_CHANGE",
        "PDE_RESUMPTION", "RANGE_REGIME", "EXPECTED_COUNTERFLOW",
        "REGIME_TRANSITION", "STRUCTURE_FLOW_ALIGNMENT", "AMBIGUOUS",
    )
    def to_envelope(self, object_id: str) -> StateEnvelope:
        return StateEnvelope(state_id=f"role_state_{object_id}_{self.version}", object_id=object_id, object_type="RoleState", symbol=self.symbol, timeframe=self.timeframe, root_id=self._root_id, parent_id=self._parent_id, parent_version=self._parent_version, state=self.state.value, previous_state=self._previous_state.value, version=self.version, source_timestamp=self._last_timestamp, event_timestamp=self._last_timestamp, processing_timestamp=self._last_timestamp, valid_until=self._last_timestamp + StateEnvelope.calculate_timeframe_validity_seconds(self.timeframe), last_seen=self._last_timestamp, configuration_version=self._configuration_version, data_version=self._data_version, feature_version=self._feature_version, authority="ROLE")

    def __init__(self,symbol:str,timeframe:str="1M")->None:
        self.symbol=symbol; self.timeframe=timeframe; self.state=RoleState.UNKNOWN; self._previous_state=RoleState.UNKNOWN; self.version=0; self._last_timestamp=-1; self._root_id=""; self._parent_id="market"; self._parent_version=1; self._configuration_version=1; self._data_version=1; self._feature_version=1
    def evaluate(self,timestamp:int,structure_direction:str,flow_state:str,regime_state:str,pde_state:str,location_state:str,data_valid:bool=True,structural_event:str="NONE",root_id:str="",parent_id:str="market",parent_version:int=1,configuration_version:int=1,data_version:int=1,feature_version:int=1,pde_resumption_state:str="RESUMPTION_NONE")->RoleEvidence:
        AuthorityMatrix.verify_capability("Role","WRITE_ROLE_STATE")
        if timestamp<=self._last_timestamp: raise ValueError("RoleEngine requires strictly increasing timestamps")
        self._last_timestamp=timestamp; self._root_id=root_id; self._parent_id=parent_id; self._parent_version=parent_version; self._configuration_version=configuration_version; self._data_version=data_version; self._feature_version=feature_version
        if not data_valid: state,reason=RoleState.UNKNOWN,"DATA_UNAVAILABLE"
        elif location_state=="BLOCKED": state,reason=RoleState.NOISE,"LOCATION_BLOCKED"
        elif pde_state in {"PDE_PULLBACK_CANDIDATE","PDE_PULLBACK_ACTIVE","PDE_WEAKENING","PDE_STRENGTHENING","PDE_DEEPENING"}: state,reason=RoleState.PULLBACK,"PDE_PULLBACK"
        elif structural_event=="RECLAIM_CONFIRMED": state,reason=RoleState.RECLAIM,"STRUCTURAL_RECLAIM"
        elif structural_event.startswith("BOS_"): state,reason=RoleState.BREAKOUT,"STRUCTURAL_BREAK"
        elif structural_event.startswith("CHOCH_"): state,reason=RoleState.TRANSITION,"CHARACTER_CHANGE"
        elif pde_state=="PDE_RESUMPTION_IN_PROGRESS" or pde_resumption_state in {"RESUMPTION_CONFIRMED","FOLLOW_THROUGH"}: state,reason=RoleState.CONTINUATION,"PDE_RESUMPTION"
        elif regime_state=="RANGE": state,reason=RoleState.RANGE_ROTATION,"RANGE_REGIME"
        elif structure_direction in ("LONG","BULLISH") and flow_state.startswith("SHORT"): state,reason=RoleState.COUNTERFLOW,"EXPECTED_COUNTERFLOW"
        elif structure_direction in ("SHORT","BEARISH") and flow_state.startswith("LONG"): state,reason=RoleState.COUNTERFLOW,"EXPECTED_COUNTERFLOW"
        elif regime_state=="TRANSITION": state,reason=RoleState.TRANSITION,"REGIME_TRANSITION"
        elif structure_direction in ("LONG","SHORT") and flow_state.startswith(structure_direction): state,reason=RoleState.CONTINUATION,"STRUCTURE_FLOW_ALIGNMENT"
        else: state,reason=RoleState.AMBIGUOUS,"INSUFFICIENT_SEMANTIC_SEPARATION"
        if state!=self.state:
            GLOBAL_STATE_REGISTRY.validate_transition("RoleState",self.state.value,state.value)
        self._previous_state=self.state; self.state=state; self.version+=1
        return RoleEvidence(state,reason,timestamp,self.version,root_id,parent_id,parent_version,configuration_version,data_version,feature_version,timestamp,timestamp+300,"Role",(reason,))

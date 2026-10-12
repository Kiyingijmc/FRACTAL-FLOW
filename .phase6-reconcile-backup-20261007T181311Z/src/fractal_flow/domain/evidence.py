"""Immutable evidence, contradiction and model-health primitives."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from typing import Iterable

@unique
class EvidenceDirection(str, Enum):
    LONG="LONG"; SHORT="SHORT"; NEUTRAL="NEUTRAL"; CONFLICT="CONFLICT"

@unique
class ContradictionKind(str, Enum):
    DIRECT_CONFLICT="DIRECT_CONFLICT"; CONTEXTUAL_CONFLICT="CONTEXTUAL_CONFLICT"; STALE_CONFLICT="STALE_CONFLICT"; DATA_CONFLICT="DATA_CONFLICT"; MODEL_CONFLICT="MODEL_CONFLICT"; EXPECTED_COUNTERFLOW="EXPECTED_COUNTERFLOW"

@unique
class ModelHealth(str, Enum):
    UNKNOWN="UNKNOWN"; HEALTHY="HEALTHY"; DEGRADED="DEGRADED"; INCONSISTENT="INCONSISTENT"

@dataclass(frozen=True)
class EvidenceItem:
    evidence_id:str; source:str; family:str; direction:EvidenceDirection; magnitude:Decimal; timestamp:int; valid_until:int|None
    quality:Decimal=Decimal("1"); correlation_group:str="DEFAULT"; causal_parent:str=""; source_version:int=1
    root_id:str=""; parent_id:str=""; parent_version:int=1; configuration_version:int=1; configuration_id:str=""; data_version:int=1; feature_version:int=1; engine_version:int=1; causal_watermark:int|None=None; reason_codes:tuple[str,...]=()
    def __post_init__(self)->None:
        if not self.evidence_id or not self.source or not self.family: raise ValueError("EvidenceItem requires identity, source and family")
        if self.configuration_version <= 0: raise ValueError("EvidenceItem configuration_version must be positive")
        if self.timestamp<0 or self.magnitude<0 or not Decimal(0)<=self.quality<=Decimal(1): raise ValueError("EvidenceItem has invalid magnitude, timestamp or quality")
        if self.valid_until is not None and self.valid_until<self.timestamp: raise ValueError("Evidence valid_until cannot precede timestamp")
        if self.causal_watermark is not None and self.causal_watermark<self.timestamp: raise ValueError("Evidence causal watermark cannot precede timestamp")
    def weight(self,now:int|None=None,half_life_bars:int|None=None)->Decimal:
        if self.valid_until is not None and now is not None and now>self.valid_until: return Decimal(0)
        if half_life_bars is None or now is None or now<=self.timestamp: return self.magnitude*self.quality
        age=Decimal(max(0,now-self.timestamp)); half=Decimal(max(1,half_life_bars)); return self.magnitude*self.quality*(Decimal(2)**(-(age/half)))

@dataclass(frozen=True)
class Contradiction:
    kind:ContradictionKind; sources:tuple[str,...]; reason:str; timestamp:int

@dataclass(frozen=True)
class EvidenceSummary:
    long_score:Decimal; short_score:Decimal; contradiction:bool; contributing_families:tuple[str,...]; conflicting_families:tuple[str,...]
    contradictions:tuple[Contradiction,...]=(); model_health:ModelHealth=ModelHealth.UNKNOWN; evidence_count:int=0

class EvidenceAggregator:
    def __init__(self,family_cap:Decimal=Decimal("1.0"),total_cap:Decimal=Decimal("3.0"),max_items:int=128)->None:
        if family_cap<=0 or total_cap<=0 or max_items<=0: raise ValueError("Evidence caps must be positive")
        self.family_cap=family_cap; self.total_cap=total_cap; self.max_items=max_items; self.version=0
    def summarize(self,items:Iterable[EvidenceItem],now:int|None=None)->EvidenceSummary:
        items=tuple(items)
        if len(items)>self.max_items: raise ValueError(f"Evidence item count exceeds bounded capacity {self.max_items}")
        by_family={}; family_direction={}; long_score=Decimal(0); short_score=Decimal(0); conflict=set(); families=set(); used_groups=set(); contradictions=[]
        families.update(item.family for item in items)
        ranked=sorted(items,key=lambda x:(x.weight(now),x.evidence_id),reverse=True)
        for item in ranked:
            w=item.weight(now)
            if w<=0 or item.correlation_group in used_groups: continue
            current=by_family.get(item.family,Decimal(0)); contribution=min(w,max(Decimal(0),self.family_cap-current))
            if contribution<=0: continue
            by_family[item.family]=current+contribution; used_groups.add(item.correlation_group); families.add(item.family)
            previous=family_direction.get(item.family)
            if previous is not None and previous!=item.direction and item.direction not in (EvidenceDirection.NEUTRAL,EvidenceDirection.CONFLICT):
                conflict.add(item.family); contradictions.append(Contradiction(ContradictionKind.DIRECT_CONFLICT,(item.source,),f"family {item.family} has opposing directional evidence",item.timestamp))
            elif item.direction in (EvidenceDirection.LONG,EvidenceDirection.SHORT): family_direction[item.family]=item.direction
            if item.direction==EvidenceDirection.LONG: long_score+=contribution
            elif item.direction==EvidenceDirection.SHORT: short_score+=contribution
            if long_score+short_score>=self.total_cap: break
        total=max(Decimal(1),long_score+short_score)
        self.version+=1
        balanced_conflict=long_score>0 and short_score>0 and abs(long_score-short_score)<Decimal("0.10")
        if balanced_conflict: contradictions.append(Contradiction(ContradictionKind.CONTEXTUAL_CONFLICT,tuple(sorted({x.source for x in items if x.direction in (EvidenceDirection.LONG,EvidenceDirection.SHORT)})),"directional evidence is materially balanced",now or 0))
        health=ModelHealth.INCONSISTENT if contradictions else ModelHealth.HEALTHY if items else ModelHealth.UNKNOWN
        return EvidenceSummary(min(self.total_cap,long_score)/total,min(self.total_cap,short_score)/total,bool(contradictions),tuple(sorted(families)),tuple(sorted(conflict)),tuple(contradictions),health,len(items))

"""Phase 3 multi-timeframe behavioral orchestration and opportunity construction.

Phase 3 composes the authoritative Phase 2 engines into a deterministic, causal
MTF layer.  It remains informational: it may describe opportunity state, evidence,
structure and lifecycle, but it cannot authorize execution, risk or sizing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum, unique
import hashlib
import json
from typing import Any, Mapping, Iterable
from copy import deepcopy

from src.fractal_flow.domain.market import Timeframe
from src.fractal_flow.domain.models import Direction, OpportunityObject
from src.fractal_flow.domain.phase2 import Phase2Evaluation


@unique
class Phase3Role(str, Enum):
    CONTEXT = "CONTEXT"
    DIRECTION = "DIRECTION"
    STRUCTURE = "STRUCTURE"
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    CONFIRMATION = "CONFIRMATION"
    EXECUTION = "EXECUTION"
    MICRO = "MICRO"


@unique
class OpportunityState(str, Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    TRIGGER_READY = "TRIGGER_READY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class Phase3InvariantError(ValueError):
    """Raised when a Phase 3 causal, hierarchy, or lifecycle invariant is violated."""


@dataclass(frozen=True)
class TimeframeMapping:
    context: Timeframe = Timeframe.H4
    direction: Timeframe = Timeframe.H1
    structure: Timeframe = Timeframe.M30
    primary: Timeframe = Timeframe.M15
    secondary: Timeframe = Timeframe.M5
    confirmation: Timeframe = Timeframe.M1
    execution: Timeframe = Timeframe.M1
    micro: Timeframe = Timeframe.M1
    version: int = 1

    def __post_init__(self) -> None:
        values = {name: getattr(self, name) for name in (
            "context", "direction", "structure", "primary", "secondary",
            "confirmation", "execution", "micro")}
        for name, value in values.items():
            object.__setattr__(self, name, Timeframe.validate(value))
        if self.version <= 0:
            raise Phase3InvariantError("Timeframe mapping version must be positive")
        if not (self.context > self.direction > self.structure > self.primary >= self.secondary >= self.confirmation):
            raise Phase3InvariantError("context > direction > structure > primary > secondary >= confirmation is required")
        if self.execution > self.confirmation or self.micro > self.execution:
            raise Phase3InvariantError("execution/micro must not be higher than confirmation/execution")

    @classmethod
    def canonical(cls) -> "TimeframeMapping":
        return cls()

    def migrate_primary_down(self) -> "TimeframeMapping":
        """Move primary/confirmation authority one level down, stopping at M1.

        Canonical path is M15 -> M5 -> M1.  The lower layers are deliberately
        allowed to duplicate M1 because the execution boundary is the floor.
        """
        if self.primary == Timeframe.M15:
            return TimeframeMapping(
                context=self.context, direction=self.direction, structure=self.structure,
                primary=Timeframe.M5, secondary=Timeframe.M1, confirmation=Timeframe.M1,
                execution=Timeframe.M1, micro=Timeframe.M1, version=self.version + 1)
        if self.primary == Timeframe.M5:
            return TimeframeMapping(
                context=self.context, direction=self.direction, structure=self.structure,
                primary=Timeframe.M1, secondary=Timeframe.M1, confirmation=Timeframe.M1,
                execution=Timeframe.M1, micro=Timeframe.M1, version=self.version + 1)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k).value if isinstance(getattr(self, k), Enum) else getattr(self, k)
                for k in ("context", "direction", "structure", "primary", "secondary",
                          "confirmation", "execution", "micro", "version")}


@dataclass(frozen=True)
class MTFNode:
    role: Phase3Role
    timeframe: Timeframe
    evaluation_timestamp: int
    sequence: int
    engine_versions: tuple[tuple[str, int], ...]
    direction: str
    structure: str
    flow: str
    regime: str
    pde: str
    pde_resumption: str
    role_state: str
    location: str
    valid: bool
    pde_episode_id: str = ""
    pde_parent_id: str = ""
    pde_direction: str = ""
    pde_maturity: str = "UNKNOWN"
    pde_recovery_ratio: str = "0"
    pde_impulse_amplitude: str = "0"
    pde_pullback_depth: str = "0"
    pde_resumption_displacement: str = "0"
    pde_false_resumption_risk: str = "0"
    regime_efficiency: str = "0"
    regime_persistence: str = "0"
    configuration_id: str = ""
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    causal_watermark: int | None = None

    @classmethod
    def from_evaluation(cls, role: Phase3Role, evaluation: Phase2Evaluation) -> "MTFNode":
        pde = evaluation.pde
        structure = evaluation.structure
        flow = evaluation.flow
        regime = evaluation.regime
        role_e = evaluation.role
        location = evaluation.location
        config_id = getattr(evaluation.context, "configuration_id", "")
        return cls(
            role=role, timeframe=Timeframe.validate(evaluation.bar.timeframe),
            evaluation_timestamp=evaluation.bar.close_timestamp, sequence=evaluation.bar.sequence,
            engine_versions=(("structure", structure.state_version), ("flow", flow.state_version),
                             ("regime", regime.version), ("pde", pde.version),
                             ("role", role_e.version), ("location", location.version),
                             ("volatility", evaluation.volatility.version)),
            direction=pde.direction, structure=structure.structural_ownership,
            flow=flow.flow_state.value, regime=regime.state.value, pde=pde.state.value,
            pde_resumption=pde.resumption_state.value, role_state=role_e.state.value,
            location=location.state.value,
            valid=evaluation.context.is_usable(evaluation.bar.close_timestamp),
            pde_episode_id=getattr(pde, "episode_id", ""), pde_parent_id=getattr(pde, "parent_id", ""),
            pde_direction=pde.direction, pde_recovery_ratio=str(getattr(pde, "recovery_ratio", 0)),
            pde_impulse_amplitude=str(getattr(pde, "impulse_amplitude", 0)),
            pde_pullback_depth=str(getattr(pde, "pullback_depth", 0)),
            pde_resumption_displacement=str(getattr(pde, "resumption_displacement", 0)),
            pde_maturity=_pde_maturity(pde),
            pde_false_resumption_risk=_false_resumption_risk(pde),
            regime_efficiency=str(getattr(regime, "efficiency", 0)), regime_persistence=str(getattr(regime, "persistence", 0)),
            configuration_id=config_id,
            configuration_version=getattr(regime, "configuration_version", 1),
            data_version=getattr(regime, "data_version", 1),
            feature_version=getattr(regime, "feature_version", 1),
            causal_watermark=getattr(pde, "causal_watermark", evaluation.bar.close_timestamp),
        )


@dataclass(frozen=True)
class MTFParentBinding:
    parent_role: Phase3Role
    child_role: Phase3Role
    parent_timestamp: int
    child_timestamp: int
    parent_pde_version: int
    child_pde_version: int
    parent_episode_id: str = ""
    child_episode_id: str = ""
    parent_direction: str = ""
    child_direction: str = ""
    containment: str = "UNKNOWN"


@dataclass(frozen=True)
class EvidencePolicy:
    """Versioned deterministic Phase 3 evidence policy.

    The policy is descriptive only.  It cannot authorize execution, risk, or
    sizing.  Versioning makes historical evidence interpretation replay-safe.
    """

    version: int = 1
    context: Decimal = Decimal("0.25")
    direction: Decimal = Decimal("0.50")
    structure: Decimal = Decimal("0.75")
    primary: Decimal = Decimal("1.00")
    secondary: Decimal = Decimal("0.80")
    confirmation: Decimal = Decimal("0.70")
    execution: Decimal = Decimal("0.50")
    micro: Decimal = Decimal("0.40")

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise Phase3InvariantError("Evidence policy version must be positive")
        if any(value < 0 for value in (self.context, self.direction, self.structure, self.primary,
                                       self.secondary, self.confirmation, self.execution, self.micro)):
            raise Phase3InvariantError("Evidence policy weights must be non-negative")

    def weight(self, role: Phase3Role) -> Decimal:
        return {
            Phase3Role.CONTEXT: self.context, Phase3Role.DIRECTION: self.direction,
            Phase3Role.STRUCTURE: self.structure, Phase3Role.PRIMARY: self.primary,
            Phase3Role.SECONDARY: self.secondary, Phase3Role.CONFIRMATION: self.confirmation,
            Phase3Role.EXECUTION: self.execution, Phase3Role.MICRO: self.micro,
        }[role]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version, "context": str(self.context), "direction": str(self.direction),
            "structure": str(self.structure), "primary": str(self.primary),
            "secondary": str(self.secondary), "confirmation": str(self.confirmation),
            "execution": str(self.execution), "micro": str(self.micro),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidencePolicy":
        return cls(**{
            "version": int(payload["version"]),
            **{name: Decimal(str(payload[name])) for name in (
                "context", "direction", "structure", "primary", "secondary",
                "confirmation", "execution", "micro")},
        })


@dataclass(frozen=True)
class MTFEvidenceSummary:
    long_score: Decimal
    short_score: Decimal
    directional_bias: str
    family_count: int
    diversity_score: Decimal
    contradiction: bool
    false_resumption_risk: Decimal
    model_health: str
    reason_codes: tuple[str, ...] = ()
    policy_version: int = 1


@dataclass(frozen=True)
class MTFHierarchy:
    watermark: int
    mapping: TimeframeMapping
    nodes: tuple[MTFNode, ...]
    parent_links: tuple[tuple[str, str], ...]
    bindings: tuple[MTFParentBinding, ...]
    coherent: bool
    contradiction: bool
    reason_codes: tuple[str, ...]
    flow_alignment: str = "UNKNOWN"
    regime_alignment: str = "UNKNOWN"
    role_alignment: str = "UNKNOWN"
    location_alignment: str = "UNKNOWN"
    evidence: MTFEvidenceSummary | None = None
    corridor_low: Decimal | None = None
    corridor_high: Decimal | None = None

    def node(self, role: Phase3Role) -> MTFNode | None:
        return next((node for node in self.nodes if node.role is role), None)


@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity: OpportunityObject
    hierarchy: MTFHierarchy
    opportunity_version: int
    migration_version: int
    source_watermark: int
    reason_codes: tuple[str, ...]
    expires_at: int = 0
    lifecycle_reason_codes: tuple[str, ...] = ()
    configuration_ids: tuple[str, ...] = ()
    data_versions: tuple[int, ...] = ()
    feature_versions: tuple[int, ...] = ()
    source_fingerprints: tuple[str, ...] = ()


def _pde_maturity(pde: Any) -> str:
    state = getattr(getattr(pde, "state", None), "value", str(getattr(pde, "state", "UNKNOWN")))
    if state in {"PDE_FOLLOW_THROUGH"}:
        return "MATURE"
    if state in {"PDE_RESUMPTION_IN_PROGRESS", "PDE_STRENGTHENING"}:
        return "DEVELOPING"
    if state in {"PDE_PULLBACK_ACTIVE", "PDE_PULLBACK_CANDIDATE", "PDE_DEEPENING", "PDE_WEAKENING"}:
        return "ACTIVE"
    return "EARLY"


def _false_resumption_risk(pde: Any) -> str:
    res = getattr(getattr(pde, "resumption_state", None), "value", str(getattr(pde, "resumption_state", "")))
    if res == "RESUMPTION_FAILED" or getattr(getattr(pde, "state", None), "value", "") == "PDE_RESUMPTION_FAILED":
        return "1"
    if res in {"RECOVERY_CANDIDATE", "DISPLACEMENT_CANDIDATE"}:
        return "0.5"
    return "0"


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _enum_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _enum_value(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_enum_value(v) for v in value]
    if isinstance(value, set):
        values = [_enum_value(v) for v in value]
        return sorted(values, key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")))
    return value


def _opportunity_to_dict(opportunity: OpportunityObject) -> dict[str, Any]:
    return _enum_value(opportunity)


def _opportunity_from_dict(payload: Mapping[str, Any]) -> OpportunityObject:
    data = dict(payload)
    data["direction"] = Direction(data["direction"])
    return OpportunityObject(**data)


def _node_to_dict(node: MTFNode) -> dict[str, Any]:
    return _enum_value(node)


def _node_from_dict(payload: Mapping[str, Any]) -> MTFNode:
    data = dict(payload)
    data["role"] = Phase3Role(data["role"])
    data["timeframe"] = Timeframe.validate(data["timeframe"])
    data["engine_versions"] = tuple(tuple(x) for x in data["engine_versions"])
    return MTFNode(**data)


class Phase3Orchestrator:
    """Causal MTF coordinator over independently authoritative Phase 2 evaluations."""

    SNAPSHOT_SCHEMA = "phase3-mtf-v2"
    REQUIRED_ROLES = (Phase3Role.CONTEXT, Phase3Role.DIRECTION, Phase3Role.STRUCTURE,
                      Phase3Role.PRIMARY, Phase3Role.SECONDARY, Phase3Role.CONFIRMATION,
                      Phase3Role.EXECUTION)
    LIFECYCLE_TRANSITIONS = {
        OpportunityState.DISCOVERED: {OpportunityState.VALIDATING, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.VALIDATING: {OpportunityState.VALID, OpportunityState.DEGRADED, OpportunityState.STALE, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.VALID: {OpportunityState.TRIGGER_READY, OpportunityState.DEGRADED, OpportunityState.STALE, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.TRIGGER_READY: {OpportunityState.VALID, OpportunityState.DEGRADED, OpportunityState.STALE, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.DEGRADED: {OpportunityState.VALID, OpportunityState.TRIGGER_READY, OpportunityState.STALE, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.STALE: {OpportunityState.VALID, OpportunityState.DEGRADED, OpportunityState.INVALIDATED, OpportunityState.EXPIRED},
        OpportunityState.EXPIRED: set(),
        OpportunityState.INVALIDATED: set(),
    }

    def __init__(self, symbol: str, mapping: TimeframeMapping | None = None,
                 history_capacity: int = 256, opportunity_budget: int = 3,
                 evidence_policy: EvidencePolicy | None = None) -> None:
        if not symbol or history_capacity <= 0 or opportunity_budget <= 0:
            raise ValueError("symbol, history_capacity and opportunity_budget must be valid")
        self.symbol = symbol
        self.mapping = mapping or TimeframeMapping.canonical()
        self.history_capacity = history_capacity
        self.opportunity_budget = opportunity_budget
        self.evidence_policy = evidence_policy or EvidencePolicy()
        self._evaluations: dict[Timeframe, dict[int, Phase2Evaluation]] = {}
        self._last_ingested: dict[Timeframe, tuple[int, int]] = {}
        self._opportunities: dict[str, OpportunityCandidate] = {}
        self._root_to_current: dict[str, str] = {}
        self._last_watermark = -1
        self._mapping_history: list[TimeframeMapping] = [self.mapping]
        self._pending_migration_parent_id: str | None = None
        self._latest_opportunity_id: str | None = None
        self._evaluation_index: dict[Timeframe, list[dict[str, Any]]] = {}
        self._lifecycle_history: list[dict[str, Any]] = []

    @property
    def evaluations(self) -> Mapping[Timeframe, Mapping[int, Phase2Evaluation]]:
        return self._evaluations

    def _stage_transaction(self) -> "Phase3Orchestrator":
        """Create a mutation-isolated orchestrator staging copy without deep-copying evaluations.

        Phase2Evaluation objects are treated as committed immutable evidence by this
        layer; ``ingest`` only mutates Phase3-owned containers.  Copying those
        containers rather than recursively copying every historical engine object
        removes the quadratic transaction cost that otherwise dominates long MTF
        streams while preserving rollback isolation for every Phase3-owned field.
        """
        staged = object.__new__(type(self))
        staged.symbol = self.symbol
        staged.mapping = self.mapping
        staged.history_capacity = self.history_capacity
        staged.opportunity_budget = self.opportunity_budget
        staged.evidence_policy = self.evidence_policy
        staged._evaluations = {tf: dict(bucket) for tf, bucket in self._evaluations.items()}
        staged._last_ingested = dict(self._last_ingested)
        staged._opportunities = dict(self._opportunities)
        staged._root_to_current = dict(self._root_to_current)
        staged._last_watermark = self._last_watermark
        staged._mapping_history = list(self._mapping_history)
        staged._pending_migration_parent_id = self._pending_migration_parent_id
        staged._latest_opportunity_id = self._latest_opportunity_id
        staged._evaluation_index = {tf: list(entries) for tf, entries in self._evaluation_index.items()}
        staged._lifecycle_history = list(self._lifecycle_history)
        return staged

    def ingest(self, evaluation: Phase2Evaluation) -> None:
        bar = evaluation.bar
        if bar.symbol != self.symbol:
            raise Phase3InvariantError("Phase 3 symbol mismatch")
        tf = Timeframe.validate(bar.timeframe)
        watermark = (bar.close_timestamp, bar.sequence)
        previous = self._last_ingested.get(tf)
        if previous is not None and watermark <= previous:
            raise Phase3InvariantError(f"Out-of-order evaluation for {tf.value}: {watermark} <= {previous}")
        if evaluation.context.watermark.timestamp != bar.close_timestamp:
            raise Phase3InvariantError("Phase 2 evaluation watermark does not match its bar")
        self._evaluations.setdefault(tf, {})[bar.close_timestamp] = evaluation
        self._evaluation_index.setdefault(tf, []).append({
            "timestamp": bar.close_timestamp, "sequence": bar.sequence,
            "fingerprint": bar.fingerprint(), "pde_version": evaluation.pde.version,
            "configuration_id": getattr(evaluation.context, "configuration_id", ""),
            "feature_version": getattr(evaluation.pde, "feature_version", 1),
        })
        self._evaluation_index[tf] = self._evaluation_index[tf][-self.history_capacity:]
        self._last_ingested[tf] = watermark
        self._last_watermark = max(self._last_watermark, bar.close_timestamp)
        bucket = self._evaluations[tf]
        while len(bucket) > self.history_capacity:
            bucket.pop(min(bucket))

    def _latest_at(self, timeframe: Timeframe, watermark: int) -> Phase2Evaluation | None:
        bucket = self._evaluations.get(timeframe)
        if not bucket:
            return None
        eligible = [ts for ts in bucket if ts <= watermark]
        return bucket[max(eligible)] if eligible else None

    def _node_at(self, role: Phase3Role, timeframe: Timeframe, watermark: int) -> MTFNode | None:
        evaluation = self._latest_at(timeframe, watermark)
        return MTFNode.from_evaluation(role, evaluation) if evaluation else None

    def _role_timeframes(self) -> dict[Phase3Role, Timeframe]:
        return {role: Timeframe.validate(getattr(self.mapping, role.value.lower())) for role in Phase3Role}

    @staticmethod
    def _flow_side(flow: str) -> str:
        if flow.startswith("LONG"): return "LONG"
        if flow.startswith("SHORT"): return "SHORT"
        return "NEUTRAL"

    @staticmethod
    def _structure_side(structure: str) -> str:
        if structure == "BULLISH": return "LONG"
        if structure == "BEARISH": return "SHORT"
        return "NEUTRAL"

    def _fusion(self, nodes: list[MTFNode]) -> tuple[str, str, str, str]:
        directional = [self._flow_side(n.flow) for n in nodes if self._flow_side(n.flow) != "NEUTRAL"]
        flow_alignment = "ALIGNED" if directional and len(set(directional)) == 1 else "CONTESTED" if len(set(directional)) > 1 else "UNKNOWN"
        regimes = {n.regime for n in nodes if n.regime not in {"UNKNOWN"}}
        regime_alignment = "TRANSITION" if "TRANSITION" in regimes else "ALIGNED" if len(regimes) == 1 and regimes else "MIXED" if regimes else "UNKNOWN"
        roles = {n.role_state for n in nodes if n.role_state not in {"UNKNOWN", "AMBIGUOUS"}}
        role_alignment = "ALIGNED" if len(roles) == 1 and roles else "MIXED" if roles else "UNKNOWN"
        locations = [n.location for n in nodes]
        location_alignment = "BLOCKED" if "BLOCKED" in locations else "CONGESTED" if "CONGESTED" in locations else "FAVORABLE" if "FAVORABLE" in locations else "MIXED" if locations else "UNKNOWN"
        return flow_alignment, regime_alignment, role_alignment, location_alignment

    def _evidence(self, nodes: list[MTFNode], contradiction: bool) -> MTFEvidenceSummary:
        long_score = Decimal(0); short_score = Decimal(0); families: set[str] = set(); false_risk = Decimal(0); reasons: list[str] = []
        for node in nodes:
            weight = self.evidence_policy.weight(node.role)
            flow = self._flow_side(node.flow)
            if flow == "LONG": long_score += weight
            elif flow == "SHORT": short_score += weight
            structure = self._structure_side(node.structure)
            if structure == "LONG": long_score += weight * Decimal("0.5")
            elif structure == "SHORT": short_score += weight * Decimal("0.5")
            if node.pde not in {"PDE_NONE"}: families.add("PDE")
            if node.flow not in {"UNKNOWN", "BALANCED", "CONTESTED"}: families.add("FLOW")
            if node.regime not in {"UNKNOWN"}: families.add("REGIME")
            if node.role_state not in {"UNKNOWN"}: families.add("ROLE")
            if node.location not in {"OPEN", "UNKNOWN"}: families.add("LOCATION")
            false_risk = max(false_risk, Decimal(node.pde_false_resumption_risk))
        total = long_score + short_score
        bias = "LONG" if long_score > short_score else "SHORT" if short_score > long_score else "NEUTRAL"
        if contradiction: reasons.append("DIRECTIONAL_CONTRADICTION")
        if false_risk > 0: reasons.append("FALSE_RESUMPTION_EVIDENCE_PRESENT")
        diversity = Decimal(len(families)) / Decimal("5")
        return MTFEvidenceSummary(long_score, short_score, bias, len(families), min(Decimal(1), diversity), contradiction, false_risk, "INCONSISTENT" if contradiction else "HEALTHY" if total > 0 else "UNKNOWN", tuple(reasons), self.evidence_policy.version)

    def hierarchy_at(self, watermark: int) -> MTFHierarchy:
        if watermark < 0:
            raise ValueError("watermark must be non-negative")
        role_tfs = self._role_timeframes()
        nodes = tuple(node for role, tf in role_tfs.items() if (node := self._node_at(role, tf, watermark)) is not None)
        by_role = {n.role: n for n in nodes}
        reasons: list[str] = []
        links: list[tuple[str, str]] = []
        bindings: list[MTFParentBinding] = []
        coherent = True
        for role in self.REQUIRED_ROLES:
            if by_role.get(role) is None:
                coherent = False; reasons.append(f"MISSING_REQUIRED_{role.value}")
        ordered = [Phase3Role.CONTEXT, Phase3Role.DIRECTION, Phase3Role.STRUCTURE, Phase3Role.PRIMARY, Phase3Role.SECONDARY, Phase3Role.CONFIRMATION, Phase3Role.EXECUTION]
        for parent_role, child_role in zip(ordered, ordered[1:]):
            parent, child = by_role.get(parent_role), by_role.get(child_role)
            if parent is None or child is None: continue
            if parent.evaluation_timestamp > child.evaluation_timestamp or child.evaluation_timestamp > watermark:
                coherent = False; reasons.append(f"TEMPORAL_SKEW_{parent_role.value}_{child_role.value}")
                continue
            links.append((parent_role.value, child_role.value))
            containment = "CONTAINED" if not parent.pde_episode_id or not child.pde_episode_id or child.pde_parent_id in {"", parent.pde_episode_id, parent.pde_parent_id} else "DIVERGENT"
            if containment == "DIVERGENT" and parent_role in {Phase3Role.PRIMARY, Phase3Role.SECONDARY}:
                reasons.append(f"PDE_EPISODE_DIVERGENCE_{parent_role.value}_{child_role.value}")
            bindings.append(MTFParentBinding(parent_role, child_role, parent.evaluation_timestamp, child.evaluation_timestamp,
                                             dict(parent.engine_versions).get("pde", 0), dict(child.engine_versions).get("pde", 0),
                                             parent.pde_episode_id, child.pde_episode_id, parent.pde_direction, child.pde_direction, containment))
        contradiction = False
        primary, secondary, confirmation = by_role.get(Phase3Role.PRIMARY), by_role.get(Phase3Role.SECONDARY), by_role.get(Phase3Role.CONFIRMATION)
        structure = by_role.get(Phase3Role.STRUCTURE)
        direction_node = by_role.get(Phase3Role.DIRECTION)
        if structure and direction_node and self._structure_side(structure.structure) not in {"NEUTRAL", self._flow_side(direction_node.flow)}:
            contradiction = True; reasons.append("STRUCTURE_DIRECTION_CONFLICT")
        if primary and secondary:
            ps, ss = self._flow_side(primary.flow), self._flow_side(secondary.flow)
            pd, sd = primary.direction, secondary.direction
            if pd in {"LONG", "SHORT"} and sd in {"LONG", "SHORT"} and pd != sd:
                contradiction = True; reasons.append("PRIMARY_SECONDARY_DIRECTION_CONFLICT")
            if ps != "NEUTRAL" and ss != "NEUTRAL" and ps != ss:
                contradiction = True; reasons.append("PRIMARY_SECONDARY_FLOW_CONFLICT")
            if primary.structure in {"BULLISH", "BEARISH"} and sd in {"LONG", "SHORT"} and sd != self._structure_side(primary.structure):
                contradiction = True; reasons.append("STRUCTURE_CHILD_DIRECTION_CONFLICT")
        if secondary and confirmation:
            ss, cs = self._flow_side(secondary.flow), self._flow_side(confirmation.flow)
            if ss != "NEUTRAL" and cs != "NEUTRAL" and ss != cs:
                contradiction = True; reasons.append("SECONDARY_CONFIRMATION_DIRECTION_CONFLICT")
        if any(not n.valid for n in nodes): reasons.append("ONE_OR_MORE_NODES_NOT_USABLE")
        if any(n.pde_resumption == "RESUMPTION_FAILED" or n.pde == "PDE_RESUMPTION_FAILED" for n in nodes):
            reasons.append("FALSE_RESUMPTION_OR_RESUMPTION_FAILURE")
        flow_alignment, regime_alignment, role_alignment, location_alignment = self._fusion(list(nodes))
        micro = by_role.get(Phase3Role.MICRO)
        if micro and micro.pde in {"PDE_PULLBACK_ACTIVE", "PDE_DEEPENING", "PDE_WEAKENING"}:
            reasons.append("MICRO_PULLBACK_ACTIVE")
        if micro and micro.pde_resumption == "RESUMPTION_FAILED":
            contradiction = True; reasons.append("MICRO_FALSE_RESUMPTION")
        evidence = self._evidence(list(nodes), contradiction)
        if flow_alignment == "CONTESTED": reasons.append("MTF_FLOW_CONTESTED")
        if location_alignment == "BLOCKED": reasons.append("MTF_LOCATION_BLOCKED")
        corridor_low = corridor_high = None
        primary_eval = self._latest_at(self.mapping.primary, watermark)
        if primary_eval is not None:
            corridor_low = primary_eval.structure.protected_low
            corridor_high = primary_eval.structure.protected_high
        return MTFHierarchy(watermark, self.mapping, nodes, tuple(links), tuple(bindings), coherent, contradiction,
                            tuple(dict.fromkeys(reasons)), flow_alignment, regime_alignment, role_alignment, location_alignment, evidence, corridor_low, corridor_high)

    def migrate_on_confirmed_transition(self, watermark: int) -> bool:
        hierarchy = self.hierarchy_at(watermark)
        primary_eval = self._latest_at(self.mapping.primary, watermark)
        if primary_eval is None or not hierarchy.coherent or hierarchy.contradiction:
            return False
        if self.mapping.primary == Timeframe.M1:
            return False
        transition = primary_eval.structure.bos_type
        if not (transition.startswith("BOS_") or transition.startswith("CHOCH_")):
            return False
        migrated = self.mapping.migrate_primary_down()
        if migrated == self.mapping:
            return False
        self._pending_migration_parent_id = self._latest_opportunity_id
        self.mapping = migrated
        self._mapping_history.append(migrated)
        return True

    @staticmethod
    def _direction_from_structure(structure: str) -> Direction | None:
        if structure == "BULLISH": return Direction.LONG
        if structure == "BEARISH": return Direction.SHORT
        return None

    def _setup_type(self, primary: MTFNode, secondary: MTFNode, confirmation: MTFNode, hierarchy: MTFHierarchy) -> str:
        expected = self._direction_from_structure(primary.structure)
        if expected is None: return "UNCLASSIFIED"
        pde_active = primary.pde in {"PDE_PULLBACK_ACTIVE", "PDE_WEAKENING", "PDE_STRENGTHENING", "PDE_DEEPENING", "PDE_RESUMPTION_IN_PROGRESS", "PDE_FOLLOW_THROUGH"}
        flow_expected = self._flow_side(primary.flow) == expected.value
        secondary_expected = self._flow_side(secondary.flow) in {expected.value, "NEUTRAL"}
        confirm_expected = self._flow_side(confirmation.flow) in {expected.value, "NEUTRAL"}
        if hierarchy.regime_alignment == "TRANSITION" and primary.structure != "AMBIGUOUS": return "FF-04 TRANSITION_BREAK"
        if primary.role_state == "COUNTERFLOW" and pde_active: return "FF-02 COUNTERFLOW"
        if hierarchy.regime_alignment == "ALIGNED" and primary.role_state == "RANGE_ROTATION" and primary.location in {"EXTREME", "CONGESTED"}: return "FF-03 RANGE_ROTATION"
        if primary.role_state in {"PULLBACK", "CONTINUATION", "RECLAIM"} and pde_active and flow_expected and secondary_expected and confirm_expected: return "FF-01 FLOW_CONTINUATION"
        return "UNCLASSIFIED"

    def _opportunity_root(self, direction: Direction, evaluation: Phase2Evaluation) -> str:
        episode = evaluation.pde.episode_id or f"ts:{evaluation.bar.close_timestamp}"
        return f"phase3:{self.symbol}:{direction.value}:{episode}"

    def _family_key(self, evaluation: Phase2Evaluation) -> str:
        return f"phase3:{self.symbol}:{evaluation.pde.episode_id or evaluation.bar.close_timestamp}"

    def _expire_at(self, source_watermark: int) -> int:
        return source_watermark + self.mapping.primary.seconds * 3

    @classmethod
    def _validate_lifecycle_transition(cls, previous: OpportunityState, new: OpportunityState) -> None:
        if previous == new:
            return
        if new not in cls.LIFECYCLE_TRANSITIONS.get(previous, set()):
            raise Phase3InvariantError(f"Illegal opportunity lifecycle transition: {previous.value} -> {new.value}")

    def _update_lifecycle(self, candidate: OpportunityCandidate, watermark: int, hierarchy: MTFHierarchy) -> OpportunityCandidate:
        state = OpportunityState(candidate.opportunity.state)
        reason = list(candidate.lifecycle_reason_codes)
        if state in {OpportunityState.EXPIRED, OpportunityState.INVALIDATED}:
            return candidate
        if watermark >= candidate.expires_at:
            state = OpportunityState.EXPIRED; reason.append("TTL_EXPIRED")
        elif hierarchy.contradiction or not hierarchy.coherent:
            state = OpportunityState.INVALIDATED; reason.append("HIERARCHY_INVALIDATED")
        elif hierarchy.evidence and hierarchy.evidence.false_resumption_risk >= Decimal("1"):
            state = OpportunityState.DEGRADED; reason.append("FALSE_RESUMPTION_RISK")
        elif any(not n.valid for n in hierarchy.nodes):
            state = OpportunityState.STALE; reason.append("SOURCE_STALE")
        elif hierarchy.node(Phase3Role.EXECUTION) and hierarchy.node(Phase3Role.EXECUTION).valid:
            confirmation = hierarchy.node(Phase3Role.CONFIRMATION)
            if confirmation and confirmation.pde_resumption in {"RESUMPTION_CONFIRMED", "FOLLOW_THROUGH"}:
                state = OpportunityState.TRIGGER_READY
            else:
                state = OpportunityState.VALID
        self._validate_lifecycle_transition(OpportunityState(candidate.opportunity.state), state)
        updated = deepcopy(candidate.opportunity)
        updated.state = state.value
        updated.entry_allowed = False
        updated.confidence = min(1.0, max(0.0, updated.confidence))
        updated_candidate = OpportunityCandidate(
            updated, hierarchy, candidate.opportunity_version, candidate.migration_version,
            candidate.source_watermark, candidate.reason_codes, candidate.expires_at,
            tuple(dict.fromkeys(reason)), candidate.configuration_ids, candidate.data_versions,
            candidate.feature_versions, candidate.source_fingerprints,
        )
        self._opportunities[updated.opportunity_id] = updated_candidate
        self._lifecycle_history.append({"id": updated.opportunity_id, "timestamp": watermark, "state": state.value, "reasons": tuple(dict.fromkeys(reason))})
        self._lifecycle_history = self._lifecycle_history[-self.history_capacity:]
        return updated_candidate

    def advance_lifecycle(self, watermark: int) -> tuple[OpportunityCandidate, ...]:
        hierarchy = self.hierarchy_at(watermark)
        updated = []
        for candidate in tuple(self._opportunities.values()):
            if candidate.source_watermark <= watermark:
                updated.append(self._update_lifecycle(candidate, watermark, hierarchy))
        return tuple(updated)

    def construct_opportunity(self, watermark: int) -> OpportunityCandidate | None:
        hierarchy = self.hierarchy_at(watermark)
        required = [hierarchy.node(role) for role in (Phase3Role.CONTEXT, Phase3Role.DIRECTION, Phase3Role.STRUCTURE, Phase3Role.PRIMARY, Phase3Role.SECONDARY, Phase3Role.CONFIRMATION, Phase3Role.EXECUTION)]
        if not hierarchy.coherent or hierarchy.contradiction or any(node is None for node in required): return None
        if any(not node.valid for node in required if node is not None): return None
        primary, secondary, confirmation, execution = (hierarchy.node(r) for r in (Phase3Role.PRIMARY, Phase3Role.SECONDARY, Phase3Role.CONFIRMATION, Phase3Role.EXECUTION))
        assert primary and secondary and confirmation and execution
        direction = self._direction_from_structure(primary.structure)
        if direction is None or primary.direction not in {direction.value, ""}: return None
        if hierarchy.evidence is None or hierarchy.evidence.contradiction or hierarchy.evidence.false_resumption_risk >= Decimal("1"): return None
        setup = self._setup_type(primary, secondary, confirmation, hierarchy)
        if setup == "UNCLASSIFIED": return None
        primary_eval = self._latest_at(self.mapping.primary, watermark)
        if primary_eval is None: return None
        target = primary_eval.structure.protected_high if direction is Direction.LONG else primary_eval.structure.protected_low
        if target is None: return None
        price = primary_eval.bar.close; distance = target - price if direction is Direction.LONG else price - target
        volatility = primary_eval.volatility.atr_14
        if distance <= 0 or volatility <= 0: return None
        opportunity_space = distance / volatility
        if opportunity_space <= 0: return None
        root_id = self._opportunity_root(direction, primary_eval)
        existing_id = self._root_to_current.get(root_id)
        previous = self._opportunities.get(existing_id) if existing_id else None
        if previous is not None and previous.migration_version == self.mapping.version:
            version = previous.opportunity_version + 1
            opportunity_id = existing_id
            parent_id = previous.opportunity.parent_opportunity_id
        else:
            family = self._family_key(primary_eval)
            family_candidates = [c for c in self._opportunities.values() if c.opportunity.root_id.endswith(family.split(":", 3)[-1])]
            if len(family_candidates) >= self.opportunity_budget: return None
            opposite = [c for c in family_candidates if c.opportunity.direction is not direction]
            if opposite and not (primary_eval.structure.bos_type.startswith("BOS_") or primary_eval.structure.bos_type.startswith("CHOCH_")):
                return None
            opportunity_id = hashlib.sha256(f"{root_id}:mapping:{self.mapping.version}".encode()).hexdigest()[:24]
            parent_id = previous.opportunity.opportunity_id if previous is not None else self._pending_migration_parent_id
            version = 1
            self._pending_migration_parent_id = None
        structural_edge = Decimal("1") if self._structure_side(primary.structure) == direction.value else Decimal("0")
        evidence_score = hierarchy.evidence.long_score if direction is Direction.LONG else hierarchy.evidence.short_score
        confidence = min(Decimal("1"), (structural_edge + min(Decimal("1"), evidence_score / Decimal("3"))) / Decimal("2"))
        opportunity = OpportunityObject(
            opportunity_id=opportunity_id, root_id=root_id, symbol=self.symbol, session="UNKNOWN",
            strategy_mode="DEFAULT", posture="DIRECTIONAL", environment=primary.regime,
            environment_tf=self.mapping.context.value, location=primary.location, location_tf=self.mapping.primary.value,
            dominant_flow=primary.flow, local_flow=secondary.flow, market_role=primary.role_state,
            primary_pullback_id=primary.pde_episode_id, setup_type=setup, direction=direction,
            structural_edge=float(structural_edge), opportunity_space=float(opportunity_space), tradeability="UNASSESSED",
            execution_quality=1.0 if execution.location != "BLOCKED" else 0.0,
            entry_profile="PULLBACK_RESUMPTION" if primary.role_state == "PULLBACK" else "STRUCTURAL_CONTINUATION",
            risk_class="UNASSESSED", ttl_class="TIMEFRAME_BOUNDED", confidence=float(confidence),
            state=OpportunityState.VALID.value, entry_allowed=False, parent_opportunity_id=parent_id)
        provenance_nodes = hierarchy.nodes
        candidate = OpportunityCandidate(
            opportunity, hierarchy, version, self.mapping.version, watermark,
            hierarchy.reason_codes, self._expire_at(watermark), ("DISCOVERED", "VALIDATING", "VALID"),
            tuple(sorted({n.configuration_id for n in provenance_nodes if n.configuration_id})),
            tuple(sorted({n.data_version for n in provenance_nodes})),
            tuple(sorted({n.feature_version for n in provenance_nodes})),
            tuple(sorted({f"{n.role.value}:{n.evaluation_timestamp}:{n.sequence}" for n in provenance_nodes})),
        )
        self._opportunities[opportunity_id] = candidate
        self._lifecycle_history.extend((
            {"id": opportunity_id, "timestamp": watermark, "state": OpportunityState.DISCOVERED.value, "reasons": ("OPPORTUNITY_DISCOVERED",)},
            {"id": opportunity_id, "timestamp": watermark, "state": OpportunityState.VALIDATING.value, "reasons": ("HIERARCHY_VALIDATED",)},
            {"id": opportunity_id, "timestamp": watermark, "state": OpportunityState.VALID.value, "reasons": tuple(hierarchy.reason_codes)},
        ))
        self._lifecycle_history = self._lifecycle_history[-self.history_capacity:]
        self._root_to_current[root_id] = opportunity_id
        self._latest_opportunity_id = opportunity_id
        return candidate

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.SNAPSHOT_SCHEMA, "symbol": self.symbol, "history_capacity": self.history_capacity,
            "opportunity_budget": self.opportunity_budget, "evidence_policy": self.evidence_policy.to_dict(), "mapping": self.mapping.to_dict(),
            "mapping_history": [m.to_dict() for m in self._mapping_history], "last_watermark": self._last_watermark,
            "last_ingested": {tf.value: list(wm) for tf, wm in sorted(self._last_ingested.items(), key=lambda x: x[0].level)},
            "root_to_current": dict(sorted(self._root_to_current.items())),
            "pending_migration_parent_id": self._pending_migration_parent_id, "latest_opportunity_id": self._latest_opportunity_id,
            "evaluation_index": {tf.value: list(entries) for tf, entries in sorted(self._evaluation_index.items(), key=lambda x: x[0].level)},
            "opportunities": {oid: self._candidate_to_dict(c) for oid, c in sorted(self._opportunities.items())},
            "lifecycle_history": list(self._lifecycle_history),
        }

    @staticmethod
    def _candidate_to_dict(candidate: OpportunityCandidate) -> dict[str, Any]:
        h = candidate.hierarchy
        return {
            "opportunity": _opportunity_to_dict(candidate.opportunity),
            "opportunity_version": candidate.opportunity_version, "migration_version": candidate.migration_version,
            "source_watermark": candidate.source_watermark, "reason_codes": list(candidate.reason_codes),
            "expires_at": candidate.expires_at, "lifecycle_reason_codes": list(candidate.lifecycle_reason_codes),
            "configuration_ids": list(candidate.configuration_ids), "data_versions": list(candidate.data_versions),
            "feature_versions": list(candidate.feature_versions), "source_fingerprints": list(candidate.source_fingerprints),
            "hierarchy": {
                "watermark": h.watermark, "mapping": h.mapping.to_dict(), "nodes": [_node_to_dict(n) for n in h.nodes],
                "parent_links": [list(x) for x in h.parent_links], "bindings": [_enum_value(b) for b in h.bindings],
                "coherent": h.coherent, "contradiction": h.contradiction, "reason_codes": list(h.reason_codes),
                "flow_alignment": h.flow_alignment, "regime_alignment": h.regime_alignment,
                "role_alignment": h.role_alignment, "location_alignment": h.location_alignment,
                "evidence": _enum_value(h.evidence) if h.evidence else None,
                "corridor_low": _enum_value(h.corridor_low), "corridor_high": _enum_value(h.corridor_high),
            },
        }

    @staticmethod
    def _candidate_from_dict(payload: Mapping[str, Any]) -> OpportunityCandidate:
        h = payload["hierarchy"]
        mapping = TimeframeMapping(**{k: Timeframe.validate(v) if k != "version" else int(v) for k, v in h["mapping"].items()})
        evidence_payload = h.get("evidence")
        evidence = None
        if evidence_payload:
            evidence = MTFEvidenceSummary(
                Decimal(evidence_payload["long_score"]["__decimal__"] if isinstance(evidence_payload["long_score"], dict) else evidence_payload["long_score"]),
                Decimal(evidence_payload["short_score"]["__decimal__"] if isinstance(evidence_payload["short_score"], dict) else evidence_payload["short_score"]),
                evidence_payload["directional_bias"], int(evidence_payload["family_count"]),
                Decimal(evidence_payload["diversity_score"]["__decimal__"] if isinstance(evidence_payload["diversity_score"], dict) else evidence_payload["diversity_score"]),
                bool(evidence_payload["contradiction"]), Decimal(evidence_payload["false_resumption_risk"]["__decimal__"] if isinstance(evidence_payload["false_resumption_risk"], dict) else evidence_payload["false_resumption_risk"]),
                evidence_payload["model_health"], tuple(evidence_payload.get("reason_codes", ())), int(evidence_payload.get("policy_version", 1)))
        bindings = []
        for b in h["bindings"]:
            bindings.append(MTFParentBinding(Phase3Role(b["parent_role"]), Phase3Role(b["child_role"]), b["parent_timestamp"], b["child_timestamp"], b["parent_pde_version"], b["child_pde_version"], b.get("parent_episode_id", ""), b.get("child_episode_id", ""), b.get("parent_direction", ""), b.get("child_direction", ""), b.get("containment", "UNKNOWN")))
        hierarchy = MTFHierarchy(h["watermark"], mapping, tuple(_node_from_dict(n) for n in h["nodes"]), tuple(tuple(x) for x in h["parent_links"]), tuple(bindings), bool(h["coherent"]), bool(h["contradiction"]), tuple(h["reason_codes"]), h.get("flow_alignment", "UNKNOWN"), h.get("regime_alignment", "UNKNOWN"), h.get("role_alignment", "UNKNOWN"), h.get("location_alignment", "UNKNOWN"), evidence, _decimal_optional(h.get("corridor_low")), _decimal_optional(h.get("corridor_high")))
        return OpportunityCandidate(_opportunity_from_dict(payload["opportunity"]), hierarchy, int(payload["opportunity_version"]), int(payload["migration_version"]), int(payload["source_watermark"]), tuple(payload["reason_codes"]), int(payload.get("expires_at", 0)), tuple(payload.get("lifecycle_reason_codes", ())), tuple(payload.get("configuration_ids", ())), tuple(int(v) for v in payload.get("data_versions", ())), tuple(int(v) for v in payload.get("feature_versions", ())), tuple(payload.get("source_fingerprints", ())))

    @classmethod
    def from_snapshot_state(cls, payload: dict[str, Any]) -> "Phase3Orchestrator":
        if payload.get("schema_version") not in {cls.SNAPSHOT_SCHEMA, "phase3-mtf-v1"}:
            raise ValueError(f"Unsupported Phase3 snapshot schema: {payload.get('schema_version')!r}")
        mapping_payload = payload.get("mapping")
        if not isinstance(mapping_payload, dict): raise ValueError("Phase3 snapshot lacks mapping")
        mapping = TimeframeMapping(**{k: Timeframe.validate(v) if k != "version" else int(v) for k, v in mapping_payload.items()})
        policy = EvidencePolicy.from_dict(payload.get("evidence_policy", EvidencePolicy().to_dict()))
        restored = cls(str(payload["symbol"]), mapping=mapping, history_capacity=int(payload["history_capacity"]), opportunity_budget=int(payload.get("opportunity_budget", 3)), evidence_policy=policy)
        if payload.get("evidence_policy") is not None and restored.evidence_policy.to_dict() != payload["evidence_policy"]:
            raise Phase3InvariantError("Phase 3 evidence policy provenance mismatch")
        restored._last_watermark = int(payload.get("last_watermark", -1))
        restored._last_ingested = {Timeframe.validate(tf): (int(wm[0]), int(wm[1])) for tf, wm in payload.get("last_ingested", {}).items()}
        restored._root_to_current = dict(payload.get("root_to_current", {})); restored._pending_migration_parent_id = payload.get("pending_migration_parent_id"); restored._latest_opportunity_id = payload.get("latest_opportunity_id")
        restored._evaluation_index = {Timeframe.validate(tf): list(entries) for tf, entries in payload.get("evaluation_index", {}).items()}
        restored._mapping_history = [TimeframeMapping(**{k: Timeframe.validate(v) if k != "version" else int(v) for k, v in item.items()}) for item in payload.get("mapping_history", [])] or [mapping]
        if payload.get("schema_version") == cls.SNAPSHOT_SCHEMA:
            restored._opportunities = {oid: cls._candidate_from_dict(item) for oid, item in payload.get("opportunities", {}).items()}
            restored._lifecycle_history = list(payload.get("lifecycle_history", []))[-restored.history_capacity:]
        return restored

    @classmethod
    def reconstruct_from_phase2_durable(
        cls,
        stores: Mapping[Timeframe, Any],
        mapping: TimeframeMapping,
        *,
        history_capacity: int = 256,
        opportunity_budget: int = 3,
        evidence_policy: EvidencePolicy | None = None,
        expected_state_hash: str | None = None,
    ) -> "Phase3Orchestrator":
        """Reconstruct derived Phase3 state exclusively from Phase2 durable journals."""
        if not stores:
            raise Phase3InvariantError("At least one Phase2 durable store is required")
        symbol: str | None = None
        replay_items: list[tuple[int, int, int, Phase2Evaluation]] = []
        for tf, store in stores.items():
            tf_obj = Timeframe.validate(tf)
            for evaluation in store.replay_evaluations():
                if symbol is None:
                    symbol = evaluation.bar.symbol
                if evaluation.bar.symbol != symbol or Timeframe.validate(evaluation.bar.timeframe) != tf_obj:
                    raise Phase3InvariantError("Phase2 durable replay contains an identity mismatch")
                replay_items.append((evaluation.bar.close_timestamp, evaluation.bar.sequence, tf_obj.level, evaluation))
        if symbol is None:
            raise Phase3InvariantError("Phase2 durable replay produced no evaluations")
        replay_items.sort(key=lambda item: (item[0], item[1], item[2]))
        orchestrator = cls(symbol, mapping=mapping, history_capacity=history_capacity,
                           opportunity_budget=opportunity_budget, evidence_policy=evidence_policy)
        # Rebuild by causal watermark batches.  Opportunities and migrations are
        # derived only after every Phase2 evaluation available at that watermark
        # has been ingested, preventing order-dependent partial hierarchies.
        cursor = 0
        while cursor < len(replay_items):
            watermark = replay_items[cursor][0]
            end = cursor
            while end < len(replay_items) and replay_items[end][0] == watermark:
                orchestrator.ingest(replay_items[end][3])
                end += 1
            orchestrator.migrate_on_confirmed_transition(watermark)
            orchestrator.construct_opportunity(watermark)
            orchestrator.advance_lifecycle(watermark)
            cursor = end
        if expected_state_hash is not None and orchestrator.state_hash() != expected_state_hash:
            raise Phase3InvariantError("Phase2 durable replay did not reproduce the expected Phase3 state hash")
        return orchestrator

    def state_hash(self) -> str:
        payload = json.dumps(_enum_value(self.snapshot_state()), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decimal_optional(value: Any) -> Decimal | None:
    if value is None: return None
    if isinstance(value, dict) and "__decimal__" in value: return Decimal(value["__decimal__"])
    return Decimal(value)


class Phase3Pipeline:
    """Atomic composition of canonical Phase 2 pipelines and Phase 3 orchestration."""

    SNAPSHOT_SCHEMA = "phase3-pipeline-v2"

    def __init__(self, symbol: str, instrument: Any | None = None, mapping: TimeframeMapping | None = None,
                 history_capacity: int = 256, opportunity_budget: int = 3,
                 evidence_policy: EvidencePolicy | None = None) -> None:
        from src.fractal_flow.domain.phase2 import Phase2Pipeline
        self.symbol = symbol; self.mapping = mapping or TimeframeMapping.canonical(); self.history_capacity = history_capacity
        self.opportunity_budget = opportunity_budget
        self.evidence_policy = evidence_policy or EvidencePolicy()
        self.orchestrator = Phase3Orchestrator(symbol, self.mapping, history_capacity, opportunity_budget, self.evidence_policy)
        unique_timeframes = {self.mapping.context, self.mapping.direction, self.mapping.structure, self.mapping.primary,
                             self.mapping.secondary, self.mapping.confirmation, self.mapping.execution, self.mapping.micro}
        self.pipelines = {tf: Phase2Pipeline(symbol, tf.value, instrument=instrument, history_capacity=history_capacity) for tf in unique_timeframes}
        self.instrument = next(iter(self.pipelines.values())).instrument

    def process_bar(self, bar: Any) -> Phase2Evaluation:
        """Stage both Phase 2 and Phase 3; publish neither until both succeed."""
        tf = Timeframe.validate(bar.timeframe)
        if tf not in self.pipelines: raise Phase3InvariantError(f"Timeframe {tf.value} is not part of the active Phase 3 mapping")
        staged_pipeline = self.pipelines[tf]._stage_transaction()
        staged_orchestrator = self.orchestrator._stage_transaction()
        evaluation = staged_pipeline.process_bar(bar)
        staged_orchestrator.ingest(evaluation)
        self.pipelines[tf] = staged_pipeline
        self.orchestrator = staged_orchestrator
        return evaluation

    def hierarchy_at(self, watermark: int) -> MTFHierarchy: return self.orchestrator.hierarchy_at(watermark)
    def construct_opportunity(self, watermark: int) -> OpportunityCandidate | None: return self.orchestrator.construct_opportunity(watermark)
    def advance_lifecycle(self, watermark: int) -> tuple[OpportunityCandidate, ...]: return self.orchestrator.advance_lifecycle(watermark)

    def migrate_on_confirmed_transition(self, watermark: int) -> bool:
        """Atomically stage mapping migration and any required Phase2 pipelines."""
        staged_orchestrator = self.orchestrator._stage_transaction()
        if not staged_orchestrator.migrate_on_confirmed_transition(watermark):
            return False
        staged_pipelines = dict(self.pipelines)
        from src.fractal_flow.domain.phase2 import Phase2Pipeline
        for tf in {staged_orchestrator.mapping.primary, staged_orchestrator.mapping.secondary,
                   staged_orchestrator.mapping.confirmation, staged_orchestrator.mapping.execution,
                   staged_orchestrator.mapping.micro}:
            if tf not in staged_pipelines:
                staged_pipelines[tf] = Phase2Pipeline(
                    self.symbol, tf.value, instrument=self.instrument, history_capacity=self.history_capacity
                )
        # Validate the staged topology before publishing either side.
        staged_orchestrator.hierarchy_at(watermark)
        self.orchestrator = staged_orchestrator
        self.mapping = staged_orchestrator.mapping
        self.pipelines = staged_pipelines
        return True

    def snapshot_state(self) -> dict[str, Any]:
        return {"schema_version": self.SNAPSHOT_SCHEMA, "symbol": self.symbol, "mapping": self.mapping.to_dict(), "history_capacity": self.history_capacity,
                "opportunity_budget": self.opportunity_budget, "evidence_policy": self.evidence_policy.to_dict(), "orchestrator": self.orchestrator.snapshot_state(),
                "pipelines": {tf.value: pipeline.snapshot_state() for tf, pipeline in sorted(self.pipelines.items(), key=lambda x: x[0].level)}}

    @classmethod
    def from_snapshot_state(cls, payload: dict[str, Any]) -> "Phase3Pipeline":
        from src.fractal_flow.domain.phase2 import Phase2Pipeline
        if payload.get("schema_version") not in {cls.SNAPSHOT_SCHEMA, "phase3-pipeline-v1"}: raise ValueError("Unsupported Phase3Pipeline snapshot schema")
        mapping_payload = payload["mapping"]
        mapping = TimeframeMapping(**{k: Timeframe.validate(v) if k != "version" else int(v) for k, v in mapping_payload.items()})
        restored = cls.__new__(cls); restored.symbol = str(payload["symbol"]); restored.mapping = mapping; restored.history_capacity = int(payload["history_capacity"]); restored.opportunity_budget = int(payload.get("opportunity_budget", 3)); restored.evidence_policy = EvidencePolicy.from_dict(payload.get("evidence_policy", EvidencePolicy().to_dict()))
        restored.pipelines = {Timeframe.validate(tf): Phase2Pipeline.from_snapshot_state(state) for tf, state in payload.get("pipelines", {}).items()}
        if not restored.pipelines:
            raise Phase3InvariantError("Phase3Pipeline snapshot contains no Phase2 pipelines")
        restored.instrument = next(iter(restored.pipelines.values())).instrument
        restored.orchestrator = Phase3Orchestrator.from_snapshot_state(payload["orchestrator"])
        if restored.orchestrator.evidence_policy.to_dict() != restored.evidence_policy.to_dict():
            raise Phase3InvariantError("Phase3Pipeline evidence policy provenance mismatch")
        return restored

    def state_hash(self) -> str:
        return hashlib.sha256(json.dumps(_enum_value(self.snapshot_state()), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

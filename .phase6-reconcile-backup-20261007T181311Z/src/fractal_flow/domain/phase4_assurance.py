"""Phase 4 assurance primitives: replay, causal differential testing, and capability checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from .phase4 import Phase4ValidationError, TradeDecisionV4


class ReplayIntegrityError(ValueError):
    """Raised when an assurance event stream cannot be replayed deterministically."""


@dataclass(frozen=True)
class Phase4ReplayEvent:
    sequence: int
    event_type: str
    event_timestamp: int
    payload: Mapping[str, object]
    previous_hash: str = ""
    event_hash: str = ""

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 1:
            raise ReplayIntegrityError("replay sequence must start at one")
        if type(self.event_timestamp) is not int or self.event_timestamp < 0:
            raise ReplayIntegrityError("replay event timestamp must be a non-negative integer")
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ReplayIntegrityError("replay event_type is required")
        canonical = json.dumps(
            {
                "sequence": self.sequence,
                "event_type": self.event_type,
                "event_timestamp": self.event_timestamp,
                "payload": self.payload,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if self.event_hash and self.event_hash != expected:
            raise ReplayIntegrityError("replay event hash mismatch")
        object.__setattr__(self, "event_hash", expected)


class Phase4ReplayLog:
    """Append-only, hash-chained assurance log for deterministic Phase 4 handoffs."""

    def __init__(self) -> None:
        self._events: list[Phase4ReplayEvent] = []

    @property
    def events(self) -> tuple[Phase4ReplayEvent, ...]:
        return tuple(self._events)

    def append(self, event_type: str, event_timestamp: int, payload: Mapping[str, object]) -> Phase4ReplayEvent:
        previous_hash = self._events[-1].event_hash if self._events else ""
        event = Phase4ReplayEvent(
            sequence=len(self._events) + 1,
            event_type=event_type,
            event_timestamp=event_timestamp,
            payload=dict(payload),
            previous_hash=previous_hash,
        )
        self._events.append(event)
        return event

    def verify(self) -> None:
        previous = ""
        for expected_sequence, event in enumerate(self._events, start=1):
            if event.sequence != expected_sequence:
                raise ReplayIntegrityError("replay sequence gap or duplicate")
            if event.previous_hash != previous:
                raise ReplayIntegrityError("replay hash-chain discontinuity")
            rebuilt = Phase4ReplayEvent(
                sequence=event.sequence,
                event_type=event.event_type,
                event_timestamp=event.event_timestamp,
                payload=event.payload,
                previous_hash=event.previous_hash,
                event_hash=event.event_hash,
            )
            if rebuilt.event_hash != event.event_hash:
                raise ReplayIntegrityError("replay event is not canonical")
            previous = event.event_hash

    def fingerprint(self) -> str:
        self.verify()
        return hashlib.sha256(
            json.dumps(
                [event.event_hash for event in self._events],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def replay_decision_outcomes(self) -> tuple[tuple[str, bool], ...]:
        """Reconstruct the recorded decision outcome without trusting a caller-supplied total."""
        self.verify()
        outcomes: list[tuple[str, bool]] = []
        for event in self._events:
            if event.event_type != "DECISION_OUTCOME":
                continue
            decision_id = event.payload.get("decision_id")
            authorized = event.payload.get("authorized")
            if not isinstance(decision_id, str) or type(authorized) is not bool:
                raise ReplayIntegrityError("decision outcome payload is malformed")
            outcomes.append((decision_id, authorized))
        return tuple(outcomes)


def record_decision(log: Phase4ReplayLog, decision: TradeDecisionV4) -> Phase4ReplayEvent:
    """Record only canonical decision identity and authority outcome, never mutable process state."""
    return log.append(
        "DECISION_OUTCOME",
        decision.created_at,
        {
            "decision_id": decision.decision_id,
            "opportunity_id": decision.opportunity_id,
            "authorized": decision.authorized,
        },
    )


@dataclass(frozen=True)
class Phase4Capability:
    """Least-privilege capability for the Phase 4 handoff only."""

    capability_id: str
    decision_id: str
    opportunity_id: str
    scope: tuple[str, ...]
    issued_at: int
    _proof: object

    def require(self, action: str, decision_id: str, at: int, opportunity=None) -> None:
        if self._proof is not _CAPABILITY_PROOF:
            raise Phase4ValidationError("invalid Phase 4 capability proof")
        if decision_id != self.decision_id:
            raise Phase4ValidationError("capability is bound to a different decision")
        if type(at) is not int or at < self.issued_at:
            raise Phase4ValidationError("capability use is outside its causal lifetime")
        if opportunity is None or opportunity.opportunity_id != self.opportunity_id:
            raise Phase4ValidationError("authoritative opportunity context is required")
        if not opportunity.is_live(at):
            raise Phase4ValidationError("capability is revoked by non-live opportunity state")
        if action not in self.scope:
            raise Phase4ValidationError("action exceeds Phase 4 capability scope")



_CAPABILITY_PROOF = object()
_PHASE4_HANDOFF = "PHASE4_HANDOFF"


def capability_for(decision: TradeDecisionV4) -> Phase4Capability:
    if not decision.phase4_ready:
        raise Phase4ValidationError("non-authoritative decision cannot mint a capability")
    raw = f"{decision.decision_id}|{_PHASE4_HANDOFF}|{decision.created_at}"
    return Phase4Capability(
        capability_id=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        decision_id=decision.decision_id,
        opportunity_id=decision.opportunity_id,
        scope=(_PHASE4_HANDOFF,),
        issued_at=decision.created_at,
        _proof=_CAPABILITY_PROOF,
    )


def assert_capability_is_least_privilege(capability: Phase4Capability) -> None:
    forbidden = {
        "SUBMIT_ORDER",
        "CREATE_EXECUTION_INTENT",
        "ALLOCATE_RISK",
        "SIZE_TRADE",
        "MODIFY_POSITION",
    }
    if forbidden.intersection(capability.scope):
        raise Phase4ValidationError("Phase 4 capability contains forbidden execution authority")

@dataclass(frozen=True)
class DecisionReplayFixture:
    """Canonical serialized inputs required to reconstruct one Phase 4 decision."""

    opportunity: Mapping[str, object]
    tradeability: Mapping[str, object]
    entry_plan: Mapping[str, object]
    gates: tuple[Mapping[str, object], ...]
    confidence: Mapping[str, object]
    created_at: int

    def to_payload(self) -> Mapping[str, object]:
        return {
            "opportunity": dict(self.opportunity),
            "tradeability": dict(self.tradeability),
            "entry_plan": dict(self.entry_plan),
            "gates": [dict(g) for g in self.gates],
            "confidence": dict(self.confidence),
            "created_at": self.created_at,
        }

    @classmethod
    def from_inputs(cls, opportunity, tradeability, entry_plan, gates, confidence, created_at: int) -> "DecisionReplayFixture":
        return cls(
            opportunity={
                "opportunity_id": opportunity.opportunity_id,
                "root_id": opportunity.root_id,
                "parent_opportunity_id": opportunity.parent_opportunity_id,
                "symbol": opportunity.symbol,
                "direction": opportunity.direction,
                "setup_family": opportunity.setup_family,
                "primary_pullback_id": opportunity.primary_pullback_id,
                "created_at": opportunity.created_at,
                "expires_at": opportunity.expires_at,
                "state": opportunity.state.value,
                "opportunity_space": str(opportunity.opportunity_space),
                "structural_edge": str(opportunity.structural_edge),
                "confidence": str(opportunity.confidence),
                "max_entries": opportunity.max_entries,
            },
            tradeability={
                "opportunity_id": tradeability.opportunity_id,
                "status": tradeability.status.value,
                "spread": str(tradeability.spread),
                "total_cost": str(tradeability.total_cost),
                "gross_move": str(tradeability.gross_move),
                "opportunity_space": str(tradeability.opportunity_space),
                "execution_quality": str(tradeability.execution_quality),
                "reasons": list(tradeability.reasons),
                "observed_timestamp": tradeability.observed_timestamp,
                "liquidity_ok": tradeability.liquidity_ok,
                "profile": {
                    "max_spread": str(tradeability.profile.max_spread),
                    "max_cost_ratio": str(tradeability.profile.max_cost_ratio),
                    "min_opportunity_space": str(tradeability.profile.min_opportunity_space),
                    "min_execution_quality": str(tradeability.profile.min_execution_quality),
                },
            },
            entry_plan={
                "entry_plan_id": entry_plan.entry_plan_id,
                "opportunity_id": entry_plan.opportunity_id,
                "symbol": entry_plan.symbol,
                "direction": entry_plan.direction,
                "entry_price": str(entry_plan.entry_price),
                "structural_stop": str(entry_plan.structural_stop),
                "atr_buffer": str(entry_plan.atr_buffer),
                "target_price": str(entry_plan.target_price),
                "minimum_rr_after_costs": str(entry_plan.minimum_rr_after_costs),
                "quote_timestamp": entry_plan.quote_timestamp,
                "expected_total_cost": str(entry_plan.expected_total_cost),
            },
            gates=tuple({
                "gate": g.gate.value,
                "passed": g.passed,
                "reason": g.reason,
                "observed_timestamp": g.observed_timestamp,
                "producer": g.producer,
                "evidence_version": g.evidence_version,
            } for g in gates),
            confidence={
                "value": str(confidence.value),
                "source": confidence.source,
                "model_version": confidence.model_version,
                "observed_timestamp": confidence.observed_timestamp,
            },
            created_at=created_at,
        )

    def replay(self) -> TradeDecisionV4:
        from decimal import Decimal
        from .phase4 import (
            ConfidenceEvidence,
            EntryPlanV4,
            ExecutionQualityProfile,
            GateEvidence,
            Opportunity,
            OpportunityState,
            TradeabilityAssessmentV4,
            TradeabilityStatus,
            make_decision,
        )

        op = self.opportunity
        opportunity = Opportunity(
            opportunity_id=str(op["opportunity_id"]),
            root_id=str(op["root_id"]),
            parent_opportunity_id=op["parent_opportunity_id"],
            symbol=str(op["symbol"]),
            direction=str(op["direction"]),
            setup_family=str(op["setup_family"]),
            primary_pullback_id=str(op["primary_pullback_id"]),
            created_at=int(op["created_at"]),
            expires_at=int(op["expires_at"]),
            state=OpportunityState(str(op["state"])),
            opportunity_space=Decimal(str(op["opportunity_space"])),
            structural_edge=Decimal(str(op["structural_edge"])),
            confidence=Decimal(str(op["confidence"])),
            max_entries=int(op.get("max_entries", 1)),
        )
        tp = self.tradeability["profile"]
        profile = ExecutionQualityProfile(
            Decimal(str(tp["max_spread"])),
            Decimal(str(tp["max_cost_ratio"])),
            Decimal(str(tp["min_opportunity_space"])),
            Decimal(str(tp["min_execution_quality"])),
        )
        t = self.tradeability
        tradeability = TradeabilityAssessmentV4(
            str(t["opportunity_id"]),
            TradeabilityStatus(str(t["status"])),
            Decimal(str(t["spread"])),
            Decimal(str(t["total_cost"])),
            Decimal(str(t["gross_move"])),
            Decimal(str(t["opportunity_space"])),
            Decimal(str(t["execution_quality"])),
            tuple(str(x) for x in t["reasons"]),
            int(t["observed_timestamp"]),
            bool(t["liquidity_ok"]),
            profile,
        )
        ep = self.entry_plan
        entry_plan = EntryPlanV4(
            str(ep["entry_plan_id"]),
            str(ep["opportunity_id"]),
            str(ep["symbol"]),
            str(ep["direction"]),
            Decimal(str(ep["entry_price"])),
            Decimal(str(ep["structural_stop"])),
            Decimal(str(ep["atr_buffer"])),
            Decimal(str(ep["target_price"])),
            Decimal(str(ep["minimum_rr_after_costs"])),
            int(ep["quote_timestamp"]),
            Decimal(str(ep["expected_total_cost"])),
        )
        gates = tuple(
            GateEvidence(
                g["gate"],
                bool(g["passed"]),
                str(g["reason"]),
                int(g["observed_timestamp"]),
                str(g["producer"]),
                int(g["evidence_version"]),
            )
            for g in self.gates
        )
        c = self.confidence
        confidence = ConfidenceEvidence(Decimal(str(c["value"])), str(c["source"]), str(c["model_version"]), int(c["observed_timestamp"]))
        return make_decision(opportunity, tradeability, entry_plan, gates, confidence, self.created_at)

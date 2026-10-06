"""Phase 4 authority-integrity domain primitives.

Phase 4 is a deterministic, account-free handoff boundary.  It establishes
whether an opportunity, its tradeability evidence, and its entry geometry are
internally coherent and causally complete enough for the next protection /
allocation layer.  It does not authorize broker exposure, sizing, or order
submission.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class Phase4ValidationError(ValueError):
    """Raised when a Phase 4 domain object violates a mandatory invariant."""


def _decimal(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise Phase4ValidationError(f"{name} must be a Decimal-compatible finite number") from exc
    if not result.is_finite():
        raise Phase4ValidationError(f"{name} must be finite")
    return result


def _strict_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise Phase4ValidationError(f"{name} must be a boolean")
    return value


@dataclass(frozen=True)
class AccountProfile:
    account_id: str
    broker: str
    currency: str
    enabled: bool = True
    default_lane: str = "PRIMARY"

    def __post_init__(self) -> None:
        for name in ("account_id", "broker", "currency", "default_lane"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise Phase4ValidationError(f"{name} must be a non-empty string")
        _strict_bool(self.enabled, "enabled")
        if not self.account_id.strip() or self.account_id != self.account_id.strip():
            raise Phase4ValidationError("account_id must be canonical and trimmed")


@dataclass(frozen=True)
class AccountRegistry:
    profiles: Mapping[str, AccountProfile]

    def __post_init__(self) -> None:
        if not isinstance(self.profiles, Mapping):
            raise Phase4ValidationError("profiles must be a mapping")
        if len(self.profiles) != len(set(self.profiles)):
            raise Phase4ValidationError("duplicate account identifiers")
        for account_id, profile in self.profiles.items():
            if account_id != profile.account_id:
                raise Phase4ValidationError("account registry key must equal profile account_id")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AccountRegistry":
        import yaml

        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        raw = payload.get("accounts", payload)
        if not isinstance(raw, dict) or not raw:
            raise Phase4ValidationError("accounts.yaml must contain a non-empty accounts mapping")
        profiles: dict[str, AccountProfile] = {}
        required_fields = {"broker", "currency", "enabled", "default_lane"}
        for account_id, value in raw.items():
            if not isinstance(account_id, str) or not account_id.strip():
                raise Phase4ValidationError("account identifiers must be non-empty strings")
            if not isinstance(value, dict):
                raise Phase4ValidationError(f"invalid account profile for {account_id}")
            if set(value) != required_fields:
                missing = sorted(required_fields - set(value))
                extra = sorted(set(value) - required_fields)
                raise Phase4ValidationError(
                    f"invalid account profile for {account_id}: missing={missing}, extra={extra}"
                )
            profile = AccountProfile(
                account_id=account_id,
                broker=value["broker"],
                currency=value["currency"],
                enabled=value["enabled"],
                default_lane=value["default_lane"],
            )
            if profile.account_id in profiles:
                raise Phase4ValidationError(f"duplicate account_id: {profile.account_id}")
            profiles[profile.account_id] = profile
        return cls(profiles=profiles)

    def get(self, account_id: str) -> AccountProfile:
        try:
            return self.profiles[account_id]
        except KeyError as exc:
            raise Phase4ValidationError(f"unknown account_id: {account_id}") from exc


@dataclass(frozen=True)
class AnalysisEnvelope:
    """Account-free analysis envelope. Account identity is intentionally absent."""

    symbol: str
    source_timestamp: int
    analysis_id: str
    payload_hash: str
    schema_version: int = 1

    @classmethod
    def create(cls, symbol: str, source_timestamp: int, payload: Mapping[str, object]) -> "AnalysisEnvelope":
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        aid = hashlib.sha256(f"{symbol}|{source_timestamp}|{digest}".encode("utf-8")).hexdigest()
        return cls(symbol, source_timestamp, aid, digest)


class OpportunityState(str, Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    TRIGGER_READY = "TRIGGER_READY"
    DEGRADED = "DEGRADED"
    INVALIDATED = "INVALIDATED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class LiquiditySweepModifier:
    kind: str
    observed_timestamp: int

    def __post_init__(self) -> None:
        if self.kind not in {"SWEEP_RECOVERY", "SWEEP_REJECTION", "SWEEP_CONTINUATION"}:
            raise Phase4ValidationError("liquidity sweep must be an approved trigger modifier")


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    root_id: str
    parent_opportunity_id: str | None
    symbol: str
    direction: str
    setup_family: str
    primary_pullback_id: str
    created_at: int
    expires_at: int
    state: OpportunityState
    opportunity_space: Decimal
    structural_edge: Decimal
    confidence: Decimal
    sweep_modifier: LiquiditySweepModifier | None = None
    max_entries: int = 1
    strategy_mode: str | None = None

    def __post_init__(self) -> None:
        if self.setup_family not in {"FF-01", "FF-02", "FF-03", "FF-04"}:
            raise Phase4ValidationError("unknown setup family")
        if self.direction not in {"LONG", "SHORT"}:
            raise Phase4ValidationError("direction must be LONG or SHORT")
        if not self.root_id or not self.symbol or not self.primary_pullback_id:
            raise Phase4ValidationError("root_id, symbol and primary_pullback_id are required")
        if type(self.created_at) is not int or type(self.expires_at) is not int:
            raise Phase4ValidationError("opportunity timestamps must be integers")
        if self.created_at < 0 or self.expires_at <= self.created_at:
            raise Phase4ValidationError("opportunity expiry must be after non-negative creation time")
        if self.max_entries < 1:
            raise Phase4ValidationError("max_entries must be positive")
        for name in ("opportunity_space", "structural_edge", "confidence"):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        if self.opportunity_space < 0 or self.structural_edge < 0:
            raise Phase4ValidationError("opportunity_space and structural_edge cannot be negative")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise Phase4ValidationError("confidence must be within [0, 1]")
        canonical = self.deterministic_id(self.root_id, self.symbol, self.primary_pullback_id, self.setup_family, self.direction)
        if self.opportunity_id != canonical:
            raise Phase4ValidationError("opportunity_id does not match canonical deterministic identity")
        if self.sweep_modifier and not self.created_at <= self.sweep_modifier.observed_timestamp < self.expires_at:
            raise Phase4ValidationError("sweep modifier timestamp must be within opportunity lifetime")

    @staticmethod
    def deterministic_id(root_id: str, symbol: str, primary_pullback_id: str, setup_family: str, direction: str) -> str:
        raw = "|".join((root_id, symbol, primary_pullback_id, setup_family, direction))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_live(self, observed_timestamp: int, parent: "Opportunity | None" = None) -> bool:
        if not self.created_at <= observed_timestamp < self.expires_at:
            return False
        if self.state not in {OpportunityState.VALID, OpportunityState.TRIGGER_READY}:
            return False
        if self.parent_opportunity_id is None:
            return True
        return (
            parent is not None
            and parent.opportunity_id == self.parent_opportunity_id
            and parent.is_live(observed_timestamp)
        )


from .phase3 import TimeframeMapping


class TradeabilityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    MARGINAL = "MARGINAL"
    FAIL_SPREAD = "FAIL_SPREAD"
    FAIL_COST = "FAIL_COST"
    FAIL_LIQUIDITY = "FAIL_LIQUIDITY"
    FAIL_EXECUTION = "FAIL_EXECUTION"
    FAIL_OPPORTUNITY_SPACE = "FAIL_OPPORTUNITY_SPACE"
    FAIL_INVALID_INPUT = "FAIL_INVALID_INPUT"


@dataclass(frozen=True)
class ExecutionQualityProfile:
    max_spread: Decimal
    max_cost_ratio: Decimal
    min_opportunity_space: Decimal
    min_execution_quality: Decimal

    def __post_init__(self) -> None:
        for name in ("max_spread", "max_cost_ratio", "min_opportunity_space", "min_execution_quality"):
            value = _decimal(getattr(self, name), name)
            object.__setattr__(self, name, value)
            if value < 0:
                raise Phase4ValidationError(f"{name} cannot be negative")
        if self.max_cost_ratio <= 0:
            raise Phase4ValidationError("max_cost_ratio must be positive")


@dataclass(frozen=True)
class TradeabilityAssessmentV4:
    opportunity_id: str
    status: TradeabilityStatus
    spread: Decimal
    total_cost: Decimal
    gross_move: Decimal
    opportunity_space: Decimal
    execution_quality: Decimal
    reasons: tuple[str, ...] = ()
    observed_timestamp: int = 0
    liquidity_ok: bool = True
    profile: ExecutionQualityProfile | None = None

    def __post_init__(self) -> None:
        for name in ("spread", "total_cost", "gross_move", "opportunity_space", "execution_quality"):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        if any(getattr(self, name) < 0 for name in ("spread", "total_cost", "gross_move", "opportunity_space")):
            raise Phase4ValidationError("tradeability economics cannot be negative")
        if not 0 <= self.execution_quality <= 1:
            raise Phase4ValidationError("execution_quality must be within [0, 1]")
        _strict_bool(self.liquidity_ok, "liquidity_ok")
        if type(self.observed_timestamp) is not int:
            raise Phase4ValidationError("tradeability observed_timestamp must be an integer")
        if self.profile is None:
            raise Phase4ValidationError("tradeability assessment must carry its authoritative profile")
        reasons = set(self.reasons)
        expected: list[str] = []
        if self.spread > self.profile.max_spread:
            expected.append("SPREAD")
        if self.gross_move <= 0 or self.total_cost >= self.gross_move or self.total_cost / self.gross_move > self.profile.max_cost_ratio:
            expected.append("COST")
        if not self.liquidity_ok:
            expected.append("LIQUIDITY")
        if self.opportunity_space < self.profile.min_opportunity_space:
            expected.append("OPPORTUNITY_SPACE")
        if self.execution_quality < self.profile.min_execution_quality:
            expected.append("EXECUTION")
        expected_status = (
            TradeabilityStatus.FAIL_SPREAD if "SPREAD" in expected else
            TradeabilityStatus.FAIL_COST if "COST" in expected else
            TradeabilityStatus.FAIL_LIQUIDITY if "LIQUIDITY" in expected else
            TradeabilityStatus.FAIL_OPPORTUNITY_SPACE if "OPPORTUNITY_SPACE" in expected else
            TradeabilityStatus.FAIL_EXECUTION if "EXECUTION" in expected else
            TradeabilityStatus.PASS
        )
        if self.status != expected_status or reasons != set(expected):
            raise Phase4ValidationError("tradeability status/reasons do not match authoritative inputs")


class TradeabilityEngine:
    """Economic gate. It cannot authorize, size, or submit a trade."""

    def evaluate(
        self,
        opportunity: Opportunity,
        spread: Decimal,
        commission: Decimal,
        slippage: Decimal,
        gross_move: Decimal,
        liquidity_ok: bool,
        execution_quality: Decimal,
        profile: ExecutionQualityProfile,
        observed_timestamp: int | None = None,
        parent_opportunity: Opportunity | None = None,
    ) -> TradeabilityAssessmentV4:
        spread = _decimal(spread, "spread")
        commission = _decimal(commission, "commission")
        slippage = _decimal(slippage, "slippage")
        gross_move = _decimal(gross_move, "gross_move")
        eq = _decimal(execution_quality, "execution_quality")
        _strict_bool(liquidity_ok, "liquidity_ok")
        if any(value < 0 for value in (spread, commission, slippage)):
            raise Phase4ValidationError("spread, commission and slippage cannot be negative")
        if gross_move <= 0:
            raise Phase4ValidationError("gross_move must be positive")
        if not 0 <= eq <= 1:
            raise Phase4ValidationError("execution_quality must be within [0, 1]")
        observed = opportunity.created_at if observed_timestamp is None else observed_timestamp
        if not opportunity.is_live(observed, parent_opportunity):
            raise Phase4ValidationError("tradeability cannot be assessed for a non-live opportunity")
        if observed < opportunity.created_at or observed >= opportunity.expires_at:
            raise Phase4ValidationError("tradeability observation is outside opportunity lifetime")
        total_cost = spread + commission + slippage
        oq = opportunity.opportunity_space
        reasons: list[str] = []
        if spread > profile.max_spread:
            reasons.append("SPREAD")
        if total_cost >= gross_move or total_cost / gross_move > profile.max_cost_ratio:
            reasons.append("COST")
        if not liquidity_ok:
            reasons.append("LIQUIDITY")
        if oq < profile.min_opportunity_space:
            reasons.append("OPPORTUNITY_SPACE")
        if eq < profile.min_execution_quality:
            reasons.append("EXECUTION")
        if "SPREAD" in reasons:
            status = TradeabilityStatus.FAIL_SPREAD
        elif "COST" in reasons:
            status = TradeabilityStatus.FAIL_COST
        elif "LIQUIDITY" in reasons:
            status = TradeabilityStatus.FAIL_LIQUIDITY
        elif "OPPORTUNITY_SPACE" in reasons:
            status = TradeabilityStatus.FAIL_OPPORTUNITY_SPACE
        elif "EXECUTION" in reasons:
            status = TradeabilityStatus.FAIL_EXECUTION
        else:
            status = TradeabilityStatus.PASS
        return TradeabilityAssessmentV4(opportunity.opportunity_id, status, spread, total_cost, gross_move, oq, eq, tuple(reasons), observed, liquidity_ok, profile)


class Phase4GateType(str, Enum):
    OPPORTUNITY = "OPPORTUNITY"
    TRADEABILITY = "TRADEABILITY"
    ENTRY_PLAN = "ENTRY_PLAN"


@dataclass(frozen=True)
class GateEvidence:
    gate: Phase4GateType | str
    passed: bool
    reason: str
    observed_timestamp: int
    producer: str = "phase4"
    evidence_version: int = 1

    def __post_init__(self) -> None:
        try:
            gate = self.gate if isinstance(self.gate, Phase4GateType) else Phase4GateType(self.gate)
        except ValueError as exc:
            raise Phase4ValidationError(f"unknown Phase 4 gate: {self.gate}") from exc
        object.__setattr__(self, "gate", gate)
        _strict_bool(self.passed, "gate.passed")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise Phase4ValidationError("gate reason must be non-empty")
        if not isinstance(self.producer, str) or not self.producer.strip():
            raise Phase4ValidationError("gate producer must be non-empty")
        if self.evidence_version < 1:
            raise Phase4ValidationError("evidence_version must be positive")
        if type(self.observed_timestamp) is not int:
            raise Phase4ValidationError("gate observed_timestamp must be an integer")


@dataclass(frozen=True)
class ConfidenceEvidence:
    value: Decimal
    source: str
    model_version: str
    observed_timestamp: int

    def __post_init__(self) -> None:
        value = _decimal(self.value, "confidence")
        object.__setattr__(self, "value", value)
        if not 0 <= value <= 1:
            raise Phase4ValidationError("confidence must be within [0, 1]")
        if not isinstance(self.source, str) or not isinstance(self.model_version, str) or not self.source.strip() or not self.model_version.strip():
            raise Phase4ValidationError("confidence provenance is required")
        if type(self.observed_timestamp) is not int:
            raise Phase4ValidationError("confidence observed_timestamp must be an integer")


@dataclass(frozen=True)
class EntryPlanV4:
    """Account/risk-free execution geometry; never position sizing or exposure authority."""

    entry_plan_id: str
    opportunity_id: str
    symbol: str
    direction: str
    entry_price: Decimal
    structural_stop: Decimal
    atr_buffer: Decimal
    target_price: Decimal
    minimum_rr_after_costs: Decimal
    quote_timestamp: int
    expected_total_cost: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in ("entry_price", "structural_stop", "atr_buffer", "target_price", "minimum_rr_after_costs", "expected_total_cost"):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        if self.direction not in {"LONG", "SHORT"}:
            raise Phase4ValidationError("direction must be LONG or SHORT")
        if self.atr_buffer <= 0:
            raise Phase4ValidationError("atr_buffer must be positive")
        if self.minimum_rr_after_costs <= 0:
            raise Phase4ValidationError("minimum_rr_after_costs must be positive")
        if self.expected_total_cost < 0:
            raise Phase4ValidationError("expected_total_cost cannot be negative")
        if type(self.quote_timestamp) is not int:
            raise Phase4ValidationError("quote_timestamp must be an integer")
        if self.direction == "LONG":
            effective_stop = self.structural_stop - self.atr_buffer
            reward = self.target_price - self.entry_price
            if not effective_stop < self.entry_price < self.target_price:
                raise Phase4ValidationError("LONG geometry requires effective_stop < entry < target")
        else:
            effective_stop = self.structural_stop + self.atr_buffer
            reward = self.entry_price - self.target_price
            if not self.target_price < self.entry_price < effective_stop:
                raise Phase4ValidationError("SHORT geometry requires target < entry < effective_stop")
        risk = abs(self.entry_price - effective_stop)
        net_reward = reward - self.expected_total_cost
        if risk <= 0 or net_reward <= 0:
            raise Phase4ValidationError("entry plan must have positive post-cost risk and reward")
        if net_reward / risk < self.minimum_rr_after_costs:
            raise Phase4ValidationError("entry plan does not satisfy minimum post-cost RR")




def _decision_fingerprint(
    opportunity_id: str,
    tradeability: TradeabilityAssessmentV4,
    entry_plan: EntryPlanV4,
    gates: Sequence[GateEvidence],
    confidence: ConfidenceEvidence,
    created_at: int,
    parent_content_hash: str = "",
) -> str:
    """Canonical identity of the complete Phase 4 decision evidence."""
    decision_seed = json.dumps(
        {
            "opportunity_id": opportunity_id,
            "tradeability": tradeability.__dict__,
            "entry_plan": entry_plan.__dict__,
            "gates": [g.__dict__ | {"gate": g.gate.value} for g in gates],
            "confidence": confidence.__dict__,
            "created_at": created_at,
            "parent_content_hash": parent_content_hash,
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(decision_seed.encode("utf-8")).hexdigest()


def _opportunity_content_hash(opportunity: Opportunity) -> str:
    payload = {
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
        "strategy_mode": opportunity.strategy_mode,
        "max_entries": opportunity.max_entries,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


_PHASE4_AUTHORITY_PROOF = object()


@dataclass(frozen=True)
class TradeDecisionV4:
    """Immutable Phase 4 decision record.

    Direct construction creates a non-authoritative record. Only ``make_decision``
    can attach the opaque authority proof after completing the full opportunity,
    lineage, temporal, tradeability, gate, confidence, and EntryPlan checks.
    """

    decision_id: str
    opportunity_id: str
    root_id: str
    account_id: str | None
    entry_plan: EntryPlanV4
    tradeability: TradeabilityAssessmentV4
    gates: tuple[GateEvidence, ...]
    confidence: ConfidenceEvidence
    created_at: int
    opportunity_content_hash: str = ""
    parent_content_hash: str = ""
    _authority_proof: object | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.created_at) is not int:
            raise Phase4ValidationError("decision created_at must be an integer")
        if self.entry_plan.opportunity_id != self.opportunity_id:
            raise Phase4ValidationError("decision opportunity_id must match entry plan")
        canonical = _decision_fingerprint(
            self.opportunity_id,
            self.tradeability,
            self.entry_plan,
            self.gates,
            self.confidence,
            self.created_at,
            self.parent_content_hash,
        )
        if self.decision_id != canonical:
            raise Phase4ValidationError("decision_id does not match canonical decision fingerprint")
        if self.opportunity_content_hash and len(self.opportunity_content_hash) != 64:
            raise Phase4ValidationError("opportunity_content_hash must be a SHA-256 digest")

    def is_live_authorized(self, authoritative_opportunity: Opportunity, at: int, parent_opportunity: Opportunity | None = None) -> bool:
        """Re-derive Phase-4 validity from current authoritative opportunity evidence."""
        if not self.phase4_ready:
            return False
        if self.opportunity_content_hash != _opportunity_content_hash(authoritative_opportunity):
            return False
        if authoritative_opportunity.opportunity_id != self.opportunity_id:
            return False
        if authoritative_opportunity.root_id != self.root_id:
            return False
        if authoritative_opportunity.parent_opportunity_id is not None:
            if parent_opportunity is None:
                return False
            if self.parent_content_hash != _opportunity_content_hash(parent_opportunity):
                return False
        return authoritative_opportunity.is_live(at, parent_opportunity)

    @property
    def phase4_ready(self) -> bool:
        # Structural validity is necessary but never sufficient for authority.
        # The opaque proof is minted only by make_decision(), so a caller who
        # reconstructs a byte-for-byte valid dataclass cannot manufacture the
        # authority bit.
        return (
            self._authority_proof is _PHASE4_AUTHORITY_PROOF
            and bool(self.opportunity_content_hash)
            and self.decision_id
            == _decision_fingerprint(
                self.opportunity_id,
                self.tradeability,
                self.entry_plan,
                self.gates,
                self.confidence,
                self.created_at,
                self.parent_content_hash,
            )
            and self.tradeability.status == TradeabilityStatus.PASS
            and self.opportunity_id == self.entry_plan.opportunity_id
            and all(g.passed for g in self.gates)
            and {g.gate for g in self.gates} == set(Phase4GateType)
        )

    @property
    def authorized(self) -> bool:
        """Phase-4 authority only; never broker/exposure authorization."""
        return self.phase4_ready


def _validate_parent(opportunity: Opportunity, parent_opportunity: Opportunity | None, at: int) -> None:
    if opportunity.parent_opportunity_id is None:
        if parent_opportunity is not None:
            raise Phase4ValidationError("parent supplied for root opportunity")
        return
    if parent_opportunity is None:
        raise Phase4ValidationError("parent opportunity evidence is required for child authorization")
    if parent_opportunity.opportunity_id != opportunity.parent_opportunity_id:
        raise Phase4ValidationError("parent opportunity identity mismatch")
    if not parent_opportunity.is_live(at):
        raise Phase4ValidationError("parent opportunity is not live")


def make_decision(
    opportunity: Opportunity,
    tradeability: TradeabilityAssessmentV4,
    entry_plan: EntryPlanV4,
    gates: Sequence[GateEvidence],
    confidence: ConfidenceEvidence,
    created_at: int,
    parent_opportunity: Opportunity | None = None,
    account_id: str | None = None,
) -> TradeDecisionV4:
    if not opportunity.is_live(created_at, parent_opportunity):
        raise Phase4ValidationError("decision cannot be constructed for a non-live opportunity")
    _validate_parent(opportunity, parent_opportunity, created_at)
    if tradeability.opportunity_id != opportunity.opportunity_id:
        raise Phase4ValidationError("tradeability evidence belongs to a different opportunity")
    if tradeability.status != TradeabilityStatus.PASS:
        raise Phase4ValidationError("non-PASS tradeability is non-authorizing")
    if tradeability.observed_timestamp > created_at:
        raise Phase4ValidationError("tradeability evidence cannot originate from the future")
    if entry_plan.opportunity_id != opportunity.opportunity_id or entry_plan.symbol != opportunity.symbol or entry_plan.direction != opportunity.direction:
        raise Phase4ValidationError("entry plan does not match opportunity identity")
    if entry_plan.quote_timestamp > created_at or entry_plan.quote_timestamp < opportunity.created_at:
        raise Phase4ValidationError("entry-plan quote is causally outside decision lifetime")
    if confidence.observed_timestamp > created_at or confidence.observed_timestamp < opportunity.created_at:
        raise Phase4ValidationError("confidence evidence is causally outside decision lifetime")
    if confidence.value > opportunity.confidence:
        raise Phase4ValidationError("decision confidence cannot exceed opportunity confidence")

    ordered = tuple(sorted(gates, key=lambda g: g.gate.value))
    if len(ordered) != len({g.gate for g in ordered}):
        raise Phase4ValidationError("duplicate gate evidence is non-authorizing")
    if {g.gate for g in ordered} != set(Phase4GateType):
        raise Phase4ValidationError("exact Phase 4 mandatory gate set is required")
    if any(g.observed_timestamp < opportunity.created_at or g.observed_timestamp > created_at for g in ordered):
        raise Phase4ValidationError("gate evidence is causally outside decision lifetime")
    gate_map = {g.gate: g for g in ordered}
    if gate_map[Phase4GateType.OPPORTUNITY].passed and not opportunity.is_live(created_at, parent_opportunity):
        raise Phase4ValidationError("opportunity gate evidence contradicts authoritative opportunity state")
    if gate_map[Phase4GateType.TRADEABILITY].passed and tradeability.status != TradeabilityStatus.PASS:
        raise Phase4ValidationError("tradeability gate evidence contradicts authoritative tradeability")
    if gate_map[Phase4GateType.ENTRY_PLAN].passed:
        # EntryPlanV4 construction is itself the authoritative geometry check.
        pass
    parent_content_hash = _opportunity_content_hash(parent_opportunity) if parent_opportunity is not None else ""
    decision_id = _decision_fingerprint(
        opportunity.opportunity_id, tradeability, entry_plan, ordered, confidence, created_at, parent_content_hash
    )
    decision = TradeDecisionV4(
        decision_id=decision_id,
        opportunity_id=opportunity.opportunity_id,
        root_id=opportunity.root_id,
        account_id=account_id.strip() if account_id is not None else None,
        entry_plan=entry_plan,
        tradeability=tradeability,
        gates=ordered,
        confidence=confidence,
        created_at=created_at,
        opportunity_content_hash=_opportunity_content_hash(opportunity),
        parent_content_hash=parent_content_hash,
    )
    # The proof is deliberately installed after construction so public
    # dataclass construction has no supported path to authority.
    object.__setattr__(decision, "_authority_proof", _PHASE4_AUTHORITY_PROOF)
    return decision

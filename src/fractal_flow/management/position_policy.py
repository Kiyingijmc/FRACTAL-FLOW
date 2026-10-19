"""Deterministic, reduce-only position-management advice.

This module is deliberately a pure policy boundary. It does not mutate Position,
write journals, create execution intents, or call a broker adapter. A caller must
independently validate broker truth and authorize any action through the existing
execution/reconciliation path.

Safety precedence:
1. Unreconciled or orphaned positions cannot be closed/reduced by this policy.
2. Confirmed structural invalidation closes only a reconciled, owned position.
3. Confirmed invalid/critical health closes only a reconciled, owned position.
4. An expired TTL is not an automatic close: explicit rescue assessment is required.
5. A stop proposal is accepted only when it is a valid, market-safe ratchet.
6. No action can increase exposure or loosen a protective stop.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Final


class ManagementPolicyError(ValueError):
    """Raised when policy inputs are malformed or non-deterministic."""


class ManagementAction(str, Enum):
    HOLD = "HOLD"
    TIGHTEN_STOP = "TIGHTEN_STOP"
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"


_ALLOWED_RECONCILED: Final[frozenset[str]] = frozenset({"RECON_NORMAL", "RECON_RECOVERED"})
_ORPHAN_RECONCILIATION: Final[frozenset[str]] = frozenset(
    {"RECON_SUSPECTED_ORPHAN", "RECON_RECONCILING", "RECON_QUARANTINED"}
)
_TTL_STATES: Final[frozenset[str]] = frozenset(
    {"TTL_ACTIVE", "TTL_WARNING", "TTL_DECAYING", "TTL_EXPIRING", "TTL_EXPIRED"}
)


def _decimal(name: str, value: Decimal | str | int) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ManagementPolicyError(f"{name} must be a decimal-compatible value") from exc
    if not result.is_finite():
        raise ManagementPolicyError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class ManagementFacts:
    """Point-in-time facts supplied by an authoritative caller.

    `ttl_rescue_viable` must be `True`/`False` only after the caller evaluates the
    configured rescue policy; `None` means no authoritative assessment exists.
    `reduction_evidence` is a boolean conclusion, not a model score.
    """

    position_id: str
    side: str
    lifecycle_state: str
    health_state: str
    ttl_state: str
    reconciliation_status: str
    current_price: Decimal
    current_stop: Decimal
    candidate_stop: Decimal | None = None
    min_stop_distance: Decimal = Decimal("0")
    structural_invalidated: bool = False
    ttl_rescue_viable: bool | None = None
    reduction_evidence: bool = False
    is_orphan: bool = False

    def __post_init__(self) -> None:
        for name in ("position_id", "lifecycle_state", "health_state", "ttl_state", "reconciliation_status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ManagementPolicyError(f"{name} is required")
        side = self.side.upper() if isinstance(self.side, str) else ""
        if side not in {"LONG", "SHORT"}:
            raise ManagementPolicyError("side must be LONG or SHORT")
        object.__setattr__(self, "side", side)
        if self.ttl_state not in _TTL_STATES:
            raise ManagementPolicyError(f"unsupported TTL state: {self.ttl_state}")
        for name in ("current_price", "current_stop", "min_stop_distance"):
            object.__setattr__(self, name, _decimal(name, getattr(self, name)))
        if self.candidate_stop is not None:
            object.__setattr__(self, "candidate_stop", _decimal("candidate_stop", self.candidate_stop))
        if self.min_stop_distance < 0:
            raise ManagementPolicyError("min_stop_distance must be non-negative")
        if self.ttl_rescue_viable not in (None, True, False):
            raise ManagementPolicyError("ttl_rescue_viable must be True, False, or None")
        if not isinstance(self.structural_invalidated, bool) or not isinstance(self.reduction_evidence, bool):
            raise ManagementPolicyError("policy evidence fields must be booleans")
        if not isinstance(self.is_orphan, bool):
            raise ManagementPolicyError("is_orphan must be a boolean")


@dataclass(frozen=True)
class ManagementAdvice:
    """Auditable recommendation; never an executable order."""

    position_id: str
    action: ManagementAction
    reason: str
    stop_candidate: Decimal | None = None
    reduce_only: bool = True

    def __post_init__(self) -> None:
        if not self.position_id or not self.reason:
            raise ManagementPolicyError("advice identity and reason are required")
        if self.action is ManagementAction.TIGHTEN_STOP and self.stop_candidate is None:
            raise ManagementPolicyError("TIGHTEN_STOP requires stop_candidate")
        if self.action is not ManagementAction.TIGHTEN_STOP and self.stop_candidate is not None:
            raise ManagementPolicyError("stop_candidate is only valid for TIGHTEN_STOP")
        if self.reduce_only is not True:
            raise ManagementPolicyError("management advice must remain reduce-only")


def _advice(facts: ManagementFacts, action: ManagementAction, reason: str,
            stop: Decimal | None = None) -> ManagementAdvice:
    return ManagementAdvice(facts.position_id, action, reason, stop, True)


def _valid_ratchet(facts: ManagementFacts) -> Decimal | None:
    candidate = facts.candidate_stop
    if candidate is None:
        return None
    if facts.side == "LONG":
        # A long stop can only move upward and must remain below market by the
        # broker-provided minimum distance.
        if candidate <= facts.current_stop:
            return None
        if candidate >= facts.current_price - facts.min_stop_distance:
            return None
    else:
        # A short stop can only move downward and must remain above market by
        # the broker-provided minimum distance.
        if candidate >= facts.current_stop:
            return None
        if candidate <= facts.current_price + facts.min_stop_distance:
            return None
    return candidate


def evaluate_management(facts: ManagementFacts) -> ManagementAdvice:
    """Evaluate a bounded, deterministic management policy without side effects."""
    reconciled = facts.reconciliation_status in _ALLOWED_RECONCILED and not facts.is_orphan
    orphaned = facts.is_orphan or facts.reconciliation_status in _ORPHAN_RECONCILIATION

    # Lifecycle terminal/in-flight states must not receive duplicate management
    # actions. This check is intentionally before structural/TTL recommendations.
    lifecycle = facts.lifecycle_state.upper()
    if lifecycle in {"POS_OPENING", "POS_CLOSING", "POS_CLOSED"}:
        return _advice(facts, ManagementAction.HOLD, "POSITION_LIFECYCLE_NOT_MANAGEABLE")

    # Orphan/uncertain positions are never strategically closed or reduced here.
    # Protective stop tightening remains permitted when the proposed ratchet is safe.
    if not reconciled:
        stop = _valid_ratchet(facts) if orphaned else None
        if stop is not None:
            return _advice(facts, ManagementAction.TIGHTEN_STOP, "ORPHAN_PROTECTIVE_RATCHET_ONLY", stop)
        return _advice(facts, ManagementAction.HOLD, "BROKER_TRUTH_OR_OWNERSHIP_UNCONFIRMED")

    # Hard structural invalidation outranks TTL rescue and all softer evidence.
    if facts.structural_invalidated:
        return _advice(facts, ManagementAction.CLOSE, "HARD_STRUCTURAL_INVALIDATION")

    health = facts.health_state.upper()
    if health in {"HEALTH_INVALID", "HEALTH_CRITICAL", "INVALID", "CRITICAL"}:
        return _advice(facts, ManagementAction.CLOSE, "POSITION_HEALTH_INVALID_OR_CRITICAL")

    if facts.ttl_state == "TTL_EXPIRED":
        if facts.ttl_rescue_viable is None:
            return _advice(facts, ManagementAction.HOLD, "TTL_EXPIRED_REQUIRES_EXPLICIT_RESCUE_ASSESSMENT")
        if facts.ttl_rescue_viable is False:
            return _advice(facts, ManagementAction.CLOSE, "TTL_EXPIRED_RESCUE_NOT_VIABLE")
        # A viable rescue does not reset TTL history or imply renewed entry authority.

    stop = _valid_ratchet(facts)
    if stop is not None:
        return _advice(facts, ManagementAction.TIGHTEN_STOP, "VALID_MARKET_SAFE_STOP_RATCHET", stop)

    if facts.reduction_evidence and health in {
        "HEALTH_STALLED", "HEALTH_DAMAGED", "STALLED", "DAMAGED"
    }:
        return _advice(facts, ManagementAction.REDUCE, "DAMAGE_OR_STALL_WITH_REDUCTION_EVIDENCE")

    if facts.ttl_state in {"TTL_WARNING", "TTL_DECAYING", "TTL_EXPIRING"}:
        return _advice(facts, ManagementAction.HOLD, "TTL_REVIEW_REQUIRED_NO_AUTOMATIC_CLOSE")

    return _advice(facts, ManagementAction.HOLD, "NO_PROVEN_PROTECTIVE_ACTION")

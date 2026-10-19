"""Fail-closed validation for causally confirmed, broker-safe stop proposals.

This module is a pure precondition gate. It does not send broker requests, mutate
positions, normalize prices, or persist modify budgets. Callers must supply
fresh bid/ask and broker-derived distances in absolute price units, and must
still route accepted proposals through the durable command/reconciliation path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class StopGateError(ValueError):
    """Raised when a stop-gate input is malformed."""


class StopGateReason(StrEnum):
    ACCEPTED = "ACCEPTED"
    STALE_OR_FUTURE_STRUCTURE = "STALE_OR_FUTURE_STRUCTURE"
    NOT_A_RATCHET = "NOT_A_RATCHET"
    PRICE_NOT_TICK_ALIGNED = "PRICE_NOT_TICK_ALIGNED"
    BROKER_STOPS_DISTANCE = "BROKER_STOPS_DISTANCE"
    BROKER_FREEZE_DISTANCE = "BROKER_FREEZE_DISTANCE"


@dataclass(frozen=True)
class StopProposal:
    position_id: str
    side: str
    current_stop: Decimal
    proposed_stop: Decimal
    bid: Decimal
    ask: Decimal
    tick_size: Decimal
    stops_distance_price: Decimal
    freeze_distance_price: Decimal
    structure_confirmed_at_ms: int
    decision_at_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.position_id, str) or not self.position_id.strip():
            raise StopGateError("position_id is required")
        side = self.side.upper() if isinstance(self.side, str) else ""
        if side not in {"LONG", "SHORT"}:
            raise StopGateError("side must be LONG or SHORT")
        object.__setattr__(self, "side", side)
        for name in (
            "current_stop", "proposed_stop", "bid", "ask", "tick_size",
            "stops_distance_price", "freeze_distance_price",
        ):
            object.__setattr__(self, name, _finite_decimal(name, getattr(self, name)))
        if self.tick_size <= 0:
            raise StopGateError("tick_size must be positive")
        if self.stops_distance_price < 0 or self.freeze_distance_price < 0:
            raise StopGateError("broker distances must be non-negative")
        if self.bid <= 0 or self.ask <= 0 or self.bid > self.ask:
            raise StopGateError("bid/ask must be positive and bid must not exceed ask")
        if self.structure_confirmed_at_ms < 0 or self.decision_at_ms < 0:
            raise StopGateError("timestamps must be non-negative")


def _finite_decimal(name: str, value: Decimal | str | int) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise StopGateError(f"{name} must be decimal-compatible") from exc
    if not result.is_finite():
        raise StopGateError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class StopGateResult:
    accepted: bool
    reason: StopGateReason
    proposed_stop: Decimal


def validate_stop_proposal(proposal: StopProposal) -> StopGateResult:
    """Validate causality, monotonicity, tick alignment, and broker distances.

    Distances are explicitly absolute price distances, not pips. For a long,
    the stop must remain below bid; for a short, it must remain above ask. The
    larger of stops/freeze distances is not substituted for the individual
    checks, so the returned reason identifies which broker constraint failed.
    """
    if proposal.structure_confirmed_at_ms > proposal.decision_at_ms:
        return StopGateResult(False, StopGateReason.STALE_OR_FUTURE_STRUCTURE, proposal.proposed_stop)

    if proposal.side == "LONG":
        if proposal.proposed_stop <= proposal.current_stop:
            return StopGateResult(False, StopGateReason.NOT_A_RATCHET, proposal.proposed_stop)
        distance = proposal.bid - proposal.proposed_stop
    else:
        if proposal.proposed_stop >= proposal.current_stop:
            return StopGateResult(False, StopGateReason.NOT_A_RATCHET, proposal.proposed_stop)
        distance = proposal.proposed_stop - proposal.ask

    if proposal.proposed_stop % proposal.tick_size != 0:
        return StopGateResult(False, StopGateReason.PRICE_NOT_TICK_ALIGNED, proposal.proposed_stop)
    if distance < proposal.stops_distance_price:
        return StopGateResult(False, StopGateReason.BROKER_STOPS_DISTANCE, proposal.proposed_stop)
    if distance < proposal.freeze_distance_price:
        return StopGateResult(False, StopGateReason.BROKER_FREEZE_DISTANCE, proposal.proposed_stop)
    return StopGateResult(True, StopGateReason.ACCEPTED, proposal.proposed_stop)

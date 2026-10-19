"""Fail-closed, operation-specific reconciliation for protective-stop changes.

This module evaluates broker observations only. It does not dispatch commands,
mutate positions, update command ledgers, or authorize retries. A confirmed result
means the requested stop is observed on the same position in a fresh,
authoritative observation after dispatch; it is not a general execution receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from src.fractal_flow.execution.broker_truth import BrokerObservation, ObservationAuthority


class StopReconciliationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    POSITION_MISSING = "POSITION_MISSING"
    STOP_MISMATCH = "STOP_MISMATCH"


@dataclass(frozen=True)
class StopChangeRequest:
    """Immutable identity and causal bounds for one stop-change command."""

    account_id: str
    account_login: int
    broker: str
    server: str
    terminal_instance: str
    session_id: str
    command_id: str
    position_ticket: str
    position_identifier: str
    symbol: str
    side: str
    requested_stop: Decimal
    dispatched_at_ms: int
    decision_at_ms: int
    max_observation_age_ms: int

    def __post_init__(self) -> None:
        for name in (
            "account_id", "broker", "server", "terminal_instance", "session_id",
            "command_id", "position_ticket", "position_identifier", "symbol",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if isinstance(self.account_login, bool) or not isinstance(self.account_login, int) or self.account_login < 0:
            raise ValueError("account_login must be a non-negative integer")
        side = self.side.upper() if isinstance(self.side, str) else ""
        if side not in {"BUY", "SELL", "LONG", "SHORT"}:
            raise ValueError("side must be BUY/SELL/LONG/SHORT")
        object.__setattr__(self, "side", "LONG" if side in {"BUY", "LONG"} else "SHORT")
        stop = self.requested_stop
        if not isinstance(stop, Decimal):
            try:
                stop = Decimal(str(stop))
            except Exception as exc:
                raise ValueError("requested_stop must be decimal-compatible") from exc
        if not stop.is_finite() or stop <= 0:
            raise ValueError("requested_stop must be finite and positive")
        object.__setattr__(self, "requested_stop", stop)
        for name in ("dispatched_at_ms", "decision_at_ms", "max_observation_age_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.decision_at_ms > self.dispatched_at_ms:
            raise ValueError("decision timestamp cannot follow dispatch timestamp")


@dataclass(frozen=True)
class StopReconciliationResult:
    status: StopReconciliationStatus
    command_id: str
    observation_id: str
    position_ticket: str
    requested_stop: Decimal
    observed_stop: Decimal | None
    reason: str

    @property
    def confirmed(self) -> bool:
        return self.status is StopReconciliationStatus.CONFIRMED


def reconcile_stop_change(
    request: StopChangeRequest,
    observation: BrokerObservation,
    *,
    now_ms: int,
) -> StopReconciliationResult:
    """Reconcile a stop change against a fresh, authoritative position snapshot.

    Exact Decimal equality is required to confirm this command. A tighter stop
    that differs from the requested value is a conflict/superseding change, not
    proof that this command was applied. This function never authorizes resend.
    """
    if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < 0:
        raise ValueError("now_ms must be a non-negative integer")

    def result(status: StopReconciliationStatus, reason: str, observed: Decimal | None = None):
        return StopReconciliationResult(
            status, request.command_id, observation.observation_id,
            request.position_ticket, request.requested_stop, observed, reason,
        )

    if observation.authority is not ObservationAuthority.AUTHORITATIVE:
        return result(StopReconciliationStatus.UNKNOWN, "OBSERVATION_NOT_AUTHORITATIVE")

    expected_context = (
        observation.account.account_id == request.account_id
        and observation.account.login == request.account_login
        and observation.account.broker == request.broker
        and observation.account.server == request.server
        and observation.account.terminal_instance == request.terminal_instance
        and observation.account.session_id == request.session_id
    )
    if not expected_context:
        return result(StopReconciliationStatus.CONFLICT, "ACCOUNT_CONTEXT_MISMATCH")
    if observation.session_id != request.session_id:
        return result(StopReconciliationStatus.CONFLICT, "OBSERVATION_SESSION_MISMATCH")

    if observation.observed_at_ms < request.dispatched_at_ms:
        return result(StopReconciliationStatus.UNKNOWN, "OBSERVATION_PRECEDES_DISPATCH")
    if observation.observed_at_ms > now_ms:
        return result(StopReconciliationStatus.UNKNOWN, "OBSERVATION_FROM_FUTURE")
    if now_ms - observation.observed_at_ms > request.max_observation_age_ms:
        return result(StopReconciliationStatus.UNKNOWN, "OBSERVATION_STALE")

    matches = [
        position for position in observation.positions
        if position.ticket == request.position_ticket
        or position.identifier == request.position_identifier
    ]
    if not matches:
        return result(StopReconciliationStatus.POSITION_MISSING, "POSITION_NOT_PRESENT_IN_AUTHORITATIVE_SNAPSHOT")
    if len(matches) != 1:
        return result(StopReconciliationStatus.CONFLICT, "AMBIGUOUS_POSITION_IDENTITY")

    position = matches[0]
    observed_side = position.side.upper() if isinstance(position.side, str) else ""
    observed_side = "LONG" if observed_side in {"BUY", "LONG"} else "SHORT" if observed_side in {"SELL", "SHORT"} else observed_side
    if (
        position.ticket != request.position_ticket
        or position.identifier != request.position_identifier
        or position.symbol != request.symbol
        or observed_side != request.side
    ):
        return result(StopReconciliationStatus.CONFLICT, "POSITION_IDENTITY_MISMATCH", position.stop_loss)
    if position.timestamp_ms < request.dispatched_at_ms or position.timestamp_ms > observation.observed_at_ms:
        return result(StopReconciliationStatus.UNKNOWN, "POSITION_STATE_NOT_CAUSALLY_CURRENT", position.stop_loss)

    if position.stop_loss is None:
        return result(StopReconciliationStatus.STOP_MISMATCH, "OBSERVED_POSITION_HAS_NO_STOP", None)

    observed_stop = position.stop_loss
    if not isinstance(observed_stop, Decimal) or not observed_stop.is_finite() or observed_stop <= 0:
        return result(StopReconciliationStatus.CONFLICT, "OBSERVED_STOP_INVALID", observed_stop)

    if observed_stop == request.requested_stop:
        return result(StopReconciliationStatus.CONFIRMED, "REQUESTED_STOP_OBSERVED", observed_stop)

    return result(StopReconciliationStatus.STOP_MISMATCH, "REQUESTED_STOP_NOT_OBSERVED_NO_RETRY_AUTHORIZED", observed_stop)

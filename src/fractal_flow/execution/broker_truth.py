"""Normalized broker-truth models and deterministic observation precedence."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from enum import StrEnum
from typing import Any

from src.fractal_flow.execution.ffbp_protocol import payload_hash


class MarginMode(StrEnum):
    NETTING = "NETTING"
    HEDGING = "HEDGING"
    EXCHANGE = "EXCHANGE"
    UNKNOWN = "UNKNOWN"


class ObservationAuthority(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    NON_AUTHORITATIVE = "NON_AUTHORITATIVE"


class ReconciliationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    ORPHAN = "ORPHAN"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class AccountContext:
    account_id: str
    login: int
    broker: str
    server: str
    currency: str
    margin_mode: MarginMode
    terminal_instance: str
    session_id: str


@dataclass(frozen=True)
class OrderTruth:
    ticket: str
    symbol: str
    side: str
    volume: Decimal
    price: Decimal
    state: str
    command_id: str | None = None
    intent_id: str | None = None
    timestamp_ms: int = 0


@dataclass(frozen=True)
class DealTruth:
    deal_id: str
    order_ticket: str | None
    symbol: str
    side: str
    volume: Decimal
    price: Decimal
    position_ticket: str | None
    position_identifier: str | None
    entry_role: str
    timestamp_ms: int


@dataclass(frozen=True)
class PositionTruth:
    ticket: str
    identifier: str
    symbol: str
    side: str
    volume: Decimal
    average_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    timestamp_ms: int


@dataclass(frozen=True)
class BrokerObservation:
    observation_id: str
    account: AccountContext
    orders: tuple[OrderTruth, ...]
    deals: tuple[DealTruth, ...]
    positions: tuple[PositionTruth, ...]
    source: str
    authority: ObservationAuthority
    observed_at_ms: int
    sequence: int | None = None
    session_id: str | None = None

    @property
    def digest(self) -> str:
        return payload_hash(self.to_wire())

    def to_wire(self) -> dict[str, Any]:
        def normalize(v: Any) -> Any:
            if isinstance(v, Decimal):
                return format(v, "f")
            if isinstance(v, StrEnum):
                return v.value
            if isinstance(v, tuple):
                return [normalize(x) for x in v]
            if hasattr(v, "__dataclass_fields__"):
                return {k: normalize(x) for k, x in asdict(v).items()}
            if isinstance(v, dict):
                return {k: normalize(x) for k, x in v.items()}
            return v
        normalized = normalize(asdict(self))
        if not isinstance(normalized, dict):
            raise TypeError("BrokerObservation wire representation must be a dictionary")
        return normalized


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    command_id: str | None
    broker_observation_id: str
    matched_order: str | None
    matched_deals: tuple[str, ...]
    matched_position_ticket: str | None
    matched_position_identifier: str | None
    filled_volume: Decimal
    remaining_volume: Decimal
    reason: str


def choose_truth(observations: list[BrokerObservation]) -> BrokerObservation:
    """Prefer fresh authoritative broker queries, then authoritative observations."""
    if not observations:
        raise ValueError("at least one broker observation is required")
    ranked = sorted(
        observations,
        key=lambda o: (
            o.authority is ObservationAuthority.AUTHORITATIVE,
            o.source in {"BROKER_SNAPSHOT", "BROKER_HISTORY", "BROKER_QUERY"},
            o.observed_at_ms,
            o.observation_id,
        ),
        reverse=True,
    )
    return ranked[0]


def reconcile_command(
    command_id: str,
    requested_volume: Decimal,
    observation: BrokerObservation,
) -> ReconciliationResult:
    orders = [o for o in observation.orders if o.command_id == command_id]
    deals = [d for d in observation.deals if any(o.ticket == d.order_ticket for o in orders)]
    filled = sum((d.volume for d in deals), Decimal("0"))
    position = next((p for p in observation.positions if any(d.position_ticket == p.ticket for d in deals)), None)
    if filled > requested_volume:
        return ReconciliationResult(ReconciliationStatus.CONFLICT, command_id, observation.observation_id,
                                    orders[0].ticket if orders else None, tuple(d.deal_id for d in deals),
                                    position.ticket if position else None, position.identifier if position else None,
                                    filled, Decimal("0"), "broker filled volume exceeds requested volume")
    if not orders and not deals:
        return ReconciliationResult(
            ReconciliationStatus.UNKNOWN,
            command_id,
            observation.observation_id,
            None,
            (),
            None,
            None,
            Decimal("0"),
            requested_volume,
            "COMMAND_NOT_OBSERVED_NO_REJECTION_PROOF",
        )
    remaining = requested_volume - filled
    status = ReconciliationStatus.CONFIRMED if remaining == 0 else ReconciliationStatus.PARTIAL
    return ReconciliationResult(status, command_id, observation.observation_id,
                                orders[0].ticket if orders else None, tuple(d.deal_id for d in deals),
                                position.ticket if position else None, position.identifier if position else None,
                                filled, remaining, "broker evidence reconciled")

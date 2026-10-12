"""Protective-policy state independent of strategy authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProtectiveState(StrEnum):
    REQUIRED = "REQUIRED"
    ARMED = "ARMED"
    UNCONFIRMED = "UNCONFIRMED"
    LOST = "LOST"
    QUARANTINED = "QUARANTINED"
    EXPIRED = "EXPIRED"
    FLATTEN_REQUIRED = "FLATTEN_REQUIRED"


@dataclass(frozen=True)
class ProtectivePolicy:
    command_id: str
    account_id: str
    position_id: str
    stop_loss: str | None
    take_profit: str | None
    expires_at_ms: int | None
    deadman: bool


@dataclass(frozen=True)
class ProtectiveRecord:
    policy: ProtectivePolicy
    state: ProtectiveState
    confirmed_at_ms: int | None = None
    reason: str = ""

    def mark_confirmed(self, now_ms: int) -> "ProtectiveRecord":
        return ProtectiveRecord(self.policy, ProtectiveState.ARMED, now_ms, "broker protection confirmed")

    def mark_unconfirmed(self, reason: str) -> "ProtectiveRecord":
        return ProtectiveRecord(self.policy, ProtectiveState.UNCONFIRMED, self.confirmed_at_ms, reason)

    def evaluate(self, now_ms: int) -> "ProtectiveRecord":
        if self.policy.expires_at_ms is not None and now_ms >= self.policy.expires_at_ms:
            return ProtectiveRecord(self.policy, ProtectiveState.EXPIRED, self.confirmed_at_ms, "protective TTL expired")
        if self.policy.deadman and self.state in {ProtectiveState.UNCONFIRMED, ProtectiveState.LOST}:
            return ProtectiveRecord(self.policy, ProtectiveState.FLATTEN_REQUIRED, self.confirmed_at_ms, "deadman protection unavailable")
        return self

    @property
    def strategy_may_resume(self) -> bool:
        return self.state is ProtectiveState.ARMED

"""Opportunity Risk Ledger for FRACTAL FLOW with atomic operations, exact Decimal accounting, and strict reservation lifecycle."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from typing import Any, Union, overload


@overload
def _to_decimal(val: None) -> None: ...


@overload
def _to_decimal(val: Union[Decimal, float, int, str]) -> Decimal: ...


def _to_decimal(val: Union[Decimal, float, int, str, None]) -> Any:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


class AccountingInvariantException(Exception):
    """Raised when risk ledger aggregate balances or entry history corrupts accounting invariants."""


@unique
class LedgerOperation(str, Enum):
    RESERVE = "RESERVE"
    ALLOCATE = "ALLOCATE"
    CONSUME = "CONSUME"
    COMMIT = "COMMIT"
    RELEASE = "RELEASE"
    ROLLBACK = "ROLLBACK"
    EXPIRE = "EXPIRE"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class RiskLedgerEntry:
    entry_id: str
    budget_id: str
    operation: LedgerOperation
    amount: Decimal
    volume: Decimal
    reference_id: str
    causation_id: str
    timestamp: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _to_decimal(self.amount))
        object.__setattr__(self, "volume", _to_decimal(self.volume))


class OpportunityRiskLedger:
    """Audit-trailed Opportunity Risk Ledger maintaining exact Decimal risk and volume balances.

    This is the singular authoritative source of truth for risk decisions.
    """

    def __init__(
        self,
        budget_id: str,
        opportunity_id: str,
        total_risk: Union[Decimal, float, int, str],
        total_volume: Union[Decimal, float, int, str],
    ) -> None:
        self.budget_id = budget_id
        self.opportunity_id = opportunity_id
        self.total_risk = _to_decimal(total_risk)
        self.total_volume = _to_decimal(total_volume)

        self.reserved_risk = Decimal("0.0")
        self.allocated_risk = Decimal("0.0")
        self.consumed_risk = Decimal("0.0")

        self.allocated_volume = Decimal("0.0")
        self.consumed_volume = Decimal("0.0")

        self.entries: list[RiskLedgerEntry] = []
        self._entries_by_id: dict[str, RiskLedgerEntry] = {}
        # Reference-tracked active reservations: reference_id -> {"amount": Decimal, "volume": Decimal, "state": str}
        self._active_reservations: dict[str, dict[str, Any]] = {}

    @property
    def remaining_risk(self) -> Decimal:
        rem = self.total_risk - self.allocated_risk - self.reserved_risk - self.consumed_risk
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(f"Negative remaining risk detected on budget '{self.budget_id}': {rem}")
        return rem

    @property
    def remaining_volume(self) -> Decimal:
        rem = self.total_volume - self.allocated_volume - self.consumed_volume
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(
                f"Negative remaining volume detected on budget '{self.budget_id}': {rem}"
            )
        return rem

    def record_operation(
        self,
        entry_id: str,
        operation: LedgerOperation,
        amount: Union[Decimal, float, int, str],
        volume: Union[Decimal, float, int, str],
        reference_id: str,
        causation_id: str,
        timestamp: int,
    ) -> RiskLedgerEntry:
        amt_dec = _to_decimal(amount)
        vol_dec = _to_decimal(volume)

        if amt_dec < Decimal("0.0") or vol_dec < Decimal("0.0"):
            raise AccountingInvariantException(
                f"Operation amount ({amount}) and volume ({volume}) must be non-negative"
            )

        # Transaction Idempotency Check
        if entry_id in self._entries_by_id:
            existing = self._entries_by_id[entry_id]
            if (
                existing.operation == operation
                and existing.amount == amt_dec
                and existing.volume == vol_dec
                and existing.reference_id == reference_id
                and existing.causation_id == causation_id
            ):
                return existing
            raise AccountingInvariantException(
                f"Duplicate transaction entry_id '{entry_id}' with conflicting operation details."
            )

        if operation == LedgerOperation.RESERVE:
            if amt_dec > self.remaining_risk:
                raise AccountingInvariantException(f"Reserve {amount} exceeds remaining risk {self.remaining_risk}")
            self.reserved_risk += amt_dec
            if reference_id in self._active_reservations:
                if self._active_reservations[reference_id]["state"] in ("RELEASED", "EXPIRED", "CANCELLED", "COMMITTED"):
                    raise AccountingInvariantException(
                        f"Cannot reserve on terminal/inactive reservation '{reference_id}' in state {self._active_reservations[reference_id]['state']}"
                    )
                self._active_reservations[reference_id]["amount"] += amt_dec
                self._active_reservations[reference_id]["volume"] += vol_dec
            else:
                self._active_reservations[reference_id] = {
                    "amount": amt_dec,
                    "volume": vol_dec,
                    "state": "RESERVED",
                    "causation_id": causation_id,
                }

        elif operation == LedgerOperation.ALLOCATE:
            if amt_dec > self.remaining_risk + self.reserved_risk:
                raise AccountingInvariantException(
                    f"Allocate {amount} exceeds available risk {self.remaining_risk + self.reserved_risk}"
                )
            if vol_dec > self.remaining_volume:
                raise AccountingInvariantException(
                    f"Allocate volume {volume} exceeds remaining volume {self.remaining_volume}"
                )

            # Deduct from specific reservation if tracked
            if reference_id in self._active_reservations:
                res_info = self._active_reservations[reference_id]
                if res_info["state"] in ("RELEASED", "EXPIRED", "CANCELLED"):
                    raise AccountingInvariantException(
                        f"Cannot allocate from inactive reservation '{reference_id}' in state {res_info['state']}"
                    )
                res_amt = res_info["amount"]
                deduct = min(res_amt, amt_dec)
                res_info["amount"] -= deduct
                res_info["state"] = "ALLOCATED"
                self.reserved_risk -= deduct
            elif self.reserved_risk >= amt_dec:
                self.reserved_risk -= amt_dec
            else:
                self.reserved_risk = Decimal("0.0")

            self.allocated_risk += amt_dec
            self.allocated_volume += vol_dec

        elif operation in (LedgerOperation.CONSUME, LedgerOperation.COMMIT):
            if amt_dec > self.allocated_risk or vol_dec > self.allocated_volume:
                raise AccountingInvariantException(
                    f"Consume/Commit {amount}/{volume} exceeds allocated risk {self.allocated_risk} / vol {self.allocated_volume}"
                )
            if reference_id in self._active_reservations:
                self._active_reservations[reference_id]["state"] = "COMMITTED"
            self.allocated_risk -= amt_dec
            self.allocated_volume -= vol_dec
            self.consumed_risk += amt_dec
            self.consumed_volume += vol_dec

        elif operation in (
            LedgerOperation.RELEASE,
            LedgerOperation.ROLLBACK,
            LedgerOperation.EXPIRE,
            LedgerOperation.CANCEL,
        ):
            # Check if releasing/expiring/cancelling an active reservation
            if reference_id in self._active_reservations:
                res_info = self._active_reservations[reference_id]
                if res_info["state"] in ("RELEASED", "EXPIRED", "CANCELLED"):
                    raise AccountingInvariantException(
                        f"Cannot {operation.value} already terminal reservation '{reference_id}' in state {res_info['state']}"
                    )
                if res_info["state"] == "COMMITTED":
                    raise AccountingInvariantException(
                        f"Cannot {operation.value} committed reservation '{reference_id}'"
                    )

                res_amt = res_info["amount"]
                if amt_dec > res_amt and res_info["state"] == "RESERVED":
                    raise AccountingInvariantException(
                        f"Cannot {operation.value} {amt_dec} for reservation '{reference_id}': exceeds active reservation amount {res_amt}"
                    )

                if res_info["state"] == "RESERVED":
                    self.reserved_risk -= amt_dec
                elif res_info["state"] == "ALLOCATED":
                    if amt_dec > self.allocated_risk or vol_dec > self.allocated_volume:
                        raise AccountingInvariantException(
                            f"Cannot {operation.value} risk {amount}/vol {volume}: exceeds allocated risk {self.allocated_risk}/vol {self.allocated_volume}"
                        )
                    self.allocated_risk -= amt_dec
                    self.allocated_volume -= vol_dec

                res_info["amount"] -= min(res_info["amount"], amt_dec)
                if res_info["amount"] == Decimal("0.0"):
                    res_info["state"] = operation.value
            else:
                # Otherwise releasing allocated risk
                if amt_dec > self.allocated_risk or vol_dec > self.allocated_volume:
                    raise AccountingInvariantException(
                        f"Cannot {operation.value} risk {amount}/vol {volume}: exceeds allocated risk {self.allocated_risk}/vol {self.allocated_volume}"
                    )
                self.allocated_risk -= amt_dec
                self.allocated_volume -= vol_dec

        entry = RiskLedgerEntry(
            entry_id=entry_id,
            budget_id=self.budget_id,
            operation=operation,
            amount=amt_dec,
            volume=vol_dec,
            reference_id=reference_id,
            causation_id=causation_id,
            timestamp=timestamp,
        )
        self.entries.append(entry)
        self._entries_by_id[entry_id] = entry
        return entry

    def replay_entries(self, entries: list[RiskLedgerEntry]) -> None:
        """Reconstructs ledger state deterministically by replaying recorded entries."""
        for entry in entries:
            self.record_operation(
                entry_id=entry.entry_id,
                operation=entry.operation,
                amount=entry.amount,
                volume=entry.volume,
                reference_id=entry.reference_id,
                causation_id=entry.causation_id,
                timestamp=entry.timestamp,
            )

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative risk ledger provenance."""
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            ProducerCapability,
            RecoveryEvidenceError,
            SealedObservation,
        )

        if not isinstance(capability, ProducerCapability) or capability.role != CapabilityRole.RISK_LEDGER:
            raise RecoveryEvidenceError(
                "OpportunityRiskLedger observation requires a valid RISK_LEDGER ProducerCapability."
            )

        import time

        faulted = getattr(self, "_faulted", False)
        payload = {
            "budget_id": self.budget_id,
            "opportunity_id": self.opportunity_id,
            "entries_count": len(self.entries),
            "total_risk": str(self.total_risk),
            "remaining_risk": str(self.remaining_risk),
            "allocated_risk": str(self.allocated_risk),
            "reserved_risk": str(self.reserved_risk),
            "consumed_risk": str(self.consumed_risk),
            "faulted": faulted,
        }
        return SealedObservation.create(capability, session_id, int(time.time()), payload)

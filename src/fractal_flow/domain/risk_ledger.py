"""Opportunity Risk Ledger for FRACTAL FLOW with atomic operations and exact Decimal accounting."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, unique
from typing import Any


class AccountingInvariantException(Exception):
    """Raised when risk ledger aggregate balances or entry history corrupts accounting invariants."""


@unique
class LedgerOperation(str, Enum):
    RESERVE = "RESERVE"
    ALLOCATE = "ALLOCATE"
    CONSUME = "CONSUME"
    RELEASE = "RELEASE"
    ROLLBACK = "ROLLBACK"
    EXPIRE = "EXPIRE"


@dataclass(frozen=True)
class RiskLedgerEntry:
    entry_id: str
    budget_id: str
    operation: LedgerOperation
    amount: float
    volume: float
    reference_id: str
    causation_id: str
    timestamp: int


class OpportunityRiskLedger:
    """Audit-trailed Opportunity Risk Ledger maintaining exact Decimal risk and volume balances."""

    def __init__(
        self,
        budget_id: str,
        opportunity_id: str,
        total_risk: float,
        total_volume: float,
    ) -> None:
        self.budget_id = budget_id
        self.opportunity_id = opportunity_id
        self.total_risk = Decimal(str(total_risk))
        self.total_volume = Decimal(str(total_volume))

        self.reserved_risk = Decimal("0.0")
        self.allocated_risk = Decimal("0.0")
        self.consumed_risk = Decimal("0.0")

        self.allocated_volume = Decimal("0.0")
        self.consumed_volume = Decimal("0.0")

        self.entries: list[RiskLedgerEntry] = []
        self._entries_by_id: dict[str, RiskLedgerEntry] = {}

    @property
    def remaining_risk(self) -> float:
        rem = (
            self.total_risk
            - self.allocated_risk
            - self.reserved_risk
            - self.consumed_risk
        )
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(
                f"Negative remaining risk detected on budget '{self.budget_id}': {rem}"
            )
        return float(rem)

    @property
    def remaining_volume(self) -> float:
        rem = self.total_volume - self.allocated_volume - self.consumed_volume
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(
                f"Negative remaining volume detected on budget '{self.budget_id}': {rem}"
            )
        return float(rem)

    def record_operation(
        self,
        entry_id: str,
        operation: LedgerOperation,
        amount: float,
        volume: float,
        reference_id: str,
        causation_id: str,
        timestamp: int,
    ) -> RiskLedgerEntry:
        amt_dec = Decimal(str(amount))
        vol_dec = Decimal(str(volume))

        if amt_dec < Decimal("0.0") or vol_dec < Decimal("0.0"):
            raise AccountingInvariantException(
                f"Operation amount ({amount}) and volume ({volume}) must be non-negative"
            )

        # Transaction Idempotency Check
        if entry_id in self._entries_by_id:
            existing = self._entries_by_id[entry_id]
            if (
                existing.operation == operation
                and Decimal(str(existing.amount)) == amt_dec
                and Decimal(str(existing.volume)) == vol_dec
                and existing.reference_id == reference_id
                and existing.causation_id == causation_id
            ):
                return existing
            raise AccountingInvariantException(
                f"Duplicate transaction entry_id '{entry_id}' with conflicting operation details."
            )

        if operation == LedgerOperation.RESERVE:
            if amt_dec > Decimal(str(self.remaining_risk)):
                raise AccountingInvariantException(
                    f"Reserve {amount} exceeds remaining risk {self.remaining_risk}"
                )
            self.reserved_risk += amt_dec

        elif operation == LedgerOperation.ALLOCATE:
            if amt_dec > Decimal(str(self.remaining_risk)) + self.reserved_risk:
                raise AccountingInvariantException(
                    f"Allocate {amount} exceeds available risk {self.remaining_risk + float(self.reserved_risk)}"
                )
            if vol_dec > Decimal(str(self.remaining_volume)):
                raise AccountingInvariantException(
                    f"Allocate volume {volume} exceeds remaining volume {self.remaining_volume}"
                )

            if self.reserved_risk >= amt_dec:
                self.reserved_risk -= amt_dec
            else:
                self.reserved_risk = Decimal("0.0")

            self.allocated_risk += amt_dec
            self.allocated_volume += vol_dec

        elif operation == LedgerOperation.CONSUME:
            if amt_dec > self.allocated_risk or vol_dec > self.allocated_volume:
                raise AccountingInvariantException(
                    f"Consume {amount}/{volume} exceeds allocated risk {self.allocated_risk} / vol {self.allocated_volume}"
                )
            self.allocated_risk -= amt_dec
            self.allocated_volume -= vol_dec
            self.consumed_risk += amt_dec
            self.consumed_volume += vol_dec

        elif operation in (
            LedgerOperation.RELEASE,
            LedgerOperation.ROLLBACK,
            LedgerOperation.EXPIRE,
        ):
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
            amount=amount,
            volume=volume,
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

        if (
            not isinstance(capability, ProducerCapability)
            or capability.role != CapabilityRole.RISK_LEDGER
        ):
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
        return SealedObservation.create(
            capability, session_id, int(time.time()), payload
        )

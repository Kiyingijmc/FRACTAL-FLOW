"""Opportunity Risk Ledger for FRACTAL FLOW with atomic operations and exact Decimal accounting."""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import List, Dict, Optional
from decimal import Decimal


class AccountingInvariantException(Exception):
    """Raised when risk ledger aggregate balances or entry history corrupts accounting invariants."""
    pass


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

    def __init__(self, budget_id: str, opportunity_id: str, total_risk: float, total_volume: float) -> None:
        self.budget_id = budget_id
        self.opportunity_id = opportunity_id
        self.total_risk = Decimal(str(total_risk))
        self.total_volume = Decimal(str(total_volume))

        self.reserved_risk = Decimal("0.0")
        self.allocated_risk = Decimal("0.0")
        self.consumed_risk = Decimal("0.0")

        self.allocated_volume = Decimal("0.0")
        self.consumed_volume = Decimal("0.0")

        self.entries: List[RiskLedgerEntry] = []

    @property
    def remaining_risk(self) -> float:
        rem = self.total_risk - self.allocated_risk - self.reserved_risk - self.consumed_risk
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(f"Negative remaining risk detected on budget '{self.budget_id}': {rem}")
        return float(rem)

    @property
    def remaining_volume(self) -> float:
        rem = self.total_volume - self.allocated_volume - self.consumed_volume
        if rem < Decimal("0.0"):
            raise AccountingInvariantException(f"Negative remaining volume detected on budget '{self.budget_id}': {rem}")
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
            raise AccountingInvariantException(f"Operation amount ({amount}) and volume ({volume}) must be non-negative")

        if operation == LedgerOperation.RESERVE:
            if amt_dec > Decimal(str(self.remaining_risk)):
                raise AccountingInvariantException(f"Reserve {amount} exceeds remaining risk {self.remaining_risk}")
            self.reserved_risk += amt_dec

        elif operation == LedgerOperation.ALLOCATE:
            if amt_dec > Decimal(str(self.remaining_risk)) + self.reserved_risk:
                raise AccountingInvariantException(f"Allocate {amount} exceeds available risk {self.remaining_risk + float(self.reserved_risk)}")
            if vol_dec > Decimal(str(self.remaining_volume)):
                raise AccountingInvariantException(f"Allocate volume {volume} exceeds remaining volume {self.remaining_volume}")

            if self.reserved_risk >= amt_dec:
                self.reserved_risk -= amt_dec
            else:
                self.reserved_risk = Decimal("0.0")

            self.allocated_risk += amt_dec
            self.allocated_volume += vol_dec

        elif operation == LedgerOperation.CONSUME:
            if amt_dec > self.allocated_risk or vol_dec > self.allocated_volume:
                raise AccountingInvariantException(f"Consume {amount}/{volume} exceeds allocated risk {self.allocated_risk} / vol {self.allocated_volume}")
            self.allocated_risk -= amt_dec
            self.allocated_volume -= vol_dec
            self.consumed_risk += amt_dec
            self.consumed_volume += vol_dec

        elif operation in (LedgerOperation.RELEASE, LedgerOperation.ROLLBACK, LedgerOperation.EXPIRE):
            self.allocated_risk = max(Decimal("0.0"), self.allocated_risk - amt_dec)
            self.allocated_volume = max(Decimal("0.0"), self.allocated_volume - vol_dec)

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
        return entry

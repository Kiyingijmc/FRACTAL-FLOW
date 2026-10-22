"""Phase 9 regression tests for injected risk-ledger ownership."""

from decimal import Decimal

import pytest

from src.fractal_flow.domain.entry import OpportunityRiskBudget
from src.fractal_flow.domain.risk_ledger import LedgerOperation, OpportunityRiskLedger


def test_injected_ledger_with_wrong_opportunity_is_rejected() -> None:
    foreign_ledger = OpportunityRiskLedger(
        budget_id="budget-opp-B",
        opportunity_id="opp-B",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
    )

    with pytest.raises(ValueError, match="opportunity_id"):
        OpportunityRiskBudget(
            opportunity_id="opp-A",
            total_risk_currency=Decimal("500"),
            total_allowed_volume=Decimal("2"),
            ledger=foreign_ledger,
        )


def test_injected_ledger_with_mismatched_risk_capacity_is_rejected() -> None:
    ledger = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("400"),
        total_volume=Decimal("2"),
    )

    with pytest.raises(ValueError, match="total_risk"):
        OpportunityRiskBudget(
            opportunity_id="opp-A",
            total_risk_currency=Decimal("500"),
            total_allowed_volume=Decimal("2"),
            ledger=ledger,
        )


def test_injected_ledger_with_mismatched_volume_capacity_is_rejected() -> None:
    ledger = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("1"),
    )

    with pytest.raises(ValueError, match="total_volume"):
        OpportunityRiskBudget(
            opportunity_id="opp-A",
            total_risk_currency=Decimal("500"),
            total_allowed_volume=Decimal("2"),
            ledger=ledger,
        )


def test_injected_ledger_from_another_account_is_rejected() -> None:
    ledger = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
        account_id="account-B",
    )

    with pytest.raises(ValueError, match="account_id"):
        OpportunityRiskBudget(
            opportunity_id="opp-A",
            total_risk_currency=Decimal("500"),
            total_allowed_volume=Decimal("2"),
            ledger=ledger,
            account_id="account-A",
        )


def test_account_bound_ledger_cannot_be_injected_into_unbound_budget() -> None:
    ledger = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
        account_id="account-A",
    )

    with pytest.raises(ValueError, match="account_id"):
        OpportunityRiskBudget(
            opportunity_id="opp-A",
            total_risk_currency=Decimal("500"),
            total_allowed_volume=Decimal("2"),
            ledger=ledger,
        )


def test_matching_account_and_injected_ledger_preserve_single_owner() -> None:
    ledger = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
        account_id="account-A",
    )

    budget = OpportunityRiskBudget(
        opportunity_id="opp-A",
        total_risk_currency=Decimal("500"),
        total_allowed_volume=Decimal("2"),
        ledger=ledger,
        account_id="account-A",
    )

    assert budget.ledger is ledger


def test_independent_account_ledgers_do_not_share_mutable_risk_state() -> None:
    ledger_a = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
        account_id="account-A",
    )
    ledger_b = OpportunityRiskLedger(
        budget_id="budget-opp-A",
        opportunity_id="opp-A",
        total_risk=Decimal("500"),
        total_volume=Decimal("2"),
        account_id="account-B",
    )

    ledger_a.record_operation(
        entry_id="reserve-A",
        operation=LedgerOperation.RESERVE,
        amount=Decimal("100"),
        volume=Decimal("0"),
        reference_id="reservation-A",
        causation_id="test",
        timestamp=1,
    )

    assert ledger_a.reserved_risk == Decimal("100")
    assert ledger_b.reserved_risk == Decimal("0.0")
    assert ledger_a.entries is not ledger_b.entries

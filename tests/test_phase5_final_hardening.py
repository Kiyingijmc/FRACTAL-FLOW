from decimal import Decimal

import pytest

from src.fractal_flow.domain.portfolio import PortfolioCandidate, PortfolioValidationError
from src.fractal_flow.domain.news_shield import NewsShield
from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
from src.fractal_flow.domain.phase4 import make_decision
from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.part5 import PartBDecisionJournal
from tests.test_phase4_foundation import confidence, gates, opportunity, plan, tradeability


def test_portfolio_candidate_requires_notional() -> None:
    with pytest.raises(TypeError):
        PortfolioCandidate("x", "EURUSD", "LONG", "EUR", "USD", Decimal("1"), Decimal("1"), Decimal("0.5"))


def test_portfolio_candidate_rejects_invalid_notional() -> None:
    with pytest.raises(PortfolioValidationError, match="notional"):
        PortfolioCandidate("x", "EURUSD", "LONG", "EUR", "USD", Decimal("1"), Decimal("1"), Decimal("0.5"), notional=Decimal("0"))


def _account():
    return AccountState("ACC_1", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)


def _spec():
    return SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))


def test_partb_reject_journal_contains_complete_input_context(tmp_path):
    opp = opportunity()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140, account_id="ACC_1")
    journal = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb.journal")))
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig(), journal=journal)
    shield = NewsShield(); shield.update_calendar(140)
    result = pipeline.evaluate(decision, _account(), _spec(), PortfolioState(), shield, 140, Decimal("500"), authoritative_opportunity=opp.__class__(**{**opp.__dict__, "state": opp.state.INVALIDATED}))
    assert result.status == "REJECT"
    record = journal.latest("ACC_1")
    assert record is not None
    assert record.context["context_version"] == 2
    assert record.context["outcome_status"] == "REJECT"
    assert record.context["decision"]["decision_id"] == decision.decision_id
    assert record.context["authoritative_opportunity"]["opportunity_id"] == opp.opportunity_id
    assert record.context_fingerprint
    reopened = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb.journal")))
    replayed = reopened.latest("ACC_1")
    assert replayed is not None
    assert replayed.fingerprint == record.fingerprint
    assert replayed.context_fingerprint == record.context_fingerprint
    assert replayed.context == record.context

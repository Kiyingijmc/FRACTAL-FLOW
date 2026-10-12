"""Runtime enforcement tests for Part-B invariants."""

from decimal import Decimal

from src.fractal_flow.domain.news_shield import NewsEvent, NewsImportance, NewsObservation, NewsShield
from src.fractal_flow.domain.portfolio import PortfolioArbitrator, PortfolioCandidate, PortfolioConfig, PortfolioState, StructuralReversalEvidence
from src.fractal_flow.domain.risk_engine import AccountFeasibilityEngine, AccountState, RiskConfig, RiskEngine, SymbolSpec


def _candidate(oid: str, symbol: str, direction: str, risk: str = "100") -> PortfolioCandidate:
    return PortfolioCandidate(oid, symbol, direction, symbol[:3], symbol[3:], Decimal("1"), Decimal(risk), Decimal("0.8"), notional=Decimal("1"))


def _spec() -> SymbolSpec:
    return SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))


def _account() -> AccountState:
    return AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)


def test_invariant_5_risk_cannot_manufacture_signal() -> None:
    # covers: [5]
    assert not hasattr(RiskEngine(RiskConfig()), "direction")


def test_invariant_6_portfolio_cannot_manufacture_direction() -> None:
    # covers: [6]
    assert not hasattr(PortfolioArbitrator(PortfolioConfig()), "direction")


def test_invariant_8_news_shield_cannot_manufacture_trades() -> None:
    # covers: [8]
    shield = NewsShield()
    shield.update_calendar(1_000)
    assert not hasattr(shield, "create_trade")
    assert not hasattr(shield, "direction")


def test_invariant_21_scheduled_and_observed_shock_are_separate() -> None:
    # covers: [21]
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(NewsEvent("N", 100, "US", ("USD",), "CPI", NewsImportance.HIGH, ("EURUSD",), 300, 120, 600))
    shield.observe(NewsObservation("N", 100, Decimal("4"), Decimal("1"), Decimal("1"), Decimal("1")))
    assert shield.scheduled_severity == "HIGH"
    assert shield.observed_severity == "EXTREME"


def test_invariant_22_checkpoint_is_not_automatic_restart() -> None:
    # covers: [22]
    shield = NewsShield()
    shield.update_calendar(1_000)
    shield.schedule(NewsEvent("N", 100, "US", ("USD",), "CPI", NewsImportance.HIGH, ("EURUSD",), 300, 120, 600))
    shield.observe(NewsObservation("N", 100, Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2")))
    shield.advance(700)
    assert shield.state.value == "POST_NEWS_VALIDATION"
    assert shield.evaluate("EURUSD", 700).passed is False


def test_invariant_28_flip_requires_structural_reversal() -> None:
    # covers: [28]
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("100")))
    state = PortfolioState(open_positions=(_candidate("old", "EURUSD", "LONG"),))
    blocked = arb.evaluate([_candidate("new", "EURUSD", "SHORT")], state)
    assert blocked.result == "REJECT"
    allowed = arb.evaluate(
        [_candidate("new", "EURUSD", "SHORT")], state,
        reversal=StructuralReversalEvidence("old", "new", True, "STRUCTURAL_REVERSAL"),
    )
    assert allowed.result == "ALLOW"


def test_invariant_37_portfolio_is_currency_and_correlation_aware() -> None:
    # covers: [37]
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("100"), max_correlated_risk=Decimal("150")))
    state = PortfolioState(open_positions=(_candidate("old", "GBPUSD", "LONG"),))
    decision = arb.evaluate([_candidate("new", "EURUSD", "LONG")], state, {("EURUSD", "GBPUSD"): Decimal("0.95")})
    assert decision.currency_exposure["USD"] == Decimal("-2")
    assert decision.risk_multiplier < Decimal("1") and decision.risk_multiplier > Decimal("0")


def test_invariant_38_account_feasibility_precedes_sizing() -> None:
    # covers: [38]
    account = _account()
    spec = _spec()
    result = AccountFeasibilityEngine().check(account, spec, Decimal("0.001"), Decimal("0.01"))
    assert result.status == "FEASIBLE"
    from pytest import raises
    blocked = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("1"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    bad = AccountFeasibilityEngine().check(blocked, spec, Decimal("0.001"), Decimal("0.01"))
    assert bad.status == "INFEASIBLE"
    with raises(ValueError):
        RiskEngine(RiskConfig()).size(blocked, spec, Decimal("0.001"), Decimal("100"), bad)

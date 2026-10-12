from decimal import Decimal

from src.fractal_flow.domain.portfolio import (
    PortfolioValidationError,
    PortfolioArbitrator,
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioState,
    StructuralReversalEvidence,
)


def candidate(oid: str, symbol: str, direction: str, score: str = "0.8", parent: str | None = None, risk: str = "100") -> PortfolioCandidate:
    return PortfolioCandidate(
        opportunity_id=oid,
        symbol=symbol,
        direction=direction,
        base_currency=symbol[:3],
        quote_currency=symbol[3:],
        volume=Decimal("1"),
        risk=Decimal(risk),
        score=Decimal(score),
        parent_opportunity_id=parent,
        notional=Decimal("1"),
    )


def test_currency_vector_is_directional_and_deterministic() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("10")))
    state = PortfolioState()
    decision = arb.evaluate([candidate("a", "EURUSD", "LONG")], state)
    assert decision.result == "ALLOW"
    assert decision.currency_exposure["EUR"] == Decimal("1")
    assert decision.currency_exposure["USD"] == Decimal("-1")


def test_currency_cap_rejects_excess_exposure() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("1")))
    state = PortfolioState(currency_exposure={"USD": Decimal("-0.5")})
    decision = arb.evaluate([candidate("a", "EURUSD", "LONG")], state)
    assert decision.result == "ALLOW"
    assert decision.risk_multiplier == Decimal("0.5")


def test_correlation_cap_is_enforced() -> None:
    arb = PortfolioArbitrator(
        PortfolioConfig(max_currency_exposure=Decimal("100"), max_correlated_risk=Decimal("150"))
    )
    state = PortfolioState(open_positions=(candidate("old", "GBPUSD", "LONG", risk="100"),))
    decision = arb.evaluate(
        [candidate("new", "EURUSD", "LONG", risk="100")],
        state,
        correlations={("EURUSD", "GBPUSD"): Decimal("0.95")},
    )
    assert decision.result == "ALLOW"
    assert decision.risk_multiplier < Decimal("1")
    assert decision.risk_multiplier > Decimal("0")


def test_deterministic_ranking_breaks_score_ties_by_identity() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("100"), max_total_risk=Decimal("100")))
    result = arb.rank([candidate("b", "EURUSD", "LONG"), candidate("a", "GBPUSD", "LONG")])
    assert [x.opportunity_id for x in result] == ["a", "b"]


def test_flip_requires_independent_structural_reversal() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("100")))
    state = PortfolioState(open_positions=(candidate("old", "EURUSD", "LONG"),))
    blocked = arb.evaluate([candidate("new", "EURUSD", "SHORT")], state)
    assert blocked.result == "REJECT"
    allowed = arb.evaluate(
        [candidate("new", "EURUSD", "SHORT")],
        state,
        reversal=StructuralReversalEvidence("old", "new", True, "STRUCTURAL_REVERSAL"),
    )
    assert allowed.result == "ALLOW"


def test_portfolio_does_not_create_direction() -> None:
    arb = PortfolioArbitrator(PortfolioConfig())
    assert not hasattr(arb, "direction")


def test_portfolio_policy_has_versioned_provenance() -> None:
    config = PortfolioConfig()
    assert config.version >= 1
    assert config.provenance


def test_same_parent_same_direction_can_merge() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_total_risk=Decimal("250"), max_currency_exposure=Decimal("100")))
    a = candidate("a", "EURUSD", "LONG", parent="root")
    b = candidate("b", "EURUSD", "LONG", parent="root")
    result = arb.evaluate([a, b], PortfolioState())
    assert result.result == "MERGE"
    assert result.merged_ids == ("a", "b")


def test_lower_ranked_candidate_is_deferred_when_higher_ranked_is_allowed() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_total_risk=Decimal("1000"), max_currency_exposure=Decimal("100")))
    result = arb.evaluate([candidate("a", "EURUSD", "LONG", score="0.9"), candidate("b", "GBPUSD", "LONG", score="0.8")], PortfolioState())
    assert result.result == "ALLOW"
    assert result.deferred_ids == ("b",)


def test_portfolio_rejects_nonfinite_notional() -> None:
    import pytest
    with pytest.raises(PortfolioValidationError):
        PortfolioCandidate("x", "EURUSD", "LONG", "EUR", "USD", Decimal("1"), Decimal("1"), Decimal("0.5"), notional=Decimal("Infinity"))


def test_portfolio_rejects_nonfinite_correlation() -> None:
    arb = PortfolioArbitrator(PortfolioConfig())
    result = arb.evaluate([candidate("x", "EURUSD", "LONG")], PortfolioState(), {("EURUSD", "GBPUSD"): Decimal("NaN")})
    assert result.result == "REJECT"
    assert result.reasons == ("INVALID_CORRELATION",)


def test_max_entries_per_opportunity_is_a_hard_pre_exposure_cap() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_entries_per_opportunity=1, max_currency_exposure=Decimal("100")))
    existing = candidate("same", "EURUSD", "LONG")
    state = PortfolioState(open_positions=(existing,))
    result = arb.evaluate([candidate("same", "EURUSD", "LONG")], state)
    assert result.result == "REJECT"
    assert "OPPORTUNITY_ENTRY_CAP" in result.reasons


def test_merge_never_bypasses_hard_total_risk_or_trade_caps() -> None:
    arb = PortfolioArbitrator(PortfolioConfig(max_total_risk=Decimal("100"), max_trades=2, max_currency_exposure=Decimal("1000")))
    a = candidate("a", "EURUSD", "LONG", parent="root", risk="60")
    b = candidate("b", "EURUSD", "LONG", parent="root", risk="60")
    result = arb.evaluate([a, b], PortfolioState())
    assert result.result != "MERGE"


def test_portfolio_rejects_mixed_exposure_units() -> None:
    existing = PortfolioCandidate("old", "EURUSD", "LONG", "EUR", "USD", Decimal("1"), Decimal("10"), Decimal("0.8"), notional=Decimal("1"), exposure_unit="USD_NOTIONAL")
    incoming = candidate("new", "GBPUSD", "LONG")
    result = PortfolioArbitrator(PortfolioConfig(max_currency_exposure=Decimal("100"))).evaluate([incoming], PortfolioState(open_positions=(existing,)))
    assert result.result == "REJECT"
    assert result.reasons == ("EXPOSURE_UNIT_MISMATCH",)

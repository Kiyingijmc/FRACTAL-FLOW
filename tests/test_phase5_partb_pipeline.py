from decimal import Decimal

from src.fractal_flow.domain.news_shield import NewsShield
from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
from src.fractal_flow.domain.phase4 import make_decision
from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
from tests.test_phase4_foundation import confidence, gates, opportunity, plan, tradeability


def decision():
    opp = opportunity()
    return make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140, account_id="ACC_1")


def account() -> AccountState:
    return AccountState("ACC_1", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)


def spec() -> SymbolSpec:
    return SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))


def test_part_b_pipeline_requires_explicit_account_and_allows_valid_request() -> None:
    pipeline = PartBDecisionPipeline(
        RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")),
        PortfolioConfig(max_correlated_risk=Decimal("500")),
    )
    shield = NewsShield(); shield.update_calendar(140)
    result = pipeline.evaluate(decision(), account(), spec(), PortfolioState(), shield, 140, Decimal("500"), authoritative_opportunity=__import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity())
    assert result.status == "ALLOW"
    assert result.allocation is not None
    assert result.allocation.approved_risk > 0


def test_part_b_pipeline_fails_closed_on_news() -> None:
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    shield = NewsShield()
    from src.fractal_flow.domain.news_shield import NewsEvent, NewsImportance, NewsObservation
    shield.schedule(NewsEvent("N", 100, "US", ("USD",), "CPI", NewsImportance.HIGH, ("EURUSD",), 300, 120, 600))
    shield.observe(NewsObservation("N", 100, Decimal("3"), Decimal("3"), Decimal("3"), Decimal("3")))
    result = pipeline.evaluate(decision(), account(), spec(), PortfolioState(), shield, 140, Decimal("100"), authoritative_opportunity=__import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity())
    assert result.status == "REJECT"
    assert "NEWS" in result.reason


def test_part_b_pipeline_rejects_account_identity_mismatch() -> None:
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    wrong = AccountState("OTHER", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    result = pipeline.evaluate(decision(), wrong, spec(), PortfolioState(), NewsShield(), 140, Decimal("100"), authoritative_opportunity=__import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity())
    assert result.status == "REJECT"
    assert "ACCOUNT_IDENTITY" in result.reason


def test_part_b_pipeline_applies_group_lane_caps_before_allow() -> None:
    from src.fractal_flow.domain.lane_pipeline import LanePipeline, LanePolicy
    lane = LanePipeline({"PRIMARY": LanePolicy(max_risk=Decimal("1"), max_entries=1)}, {"FX": Decimal("1")})
    pipeline = PartBDecisionPipeline(
        RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")),
        PortfolioConfig(max_correlated_risk=Decimal("500")),
        lane_pipeline=lane,
    )
    shield = NewsShield()
    shield.update_calendar(140)
    result = pipeline.evaluate(decision(), account(), spec(), PortfolioState(), shield, 140, Decimal("500"), lane="PRIMARY", group="FX", authoritative_opportunity=__import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity())
    assert result.status == "REJECT"
    assert result.reason.startswith("LANE:")


def test_part_b_rechecks_current_opportunity_liveness_before_allocation() -> None:
    from src.fractal_flow.domain.phase4 import OpportunityState
    opp = __import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity()
    d = decision()
    stale = opp.__class__(**{**opp.__dict__, "state": OpportunityState.INVALIDATED})
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    shield = NewsShield(); shield.update_calendar(140)
    result = pipeline.evaluate(d, account(), spec(), PortfolioState(), shield, 140, Decimal("100"), authoritative_opportunity=stale)
    assert result.status == "REJECT"
    assert result.reason == "PHASE4_AUTHORITY_STALE_OR_MISMATCHED"


def test_part_b_enforces_max_entries_per_opportunity_across_authorizations() -> None:
    from src.fractal_flow.domain.phase4 import make_decision
    opp = __import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity()
    tb = __import__("tests.test_phase4_foundation", fromlist=["tradeability"]).tradeability(opp)
    ep = __import__("tests.test_phase4_foundation", fromlist=["plan"]).plan(opp)
    gs = __import__("tests.test_phase4_foundation", fromlist=["gates"]).gates()
    conf = __import__("tests.test_phase4_foundation", fromlist=["confidence"]).confidence(opp)
    first = make_decision(opp, tb, ep, gs, conf, 140, account_id="ACC_1")
    second = make_decision(opp, tb, ep, gs, conf, 150, account_id="ACC_1")
    pipeline = PartBDecisionPipeline(RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")), PortfolioConfig(max_correlated_risk=Decimal("500")))
    shield = NewsShield(); shield.update_calendar(140)
    assert pipeline.evaluate(first, account(), spec(), PortfolioState(), shield, 140, Decimal("500"), authoritative_opportunity=opp).status == "ALLOW"
    result = pipeline.evaluate(second, account(), spec(), PortfolioState(), shield, 150, Decimal("500"), authoritative_opportunity=opp)
    assert result.status == "REJECT"
    assert result.reason == "PORTFOLIO:OPPORTUNITY_ENTRY_CAP"


def test_part_b_rejects_forged_structural_phase4_record_even_with_valid_hash() -> None:
    from src.fractal_flow.domain.phase4 import TradeDecisionV4, _decision_fingerprint, _opportunity_content_hash
    opp = __import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity()
    tb = __import__("tests.test_phase4_foundation", fromlist=["tradeability"]).tradeability(opp)
    ep = __import__("tests.test_phase4_foundation", fromlist=["plan"]).plan(opp)
    gs = tuple(__import__("tests.test_phase4_foundation", fromlist=["gates"]).gates())
    conf = __import__("tests.test_phase4_foundation", fromlist=["confidence"]).confidence(opp)
    decision_id = _decision_fingerprint(opp.opportunity_id, tb, ep, gs, conf, 140)
    forged = TradeDecisionV4(decision_id, opp.opportunity_id, opp.root_id, "ACC_1", ep, tb, gs, conf, 140, opportunity_content_hash=_opportunity_content_hash(opp))
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    shield = NewsShield(); shield.update_calendar(140)
    result = pipeline.evaluate(forged, account(), spec(), PortfolioState(), shield, 140, Decimal("100"), authoritative_opportunity=opp)
    assert result.status == "REJECT"
    assert result.reason == "PHASE4_NOT_AUTHORIZED"


def test_part_b_rejects_exact_opportunity_expiry_boundary() -> None:
    opp = __import__("tests.test_phase4_foundation", fromlist=["opportunity"]).opportunity()
    d = decision()
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    shield = NewsShield(); shield.update_calendar(200)
    result = pipeline.evaluate(d, account(), spec(), PortfolioState(), shield, 200, Decimal("100"), authoritative_opportunity=opp)
    assert result.status == "REJECT"
    assert result.reason == "PHASE4_AUTHORITY_STALE_OR_MISMATCHED"

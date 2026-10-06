from __future__ import annotations

from decimal import Decimal

import pytest

from src.fractal_flow.domain.market import Timeframe
from src.fractal_flow.domain.news_shield import NewsShield
from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.phase3 import Phase3Orchestrator
from src.fractal_flow.domain.phase4 import AccountRegistry, GateEvidence, Phase4GateType
from src.fractal_flow.domain.phase4_bridge import Phase3DecisionAdapter
from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
from tests.regression.test_phase5_r5_real_campaign import _real_mtf_bars


class PassingNews:
    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence:
        return GateEvidence(Phase4GateType.TRADEABILITY, True, "NEWS_NORMAL", timestamp, producer="NewsShield")


def _candidate(seed: int = 0):
    tfs = tuple(Timeframe.validate(tf) for tf in ("1M", "5M", "15M", "30M", "1H", "4H"))
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in tfs}
    orch = Phase3Orchestrator("EURUSD")
    for bar in _real_mtf_bars(seed, 2_000):
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orch.ingest(evaluation)
        candidate = orch.construct_opportunity(bar.close_timestamp)
        if candidate is not None:
            return candidate, orch
    pytest.fail("real Phase3 campaign did not produce an opportunity")


def _spec() -> SymbolSpec:
    return SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.00001"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))


def _account() -> AccountState:
    return AccountState("ACT_PRIMARY", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)


def test_real_phase3_to_partb_production_path() -> None:
    candidate, orch = _candidate()
    adapter = Phase3DecisionAdapter(account_registry=AccountRegistry.from_yaml("config/accounts.yaml"))
    decision = adapter.build(candidate, orch, candidate.source_watermark, PassingNews(), "ACT_PRIMARY")
    pipeline = PartBDecisionPipeline(
        RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")),
        PortfolioConfig(max_correlated_risk=Decimal("500")),
    )
    shield = NewsShield(); shield.update_calendar(candidate.source_watermark)
    result = pipeline.evaluate(decision, _account(), _spec(), PortfolioState(), shield, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate))
    assert result.status == "ALLOW", result
    assert result.allocation is not None
    assert result.allocation.approved_volume > 0


def test_real_phase3_to_partb_fails_closed_when_news_locks_down() -> None:
    candidate, orch = _candidate(1)
    adapter = Phase3DecisionAdapter(account_registry=AccountRegistry.from_yaml("config/accounts.yaml"))
    decision = adapter.build(candidate, orch, candidate.source_watermark, PassingNews(), "ACT_PRIMARY")
    shield = NewsShield()
    from src.fractal_flow.domain.news_shield import NewsEvent, NewsImportance, NewsObservation
    shield.schedule(NewsEvent("N", candidate.source_watermark, "US", ("USD",), "CPI", NewsImportance.HIGH, ("EURUSD",), 300, 120, 600))
    shield.observe(NewsObservation("N", candidate.source_watermark, Decimal("3"), Decimal("3"), Decimal("3"), Decimal("3")))
    pipeline = PartBDecisionPipeline(RiskConfig(), PortfolioConfig())
    result = pipeline.evaluate(decision, _account(), _spec(), PortfolioState(), shield, candidate.source_watermark, Decimal("100"), authoritative_opportunity=adapter._phase4_opportunity(candidate))
    assert result.status == "REJECT"
    assert result.reason.startswith("NEWS:")

from __future__ import annotations

import json
import sys
from decimal import Decimal

from src.fractal_flow.domain.market import Timeframe
from src.fractal_flow.domain.news_shield import NewsEvent, NewsImportance, NewsObservation, NewsShield
from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.phase3 import Phase3Orchestrator
from src.fractal_flow.domain.phase4 import AccountProfile, AccountRegistry, GateEvidence, Phase4GateType, Phase4ValidationError
from src.fractal_flow.domain.phase4_bridge import Phase3DecisionAdapter
from src.fractal_flow.domain.portfolio import PortfolioCandidate, PortfolioConfig, PortfolioState
from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
from tests.regression.test_phase5_r5_real_campaign import _real_mtf_bars


class PassingNews:
    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence:
        return GateEvidence(Phase4GateType.TRADEABILITY, True, "NEWS_NORMAL", timestamp, producer="NewsShield")


def main(seed: int) -> None:
    tfs = tuple(Timeframe.validate(tf) for tf in ("1M", "5M", "15M", "30M", "1H", "4H"))
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in tfs}
    orch = Phase3Orchestrator("EURUSD")
    candidate = None
    decision = None
    registry = AccountRegistry({"ACC": AccountProfile("ACC", "GENERIC_BROKER", "USD", default_lane="PRIMARY")})
    adapter = Phase3DecisionAdapter(account_registry=registry)
    for bar in _real_mtf_bars(seed, 2_000):
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orch.ingest(evaluation)
        candidate = orch.construct_opportunity(bar.close_timestamp)
        if candidate is None:
            continue
        try:
            decision = adapter.build(candidate, orch, candidate.source_watermark, PassingNews(), "ACC")
            break
        except Phase4ValidationError:
            continue
    if candidate is None or decision is None:
        print(json.dumps({"seed": seed, "candidate": False, "unexpected": 0}), flush=True)
        return
    account = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    spec = SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.00001"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))
    pipeline = PartBDecisionPipeline(RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")), PortfolioConfig(max_correlated_risk=Decimal("500")))
    constrained_portfolio = PartBDecisionPipeline(RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")), PortfolioConfig(max_correlated_risk=Decimal("150")))
    scenarios = {}

    fresh = NewsShield(); fresh.update_calendar(candidate.source_watermark)
    scenarios["baseline"] = pipeline.evaluate(decision, account, spec, PortfolioState(), fresh, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "ALLOW"

    stale = NewsShield(); stale.update_calendar(candidate.source_watermark - stale.config.calendar_max_age - 1)
    scenarios["stale_calendar"] = pipeline.evaluate(decision, account, spec, PortfolioState(), stale, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "REJECT"

    shock = NewsShield(); shock.update_calendar(candidate.source_watermark)
    shock.schedule(NewsEvent("SHOCK", candidate.source_watermark, "US", ("USD",), "CPI", NewsImportance.HIGH, ("EURUSD",), 300, 120, 600))
    shock.observe(NewsObservation("SHOCK", candidate.source_watermark, Decimal("4"), Decimal("4"), Decimal("4"), Decimal("4")))
    scenarios["observed_shock"] = pipeline.evaluate(decision, account, spec, PortfolioState(), shock, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "REJECT"

    poor_account = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("1"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    scenarios["account_infeasible"] = pipeline.evaluate(decision, poor_account, spec, PortfolioState(), fresh, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "REJECT"

    existing = PortfolioCandidate("old", "GBPUSD", "LONG", "GBP", "USD", Decimal("1"), Decimal("100"), Decimal("0.9"), notional=Decimal("1"))
    concentrated = PortfolioState(open_positions=(existing,))
    scenarios["correlation_cap"] = constrained_portfolio.evaluate(decision, account, spec, concentrated, fresh, candidate.source_watermark, Decimal("500"), correlations={("EURUSD", "GBPUSD"): Decimal("0.95")}, authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "REJECT"

    if candidate.opportunity.direction.value == "LONG":
        opposite = PortfolioCandidate("old-flip", "EURUSD", "SHORT", "EUR", "USD", Decimal("1"), Decimal("100"), Decimal("0.9"), notional=Decimal("1"))
    else:
        opposite = PortfolioCandidate("old-flip", "EURUSD", "LONG", "EUR", "USD", Decimal("1"), Decimal("100"), Decimal("0.9"), notional=Decimal("1"))
    scenarios["flip_without_reversal"] = pipeline.evaluate(decision, account, spec, PortfolioState(open_positions=(opposite,)), fresh, candidate.source_watermark, Decimal("500"), authoritative_opportunity=adapter._phase4_opportunity(candidate)).status == "REJECT"
    failures = [name for name, passed in scenarios.items() if not passed]
    print(json.dumps({"seed": seed, "candidate": True, "scenarios": scenarios, "failures": failures, "unexpected": len(failures)}, sort_keys=True), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main(int(sys.argv[1]))

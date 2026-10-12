from __future__ import annotations

import json
import sys
from decimal import Decimal

from src.fractal_flow.domain.market import Timeframe
from src.fractal_flow.domain.lane_pipeline import LanePipeline, LanePolicy
from src.fractal_flow.domain.news_shield import NewsShield
from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.phase3 import Phase3Orchestrator
from src.fractal_flow.domain.phase4 import AccountProfile, AccountRegistry, GateEvidence, Phase4GateType, Phase4ValidationError
from src.fractal_flow.domain.phase4_bridge import Phase3DecisionAdapter
from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
from tests.regression.test_phase5_r5_real_campaign import _real_mtf_bars


class PassingNews:
    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence:
        return GateEvidence(Phase4GateType.TRADEABILITY, True, "NEWS_NORMAL", timestamp, producer="NewsShield")


def main(seed: int) -> None:
    tfs = tuple(Timeframe.validate(tf) for tf in ("1M", "5M", "15M", "30M", "1H", "4H"))
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in tfs}
    orchestrator = Phase3Orchestrator("EURUSD")
    registry = AccountRegistry(
        {
            "ACT_PRIMARY": AccountProfile("ACT_PRIMARY", "GENERIC_BROKER", "USD", default_lane="PRIMARY"),
            "ACT_SECONDARY": AccountProfile("ACT_SECONDARY", "GENERIC_BROKER", "USD", default_lane="SECONDARY"),
            "ACT_TERTIARY": AccountProfile("ACT_TERTIARY", "GENERIC_BROKER", "USD", default_lane="RESEARCH"),
        }
    )
    adapter = Phase3DecisionAdapter(account_registry=registry)
    lane = LanePipeline({"PRIMARY": LanePolicy(max_risk=Decimal("1000"), max_entries=100), "SECONDARY": LanePolicy(max_risk=Decimal("1000"), max_entries=100), "RESEARCH": LanePolicy(max_risk=Decimal("1000"), max_entries=100)}, {"FX": Decimal("1000")})
    partb = PartBDecisionPipeline(
        RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")),
        PortfolioConfig(max_correlated_risk=Decimal("500")),
        lane_pipeline=lane,
    )
    symbol_spec = SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.00001"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))
    accounts = (
        AccountState("ACT_PRIMARY", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0),
        AccountState("ACT_SECONDARY", Decimal("7500"), Decimal("7500"), Decimal("6500"), Decimal("4"), Decimal("0"), Decimal("0"), 0),
        AccountState("ACT_TERTIARY", Decimal("15000"), Decimal("15000"), Decimal("12000"), Decimal("1"), Decimal("0"), Decimal("0"), 0),
    )
    candidates = 0
    authorized = 0
    blocked = 0
    processed = 0
    unexpected = 0
    authorized_by_account = {account.account_id: 0 for account in accounts}
    blocked_by_account = {account.account_id: 0 for account in accounts}
    for bar in _real_mtf_bars(seed, 10_000):
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orchestrator.ingest(evaluation)
        candidate = orchestrator.construct_opportunity(bar.close_timestamp)
        processed += 1
        if candidate is None:
            continue
        candidates += 1
        for account in accounts:
            try:
                decision = adapter.build(candidate, orchestrator, candidate.source_watermark, PassingNews(), account.account_id)
                shield = NewsShield(); shield.update_calendar(bar.close_timestamp)
                result = partb.evaluate(decision, account, symbol_spec, PortfolioState(), shield, bar.close_timestamp, Decimal("500"), lane=registry.get(account.account_id).default_lane, group="FX", authoritative_opportunity=adapter._phase4_opportunity(candidate))
                if result.status == "ALLOW":
                    authorized += 1
                    authorized_by_account[account.account_id] += 1
                else:
                    blocked += 1
                    blocked_by_account[account.account_id] += 1
            except Phase4ValidationError:
                blocked += 1
                blocked_by_account[account.account_id] += 1
            except Exception as exc:
                unexpected += 1
                if unexpected <= 5:
                    print(f"ERR {account.account_id} {type(exc).__name__}: {exc}", file=sys.stderr)
    print(json.dumps({"seed": seed, "m1_bars": 10_000, "processed": processed, "candidates": candidates, "authorized": authorized, "blocked": blocked, "unexpected": unexpected, "authorized_by_account": authorized_by_account, "blocked_by_account": blocked_by_account}, sort_keys=True))
    if unexpected:
        raise SystemExit(1)


if __name__ == "__main__":
    main(int(sys.argv[1]))

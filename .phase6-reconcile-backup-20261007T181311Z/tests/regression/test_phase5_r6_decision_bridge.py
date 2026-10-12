from __future__ import annotations

import pytest

from src.fractal_flow.domain.phase4 import GateEvidence
from src.fractal_flow.domain.phase4_bridge import Phase3DecisionAdapter
from src.fractal_flow.domain.phase4 import AccountRegistry
from tests.regression.test_phase5_r5_real_campaign import _real_mtf_bars
from src.fractal_flow.domain.market import Timeframe
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.phase3 import Phase3Orchestrator


class _PassingNews:
    def evaluate(self, symbol: str, timestamp: int) -> GateEvidence:
        from src.fractal_flow.domain.phase4 import Phase4GateType
        return GateEvidence(Phase4GateType.TRADEABILITY, True, "NEWS_INTERFACE_READY", timestamp, producer="test-news-port")


def _real_candidate():
    tfs = tuple(Timeframe.validate(tf) for tf in ("1M", "5M", "15M", "30M", "1H", "4H"))
    pipelines = {tf: Phase2Pipeline("EURUSD", tf.value) for tf in tfs}
    orch = Phase3Orchestrator("EURUSD")
    for bar in _real_mtf_bars(0, 1_500):
        evaluation = pipelines[Timeframe.validate(bar.timeframe)].process_bar(bar)
        orch.ingest(evaluation)
        candidate = orch.construct_opportunity(bar.close_timestamp)
        if candidate is not None:
            return candidate, orch
    pytest.fail("real Phase3 campaign did not produce an opportunity")


def test_r6_real_phase3_output_builds_phase4_decision_from_derived_evidence() -> None:
    candidate, orch = _real_candidate()
    adapter = Phase3DecisionAdapter(account_registry=AccountRegistry.from_yaml("config/accounts.yaml"))
    decision = adapter.build(candidate, orch, candidate.source_watermark, _PassingNews(), "ACT_PRIMARY")
    assert decision.opportunity_id
    assert decision.entry_plan.structural_stop in {
        orch._latest_at(orch.mapping.primary, candidate.source_watermark).structure.protected_low,
        orch._latest_at(orch.mapping.primary, candidate.source_watermark).structure.protected_high,
    }
    assert decision.opportunity_content_hash
    assert adapter.recheck_liveness(decision, candidate, candidate.source_watermark)


def test_r6_forged_or_expired_candidate_fails_live_authority_recheck() -> None:
    from dataclasses import replace
    candidate, orch = _real_candidate()
    adapter = Phase3DecisionAdapter(account_registry=AccountRegistry.from_yaml("config/accounts.yaml"))
    decision = adapter.build(candidate, orch, candidate.source_watermark, _PassingNews(), "ACT_PRIMARY")
    expired = replace(candidate, opportunity=replace(candidate.opportunity, state="EXPIRED"))
    assert not adapter.recheck_liveness(decision, expired, candidate.expires_at)


def test_r6_object_mutation_cannot_restore_live_authority_after_expiry() -> None:
    from dataclasses import replace
    candidate, orch = _real_candidate()
    adapter = Phase3DecisionAdapter(account_registry=AccountRegistry.from_yaml("config/accounts.yaml"))
    decision = adapter.build(candidate, orch, candidate.source_watermark, _PassingNews(), "ACT_PRIMARY")
    expired = replace(candidate.opportunity, state="EXPIRED")
    object.__setattr__(decision, "opportunity_content_hash", "0" * 64)
    assert not decision.is_live_authorized(adapter._phase4_opportunity(replace(candidate, opportunity=expired)), candidate.expires_at)

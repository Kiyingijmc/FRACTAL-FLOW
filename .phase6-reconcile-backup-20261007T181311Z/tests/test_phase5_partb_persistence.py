from decimal import Decimal

from src.fractal_flow.domain.news_shield import NewsShield
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.part5 import PartBDecisionJournal


def test_partb_journal_roundtrip_and_idempotency(tmp_path) -> None:
    path = tmp_path / "partb.journal"
    store = PartBDecisionJournal(DurableEventJournal(str(path)))
    first = store.append(
        account_id="ACC",
        decision_id="DEC-1",
        observed_timestamp=100,
        status="ALLOW",
        reason="PART_B_AUTHORIZED",
        allocation={"approved_risk": "10.00", "approved_volume": "0.01"},
        news_state_hash=NewsShield().state_hash(),
    )
    duplicate = store.append(
        account_id="ACC",
        decision_id="DEC-1",
        observed_timestamp=100,
        status="ALLOW",
        reason="PART_B_AUTHORIZED",
        allocation={"approved_risk": "10.00", "approved_volume": "0.01"},
        news_state_hash=first.news_state_hash,
    )
    assert duplicate == first

    restarted = PartBDecisionJournal(DurableEventJournal(str(path)))
    assert restarted.replay() == (first,)
    assert restarted.latest("ACC") == first


def test_partb_journal_rejects_idempotency_conflict(tmp_path) -> None:
    store = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb.journal")))
    kwargs = dict(
        account_id="ACC",
        decision_id="DEC-1",
        observed_timestamp=100,
        status="ALLOW",
        reason="PART_B_AUTHORIZED",
        allocation={"approved_risk": "10.00"},
        news_state_hash=NewsShield().state_hash(),
    )
    store.append(**kwargs)
    from src.fractal_flow.persistence.journal import JournalCorruptionException
    try:
        store.append(**{**kwargs, "reason": "TAMPERED"})
    except JournalCorruptionException:
        pass
    else:
        raise AssertionError("conflicting Part-B idempotency outcome was accepted")


def test_partb_journal_uses_strict_aggregate_versions(tmp_path) -> None:
    store = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb.journal")))
    for idx in range(2):
        store.append(
            account_id="ACC",
            decision_id=f"DEC-{idx}",
            observed_timestamp=100 + idx,
            status="REJECT",
            reason="NEWS_LOCKDOWN",
            allocation=None,
            news_state_hash=NewsShield().state_hash(),
        )
    records = store.journal.get_events_for_aggregate("PART_B_DECISION", "ACC")
    assert [event.aggregate_version for event in records] == [1, 2]


def test_partb_pipeline_can_persist_authoritative_outcome(tmp_path) -> None:
    from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
    from src.fractal_flow.domain.phase4 import make_decision
    from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
    from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
    from tests.test_phase4_foundation import confidence, gates, opportunity, plan, tradeability

    opp = opportunity()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140, account_id="ACC")
    account = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    spec = SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))
    journal = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb.journal")))
    shield = NewsShield(); shield.update_calendar(140)
    pipeline = PartBDecisionPipeline(RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")), PortfolioConfig(max_correlated_risk=Decimal("500")), journal=journal)
    result = pipeline.evaluate(decision, account, spec, PortfolioState(), shield, 140, Decimal("500"), authoritative_opportunity=opp)
    assert result.status == "ALLOW"
    record = journal.latest("ACC")
    assert record is not None
    assert record.decision_id == decision.decision_id
    assert record.status == result.status
    assert record.news_state_hash == shield.state_hash()


def test_partb_journal_persists_reconstruction_context_and_fingerprint(tmp_path) -> None:
    store = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb-context.journal")))
    context = {
        "opportunity_id": "OPP-1",
        "account_snapshot": {"equity": "10000", "currency": "USD"},
        "symbol_spec": {"symbol": "EURUSD", "contract_size": "100000"},
        "risk_config_version": 2,
        "portfolio_config_version": 3,
        "lane_policy_version": 4,
        "requested_risk": "100",
        "portfolio_state": {"open_positions": []},
    }
    record = store.append(
        account_id="ACC",
        decision_id="DEC-CTX",
        observed_timestamp=100,
        status="ALLOW",
        reason="PART_B_AUTHORIZED",
        allocation={"approved_risk": "10.00", "approved_volume": "0.01"},
        news_state_hash=NewsShield().state_hash(),
        context=context,
    )
    restarted = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "partb-context.journal")))
    restored = restarted.latest("ACC")
    assert restored is not None
    assert dict(restored.context) == {**context, "portfolio_state": {"open_positions": ()}}
    assert restored.context_fingerprint == record.context_fingerprint
    assert restarted.authorized_for_opportunity("ACC", "OPP-1") == (restored,)


def test_partb_lane_group_caps_survive_pipeline_restart(tmp_path) -> None:
    from src.fractal_flow.domain.lane_pipeline import LanePipeline, LanePolicy
    from src.fractal_flow.domain.part5_pipeline import PartBDecisionPipeline
    from src.fractal_flow.domain.phase4 import make_decision
    from src.fractal_flow.domain.portfolio import PortfolioConfig, PortfolioState
    from src.fractal_flow.domain.risk_engine import AccountState, RiskConfig, SymbolSpec
    from tests.test_phase4_foundation import confidence, gates, opportunity, plan, tradeability

    account = AccountState("ACC", Decimal("10000"), Decimal("10000"), Decimal("9000"), Decimal("2"), Decimal("0"), Decimal("0"), 0)
    spec = SymbolSpec("EURUSD", "EUR", "USD", Decimal("100000"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.0005"), Decimal("1000"), Decimal("0.0001"), Decimal("0"))
    opp1 = opportunity()
    opp2 = opportunity(root_id="root-2", primary_pullback_id="pb-2")
    d1 = make_decision(opp1, tradeability(opp1), plan(opp1), gates(), confidence(opp1), 140, account_id="ACC")
    d2 = make_decision(opp2, tradeability(opp2), plan(opp2), gates(), confidence(opp2), 150, account_id="ACC")
    journal = PartBDecisionJournal(DurableEventJournal(str(tmp_path / "lane.journal")))
    lane = LanePipeline({"PRIMARY": LanePolicy(max_risk=Decimal("1000"), max_entries=10)}, {"FX": Decimal("700")})
    kwargs = dict(risk_config=RiskConfig(risk_fraction=Decimal("0.10"), max_risk_per_trade=Decimal("500")), portfolio_config=PortfolioConfig(max_correlated_risk=Decimal("500"), max_total_risk=Decimal("1000")), lane_pipeline=lane)
    shield = NewsShield(); shield.update_calendar(140)
    first = PartBDecisionPipeline(journal=journal, **kwargs).evaluate(d1, account, spec, PortfolioState(), shield, 140, Decimal("500"), lane="PRIMARY", group="FX", authoritative_opportunity=opp1)
    assert first.status == "ALLOW"
    restarted = PartBDecisionPipeline(journal=PartBDecisionJournal(DurableEventJournal(str(tmp_path / "lane.journal"))), **kwargs)
    shield2 = NewsShield(); shield2.update_calendar(150)
    second = restarted.evaluate(d2, account, spec, PortfolioState(), shield2, 150, Decimal("500"), lane="PRIMARY", group="FX", authoritative_opportunity=opp2)
    assert second.status == "REJECT"
    assert second.reason.startswith("LANE:")

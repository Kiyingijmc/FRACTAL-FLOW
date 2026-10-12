from decimal import Decimal
from pathlib import Path

import pytest

from src.fractal_flow.domain.phase4 import (
    AccountProfile,
    AccountRegistry,
    AnalysisEnvelope,
    ConfidenceEvidence,
    EntryPlanV4,
    ExecutionQualityProfile,
    GateEvidence,
    LiquiditySweepModifier,
    Opportunity,
    OpportunityState,
    Phase4GateType,
    Phase4ValidationError,
    TimeframeMapping,
    TradeabilityEngine,
    TradeabilityStatus,
    make_decision,
)

ROOT = Path(__file__).parents[1]


def opportunity(**kwargs):
    base = dict(
        root_id="root-1", parent_opportunity_id=None,
        symbol="EURUSD", direction="LONG", setup_family="FF-01",
        primary_pullback_id="pb-1", created_at=100, expires_at=200,
        state=OpportunityState.VALID, opportunity_space=Decimal("20"),
        structural_edge=Decimal("5"), confidence=Decimal("0.9"),
    )
    base.update(kwargs)
    base.setdefault("opportunity_id", Opportunity.deterministic_id(base["root_id"], base["symbol"], base["primary_pullback_id"], base["setup_family"], base["direction"]))
    return Opportunity(**base)


def profile():
    return ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))


def tradeability(opp=None, **kwargs):
    opp = opp or opportunity()
    values = dict(spread=Decimal("1"), commission=Decimal("0.1"), slippage=Decimal("0.1"), gross_move=Decimal("10"), liquidity_ok=True, execution_quality=Decimal("0.8"), profile=profile())
    values.update(kwargs)
    return TradeabilityEngine().evaluate(opp, values.pop("spread"), values.pop("commission"), values.pop("slippage"), values.pop("gross_move"), values.pop("liquidity_ok"), values.pop("execution_quality"), values.pop("profile"), **values)


def plan(opp=None, **kwargs):
    opp = opp or opportunity()
    base = dict(entry_plan_id="ep", opportunity_id=opp.opportunity_id, symbol=opp.symbol, direction=opp.direction,
                entry_price=Decimal("1.1"), structural_stop=Decimal("1.0"), atr_buffer=Decimal("0.01"),
                target_price=Decimal("1.3"), minimum_rr_after_costs=Decimal("1.5"), quote_timestamp=120,
                expected_total_cost=Decimal("0.01"))
    base.update(kwargs)
    return EntryPlanV4(**base)


def gates(passed=True, observed=130):
    return [
        GateEvidence(Phase4GateType.ENTRY_PLAN, passed, "ENTRY_OK", observed),
        GateEvidence(Phase4GateType.OPPORTUNITY, passed, "OPP_OK", observed),
        GateEvidence(Phase4GateType.TRADEABILITY, passed, "TRADE_OK", observed),
    ]


def confidence(opp=None, observed=130, value=Decimal("0.8")):
    opp = opp or opportunity()
    return ConfidenceEvidence(value, "phase4-test", "1", observed)


def test_account_registry_and_default_lane():
    reg = AccountRegistry.from_yaml(ROOT / "config" / "accounts.yaml")
    assert reg.get("ACT_PRIMARY").enabled


def test_account_profile_rejects_truthiness_coercion():
    with pytest.raises(Phase4ValidationError):
        AccountProfile("A", "B", "USD", enabled="false")


def test_analysis_envelope_is_account_free_and_deterministic():
    a = AnalysisEnvelope.create("EURUSD", 100, {"direction": "LONG"})
    b = AnalysisEnvelope.create("EURUSD", 100, {"direction": "LONG"})
    assert a == b
    assert "account_id" not in a.__dict__


def test_opportunity_identity_is_enforced_and_sweep_is_modifier():
    oid = Opportunity.deterministic_id("root", "EURUSD", "pb", "FF-01", "LONG")
    a = Opportunity(oid, "root", None, "EURUSD", "LONG", "FF-01", "pb", 100, 200, OpportunityState.VALID, Decimal("20"), Decimal("5"), Decimal("0.9"), LiquiditySweepModifier("SWEEP_RECOVERY", 150))
    assert a.opportunity_id == oid
    with pytest.raises(Phase4ValidationError):
        Opportunity("forged", "root", None, "EURUSD", "LONG", "FF-01", "pb", 100, 200, OpportunityState.VALID, Decimal("20"), Decimal("5"), Decimal("0.9"))
    with pytest.raises(Phase4ValidationError):
        LiquiditySweepModifier("STANDALONE_STRATEGY", 150)


def test_opportunity_is_live_is_causally_bounded():
    opp = opportunity()
    assert not opp.is_live(50)
    assert opp.is_live(100)
    assert not opp.is_live(200)
    assert not opportunity(state=OpportunityState.INVALIDATED).is_live(150)


def test_parent_invalidation_propagates_to_child():
    parent = opportunity(root_id="parent-root", primary_pullback_id="pb-parent")
    child = opportunity(parent_opportunity_id=parent.opportunity_id, root_id="child-root", primary_pullback_id="pb-child")
    assert child.is_live(120, parent)
    invalid_parent = Opportunity(**{**parent.__dict__, "state": OpportunityState.INVALIDATED})
    assert not child.is_live(120, invalid_parent)


def test_timeframe_migration_is_explicit_and_bounded():
    # covers: [26]
    mapping = TimeframeMapping()
    assert mapping.primary_tf == "M15"
    mapping = mapping.migrate_primary_down()
    assert mapping.primary_tf == "M5"
    assert mapping.migrate_primary_down().primary_tf == "M5"
    assert mapping.primary_tf > mapping.execution_tf


def test_tradeability_cost_dominated_target_fails():
    result = TradeabilityEngine().evaluate(
        opportunity(opportunity_space=Decimal("5")), Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4"), True, Decimal("1"), profile(), observed_timestamp=120,
    )
    assert result.status == TradeabilityStatus.FAIL_COST


def test_tradeability_rejects_malformed_economics():
    with pytest.raises(Phase4ValidationError):
        TradeabilityEngine().evaluate(opportunity(), Decimal("-1"), Decimal("0"), Decimal("0"), Decimal("10"), True, Decimal("1"), profile())
    with pytest.raises(Phase4ValidationError):
        TradeabilityEngine().evaluate(opportunity(), Decimal("1"), Decimal("0"), Decimal("0"), Decimal("0"), True, Decimal("1"), profile())
    with pytest.raises(Phase4ValidationError):
        ExecutionQualityProfile(Decimal("-1"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))


def test_spread_spike_cannot_be_overridden():
    result = TradeabilityEngine().evaluate(opportunity(), Decimal("10"), Decimal("0"), Decimal("0"), Decimal("100"), True, Decimal("1"), ExecutionQualityProfile(Decimal("2"), Decimal("0.5"), Decimal("2"), Decimal("0.5")), observed_timestamp=120)
    assert result.status == TradeabilityStatus.FAIL_SPREAD


def test_entry_plan_enforces_long_geometry_and_post_cost_rr():
    with pytest.raises(Phase4ValidationError):
        plan(target_price=Decimal("1.05"))
    with pytest.raises(Phase4ValidationError):
        plan(structural_stop=Decimal("1.2"))
    with pytest.raises(Phase4ValidationError):
        plan(atr_buffer=Decimal("0"))
    with pytest.raises(Phase4ValidationError):
        plan(target_price=Decimal("1.2"), minimum_rr_after_costs=Decimal("2"))


def test_entry_plan_enforces_short_geometry():
    opp = opportunity(direction="SHORT")
    with pytest.raises(Phase4ValidationError):
        plan(opp, entry_price=Decimal("1.1"), structural_stop=Decimal("1.0"), target_price=Decimal("0.9"))
    assert plan(opp, entry_price=Decimal("1.1"), structural_stop=Decimal("1.2"), target_price=Decimal("0.8"), minimum_rr_after_costs=Decimal("1.5"))


def test_authority_requires_exact_mandatory_gates_and_tradeability():
    opp = opportunity()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140)
    assert decision.phase4_ready
    assert decision.authorized
    failed = make_decision(opp, tradeability(opp), plan(opp), gates(passed=False), confidence(opp), 140)
    assert not failed.authorized
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opp), plan(opp), gates()[:-1], confidence(opp), 140)



def test_confidence_cannot_authorize_failed_gate():
    # covers: [2]
    # covers: [3]
    # covers: [4]
    opp = opportunity()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(passed=False), confidence(opp), 140)
    assert not decision.authorized


def test_opportunity_identity_is_deterministic_and_sweep_is_modifier():
    # covers: [29]
    test_opportunity_identity_is_enforced_and_sweep_is_modifier()

def test_failed_tradeability_is_non_authorizing():
    opp = opportunity()
    bad = tradeability(opp, spread=Decimal("10"))
    assert bad.status == TradeabilityStatus.FAIL_SPREAD
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, bad, plan(opp), gates(), confidence(opp), 140)


def test_invalidated_opportunity_cannot_authorize():
    opp = opportunity(state=OpportunityState.INVALIDATED)
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opportunity()), plan(opportunity()), gates(), confidence(opportunity()), 140)


def test_future_and_precreation_evidence_are_rejected():
    opp = opportunity()
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opp), plan(opp), [*gates(observed=101), GateEvidence(Phase4GateType.ENTRY_PLAN, True, "DUP", 101)], confidence(opp), 140)
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opp), plan(opp), gates(observed=99), confidence(opp), 140)


def test_duplicate_and_unknown_gates_are_rejected():
    opp = opportunity()
    duplicate = gates() + [GateEvidence(Phase4GateType.TRADEABILITY, True, "DUP", 130)]
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opp), plan(opp), duplicate, confidence(opp), 140)
    with pytest.raises(Phase4ValidationError):
        GateEvidence("FAKE_GATE", True, "x", 130)


def test_parent_invalidation_blocks_child_decision():
    parent = opportunity(root_id="parent-root", primary_pullback_id="pb-parent")
    child = opportunity(parent_opportunity_id=parent.opportunity_id, root_id="child-root", primary_pullback_id="pb-child")
    child_tb = tradeability(child, parent_opportunity=parent)
    with pytest.raises(Phase4ValidationError):
        make_decision(child, child_tb, plan(child), gates(), confidence(child), 140, parent_opportunity=Opportunity(**{**parent.__dict__, "state": OpportunityState.INVALIDATED}))


def test_confidence_is_bounded_provenanced_and_non_escalating():
    opp = opportunity()
    with pytest.raises(Phase4ValidationError):
        ConfidenceEvidence(Decimal("2"), "test", "1", 120)
    with pytest.raises(Phase4ValidationError):
        make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp, value=Decimal("0.95")), 140)


def test_decision_fingerprint_is_input_order_invariant():
    opp = opportunity()
    a = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140)
    b = make_decision(opp, tradeability(opp), plan(opp), list(reversed(gates())), confidence(opp), 140)
    assert a.decision_id == b.decision_id


def test_account_identity_propagates_into_execution_risk_event_and_config():
    from src.fractal_flow.config.config import BaseConfig, compute_effective_config
    from src.fractal_flow.domain.event import Event
    from src.fractal_flow.domain.models import ExecutionIntent, OrderSide
    from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger

    cfg = compute_effective_config(BaseConfig(), "EURUSD", account_id="ACC_2")
    assert cfg.account_id == "ACC_2"
    ledger = OpportunityRiskLedger("b", "o", Decimal("10"), Decimal("1"), account_id="ACC_2")
    assert ledger.account_id == "ACC_2"
    intent = ExecutionIntent("i", "d", "o", "r", "k", "EURUSD", OrderSide.BUY, Decimal("1"), Decimal("1"), Decimal("0.9"), {}, cfg.effective_config_id, 1, {}, 100, Decimal("0"), "PENDING", 100, 100, account_id="ACC_2")
    assert intent.account_id == "ACC_2"
    event = Event("e", "X", "O", "o", "r", "p", 1, 1, 1, 1, {}, account_id="ACC_2")
    assert event.account_id == "ACC_2"


def test_entry_plan_contains_no_account_or_volume_authority():
    fields = EntryPlanV4.__dataclass_fields__
    assert "account_id" not in fields
    assert "volume" not in fields

"""Independent hostile tests for the Phase 4 authority kernel.

These tests intentionally attempt to manufacture authorization by mutating one
safety signal at a time. They are kept separate from the construction tests so
that closure does not depend on a single happy-path test module.
"""
from decimal import Decimal

import pytest

from src.fractal_flow.domain.phase4 import (
    ConfidenceEvidence,
    EntryPlanV4,
    ExecutionQualityProfile,
    GateEvidence,
    Opportunity,
    OpportunityState,
    Phase4GateType,
    Phase4ValidationError,
    TradeabilityAssessmentV4,
    TradeabilityEngine,
    TradeabilityStatus,
    TradeDecisionV4,
    _decision_fingerprint,
    make_decision,
)


def make_opp(**changes):
    data = dict(
        root_id="root", parent_opportunity_id=None, symbol="EURUSD", direction="LONG",
        setup_family="FF-01", primary_pullback_id="pb", created_at=100, expires_at=200,
        state=OpportunityState.VALID, opportunity_space=Decimal("20"),
        structural_edge=Decimal("5"), confidence=Decimal("0.9"),
    )
    data.update(changes)
    data.setdefault("opportunity_id", Opportunity.deterministic_id(data["root_id"], data["symbol"], data["primary_pullback_id"], data["setup_family"], data["direction"]))
    return Opportunity(**data)


def profile():
    return ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))


def tradeability(opp, **changes):
    values = dict(spread=Decimal("1"), commission=Decimal("0.1"), slippage=Decimal("0.1"), gross_move=Decimal("10"), liquidity_ok=True, execution_quality=Decimal("0.8"), profile=profile(), observed_timestamp=120)
    values.update(changes)
    return TradeabilityEngine().evaluate(opp, values.pop("spread"), values.pop("commission"), values.pop("slippage"), values.pop("gross_move"), values.pop("liquidity_ok"), values.pop("execution_quality"), values.pop("profile"), **values)


def plan(opp):
    return EntryPlanV4("ep", opp.opportunity_id, opp.symbol, opp.direction, Decimal("1.1"), Decimal("1"), Decimal(".01"), Decimal("1.3"), Decimal("1.5"), 120, Decimal(".01"))


def confidence(opp, value=Decimal(".8")):
    return ConfidenceEvidence(value, "hostile", "1", 120)


def gates(overrides=None):
    base = {
        Phase4GateType.OPPORTUNITY: True,
        Phase4GateType.TRADEABILITY: True,
        Phase4GateType.ENTRY_PLAN: True,
    }
    base.update(overrides or {})
    return [GateEvidence(g, passed, "hostile", 130) for g, passed in base.items()]


def assert_blocked(fn):
    with pytest.raises(Phase4ValidationError):
        fn()


def test_invalidated_and_expired_opportunities_cannot_authorize():
    live = make_opp()
    for state in (OpportunityState.INVALIDATED, OpportunityState.EXPIRED, OpportunityState.STALE, OpportunityState.DEGRADED):
        assert_blocked(lambda state=state: make_decision(make_opp(state=state), tradeability(live), plan(live), gates(), confidence(live), 140))


def test_tradeability_status_is_derived_not_caller_selected():
    opp = make_opp()
    with pytest.raises(Phase4ValidationError):
        TradeabilityAssessmentV4(opp.opportunity_id, TradeabilityStatus.PASS, Decimal("10"), Decimal("1"), Decimal("10"), Decimal("20"), Decimal(".8"), (), 120, True, profile())


def test_gate_pass_cannot_override_authoritative_tradeability_or_opportunity():
    opp = make_opp()
    failed_tb = tradeability(opp, spread=Decimal("10"))
    assert_blocked(lambda: make_decision(opp, failed_tb, plan(opp), gates(), confidence(opp), 140))
    invalid = make_opp(state=OpportunityState.INVALIDATED)
    assert_blocked(lambda: make_decision(invalid, tradeability(opp), plan(opp), gates(), confidence(opp), 140))


def test_unknown_missing_duplicate_and_contradictory_gates_never_authorize():
    opp = make_opp()
    assert_blocked(lambda: GateEvidence("FAKE_GATE", True, "hostile", 130))
    decision = make_decision(opp, tradeability(opp), plan(opp), gates({Phase4GateType.OPPORTUNITY: False}), confidence(opp), 140)
    assert not decision.authorized
    dup = gates() + [GateEvidence(Phase4GateType.TRADEABILITY, True, "duplicate", 130)]
    assert_blocked(lambda: make_decision(opp, tradeability(opp), plan(opp), dup, confidence(opp), 140))
    decision = make_decision(opp, tradeability(opp), plan(opp), gates({Phase4GateType.TRADEABILITY: False}), confidence(opp), 140)
    assert not decision.authorized


def test_temporal_mutations_are_non_authorizing():
    opp = make_opp()
    assert not opp.is_live(99)
    assert not opp.is_live(200)
    assert_blocked(lambda: make_decision(opp, tradeability(opp), plan(opp), [GateEvidence(g.gate, g.passed, g.reason, 99) for g in gates()], confidence(opp), 140))
    assert_blocked(lambda: make_decision(opp, tradeability(opp, observed_timestamp=141), plan(opp), gates(), confidence(opp), 140))


def test_confidence_mutations_are_non_authorizing():
    opp = make_opp()
    assert_blocked(lambda: make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp, Decimal("0.91")), 140))
    assert_blocked(lambda: ConfidenceEvidence(Decimal("NaN"), "hostile", "1", 120))


def test_entry_geometry_mutation_matrix_is_fail_closed():
    opp = make_opp()
    mutations = [
        dict(structural_stop=Decimal("1.2")),
        dict(target_price=Decimal("1.05")),
        dict(atr_buffer=Decimal("0")),
        dict(minimum_rr_after_costs=Decimal("9")),
        dict(expected_total_cost=Decimal("10")),
    ]
    for change in mutations:
        assert_blocked(lambda change=change: EntryPlanV4("x", opp.opportunity_id, "EURUSD", "LONG", Decimal("1.1"), change.get("structural_stop", Decimal("1")), change.get("atr_buffer", Decimal(".01")), change.get("target_price", Decimal("1.3")), change.get("minimum_rr_after_costs", Decimal("1.5")), 120, change.get("expected_total_cost", Decimal(".01"))))


def test_parent_lineage_mutation_is_fail_closed():
    parent = make_opp(root_id="parent", primary_pullback_id="pp")
    child = make_opp(root_id="child", primary_pullback_id="cp", parent_opportunity_id=parent.opportunity_id)
    dead_parent = make_opp(root_id="parent", primary_pullback_id="pp", state=OpportunityState.INVALIDATED)
    child_tb = tradeability(child, parent_opportunity=parent)
    assert_blocked(lambda: make_decision(child, child_tb, plan(child), gates(), confidence(child), 140, parent_opportunity=dead_parent))


def test_valid_authority_is_permutation_invariant_and_deterministic():
    opp = make_opp()
    a = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140)
    b = make_decision(opp, tradeability(opp), plan(opp), list(reversed(gates())), confidence(opp), 140)
    assert a.phase4_ready
    assert a.decision_id == b.decision_id


def test_direct_trade_decision_construction_cannot_mint_authority():
    """A structurally valid dataclass is not an authority-bearing decision."""
    opp = make_opp()
    tb = tradeability(opp)
    ep = plan(opp)
    gs = tuple(gates())
    conf = confidence(opp)
    decision_id = _decision_fingerprint(opp.opportunity_id, tb, ep, gs, conf, 140)
    direct = TradeDecisionV4(
        decision_id=decision_id,
        opportunity_id=opp.opportunity_id,
        root_id=opp.root_id,
        account_id=None,
        entry_plan=ep,
        tradeability=tb,
        gates=gs,
        confidence=conf,
        created_at=140,
    )
    assert not direct.phase4_ready
    assert not direct.authorized


def test_direct_trade_decision_from_invalidated_opportunity_cannot_mint_authority():
    opp = make_opp(state=OpportunityState.INVALIDATED)
    tb = TradeabilityAssessmentV4(opp.opportunity_id, TradeabilityStatus.PASS, Decimal("1"), Decimal("0.2"), Decimal("10"), Decimal("20"), Decimal("0.8"), (), 120, True, profile())
    ep = plan(opp)
    gs = tuple(gates())
    conf = confidence(opp)
    decision_id = _decision_fingerprint(opp.opportunity_id, tb, ep, gs, conf, 140)
    direct = TradeDecisionV4(
        decision_id=decision_id, opportunity_id=opp.opportunity_id, root_id=opp.root_id, account_id=None,
        entry_plan=ep, tradeability=tb, gates=gs, confidence=conf, created_at=140,
    )
    assert not direct.authorized


def test_direct_trade_decision_rejects_forged_fingerprint():
    opp = make_opp()
    tb = tradeability(opp)
    ep = plan(opp)
    gs = tuple(gates())
    conf = confidence(opp)
    with pytest.raises(Phase4ValidationError):
        TradeDecisionV4(
            decision_id="forged",
            opportunity_id=opp.opportunity_id,
            root_id=opp.root_id,
            account_id=None,
            entry_plan=ep,
            tradeability=tb,
            gates=gs,
            confidence=conf,
            created_at=140,
        )


def test_direct_trade_decision_with_future_evidence_cannot_authorize():
    opp = make_opp()
    future_tb = TradeabilityAssessmentV4(opp.opportunity_id, TradeabilityStatus.PASS, Decimal("1"), Decimal("0.2"), Decimal("10"), Decimal("20"), Decimal("0.8"), (), 999, True, profile())
    ep = plan(opp)
    gs = tuple(gates())
    conf = confidence(opp)
    decision_id = _decision_fingerprint(opp.opportunity_id, future_tb, ep, gs, conf, 140)
    direct = TradeDecisionV4(
        decision_id=decision_id,
        opportunity_id=opp.opportunity_id,
        root_id=opp.root_id,
        account_id=None,
        entry_plan=ep,
        tradeability=future_tb,
        gates=gs,
        confidence=conf,
        created_at=140,
    )
    assert not direct.authorized


def test_factory_is_the_only_authority_proof_path():
    opp = make_opp()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140)
    assert decision.phase4_ready
    assert decision.authorized


def test_authority_factory_rejects_invalidated_opportunity_even_when_opportunity_gate_is_negative():
    invalid = make_opp(state=OpportunityState.INVALIDATED)
    tb = TradeabilityAssessmentV4(invalid.opportunity_id, TradeabilityStatus.PASS, Decimal("1"), Decimal("0.2"), Decimal("10"), Decimal("20"), Decimal("0.8"), (), 120, True, profile())
    opp_gates = gates({Phase4GateType.OPPORTUNITY: False})
    assert_blocked(lambda: make_decision(invalid, tb, plan(invalid), opp_gates, confidence(invalid), 140))


def test_authority_factory_rejects_failed_tradeability_even_when_tradeability_gate_is_negative():
    opp = make_opp()
    failed = tradeability(opp, spread=Decimal("10"))
    tb_gates = gates({Phase4GateType.TRADEABILITY: False})
    assert_blocked(lambda: make_decision(opp, failed, plan(opp), tb_gates, confidence(opp), 140))


def test_authority_factory_rejects_missing_mandatory_gate():
    opp = make_opp()
    assert_blocked(lambda: make_decision(opp, tradeability(opp), plan(opp), gates()[:-1], confidence(opp), 140))


def test_structurally_valid_direct_decision_cannot_become_authoritative_by_hash() -> None:
    opp = make_opp()
    tb = tradeability(opp)
    ep = plan(opp)
    gs = tuple(gates())
    conf = confidence(opp)
    decision_id = _decision_fingerprint(opp.opportunity_id, tb, ep, gs, conf, 140)
    direct = TradeDecisionV4(decision_id, opp.opportunity_id, opp.root_id, "ACC", ep, tb, gs, conf, 140, opportunity_content_hash=__import__("src.fractal_flow.domain.phase4", fromlist=["_opportunity_content_hash"])._opportunity_content_hash(opp))
    assert not direct.authorized
    assert not direct.phase4_ready


def test_factory_minted_authority_is_invalidated_by_current_opportunity_change() -> None:
    opp = make_opp()
    decision = make_decision(opp, tradeability(opp), plan(opp), gates(), confidence(opp), 140, account_id="ACC")
    assert decision.authorized
    changed = make_opp(confidence=Decimal("0.8"))
    assert not decision.is_live_authorized(changed, 140)


def test_child_authority_binds_current_parent_content() -> None:
    parent = make_opp(root_id="parent", primary_pullback_id="pp")
    child = make_opp(root_id="child", primary_pullback_id="cp", parent_opportunity_id=parent.opportunity_id)
    d = make_decision(child, tradeability(child, parent_opportunity=parent), plan(child), gates(), confidence(child), 140, parent_opportunity=parent, account_id="ACC")
    changed_parent = make_opp(root_id="parent", primary_pullback_id="pp", confidence=Decimal("0.7"))
    assert not d.is_live_authorized(child, 140, changed_parent)

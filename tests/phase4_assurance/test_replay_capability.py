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
    TradeabilityEngine,
    make_decision,
)
from src.fractal_flow.domain.phase4_assurance import (
    Phase4ReplayLog,
    ReplayIntegrityError,
    assert_capability_is_least_privilege,
    capability_for,
    record_decision,
)


def opp() -> Opportunity:
    root, symbol, pb, family, direction = "root", "EURUSD", "pb", "FF-01", "LONG"
    oid = Opportunity.deterministic_id(root, symbol, pb, family, direction)
    return Opportunity(oid, root, None, symbol, direction, family, pb, 100, 200, OpportunityState.VALID, Decimal("20"), Decimal("5"), Decimal("0.9"))


def decision():
    o = opp()
    p = ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))
    tb = TradeabilityEngine().evaluate(o, Decimal("1"), Decimal("0.1"), Decimal("0.1"), Decimal("10"), True, Decimal("0.8"), p, 120)
    ep = EntryPlanV4("ep", o.opportunity_id, o.symbol, o.direction, Decimal("1.1"), Decimal("1"), Decimal(".01"), Decimal("1.3"), Decimal("1.5"), 120, Decimal(".01"))
    gates = tuple(GateEvidence(g, True, "ok", 130) for g in Phase4GateType)
    conf = ConfidenceEvidence(Decimal(".8"), "test", "1", 120)
    return make_decision(o, tb, ep, gates, conf, 140)


def test_replay_is_hash_chained_and_deterministic():
    d = decision()
    a, b = Phase4ReplayLog(), Phase4ReplayLog()
    record_decision(a, d)
    record_decision(b, d)
    assert a.fingerprint() == b.fingerprint()
    assert a.replay_decision_outcomes() == ((d.decision_id, True),)


def test_replay_rejects_hash_tampering_and_chain_tampering():
    d = decision()
    log = Phase4ReplayLog()
    record_decision(log, d)
    event = log.events[0]
    object.__setattr__(event, "event_hash", "tampered")
    with pytest.raises(ReplayIntegrityError):
        log.verify()


def test_capability_is_bound_and_least_privilege():
    d = decision()
    cap = capability_for(d)
    cap.require("PHASE4_HANDOFF", d.decision_id, d.created_at, opp())
    assert_capability_is_least_privilege(cap)
    with pytest.raises(Exception):
        cap.require("SUBMIT_ORDER", d.decision_id, d.created_at, opp())
    with pytest.raises(Exception):
        cap.require("PHASE4_HANDOFF", "other", d.created_at, opp())


def test_full_decision_fixture_replays_to_identical_authority_and_fingerprint():
    from src.fractal_flow.domain.phase4_assurance import DecisionReplayFixture

    original = decision()
    o = opp()
    profile = ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))
    tb = TradeabilityEngine().evaluate(o, Decimal("1"), Decimal("0.1"), Decimal("0.1"), Decimal("10"), True, Decimal("0.8"), profile, 120)
    ep = original.entry_plan
    gates = original.gates
    fixture = DecisionReplayFixture.from_inputs(o, tb, ep, gates, original.confidence, original.created_at)
    replayed = fixture.replay()
    assert replayed.authorized
    assert replayed.decision_id == original.decision_id
    assert fixture.to_payload()["created_at"] == original.created_at


def test_full_replay_rejects_semantic_tampering():
    from dataclasses import replace
    from src.fractal_flow.domain.phase4_assurance import DecisionReplayFixture

    original = decision()
    o = opp()
    profile = ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))
    tb = TradeabilityEngine().evaluate(o, Decimal("1"), Decimal("0.1"), Decimal("0.1"), Decimal("10"), True, Decimal("0.8"), profile, 120)
    fixture = DecisionReplayFixture.from_inputs(o, tb, original.entry_plan, original.gates, original.confidence, original.created_at)
    changed = dict(fixture.entry_plan)
    changed["target_price"] = "1.11"
    tampered = replace(fixture, entry_plan=changed)
    with pytest.raises(ValueError):
        tampered.replay()


def test_capability_is_revoked_when_authoritative_opportunity_is_invalidated():
    from dataclasses import replace
    d = decision()
    cap = capability_for(d)
    invalid = replace(opp(), state=__import__("src.fractal_flow.domain.phase4", fromlist=["OpportunityState"]).OpportunityState.INVALIDATED)
    with pytest.raises(ValueError):
        cap.require("PHASE4_HANDOFF", d.decision_id, d.created_at, invalid)


def test_account_context_cannot_expand_phase4_capability():
    d = decision()
    cap = capability_for(d)
    assert cap.scope == ("PHASE4_HANDOFF",)
    assert not {"SUBMIT_ORDER", "ALLOCATE_RISK", "SIZE_TRADE"}.intersection(cap.scope)

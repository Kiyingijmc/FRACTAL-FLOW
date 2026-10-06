from dataclasses import replace
from decimal import Decimal
from itertools import permutations

from src.fractal_flow.domain.phase4 import (
    ConfidenceEvidence,
    EntryPlanV4,
    ExecutionQualityProfile,
    GateEvidence,
    Opportunity,
    OpportunityState,
    Phase4GateType,
    TradeabilityEngine,
    TradeabilityStatus,
    make_decision,
)


def fixture():
    root, symbol, pb, family, direction = "root", "EURUSD", "pb", "FF-01", "LONG"
    oid = Opportunity.deterministic_id(root, symbol, pb, family, direction)
    o = Opportunity(oid, root, None, symbol, direction, family, pb, 100, 200, OpportunityState.VALID, Decimal("20"), Decimal("5"), Decimal("0.9"))
    profile = ExecutionQualityProfile(Decimal("3"), Decimal("0.5"), Decimal("2"), Decimal("0.5"))
    tb = TradeabilityEngine().evaluate(o, Decimal("1"), Decimal("0.1"), Decimal("0.1"), Decimal("10"), True, Decimal("0.8"), profile, 120)
    ep = EntryPlanV4("ep", o.opportunity_id, o.symbol, o.direction, Decimal("1.1"), Decimal("1"), Decimal(".01"), Decimal("1.3"), Decimal("1.5"), 120, Decimal(".01"))
    conf = ConfidenceEvidence(Decimal(".8"), "test", "1", 120)
    return o, tb, ep, conf


def gates(*, passed=True, observed=130):
    return tuple(GateEvidence(g, passed, "ok", observed) for g in Phase4GateType)


def reference(o, tb, ep, gs, conf, at):
    if not o.is_live(at):
        return False
    if tb.opportunity_id != o.opportunity_id or tb.status is not TradeabilityStatus.PASS:
        return False
    if tb.observed_timestamp > at:
        return False
    if ep.opportunity_id != o.opportunity_id or ep.symbol != o.symbol or ep.direction != o.direction:
        return False
    if ep.quote_timestamp < o.created_at or ep.quote_timestamp > at:
        return False
    if conf.observed_timestamp < o.created_at or conf.observed_timestamp > at or conf.value > o.confidence:
        return False
    if len(gs) != 3 or {g.gate for g in gs} != set(Phase4GateType) or len({g.gate for g in gs}) != 3:
        return False
    if any(g.observed_timestamp < o.created_at or g.observed_timestamp > at for g in gs):
        return False
    return all(g.passed for g in gs)


def test_stateful_sequence_model_matches_authority_kernel():
    o, tb, ep, conf = fixture()
    actions = [
        lambda x: replace(x, state=OpportunityState.VALID),
        lambda x: replace(x, state=OpportunityState.DEGRADED),
        lambda x: replace(x, state=OpportunityState.INVALIDATED),
        lambda x: replace(x, state=OpportunityState.TRIGGER_READY),
    ]
    for first, second in permutations(actions, 2):
        current = second(first(o))
        expected = reference(current, tb, ep, gates(), conf, 140)
        try:
            actual = make_decision(current, tb, ep, gates(), conf, 140).authorized
        except ValueError:
            actual = False
        assert actual == expected


def test_stateful_mutation_sequences_never_restore_authority_from_a_failed_state():
    o, tb, ep, conf = fixture()
    failed_states = [OpportunityState.DEGRADED, OpportunityState.INVALIDATED, OpportunityState.STALE, OpportunityState.EXPIRED]
    for state in failed_states:
        failed = replace(o, state=state)
        for gate_order in permutations(gates()):
            try:
                result = make_decision(failed, tb, ep, gate_order, conf, 140).authorized
            except ValueError:
                result = False
            assert result is False


def test_differential_permutation_invariance_holds_for_all_gate_orders():
    o, tb, ep, conf = fixture()
    ids = {
        make_decision(o, tb, ep, order, conf, 140).decision_id
        for order in permutations(gates())
    }
    assert len(ids) == 1


def test_non_interference_account_metadata_cannot_change_phase4_authority():
    from src.fractal_flow.domain.phase4 import AccountProfile

    o, tb, ep, conf = fixture()
    baseline = make_decision(o, tb, ep, gates(), conf, 140)
    account_a = AccountProfile("ACC_A", "BROKER_A", "USD")
    account_b = AccountProfile("ACC_B", "BROKER_B", "EUR")
    assert account_a.account_id != account_b.account_id
    assert baseline.authorized
    assert baseline.account_id is None
    replay_a = make_decision(o, tb, ep, gates(), conf, 140)
    replay_b = make_decision(o, tb, ep, list(reversed(gates())), conf, 140)
    assert replay_a.decision_id == replay_b.decision_id == baseline.decision_id


def test_monotonic_authority_failed_gate_cannot_be_upgraded_by_adding_positive_duplicate():
    o, tb, ep, conf = fixture()
    failed = list(gates())
    failed[0] = GateEvidence(Phase4GateType.OPPORTUNITY, False, "blocked", 130)
    decision = make_decision(o, tb, ep, failed, conf, 140)
    assert not decision.authorized
    with __import__("pytest").raises(ValueError):
        make_decision(o, tb, ep, failed + [GateEvidence(Phase4GateType.OPPORTUNITY, True, "upgrade", 135)], conf, 140)

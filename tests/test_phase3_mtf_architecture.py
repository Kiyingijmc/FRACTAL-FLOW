from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.phase2 import Phase2Evaluation
from src.fractal_flow.domain.phase3 import (
    Phase3InvariantError,
    Phase3Orchestrator,
    Phase3Pipeline,
    Phase3Role,
    TimeframeMapping,
    OpportunityState,
)


def _evaluation(tf: str, ts: int, seq: int = 1, direction: str = "LONG", structure: str = "BULLISH",
                role: str = "PULLBACK", flow: str = "LONG_DOMINANT", regime: str = "TREND_UP",
                pde_state: str = "PDE_PULLBACK_ACTIVE", resumption: str = "RESUMPTION_CONFIRMED",
                bos_type: str = "NONE", episode_id: str | None = None, location_state: str = "FAVORABLE") -> Phase2Evaluation:
    tf_obj = Timeframe.validate(tf)
    bar = Bar.create("EURUSD", tf, max(0, ts - tf_obj.seconds), ts, "1.1000", "1.1020", "1.0980", "1.1010", sequence=seq)
    pde = SimpleNamespace(
        direction=direction, episode_id=episode_id or f"ep-{ts}", parent_id="", version=1,
        state=SimpleNamespace(value=pde_state), resumption_state=SimpleNamespace(value=resumption),
        recovery_ratio=Decimal("0.8"), impulse_amplitude=Decimal("0.01"), pullback_depth=Decimal("0.2"),
        resumption_displacement=Decimal("0.004"), causal_watermark=ts,
    )
    struct = SimpleNamespace(
        structural_ownership=structure, state_version=1, bos_type=bos_type,
        protected_high=Decimal("1.1100"), protected_low=Decimal("1.0900"),
    )
    flow_obj = SimpleNamespace(flow_state=SimpleNamespace(value=flow), state_version=1)
    regime_obj = SimpleNamespace(state=SimpleNamespace(value=regime), version=1, efficiency=Decimal("0.7"), persistence=Decimal("0.6"))
    role_obj = SimpleNamespace(state=SimpleNamespace(value=role), version=1)
    location = SimpleNamespace(state=SimpleNamespace(value=location_state), version=1)
    volatility = SimpleNamespace(version=1, atr_14=Decimal("0.0020"), state=SimpleNamespace(value="VALID"))
    context = SimpleNamespace(watermark=SimpleNamespace(timestamp=ts), is_usable=lambda now: True, configuration_id=f"cfg-{tf}")
    evidence = SimpleNamespace(long_score=Decimal("0.8"), short_score=Decimal("0.1"))
    return Phase2Evaluation(bar, volatility, struct, flow_obj, regime_obj, pde, location, role_obj, context, evidence)


def _ingest_required(orch: Phase3Orchestrator, ts: int = 900, **kwargs) -> None:
    for tf in ("4H", "1H", "30M", "15M", "5M", "1M"):
        orch.ingest(_evaluation(tf, ts, **kwargs))


def test_timeframe_mapping_respects_execution_floor():
    mapping = TimeframeMapping.canonical()
    first = mapping.migrate_primary_down()
    second = first.migrate_primary_down()
    assert (mapping.primary, first.primary, second.primary) == (Timeframe.M15, Timeframe.M5, Timeframe.M5)
    assert first.secondary == first.confirmation == Timeframe.M1
    assert mapping.primary > mapping.execution
    assert first.primary > first.execution
    assert second == first

def test_orchestrator_rejects_same_timeframe_reordering():
    orch = Phase3Orchestrator("EURUSD")
    orch.ingest(_evaluation("15M", 20000))
    with pytest.raises(Phase3InvariantError):
        orch.ingest(_evaluation("15M", 20000))


def test_hierarchy_requires_full_context_to_execution_chain_and_excludes_future_data():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    orch.ingest(_evaluation("15M", 21800))
    hierarchy = orch.hierarchy_at(20000)
    assert hierarchy.coherent is True
    assert all(hierarchy.node(role) is not None for role in Phase3Orchestrator.REQUIRED_ROLES)
    assert hierarchy.node(Phase3Role.PRIMARY).evaluation_timestamp == 20000
    assert hierarchy.node(Phase3Role.CONFIRMATION).evaluation_timestamp == 20000


def test_missing_confirmation_fails_closed():
    orch = Phase3Orchestrator("EURUSD")
    for tf in ("4H", "1H", "30M", "15M", "5M"):
        orch.ingest(_evaluation(tf, 20000))
    hierarchy = orch.hierarchy_at(20000)
    assert hierarchy.coherent is False
    assert "MISSING_REQUIRED_CONFIRMATION" in hierarchy.reason_codes
    assert orch.construct_opportunity(20000) is None


def test_direction_and_flow_contradictions_are_fail_closed():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    orch.ingest(_evaluation("5M", 21800, direction="SHORT", structure="BEARISH", flow="SHORT_DOMINANT"))
    hierarchy = orch.hierarchy_at(21800)
    assert hierarchy.contradiction is True
    assert "PRIMARY_SECONDARY_DIRECTION_CONFLICT" in hierarchy.reason_codes


def test_mtf_flow_regime_role_location_and_pde_evidence_are_fused():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    hierarchy = orch.hierarchy_at(20000)
    assert hierarchy.flow_alignment == "ALIGNED"
    assert hierarchy.regime_alignment == "ALIGNED"
    assert hierarchy.role_alignment == "ALIGNED"
    assert hierarchy.location_alignment == "FAVORABLE"
    assert hierarchy.evidence is not None
    assert hierarchy.evidence.family_count >= 4
    assert hierarchy.bindings[0].parent_episode_id == "ep-20000"


def test_opportunity_requires_confirmation_and_is_entry_closed():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    candidate = orch.construct_opportunity(20000)
    assert candidate is not None
    assert candidate.opportunity.setup_type == "FF-01 FLOW_CONTINUATION"
    assert candidate.opportunity.state == OpportunityState.VALID.value
    assert candidate.opportunity.entry_allowed is False
    assert candidate.opportunity.tradeability == "UNASSESSED"
    assert candidate.expires_at == 20000 + Timeframe.M15.seconds * 3
    assert candidate.hierarchy.corridor_low == Decimal("1.0900")
    assert candidate.hierarchy.corridor_high == Decimal("1.1100")



def test_setup_contracts_cover_ff02_ff03_ff04():
    for kwargs, expected in (
        (dict(role="COUNTERFLOW"), "FF-02 COUNTERFLOW"),
        (dict(role="RANGE_ROTATION", regime="RANGE", location_state="EXTREME"), "FF-03 RANGE_ROTATION"),
        (dict(regime="TRANSITION", pde_state="PDE_RESUMPTION_IN_PROGRESS"), "FF-04 TRANSITION_BREAK"),
    ):
        orch = Phase3Orchestrator("EURUSD")
        _ingest_required(orch, 20000, **kwargs)
        candidate = orch.construct_opportunity(20000)
        assert candidate is not None
        assert candidate.opportunity.setup_type == expected

def test_opportunity_snapshot_restores_identity_version_and_lineage_exactly():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    first = orch.construct_opportunity(20000)
    assert first is not None
    payload = orch.snapshot_state()
    restored = Phase3Orchestrator.from_snapshot_state(payload)
    assert restored.state_hash() == orch.state_hash()
    assert restored._opportunities[first.opportunity.opportunity_id].opportunity.root_id == first.opportunity.root_id
    assert restored._opportunities[first.opportunity.opportunity_id].expires_at == first.expires_at


def test_migration_lineage_survives_restart_and_stops_at_m5_primary():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    first = orch.construct_opportunity(20000)
    assert first is not None
    primary_tf = orch.mapping.primary.value
    ts = 21800
    orch.ingest(_evaluation(primary_tf, ts, bos_type="BOS_LONG"))
    for tf in ("5M", "1M"):
        if tf != primary_tf:
            orch.ingest(_evaluation(tf, ts))
    assert orch.migrate_on_confirmed_transition(ts) is True
    candidate = orch.construct_opportunity(ts)
    assert candidate is not None
    assert candidate.opportunity.parent_opportunity_id == first.opportunity.opportunity_id
    assert orch.mapping.primary == Timeframe.M5
    assert orch.mapping.primary > orch.mapping.execution
    assert orch.migrate_on_confirmed_transition(ts + 1800) is False


def test_opportunity_lifecycle_ttl_and_false_resumption():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    candidate = orch.construct_opportunity(20000)
    assert candidate is not None
    updated = orch.advance_lifecycle(20001)[0]
    assert updated.opportunity.state in {OpportunityState.VALID.value, OpportunityState.TRIGGER_READY.value}
    # A failed resumption is informationally degrading, never execution authority.
    orch.ingest(_evaluation("1M", 20060, pde_state="PDE_RESUMPTION_FAILED", resumption="RESUMPTION_FAILED"))
    degraded = orch.advance_lifecycle(20060)[0]
    assert degraded.opportunity.state in {OpportunityState.DEGRADED.value, OpportunityState.INVALIDATED.value}
    # Terminal invalidation is sticky; TTL must not resurrect or rewrite it.
    terminal = orch.advance_lifecycle(candidate.expires_at)[0]
    assert terminal.opportunity.state == OpportunityState.INVALIDATED.value
    assert terminal.opportunity.entry_allowed is False

    fresh = Phase3Orchestrator("EURUSD")
    _ingest_required(fresh, 20000)
    expiring = fresh.construct_opportunity(20000)
    assert expiring is not None
    expired = fresh.advance_lifecycle(expiring.expires_at)[0]
    assert expired.opportunity.state == OpportunityState.EXPIRED.value
    assert expired.opportunity.entry_allowed is False


def test_smart_overtrading_reuses_identity_and_versions_observation():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    first = orch.construct_opportunity(20000)
    second = orch.construct_opportunity(20000)
    assert first is not None and second is not None
    assert second.opportunity.opportunity_id == first.opportunity.opportunity_id
    assert second.opportunity_version == first.opportunity_version + 1


def test_flipping_requires_confirmed_structural_transition():
    orch = Phase3Orchestrator("EURUSD")
    _ingest_required(orch, 20000)
    first = orch.construct_opportunity(20000)
    assert first is not None
    # Opposite direction on the same episode without a structural transition is rejected.
    for tf in ("4H", "1H", "30M", "15M", "5M", "1M"):
        orch.ingest(_evaluation(tf, 21800, direction="SHORT", structure="BEARISH", flow="SHORT_DOMINANT", role="PULLBACK", episode_id="ep-20000"))
    assert orch.construct_opportunity(21800) is None


def test_phase3_composite_atomicity_on_orchestrator_failure(monkeypatch):
    pipeline = Phase3Pipeline("EURUSD")
    before = pipeline.state_hash()
    original = Phase3Orchestrator.ingest

    def fail(self, evaluation):
        raise RuntimeError("injected phase3 failure")

    monkeypatch.setattr(Phase3Orchestrator, "ingest", fail)
    with pytest.raises(RuntimeError):
        pipeline.process_bar(_evaluation("1M", 60).bar)
    monkeypatch.setattr(Phase3Orchestrator, "ingest", original)
    assert pipeline.state_hash() == before


def test_pipeline_snapshot_roundtrip_is_deterministic():
    pipeline = Phase3Pipeline("EURUSD")
    payload = pipeline.snapshot_state()
    restored = Phase3Pipeline.from_snapshot_state(payload)
    assert restored.state_hash() == pipeline.state_hash()


def test_phase3_reconstructs_exactly_from_phase2_durable_journals(tmp_path):
    from src.fractal_flow.domain.phase2 import Phase2Pipeline
    from src.fractal_flow.persistence.phase2 import Phase2DurableStore
    from decimal import Decimal

    def durable_bar(tf: str):
        tf_obj = Timeframe.validate(tf)
        return Bar.create(
            "EURUSD", tf, 0, tf_obj.seconds,
            Decimal("1.0995"), Decimal("1.1010"), Decimal("1.0990"), Decimal("1.1000"),
            sequence=1,
        )

    stores = {}
    live = Phase3Orchestrator("EURUSD", history_capacity=3)
    evaluations = []
    for tf in ("4H", "1H", "30M", "15M", "5M", "1M"):
        store = Phase2DurableStore(
            str(tmp_path / tf),
            Phase2Pipeline("EURUSD", tf, history_capacity=3),
        )
        evaluation = store.process_bar(durable_bar(tf))
        stores[Timeframe.validate(tf)] = store
        evaluations.append(evaluation)
    for evaluation in sorted(evaluations, key=lambda ev: Timeframe.validate(ev.bar.timeframe).level):
        live.ingest(evaluation)
    live.migrate_on_confirmed_transition(Timeframe.M1.seconds)
    live.construct_opportunity(Timeframe.M1.seconds)
    live.advance_lifecycle(Timeframe.M1.seconds)

    rebuilt = Phase3Orchestrator.reconstruct_from_phase2_durable(
        stores, TimeframeMapping.canonical(), history_capacity=3
    )
    assert rebuilt.state_hash() == live.state_hash()
    assert rebuilt.snapshot_state() == live.snapshot_state()


def test_phase3_durable_replay_rejects_identity_mismatch(tmp_path):
    from src.fractal_flow.domain.phase2 import Phase2Pipeline
    from src.fractal_flow.persistence.phase2 import Phase2DurableStore
    from decimal import Decimal

    store = Phase2DurableStore(
        str(tmp_path / "1M"), Phase2Pipeline("EURUSD", "1M", history_capacity=3)
    )
    store.process_bar(Bar.create(
        "EURUSD", "1M", 0, 60,
        Decimal("1.0995"), Decimal("1.1010"), Decimal("1.0990"), Decimal("1.1000"), sequence=1,
    ))
    with pytest.raises(Phase3InvariantError):
        Phase3Orchestrator.reconstruct_from_phase2_durable(
            {Timeframe.H1: store}, TimeframeMapping.canonical(), history_capacity=3
        )


def test_phase3_migration_pipeline_set_is_atomic_on_creation_failure(monkeypatch):
    pipeline = Phase3Pipeline("EURUSD")
    before = pipeline.state_hash()
    # Without a confirmed structural transition migration is a semantic no-op.
    assert pipeline.migrate_on_confirmed_transition(100) is False
    assert pipeline.state_hash() == before


def test_phase3_migration_pipeline_creation_failure_rolls_back_after_valid_transition(monkeypatch):
    pipeline = Phase3Pipeline("EURUSD")
    _ingest_required(pipeline.orchestrator, 20000)
    first = pipeline.orchestrator.construct_opportunity(20000)
    assert first is not None
    for tf in ("4H", "1H", "30M", "15M", "5M", "1M"):
        pipeline.orchestrator.ingest(_evaluation(
            tf, 21800, bos_type="BOS_LONG" if tf == "15M" else "NONE"
        ))
    pipeline.pipelines.pop(Timeframe.M5)
    before = pipeline.state_hash()

    from src.fractal_flow.domain import phase2 as phase2_module
    original = phase2_module.Phase2Pipeline

    class FailingPipeline:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("injected migration pipeline creation failure")

    monkeypatch.setattr(phase2_module, "Phase2Pipeline", FailingPipeline)
    with pytest.raises(RuntimeError, match="injected migration pipeline creation failure"):
        pipeline.migrate_on_confirmed_transition(21800)
    monkeypatch.setattr(phase2_module, "Phase2Pipeline", original)
    assert pipeline.state_hash() == before
    assert pipeline.mapping.primary == Timeframe.M15


def test_phase3_bounded_evaluation_eviction_preserves_opportunity_lineage():
    orch = Phase3Orchestrator("EURUSD", history_capacity=1)
    _ingest_required(orch, 20000)
    first = orch.construct_opportunity(20000)
    assert first is not None
    # A later evaluation evicts bounded source history, but opportunity lineage is
    # independently retained and remains serializable.
    orch.ingest(_evaluation("1M", 20060))
    assert first.opportunity.opportunity_id in orch._opportunities
    payload = orch.snapshot_state()
    assert first.opportunity.opportunity_id in payload["opportunities"]
    restored = Phase3Orchestrator.from_snapshot_state(payload)
    assert restored._opportunities[first.opportunity.opportunity_id].opportunity.root_id == first.opportunity.root_id


def test_phase3_evidence_policy_is_versioned_and_replay_stable():
    from src.fractal_flow.domain.phase3 import EvidencePolicy

    policy = EvidencePolicy(version=7, primary=Decimal("1.25"), confirmation=Decimal("0.65"))
    orch = Phase3Orchestrator("EURUSD", evidence_policy=policy)
    _ingest_required(orch, 20000)
    hierarchy = orch.hierarchy_at(20000)
    assert hierarchy.evidence is not None
    assert hierarchy.evidence.policy_version == 7
    payload = orch.snapshot_state()
    restored = Phase3Orchestrator.from_snapshot_state(payload)
    assert restored.evidence_policy.to_dict() == policy.to_dict()
    assert restored.state_hash() == orch.state_hash()


def test_phase3_pipeline_confirmed_migration_commits_mapping_and_pipeline_set():
    pipeline = Phase3Pipeline("EURUSD")
    _ingest_required(pipeline.orchestrator, 20000)
    assert pipeline.orchestrator.construct_opportunity(20000) is not None
    for tf in ("4H", "1H", "30M", "15M", "5M", "1M"):
        pipeline.orchestrator.ingest(_evaluation(tf, 21800, bos_type="BOS_LONG" if tf == "15M" else "NONE"))
    assert pipeline.migrate_on_confirmed_transition(21800) is True
    assert pipeline.mapping.primary == Timeframe.M5
    assert Timeframe.M5 in pipeline.pipelines
    assert pipeline.orchestrator.mapping == pipeline.mapping


def test_phase3_durable_replay_reconstructs_opportunity_lineage_deterministically():
    class ReplayStore:
        def __init__(self, evaluations):
            self._evaluations = evaluations

        def replay_evaluations(self):
            return list(self._evaluations)

    mapping = TimeframeMapping.canonical()
    by_tf = {Timeframe.validate(tf): [] for tf in ("4H", "1H", "30M", "15M", "5M", "1M")}
    for tf in by_tf:
        by_tf[tf].append(_evaluation(tf.value, 20000, episode_id="root-episode"))
        by_tf[tf].append(_evaluation(
            tf.value, 21800,
            bos_type="BOS_LONG" if tf is Timeframe.M15 else "NONE",
            episode_id="child-episode",
        ))
    stores = {tf: ReplayStore(evals) for tf, evals in by_tf.items()}

    live = Phase3Orchestrator("EURUSD", mapping=mapping)
    ordered = sorted(
        [evaluation for evaluations in by_tf.values() for evaluation in evaluations],
        key=lambda evaluation: (evaluation.bar.close_timestamp, evaluation.bar.sequence,
                                Timeframe.validate(evaluation.bar.timeframe).level),
    )
    for watermark in (20000, 21800):
        for evaluation in [e for e in ordered if e.bar.close_timestamp == watermark]:
            live.ingest(evaluation)
        live.migrate_on_confirmed_transition(watermark)
        live.construct_opportunity(watermark)
        live.advance_lifecycle(watermark)

    rebuilt = Phase3Orchestrator.reconstruct_from_phase2_durable(
        stores, mapping, expected_state_hash=live.state_hash()
    )
    assert rebuilt.state_hash() == live.state_hash()
    assert len(rebuilt._opportunities) == len(live._opportunities)
    assert {oid: c.opportunity.parent_opportunity_id for oid, c in rebuilt._opportunities.items()} == {
        oid: c.opportunity.parent_opportunity_id for oid, c in live._opportunities.items()
    }


def test_phase3_mapping_and_policy_validation_fail_closed():
    with pytest.raises(Phase3InvariantError):
        TimeframeMapping(version=0)
    with pytest.raises(Phase3InvariantError):
        TimeframeMapping(context=Timeframe.H1)
    with pytest.raises(Phase3InvariantError):
        TimeframeMapping(execution=Timeframe.M5)
    from src.fractal_flow.domain.phase3 import EvidencePolicy
    with pytest.raises(Phase3InvariantError):
        EvidencePolicy(version=0)
    with pytest.raises(Phase3InvariantError):
        EvidencePolicy(primary=Decimal("-1"))


def test_phase3_constructor_and_ingest_contracts_fail_closed():
    with pytest.raises(ValueError):
        Phase3Orchestrator("")
    with pytest.raises(ValueError):
        Phase3Orchestrator("EURUSD", history_capacity=0)
    from dataclasses import replace
    orch = Phase3Orchestrator("EURUSD")
    with pytest.raises(Phase3InvariantError, match="symbol mismatch"):
        evaluation = _evaluation("1M", 100)
        bad_bar = Bar.create("GBPUSD", "1M", 40, 100, "1.1", "1.2", "1.0", "1.1", sequence=1)
        orch.ingest(replace(evaluation, bar=bad_bar))


def test_phase3_pde_descriptors_cover_mature_and_candidate_risk_paths():
    from src.fractal_flow.domain.phase3 import _pde_maturity, _false_resumption_risk
    assert _pde_maturity(SimpleNamespace(state=SimpleNamespace(value="PDE_FOLLOW_THROUGH"))) == "MATURE"
    assert _pde_maturity(SimpleNamespace(state=SimpleNamespace(value="PDE_RESUMPTION_IN_PROGRESS"))) == "DEVELOPING"
    assert _false_resumption_risk(SimpleNamespace(
        state=SimpleNamespace(value="PDE_PULLBACK_ACTIVE"),
        resumption_state=SimpleNamespace(value="RECOVERY_CANDIDATE"),
    )) == "0.5"


def test_phase3_snapshot_rejects_invalid_policy_and_pipeline_payloads():
    orch = Phase3Orchestrator("EURUSD")
    payload = orch.snapshot_state()
    payload["evidence_policy"]["version"] = 0
    with pytest.raises(Phase3InvariantError):
        Phase3Orchestrator.from_snapshot_state(payload)
    pipeline = Phase3Pipeline("EURUSD")
    empty = pipeline.snapshot_state()
    empty["pipelines"] = {}
    with pytest.raises(Phase3InvariantError):
        Phase3Pipeline.from_snapshot_state(empty)


def test_phase3_replay_empty_and_expected_hash_fail_closed():
    with pytest.raises(Phase3InvariantError):
        Phase3Orchestrator.reconstruct_from_phase2_durable({}, TimeframeMapping.canonical())
    class EmptyStore:
        def replay_evaluations(self):
            return []
    with pytest.raises(Phase3InvariantError):
        Phase3Orchestrator.reconstruct_from_phase2_durable(
            {Timeframe.M1: EmptyStore()}, TimeframeMapping.canonical()
        )
    class OneStore:
        def replay_evaluations(self):
            return [_evaluation("1M", 60)]
    with pytest.raises(Phase3InvariantError, match="expected Phase3 state hash"):
        Phase3Orchestrator.reconstruct_from_phase2_durable(
            {Timeframe.M1: OneStore()}, TimeframeMapping.canonical(), expected_state_hash="forged"
        )


def test_phase3_pipeline_process_and_restore_contracts():
    pipeline = Phase3Pipeline("EURUSD")
    pipeline.pipelines.pop(Timeframe.M1)
    with pytest.raises(Phase3InvariantError, match="not part of the active"):
        pipeline.process_bar(_evaluation("1M", 120).bar)
    payload = pipeline.snapshot_state()
    payload["evidence_policy"]["primary"] = "9.0"
    with pytest.raises(Phase3InvariantError, match="evidence policy provenance"):
        Phase3Pipeline.from_snapshot_state(payload)


def test_phase3_pipeline_successful_process_and_wrappers_commit():
    pipeline = Phase3Pipeline("EURUSD")
    evaluation = _evaluation("1M", 120)
    before = pipeline.state_hash()
    returned = pipeline.process_bar(evaluation.bar)
    assert returned.bar == evaluation.bar
    assert pipeline.state_hash() != before
    assert pipeline.hierarchy_at(120).node(Phase3Role.CONFIRMATION) is not None
    assert pipeline.construct_opportunity(120) is None
    assert pipeline.advance_lifecycle(120) == ()

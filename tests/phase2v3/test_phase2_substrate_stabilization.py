from decimal import Decimal
import random
import pytest

from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.pde import PDEState, PDEResumptionState, PDEEngine
from src.fractal_flow.persistence.phase2 import Phase2DurableStore, Phase2RecoveryError, Phase2StoreState


def bar(ts: int, seq: int, close: Decimal) -> Bar:
    return Bar.create(
        "EURUSD", "1M", ts, ts + 60,
        close - Decimal("0.0004"), close + Decimal("0.0006"),
        close - Decimal("0.0007"), close,
        sequence=seq, data_version=1, is_closed=True,
    )


def pipeline() -> Phase2Pipeline:
    return Phase2Pipeline("EURUSD", "1M", InstrumentSpec("EURUSD", Decimal("0.00001"), 5), history_capacity=16)


def test_phase2_bar_failure_rolls_back_every_mutable_engine(monkeypatch):
    p = pipeline()
    for i in range(1, 8):
        p.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0001")))
    before = p.snapshot_state()
    original = p.role.evaluate

    def fail(*args, **kwargs):
        raise RuntimeError("injected role failure")

    monkeypatch.setattr(p.role, "evaluate", fail)
    with pytest.raises(RuntimeError, match="injected role failure"):
        p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))
    monkeypatch.setattr(p.role, "evaluate", original)
    p.role.__dict__.pop("evaluate", None)
    assert p.snapshot_state() == before

    result = p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))
    assert result.context.watermark.sequence == 8


def test_phase2_random_market_sequences_do_not_hit_illegal_state_transitions():
    rng = random.Random(423234)
    for _ in range(10):
        p = pipeline()
        price = Decimal("1.1000")
        for seq in range(1, 101):
            step = Decimal(rng.choice(["-0.0008", "-0.0004", "0", "0.0004", "0.0008"]))
            price += step
            if price <= Decimal("1.0000"):
                price = Decimal("1.0000")
            p.process_bar(bar(seq * 60, seq, price))
        assert p._last_watermark == (100 * 60 + 60, 100)


def test_pde_origin_break_invalidates_instead_of_crashing():
    pde = PDEEngine("EURUSD")
    pde._last_close = Decimal("1.1000")
    first = pde.process_bar(bar(60, 1, Decimal("1.1020")), Decimal("0.001"))
    assert first.state == PDEState.PDE_IMPULSE
    out = pde.process_bar(bar(120, 2, Decimal("1.0990")), Decimal("0.001"))
    assert out.state == PDEState.PDE_INVALIDATED
    assert "IMPULSE_ORIGIN_BROKEN" in out.reason_codes


def test_pde_resumption_requires_actual_recovery_movement():
    pde = PDEEngine("EURUSD")
    pde.state = PDEState.PDE_WEAKENING
    pde.direction = "LONG"
    pde._anchor = Decimal("1.1000")
    pde._extreme = Decimal("1.1050")
    pde._pullback_extreme = Decimal("1.1020")
    pde._last_depth = Decimal("0.60")
    pde._bars = 2
    pde._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
    flat = pde.process_bar(bar(60, 1, Decimal("1.1020")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    assert flat.state != PDEState.PDE_RESUMPTION_IN_PROGRESS
    recovered = pde.process_bar(bar(120, 2, Decimal("1.1045")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    assert recovered.recovery_ratio >= Decimal("0.75")
    assert recovered.state == PDEState.PDE_RESUMPTION_IN_PROGRESS


def test_durable_store_faults_after_journal_then_pipeline_failure_and_recovers(monkeypatch, tmp_path):
    p = pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    original = p.process_bar

    def fail(_bar):
        raise RuntimeError("injected post-journal failure")

    monkeypatch.setattr(p, "process_bar", fail)
    with pytest.raises(RuntimeError):
        store.process_bar(bar(60, 1, Decimal("1.1000")))
    assert store.lifecycle_state == Phase2StoreState.FAULTED
    assert len(store.journal.get_events_for_aggregate("Phase2Pipeline", store.pipeline_id)) == 1
    with pytest.raises(Phase2RecoveryError, match="writes are prohibited"):
        store.process_bar(bar(120, 2, Decimal("1.1002")))

    monkeypatch.setattr(p, "process_bar", original)
    recovered = store.recover()
    assert store.lifecycle_state == Phase2StoreState.ACTIVE
    assert store.pipeline is recovered
    result = store.process_bar(bar(120, 2, Decimal("1.1002")))
    assert result.context.watermark.sequence == 2


def test_recover_installs_recovered_aggregate_for_continuation(tmp_path):
    p = pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    for i in range(1, 5):
        store.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0002")))
    recovered = store.recover()
    assert store.pipeline is recovered
    result = store.process_bar(bar(5 * 60, 5, Decimal("1.1010")))
    assert result.context.watermark.sequence == 5
    assert store.pipeline._last_watermark == (360, 5)


def test_informational_engine_registry_forbids_order_submission():
    import yaml

    with open("spec/engines.yaml") as f:
        engines = yaml.safe_load(f)["engines"]
    informational = ["DataQuality", "Volatility", "Structure", "PDE", "Flow", "Regime", "Role", "Location"]
    for name in informational:
        entry = engines[name]
        assert "SUBMIT_ORDER" not in entry.get("allowed_capabilities", [])
        assert "SUBMIT_ORDER" in entry.get("forbidden_capabilities", [])


def test_phase2_stage_then_commit_isolates_nested_mutation(monkeypatch):
    p = pipeline()
    for i in range(1, 8):
        p.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0001")))
    before_hash = p.state_hash()
    before = p.snapshot_state()

    original = p.structure.process_bar

    def fail_after_nested_mutation(engine, *args, **kwargs):
        assert engine._historical_projections
        first_key = next(iter(engine._historical_projections))
        engine._historical_projections[first_key]["fault_marker"] = "staged-only"
        raise RuntimeError("injected nested structure failure")

    monkeypatch.setattr(type(p.structure), "process_bar", fail_after_nested_mutation)
    with pytest.raises(RuntimeError, match="injected nested structure failure"):
        p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))

    assert p.state_hash() == before_hash
    assert p.snapshot_state() == before
    assert all(
        "fault_marker" not in projection
        for projection in p.structure._historical_projections.values()
    )
    monkeypatch.setattr(type(p.structure), "process_bar", original)


def test_phase2_state_hash_changes_only_after_successful_commit():
    p = pipeline()
    before = p.state_hash()
    p.process_bar(bar(60, 1, Decimal("1.1000")))
    after = p.state_hash()
    assert before != after


def test_phase2_failed_stage_preserves_engine_object_identity():
    p = pipeline()
    for i in range(1, 4):
        p.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0001")))
    engines = {name: getattr(p, name) for name in p._ENGINE_FIELDS}

    def fail(*args, **kwargs):
        raise RuntimeError("injected identity failure")

    original = p.role.evaluate
    p.role.evaluate = fail
    with pytest.raises(RuntimeError, match="injected identity failure"):
        p.process_bar(bar(4 * 60, 4, Decimal("1.1004")))
    p.role.evaluate = original

    for name, engine in engines.items():
        assert getattr(p, name) is engine


@pytest.mark.parametrize(
    "stage",
    [
        "data_quality", "volatility", "structure", "flow", "regime",
        "pde", "location", "role", "evidence", "historical_commit",
    ],
)
def test_phase2_fault_matrix_preserves_committed_state_at_every_stage(stage):
    p = pipeline()
    for i in range(1, 8):
        p.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0001")))

    before = p.snapshot_state()
    before_hash = p.state_hash()
    before_watermark = p._last_watermark
    before_ids = {name: id(getattr(p, name)) for name in p._ENGINE_FIELDS}

    with p.inject_fault_after(stage):
        with pytest.raises(RuntimeError, match=rf"after stage: {stage}"):
            p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))

    assert p.snapshot_state() == before
    assert p.state_hash() == before_hash
    assert p._last_watermark == before_watermark
    assert {name: id(getattr(p, name)) for name in p._ENGINE_FIELDS} == before_ids

    # The failed transaction must not poison continuation.
    result = p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))
    assert result.context.watermark.sequence == 8


def test_phase2_fault_injection_is_not_persisted_in_snapshot():
    p = pipeline()
    with p.inject_fault_after("flow"):
        snapshot = p.snapshot_state()
    assert "fault_injection_stage" not in snapshot


def test_phase2_state_hash_is_replay_deterministic():
    p1 = pipeline()
    p2 = pipeline()
    prices = [Decimal("1.1000"), Decimal("1.1004"), Decimal("1.0998"), Decimal("1.1006")]
    for seq, price in enumerate(prices, 1):
        b = bar(seq * 60, seq, price)
        p1.process_bar(b)
        p2.process_bar(b)
    assert p1.state_hash() == p2.state_hash()
    assert p1.snapshot_state() == p2.snapshot_state()


def test_pde_pullback_geometry_is_not_retroactively_rescaled_by_volatility():
    def seeded() -> PDEEngine:
        engine = PDEEngine("EURUSD")
        engine.state = PDEState.PDE_IMPULSE
        engine.direction = "LONG"
        engine._anchor = Decimal("1.1000")
        engine._extreme = Decimal("1.1100")
        engine._impulse_amplitude = Decimal("0.0100")
        engine._bars = 1
        engine._last_close = Decimal("1.1100")
        return engine

    low_vol = seeded().process_bar(bar(60, 1, Decimal("1.1060")), Decimal("0.001"))
    high_vol = seeded().process_bar(bar(60, 1, Decimal("1.1060")), Decimal("0.005"))

    assert low_vol.pullback_depth == high_vol.pullback_depth == Decimal("0.4")
    assert low_vol.impulse_amplitude == high_vol.impulse_amplitude == Decimal("0.0100")


def test_pde_recovery_geometry_is_not_retroactively_rescaled_by_volatility():
    def seeded() -> PDEEngine:
        engine = PDEEngine("EURUSD")
        engine.state = PDEState.PDE_WEAKENING
        engine.direction = "LONG"
        engine._anchor = Decimal("1.1000")
        engine._extreme = Decimal("1.1100")
        engine._impulse_amplitude = Decimal("0.0100")
        engine._pullback_extreme = Decimal("1.1040")
        engine._last_depth = Decimal("0.6")
        engine._bars = 2
        engine._last_close = Decimal("1.1040")
        engine._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
        return engine

    low_vol = seeded().process_bar(bar(60, 1, Decimal("1.1085")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    high_vol = seeded().process_bar(bar(60, 1, Decimal("1.1085")), Decimal("0.005"), Decimal("0"), "LONG", "TREND_UP")

    assert low_vol.recovery_ratio == high_vol.recovery_ratio
    assert low_vol.recovery_ratio == Decimal("0.75")


def test_pde_pullback_candidate_rejection_returns_to_impulse():
    pde = PDEEngine("EURUSD")
    pde._last_close = Decimal("1.1000")
    pde.process_bar(bar(60, 1, Decimal("1.1050")), Decimal("0.001"))
    candidate = pde.process_bar(bar(120, 2, Decimal("1.1044")), Decimal("0.001"))
    assert candidate.state == PDEState.PDE_PULLBACK_CANDIDATE
    rejected = pde.process_bar(bar(180, 3, Decimal("1.1049")), Decimal("0.001"))
    assert rejected.state == PDEState.PDE_IMPULSE
    assert rejected.resumption_state == PDEResumptionState.RESUMPTION_NONE
    assert "PULLBACK_CANDIDATE_REJECTED" in rejected.reason_codes


def test_pde_deepening_is_geometric_not_upstream_authority_dependent():
    pde = PDEEngine("EURUSD")
    pde.state = PDEState.PDE_PULLBACK_ACTIVE
    pde.direction = "LONG"
    pde._anchor = Decimal("1.1000")
    pde._extreme = Decimal("1.1100")
    pde._impulse_amplitude = Decimal("0.0100")
    pde._pullback_extreme = Decimal("1.1020")
    pde._last_depth = Decimal("0.70")
    pde._bars = 2
    pde._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
    out = pde.process_bar(bar(60, 1, Decimal("1.1019")), Decimal("0.001"), Decimal("+10"), "LONG", "TREND_UP")
    assert out.state == PDEState.PDE_DEEPENING
    assert "PULLBACK_DEEPENING" in out.reason_codes


def test_pde_resumption_fails_on_renewed_geometric_deepening():
    pde = PDEEngine("EURUSD")
    pde.state = PDEState.PDE_RESUMPTION_IN_PROGRESS
    pde.direction = "LONG"
    pde._anchor = Decimal("1.1000")
    pde._extreme = Decimal("1.1100")
    pde._impulse_amplitude = Decimal("0.0100")
    pde._pullback_extreme = Decimal("1.1030")
    pde._last_depth = Decimal("0.70")
    pde._bars = 3
    pde._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
    pde._resume_transition(PDEResumptionState.RECOVERY_CONFIRMED)
    out = pde.process_bar(bar(60, 1, Decimal("1.1019")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    assert out.state == PDEState.PDE_RESUMPTION_FAILED
    assert out.resumption_state == PDEResumptionState.RESUMPTION_FAILED


def test_structure_current_direction_is_non_authoritative():
    from src.fractal_flow.domain.structure import StructureEngine
    engine = StructureEngine("EURUSD")
    before = engine.structural_ownership
    engine.current_direction = "LONG"
    assert engine.structural_ownership == before
    engine.current_direction = "SHORT"
    assert engine.structural_ownership == before


def test_phase2_has_no_downstream_current_direction_dependency():
    from pathlib import Path
    import ast

    source_root = Path("src/fractal_flow")
    offenders = []
    for path in source_root.rglob("*.py"):
        if path.name in {"structure.py", "structure_v23.py"}:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "current_direction":
                offenders.append(str(path))
    assert offenders == []


def test_phase2_snapshot_restart_tail_is_causally_equivalent():
    continuous = pipeline()
    prefix = pipeline()
    bars = [bar(i * 60, i, Decimal("1.1000") + Decimal(i % 4 - 1) * Decimal("0.0003")) for i in range(1, 13)]

    for item in bars[:6]:
        continuous.process_bar(item)
        prefix.process_bar(item)
    checkpoint = prefix.snapshot_state()
    restarted = Phase2Pipeline.from_snapshot_state(checkpoint)

    continuous_results = [continuous.process_bar(item) for item in bars[6:]]
    restarted_results = [restarted.process_bar(item) for item in bars[6:]]

    assert continuous.state_hash() == restarted.state_hash()
    assert continuous.snapshot_state() == restarted.snapshot_state()
    assert continuous_results == restarted_results
    assert [continuous.historical_evaluation(item.close_timestamp) for item in bars] == [
        restarted.historical_evaluation(item.close_timestamp) for item in bars
    ]


def test_pde_pullback_rules_exclude_fibonacci_and_fixed_candle_thresholds():
    from pathlib import Path
    source = Path("src/fractal_flow/domain/pde.py").read_text()
    normalized = source.replace("_bars > self.max_episode_bars", "")
    forbidden_fibonacci_literals = ("0.382", "0.5", "0.618", "38.2", "61.8")
    assert not any(token in normalized for token in forbidden_fibonacci_literals)
    # Bar count may govern finite episode lifetime, but must not determine
    # pullback qualification, depth, recovery, or resumption semantics.
    pullback_block = normalized[normalized.index("if self.state in {"): normalized.index("self._last_close = close")]
    assert "_bars" not in pullback_block


def test_pde_failed_new_episode_attempt_clears_terminal_episode_fields():
    pde = PDEEngine("EURUSD")
    pde.state = PDEState.PDE_FOLLOW_THROUGH
    pde.direction = "LONG"
    pde._anchor = Decimal("1.1000")
    pde._extreme = Decimal("1.1100")
    pde._pullback_extreme = Decimal("1.1040")
    pde._impulse_amplitude = Decimal("0.0100")
    pde._last_depth = Decimal("0.60")
    pde._bars = 9
    pde._episode_id = "EURUSD:1M:episode:7"
    pde._last_close = Decimal("1.1100")
    out = pde.process_bar(bar(60, 1, Decimal("1.1100")), Decimal("0.001"))
    assert out.state == PDEState.PDE_NONE
    assert out.direction == "UNKNOWN"
    assert out.episode_id == ""
    assert out.impulse_amplitude == Decimal("0")
    assert out.pullback_depth == Decimal("0")
    assert pde._anchor is None
    assert pde._extreme is None
    assert pde._pullback_extreme is None
    assert pde._bars == 0


def test_pde_formal_spec_matches_committed_geometry_model():
    from pathlib import Path
    spec = Path("docs/PHASE2_PDE_FORMAL_SPEC.md").read_text(encoding="utf-8")
    assert "(extreme - close) / impulse_amplitude" in spec
    assert "(close - extreme) / impulse_amplitude" in spec
    assert "(close - pullback_extreme) / (extreme - pullback_extreme)" in spec
    assert "(pullback_extreme - close) / (pullback_extreme - extreme)" in spec
    assert "(extreme - close) / max(v_local, extreme - anchor)" not in spec
    assert "(close - pullback_extreme) / max(v_local, extreme - pullback_extreme)" not in spec




def test_invariant_matrix_does_not_invoke_pytest_recursively():
    import ast
    from pathlib import Path

    source = Path("tests/test_42_invariants.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="tests/test_42_invariants.py")
    recursive_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pytest"
        and node.func.attr == "main"
    ]
    assert recursive_calls == []

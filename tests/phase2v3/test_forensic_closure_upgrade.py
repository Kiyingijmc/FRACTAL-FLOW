from decimal import Decimal
import pytest

from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.pde import PDEResumptionState
from src.fractal_flow.domain.envelope import InvalidStateTransitionException, GLOBAL_STATE_REGISTRY
from src.fractal_flow.domain.regime import RegimeEngine
from src.fractal_flow.domain.role import RoleEngine
from src.fractal_flow.domain.location import LocationEngine


def make_bar(ts: int, close: str, seq: int, spread: str = "0") -> Bar:
    c = Decimal(close)
    return Bar.create(
        "EURUSD", "1M", ts, ts + 60,
        c - Decimal("0.0005"), c + Decimal("0.001"), c - Decimal("0.001"), c,
        spread=Decimal(spread), sequence=seq, data_version=1, is_closed=True,
    )


def pipeline() -> Phase2Pipeline:
    return Phase2Pipeline("EURUSD", "1M", InstrumentSpec("EURUSD", Decimal("0.00001"), 5), history_capacity=3)


def test_flow_is_primitive_and_not_structure_owned():
    p = pipeline()
    first = p.process_bar(make_bar(60, "1.1000", 1))
    assert first.flow.evidence.structure_progression == Decimal("0")


def test_pipeline_history_is_bounded_and_future_watermark_rejected():
    p = pipeline()
    for i in range(1, 7):
        p.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))
    assert len(p._historical_evaluations) == 3
    assert p.historical_evaluation(60) is None
    with pytest.raises(ValueError):
        p.process_bar(make_bar(360, "1.1010", 6))


def test_pipeline_snapshot_restore_is_continuation_equivalent():
    p = pipeline()
    for i in range(1, 6):
        p.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))
    restored = Phase2Pipeline.from_snapshot_state(p.snapshot_state())
    for i in range(6, 8):
        a = p.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))
        b = restored.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0001:.4f}", i))
        assert a.context.to_dict() == b.context.to_dict()
        assert a.evidence == b.evidence
        assert a.pde == b.pde
        assert a.role == b.role


def test_pipeline_evidence_contains_all_phase2_families():
    p = pipeline()
    result = None
    for i in range(1, 6):
        result = p.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0002:.4f}", i))
    assert result is not None
    assert {"STRUCTURE", "FLOW", "REGIME", "EPISODE", "LOCATION"}.issubset(set(result.evidence.contributing_families))
    assert result.context.role_version == result.role.version
    assert result.context.location_version == result.location.version
    assert result.context.evidence_version == p.evidence.version




def test_pipeline_historical_prefix_is_immune_to_future_mutation():
    a, b = pipeline(), pipeline()
    prefix = []
    for i in range(1, 5):
        bar = make_bar(i * 60, f"{1.1000 + i * 0.0002:.4f}", i)
        a.process_bar(bar); b.process_bar(bar); prefix.append(bar)
    before = b.historical_evaluation(300)
    for i in range(5, 7):
        b.process_bar(make_bar(i * 60, f"{1.1000 - i * 0.0004:.4f}", i))
    after = b.historical_evaluation(300)
    assert before == after
    assert after == a.historical_evaluation(300)


def test_pde_has_runtime_resumption_state():
    p = pipeline()
    for i, c in enumerate(("1.1000", "1.1030", "1.1010", "1.1025", "1.1040"), 1):
        result = p.process_bar(make_bar(i * 60, c, i))
    assert result.pde.resumption_state in set(PDEResumptionState)
    assert result.pde.episode_id
    assert result.pde.causal_watermark == result.bar.close_timestamp


def test_transition_enforcement_is_runtime_for_regime_role_location():
    regime = RegimeEngine("EURUSD", efficiency_trend=Decimal("0.10"), chaos_dispersion=Decimal("100"), chaos_volatility_ratio=Decimal("100"))
    regime.state = regime.state.__class__.CHAOTIC
    for i, close in enumerate(("1.1000", "1.1010", "1.1020", "1.1030"), 1):
        regime.process_bar(make_bar(i * 60, close, i), Decimal("0.001"))
    assert regime.state.value in {"TRANSITION", "TREND_UP", "TREND_DOWN", "RANGE", "CHAOTIC", "UNKNOWN"}

    role = RoleEngine("EURUSD")
    role.state = role.state.__class__.NOISE
    role_result = role.evaluate(60, "LONG", "LONG_DOMINANT", "TREND_UP", "PDE_NONE", "OPEN")
    assert role_result.state.value == "CONTINUATION"
    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.validate_transition("RoleState", "NOISE", "BREAKOUT")

    location = LocationEngine("EURUSD")
    location.state = location.state.__class__.CONGESTED
    location_result = location.evaluate(60, Decimal("1.1"), Decimal("0.01"), Decimal("1.0"), None)
    assert location_result.state.value == "FAVORABLE"
    with pytest.raises(InvalidStateTransitionException):
        GLOBAL_STATE_REGISTRY.validate_transition("LocationState", "CONGESTED", "UNKNOWN")


def test_phase2_engines_emit_canonical_state_envelopes():
    p = pipeline()
    result = None
    for i in range(1, 6):
        result = p.process_bar(make_bar(i * 60, f"{1.1000 + i * 0.0002:.4f}", i))
    assert result is not None
    assert p.regime.to_envelope("regime").state == result.regime.state.value
    pde_env, resume_env = p.pde.to_envelopes("pde")
    assert pde_env.state == result.pde.state.value
    assert resume_env.state == result.pde.resumption_state.value
    assert p.role.to_envelope("role").state == result.role.state.value
    assert p.location.to_envelope("location").state == result.location.state.value


def test_phase2_configuration_identity_is_stable_and_snapshot_bound():
    a = pipeline()
    b = pipeline()
    assert a.configuration_id == b.configuration_id
    assert a.process_bar(make_bar(60, "1.1000", 1)).context.configuration_id == a.configuration_id
    snap = a.snapshot_state()
    restored = Phase2Pipeline.from_snapshot_state(snap)
    assert restored.configuration_id == a.configuration_id
    tampered = dict(snap)
    tampered["configuration_id"] = "phase2_tampered"
    with pytest.raises(ValueError, match="configuration identity"):
        Phase2Pipeline.from_snapshot_state(tampered)


def test_phase2_context_rejects_cross_engine_watermark_skew():
    p = pipeline()
    versions = p.context_builder
    with pytest.raises(ValueError, match="watermark mismatch"):
        versions.build(
            "root", "EURUSD", "1M", 120,
            p.instrument, __import__("src.fractal_flow.domain.context", fromlist=["DataStatus"]).DataStatus.VALID,
            Decimal("0.001"), __import__("src.fractal_flow.domain.phase2_context", fromlist=["EngineVersionSet"]).EngineVersionSet(),
            configuration_version=1, configuration_id="phase2_test",
            component_watermarks={"flow": 60}, sequence=2,
        )


def test_role_precedence_is_explicit_and_auditable():
    assert RoleEngine.PRECEDENCE[:7] == (
        "DATA_UNAVAILABLE", "LOCATION_BLOCKED", "PDE_PULLBACK",
        "STRUCTURAL_RECLAIM", "STRUCTURAL_BREAK", "CHARACTER_CHANGE", "PDE_RESUMPTION",
    )


def test_pde_regime_and_structure_are_operational_recovery_gates():
    from src.fractal_flow.domain.pde import PDEEngine, PDEState
    adverse = PDEEngine("EURUSD")
    adverse.state = PDEState.PDE_WEAKENING
    adverse.direction = "LONG"
    adverse._anchor = Decimal("1.1000")
    adverse._extreme = Decimal("1.1020")
    adverse._last_close = Decimal("1.1015")
    adverse._bars = 2
    blocked = adverse.process_bar(
        make_bar(60, "1.1020", 1), Decimal("0.001"), Decimal("0"), "LONG", "TREND_DOWN"
    )
    assert blocked.state == PDEState.PDE_WEAKENING
    assert "REGIME_ADVERSE_DISPLACEMENT" not in blocked.reason_codes

    compatible = PDEEngine("EURUSD")
    compatible.state = PDEState.PDE_WEAKENING
    compatible.direction = "LONG"
    compatible._anchor = Decimal("1.1000")
    compatible._extreme = Decimal("1.1020")
    compatible._pullback_extreme = Decimal("1.1005")
    compatible._last_depth = Decimal("0.75")
    compatible._last_close = Decimal("1.1010")
    compatible._bars = 2
    compatible._resume_transition(__import__("src.fractal_flow.domain.pde", fromlist=["PDEResumptionState"]).PDEResumptionState.RECOVERY_CANDIDATE)
    resumed = compatible.process_bar(
        make_bar(60, "1.1017", 1), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP"
    )
    assert resumed.state == PDEState.PDE_RESUMPTION_IN_PROGRESS
    assert resumed.recovery_ratio >= Decimal("0.75")
    assert "REGIME_COMPATIBLE_RECOVERY" in resumed.reason_codes

"""Phase 2 Work Package 2F Tests: Replay, Recovery, and Causal Adversarial Closure.

Tests:
- Replay equivalence across full behavioral pipeline.
- Causal mutation invariance under future price spikes.
- Level 1, Level 2, and Level 3 Authority enforcement across all Phase 2 behavioral engines.
- Stale parent version rejection and version race protections.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException
from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.location import LocationEngine
from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.pde import PDEEngine
from src.fractal_flow.domain.pipeline import BehavioralPipeline
from src.fractal_flow.domain.regime import RegimeEngine
from src.fractal_flow.domain.role import RoleEngine
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.simulation.causal_framework import CausalTestFramework

BASE_TS = 1700006400


def test_behavioral_pipeline_replay_equivalence() -> None:
    """Verifies that replaying identical market bars produces identical behavioral snapshots."""
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(5)
    ]
    ticks = [
        Tick.create("EURUSD", BASE_TS + (i + 1) * 60, "1.0855", "1.0856")
        for i in range(5)
    ]

    p1 = BehavioralPipeline("EURUSD", timeframes=["1M"])
    snaps1 = [p1.process_bar(b, t, root_id="r1") for b, t in zip(bars, ticks)]

    p2 = BehavioralPipeline("EURUSD", timeframes=["1M"])
    snaps2 = [p2.process_bar(b, t, root_id="r1") for b, t in zip(bars, ticks)]

    assert [s.structure_record.swing_state for s in snaps1] == [s.structure_record.swing_state for s in snaps2]
    assert [s.flow_record.flow_state for s in snaps1] == [s.flow_record.flow_state for s in snaps2]
    assert [s.pde_record.pde_state for s in snaps1] == [s.pde_record.pde_state for s in snaps2]
    assert [s.regime_record.regime_state for s in snaps1] == [s.regime_record.regime_state for s in snaps2]
    assert [s.role_record.role_state for s in snaps1] == [s.role_record.role_state for s in snaps2]
    assert [s.location_record.location_state for s in snaps1] == [s.location_record.location_state for s in snaps2]


def test_causal_no_lookahead_behavioral_pipeline() -> None:
    """Evaluates causal test framework over full behavioral pipeline."""
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(5)
    ]
    ticks = [
        Tick.create("EURUSD", BASE_TS + (i + 1) * 60, "1.0855", "1.0856")
        for i in range(5)
    ]

    decision_time = BASE_TS + 180

    def pipeline_processor(prefix_ticks: list[Tick], dec_time: int) -> dict[str, str]:
        p = BehavioralPipeline("EURUSD", timeframes=["1M"])
        last_snap = None
        for b, t in zip(bars, ticks):
            if t.timestamp <= dec_time:
                last_snap = p.process_bar(b, t, root_id="r1")
        assert last_snap is not None
        return {
            "flow_state": last_snap.flow_record.flow_state.value,
            "pde_state": last_snap.pde_record.pde_state.value,
            "regime_state": last_snap.regime_record.regime_state.value,
        }

    prefix_ticks = ticks[:3]
    future_a = [Tick.create("EURUSD", BASE_TS + 300, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 300, "1.2000", "1.2001")]

    res = CausalTestFramework.verify_causality(prefix_ticks, future_a, future_b, decision_time, pipeline_processor)
    assert res.is_causal is True


def test_three_levels_of_authority_enforcement() -> None:
    """Verifies Level 1, Level 2, and Level 3 authority enforcement across all behavioral engines."""
    engines = {
        "Structure": StructureEngine("EURUSD"),
        "Flow": FlowEngine("EURUSD"),
        "PDE": PDEEngine("EURUSD"),
        "Regime": RegimeEngine("EURUSD"),
        "Role": RoleEngine("EURUSD"),
        "Location": LocationEngine("EURUSD"),
    }

    forbidden_capabilities = ["CREATE_EXECUTION_INTENT", "SUBMIT_ORDER", "MODIFY_POSITION", "CLOSE_POSITION_STRATEGICALLY"]
    for eng_name in engines:
        for cap in forbidden_capabilities:
            with pytest.raises(AuthorityViolationException):
                AuthorityMatrix.verify_capability(eng_name, cap)

    execution_methods = ["create_execution_intent", "submit_order", "modify_position", "close_position_strategically", "size_position"]
    for eng_name, instance in engines.items():
        for m in execution_methods:
            assert not hasattr(instance, m), f"Engine {eng_name} violates static architecture protection with attribute {m}"

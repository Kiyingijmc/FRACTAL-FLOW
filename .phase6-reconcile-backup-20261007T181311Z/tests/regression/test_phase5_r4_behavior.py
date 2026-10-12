"""R4 behavioral/spec-parity regression guards."""
from decimal import Decimal
from pathlib import Path

from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.pde import PDEEngine, PDEState
from src.fractal_flow.domain.phase3 import TimeframeMapping
from src.fractal_flow.domain.structure_v23 import StructureEngineV23

ROOT = Path(__file__).resolve().parents[2]


def _bar(ts: int, seq: int, close: str, timeframe: str = "1M") -> Bar:
    c = Decimal(close)
    return Bar.create("EURUSD", timeframe, ts - 60, ts, c, c + Decimal("0.0010"), c - Decimal("0.0010"), c, sequence=seq)


def test_r4_has_one_canonical_timeframe_mapping_type():
    phase3 = (ROOT / "src/fractal_flow/domain/phase3.py").read_text()
    phase4 = (ROOT / "src/fractal_flow/domain/phase4.py").read_text()
    assert phase3.count("class TimeframeMapping") == 1
    assert phase4.count("class TimeframeMapping") == 0
    mapping = TimeframeMapping.canonical()
    assert mapping.primary_tf == "M15"
    assert mapping.migrate_primary_down().primary_tf == "M5"
    assert mapping.migrate_primary_down().migrate_primary_down() == mapping.migrate_primary_down()


def test_r4_primary_pullback_remains_above_execution_floor():
    mapping = TimeframeMapping.canonical().migrate_primary_down()
    assert mapping.primary > mapping.execution
    assert mapping.primary.name == "M5"
    assert mapping.execution.name == "M1"


def test_r4_flow_structure_progression_is_derived_from_production_structure():
    from src.fractal_flow.domain.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline("EURUSD", "1M")
    evaluation = pipeline.process_bar(_bar(60, 1, "1.1000"))
    assert evaluation.flow.evidence.structure_progression == pipeline.structure.structure_progression()


def test_r4_pde_maturity_is_descriptive_and_explicit():
    pde = PDEEngine("EURUSD", "1M", min_impulse=Decimal("0.1"))
    first = pde.process_bar(_bar(60, 1, "1.1000"), Decimal("0.0010"))
    assert first.maturity == "EARLY"
    assert first.state in set(PDEState)
    assert first.maturity not in {"PASS", "FAIL", "ENTRY_READY"}


def test_r4_flow_weights_are_versioned_in_effective_configuration():
    from src.fractal_flow.domain.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline("EURUSD", "1M")
    weights = pipeline.configuration.flow
    assert weights["displacement_weight"] == Decimal("0.3")
    assert weights["efficiency_weight"] == Decimal("0.3")
    assert weights["persistence_weight"] == Decimal("0.2")
    assert weights["structure_progression_weight"] == Decimal("0.2")
    assert weights["persistence_scale"] == Decimal("5.0")


def test_r4_pde_exposes_documented_impulse_feature_vector():
    from src.fractal_flow.domain.pde import PDEImpulseState
    from src.fractal_flow.domain.phase2 import Phase2Pipeline
    pipeline = Phase2Pipeline("EURUSD", "1M")
    pipeline.process_bar(_bar(60, 1, "1.1000"))
    evaluation = pipeline.process_bar(_bar(120, 2, "1.1010"))
    pde = evaluation.pde
    assert pde.impulse_state in set(PDEImpulseState)
    for value in (pde.impulse_displacement, pde.impulse_efficiency, pde.impulse_structure_progression, pde.impulse_persistence, pde.impulse_range_expansion, pde.impulse_quality):
        assert isinstance(value, Decimal)
        assert value.is_finite()
    assert Decimal("0") <= pde.impulse_efficiency <= Decimal("1")
    assert Decimal("0") <= pde.impulse_persistence <= Decimal("1")
    assert Decimal("0") <= pde.impulse_quality <= Decimal("1")

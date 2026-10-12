"""Phase 1F Tests: Lineage and Version Propagation in Structure Transitions."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine

BASE_TS = 1700006400


def test_structure_transition_records_all_required_lineage_and_version_fields() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")

    rec = engine.process_bar(
        b1,
        v_local=Decimal("0.0010"),
        root_id="root_eurusd_01",
        parent_id="parent_h1_01",
        parent_version=5,
        config_version=2,
        data_version=3,
        feature_version=4,
    )

    assert rec.root_id == "root_eurusd_01"
    assert rec.parent_id == "parent_h1_01"
    assert rec.parent_version == 5
    assert rec.state_version == 1
    assert rec.config_version == 2
    assert rec.data_version == 3
    assert rec.feature_version == 4
    assert rec.authority == "STRUCTURE"
    assert rec.timestamp == BASE_TS + 60

    envelope = rec.to_envelope("struct_eurusd_m1")
    assert envelope.object_type == "SwingState"
    assert envelope.root_id == "root_eurusd_01"
    assert envelope.parent_id == "parent_h1_01"
    assert envelope.parent_version == 5
    assert envelope.version == 1
    assert envelope.configuration_version == 2
    assert envelope.data_version == 3
    assert envelope.feature_version == 4

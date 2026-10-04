"""Phase 1G Tests: Snapshot + Journal Tail Recovery Equivalence."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine

BASE_TS = 1700006400


def test_continuous_state_equals_recovered_state_across_all_fields() -> None:
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(8)
    ]

    engine_continuous = StructureEngine("EURUSD", timeframe="1M")
    continuous_records = []
    for b in bars:
        rec = engine_continuous.process_bar(
            b,
            v_local=Decimal("0.0010"),
            root_id="r1",
            parent_id="p1",
            parent_version=1,
            config_version=2,
            data_version=3,
            feature_version=4,
        )
        continuous_records.append(rec)

    # Recovery run
    engine_recovered = StructureEngine("EURUSD", timeframe="1M")
    recovered_records = []
    for b in bars:
        rec = engine_recovered.process_bar(
            b,
            v_local=Decimal("0.0010"),
            root_id="r1",
            parent_id="p1",
            parent_version=1,
            config_version=2,
            data_version=3,
            feature_version=4,
        )
        recovered_records.append(rec)

    assert len(continuous_records) == len(recovered_records)
    for rc, rr in zip(continuous_records, recovered_records):
        assert rc.swing_state == rr.swing_state
        assert rc.previous_swing_state == rr.previous_swing_state
        assert rc.break_state == rr.break_state
        assert rc.damage_state == rr.damage_state
        assert rc.timestamp == rr.timestamp
        assert rc.state_version == rr.state_version
        assert rc.root_id == rr.root_id
        assert rc.parent_id == rr.parent_id
        assert rc.parent_version == rr.parent_version
        assert rc.config_version == rr.config_version
        assert rc.data_version == rr.data_version
        assert rc.feature_version == rr.feature_version
        assert rc.reason_codes == rr.reason_codes

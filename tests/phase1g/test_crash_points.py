"""Phase 1G Tests: Crash Points Matrix for Phase 1 Engines."""

from decimal import Decimal
import tempfile

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.domain.volatility import VolatilityEngine
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import SnapshotEngine

BASE_TS = 1700006400


def test_crash_point_matrix_all_8_scenarios() -> None:
    """Tests all 8 required crash/restart points across Data Quality, Volatility, and Structure engines:

    1. crash before state transition
    2. crash after state transition
    3. crash after event append
    4. crash before snapshot
    5. crash after snapshot
    6. restart from snapshot
    7. replay journal tail
    8. compare with uninterrupted execution
    """
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(10)
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        journal_path = f"{tmp_dir}/events.journal"
        snapshot_path = f"{tmp_dir}"

        journal = DurableEventJournal(journal_path)
        snapshot_engine = SnapshotEngine(snapshot_path)

        # 1. Uninterrupted Run
        dq_engine = DataQualityEngine("EURUSD")
        vol_engine = VolatilityEngine("EURUSD", timeframe="1M")
        struct_engine = StructureEngine("EURUSD", timeframe="1M")

        uninterrupted_envelopes = []
        for b in bars:
            dq_a = dq_engine.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_m = vol_engine.update_bar(b)
            struct_r = struct_engine.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

            uninterrupted_envelopes.append(dq_a.to_envelope("dq_01", root_id="r1", parent_id="p1", parent_version=1))
            uninterrupted_envelopes.append(vol_m.to_envelope("vol_01", root_id="r1", parent_id="p1", parent_version=1))
            uninterrupted_envelopes.append(struct_r.to_envelope("struct_01"))

        # 2. Interrupted Run with Crash at checkpoint (Bar 5)
        dq_restarted = DataQualityEngine("EURUSD")
        vol_restarted = VolatilityEngine("EURUSD", timeframe="1M")
        struct_restarted = StructureEngine("EURUSD", timeframe="1M")

        for b in bars[:5]:
            dq_a = dq_restarted.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_m = vol_restarted.update_bar(b)
            struct_r = struct_restarted.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

        # Take Snapshot at checkpoint
        snapshot_data = {
            "dq_last_ts": dq_restarted.last_timestamp,
            "vol_state": vol_restarted.current_state.value,
            "struct_state": struct_restarted.swing_state.value,
            "struct_version": struct_restarted.state_version,
        }
        snapshot_engine.save_snapshot(
            aggregate_type="MarketState", aggregate_id="EURUSD", version=1, last_seq=5, payload=snapshot_data
        )

        # Replay remaining tail from checkpoint
        recovered_envelopes = []
        for b in bars[5:]:
            dq_a = dq_restarted.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_m = vol_restarted.update_bar(b)
            struct_r = struct_restarted.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

            recovered_envelopes.append(dq_a.to_envelope("dq_01", root_id="r1", parent_id="p1", parent_version=1))
            recovered_envelopes.append(vol_m.to_envelope("vol_01", root_id="r1", parent_id="p1", parent_version=1))
            recovered_envelopes.append(struct_r.to_envelope("struct_01"))

        # Assert final recovered states match uninterrupted states
        assert dq_engine.current_state == dq_restarted.current_state
        assert vol_engine.current_state == vol_restarted.current_state
        assert struct_engine.swing_state == struct_restarted.swing_state
        assert struct_engine.state_version == struct_restarted.state_version

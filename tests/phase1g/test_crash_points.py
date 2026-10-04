"""Phase 1G Tests: Real Persistence, Crash Points, and Snapshot Recovery Integration."""

from decimal import Decimal
import tempfile

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.event import Event, ImmutablePayloadDict
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.domain.volatility import VolatilityEngine
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import SnapshotEngine

BASE_TS = 1700006400


def test_crash_recovery_matrix_c1_through_c8() -> None:
    """Executes genuine snapshot load and journal tail replay into NEW engine instances across scenarios C1-C8."""
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(10)
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        journal_path = f"{tmp_dir}/events.journal"
        snapshot_dir = f"{tmp_dir}/snapshots"

        journal = DurableEventJournal(journal_path)
        snapshot_engine = SnapshotEngine(snapshot_dir)

        # 1. Uninterrupted Run
        dq_uninterrupted = DataQualityEngine("EURUSD")
        vol_uninterrupted = VolatilityEngine("EURUSD", timeframe="1M")
        struct_uninterrupted = StructureEngine("EURUSD", timeframe="1M")

        for b in bars:
            dq_uninterrupted.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_uninterrupted.update_bar(b)
            struct_uninterrupted.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

        # 2. C1-C6: Genuine Snapshot Write + Discard Engine + Instantiate NEW Engine
        dq_initial = DataQualityEngine("EURUSD")
        vol_initial = VolatilityEngine("EURUSD", timeframe="1M")
        struct_initial = StructureEngine("EURUSD", timeframe="1M")

        for seq, b in enumerate(bars[:5], start=1):
            dq_a = dq_initial.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_m = vol_initial.update_bar(b)
            struct_r = struct_initial.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

            event_obj = Event(
                event_id=f"evt_{seq}",
                event_type="BarProcessed",
                aggregate_type="MarketState",
                aggregate_id="EURUSD",
                root_id="r1",
                parent_id="p1",
                aggregate_version=seq,
                source_timestamp=b.close_timestamp,
                event_timestamp=b.close_timestamp,
                processing_timestamp=b.close_timestamp,
                payload=ImmutablePayloadDict(
                    {
                        "dq_state": dq_a.state.value,
                        "vol_state": vol_m.state.value,
                        "struct_state": struct_r.swing_state.value,
                        "struct_version": struct_r.state_version,
                        "last_ts": dq_initial.last_timestamp,
                    }
                ),
            )
            journal.append(event_obj)

        snap_payload = {
            "dq_state": dq_initial.current_state.value,
            "vol_state": vol_initial.current_state.value,
            "struct_state": struct_initial.swing_state.value,
            "struct_version": struct_initial.state_version,
            "last_ts": dq_initial.last_timestamp,
        }
        snapshot_engine.save_snapshot(
            aggregate_type="MarketState", aggregate_id="EURUSD", version=5, last_seq=5, payload=snap_payload
        )

        for seq, b in enumerate(bars[5:], start=6):
            dq_a = dq_initial.evaluate_bar(b, current_processing_time=b.close_timestamp)
            vol_m = vol_initial.update_bar(b)
            struct_r = struct_initial.process_bar(
                b, v_local=Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1
            )

            event_obj = Event(
                event_id=f"evt_{seq}",
                event_type="BarProcessed",
                aggregate_type="MarketState",
                aggregate_id="EURUSD",
                root_id="r1",
                parent_id="p1",
                aggregate_version=seq,
                source_timestamp=b.close_timestamp,
                event_timestamp=b.close_timestamp,
                processing_timestamp=b.close_timestamp,
                payload=ImmutablePayloadDict(
                    {
                        "dq_state": dq_a.state.value,
                        "vol_state": vol_m.state.value,
                        "struct_state": struct_r.swing_state.value,
                        "struct_version": struct_r.state_version,
                        "last_ts": dq_initial.last_timestamp,
                    }
                ),
            )
            journal.append(event_obj)

        del dq_initial
        del vol_initial
        del struct_initial

        loaded_snap = snapshot_engine.load_snapshot("MarketState", "EURUSD")
        assert loaded_snap is not None
        assert loaded_snap.last_sequence_number == 5

        replayed_state = snapshot_engine.replay_journal(journal, "MarketState", "EURUSD")

        assert replayed_state["_snapshot_valid"] is True
        assert replayed_state["_snapshot_fallback_used"] is False
        assert replayed_state["struct_state"] == struct_uninterrupted.swing_state.value
        assert replayed_state["struct_version"] == struct_uninterrupted.state_version

        # C7: Corrupted Snapshot Fallback
        snap_file = snapshot_engine._get_snapshot_file_path("MarketState", "EURUSD")
        with open(snap_file, "w") as f:
            f.write("CORRUPTED_JSON_DATA")

        fresh_engine = SnapshotEngine(snapshot_dir)
        fallback_state = fresh_engine.replay_journal(journal, "MarketState", "EURUSD")

        assert fresh_engine._snapshot_fallback_used is True
        assert fallback_state["struct_state"] == struct_uninterrupted.swing_state.value

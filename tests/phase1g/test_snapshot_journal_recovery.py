"""Phase 1G Tests: Snapshot + Journal Tail Recovery Equivalence."""

from decimal import Decimal
import tempfile

from src.fractal_flow.domain.event import Event, ImmutablePayloadDict
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.persistence.journal import DurableEventJournal
from src.fractal_flow.persistence.snapshot import SnapshotEngine

BASE_TS = 1700006400


def test_continuous_state_equals_recovered_state_across_all_fields() -> None:
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(8)
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        journal_path = f"{tmp_dir}/events.journal"
        snapshot_dir = f"{tmp_dir}/snapshots"

        journal = DurableEventJournal(journal_path)
        snapshot_engine = SnapshotEngine(snapshot_dir)

        # 1. Continuous Run
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

        # 2. Persisted Run
        engine_initial = StructureEngine("EURUSD", timeframe="1M")
        for seq, b in enumerate(bars[:4], start=1):
            rec = engine_initial.process_bar(
                b,
                v_local=Decimal("0.0010"),
                root_id="r1",
                parent_id="p1",
                parent_version=1,
                config_version=2,
                data_version=3,
                feature_version=4,
            )
            event_obj = Event(
                event_id=f"evt_{seq}",
                event_type="StructureTransitioned",
                aggregate_type="Structure",
                aggregate_id="EURUSD",
                root_id="r1",
                parent_id="p1",
                aggregate_version=seq,
                source_timestamp=b.close_timestamp,
                event_timestamp=b.close_timestamp,
                processing_timestamp=b.close_timestamp,
                payload=ImmutablePayloadDict(
                    {
                        "swing_state": rec.swing_state.value,
                        "break_state": rec.break_state.value,
                        "damage_state": rec.damage_state.value,
                        "state_version": rec.state_version,
                    }
                ),
            )
            journal.append(event_obj)

        snapshot_engine.save_snapshot(
            aggregate_type="Structure",
            aggregate_id="EURUSD",
            version=4,
            last_seq=4,
            payload={
                "swing_state": engine_initial.swing_state.value,
                "break_state": engine_initial.break_state.value,
                "damage_state": engine_initial.damage_state.value,
                "state_version": engine_initial.state_version,
            },
        )

        for seq, b in enumerate(bars[4:], start=5):
            rec = engine_initial.process_bar(
                b,
                v_local=Decimal("0.0010"),
                root_id="r1",
                parent_id="p1",
                parent_version=1,
                config_version=2,
                data_version=3,
                feature_version=4,
            )
            event_obj = Event(
                event_id=f"evt_{seq}",
                event_type="StructureTransitioned",
                aggregate_type="Structure",
                aggregate_id="EURUSD",
                root_id="r1",
                parent_id="p1",
                aggregate_version=seq,
                source_timestamp=b.close_timestamp,
                event_timestamp=b.close_timestamp,
                processing_timestamp=b.close_timestamp,
                payload=ImmutablePayloadDict(
                    {
                        "swing_state": rec.swing_state.value,
                        "break_state": rec.break_state.value,
                        "damage_state": rec.damage_state.value,
                        "state_version": rec.state_version,
                    }
                ),
            )
            journal.append(event_obj)

        # Replay into fresh state dictionary
        recovered_state = snapshot_engine.replay_journal(journal, "Structure", "EURUSD")

        assert recovered_state["swing_state"] == engine_continuous.swing_state.value
        assert recovered_state["break_state"] == engine_continuous.break_state.value
        assert recovered_state["damage_state"] == engine_continuous.damage_state.value
        assert recovered_state["state_version"] == engine_continuous.state_version

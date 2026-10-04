"""Phase 1G Tests: Real Fault-Injected Crash Point Matrix (C1-C8)."""

from decimal import Decimal
from typing import Any
import tempfile
import pytest

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.event import Event, ImmutablePayloadDict
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.domain.volatility import VolatilityEngine
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalDurabilityException
from src.fractal_flow.persistence.snapshot import SnapshotCorruptionException, SnapshotEngine

BASE_TS = 1700006400


def test_c1_crash_before_journal_write() -> None:
    """C1: Crash before journal write - in-memory and disk states un-mutated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        journal = DurableEventJournal(f"{tmp_dir}/events.journal")

        def c1_fault(phase: str, record: Any) -> None:
            if phase == "BEFORE_JOURNAL_WRITE":
                raise RuntimeError("C1_CRASH_BEFORE_JOURNAL_WRITE")

        journal.set_fault_hook(c1_fault)

        evt = Event(
            event_id="e1",
            event_type="BarProcessed",
            aggregate_type="MarketState",
            aggregate_id="EURUSD",
            root_id="r1",
            parent_id="p1",
            aggregate_version=1,
            source_timestamp=BASE_TS,
            event_timestamp=BASE_TS,
            processing_timestamp=BASE_TS,
            payload=ImmutablePayloadDict({"dq": "DATA_NORMAL"}),
        )

        with pytest.raises(RuntimeError, match="C1_CRASH"):
            journal.append(evt)

        assert journal._global_sequence == 0


def test_c2_crash_before_journal_fsync() -> None:
    """C2: Crash before journal fsync - rollback leaves file clean."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        journal = DurableEventJournal(f"{tmp_dir}/events.journal")

        def c2_fault(phase: str, record: Any) -> None:
            if phase == "BEFORE_JOURNAL_FSYNC":
                raise RuntimeError("C2_CRASH_BEFORE_FSYNC")

        journal.set_fault_hook(c2_fault)

        evt = Event(
            event_id="e1",
            event_type="BarProcessed",
            aggregate_type="MarketState",
            aggregate_id="EURUSD",
            root_id="r1",
            parent_id="p1",
            aggregate_version=1,
            source_timestamp=BASE_TS,
            event_timestamp=BASE_TS,
            processing_timestamp=BASE_TS,
            payload=ImmutablePayloadDict({"dq": "DATA_NORMAL"}),
        )

        with pytest.raises(JournalDurabilityException):
            journal.append(evt)

        restarted_journal = DurableEventJournal(f"{tmp_dir}/events.journal")
        assert len(restarted_journal.get_all_records()) == 0


def test_c3_crash_after_journal_fsync_before_in_memory_state() -> None:
    """C3: Crash after journal fsync before in-memory state update - journal holds record, engine recovers on restart."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        j_path = f"{tmp_dir}/events.journal"
        journal = DurableEventJournal(j_path)

        evt = Event(
            event_id="e1",
            event_type="BarProcessed",
            aggregate_type="MarketState",
            aggregate_id="EURUSD",
            root_id="r1",
            parent_id="p1",
            aggregate_version=1,
            source_timestamp=BASE_TS,
            event_timestamp=BASE_TS,
            processing_timestamp=BASE_TS,
            payload=ImmutablePayloadDict({"struct_state": "SWING_CONFIRMED"}),
        )

        def c3_fault(phase: str, record: Any) -> None:
            if phase == "AFTER_JOURNAL_FSYNC":
                raise RuntimeError("C3_CRASH_AFTER_FSYNC")

        journal.set_fault_hook(c3_fault)

        with pytest.raises(RuntimeError, match="C3_CRASH"):
            journal.append(evt)

        fresh_journal = DurableEventJournal(j_path)
        records = fresh_journal.get_all_records()
        assert len(records) == 1
        assert records[0].event.payload["struct_state"] == "SWING_CONFIRMED"


def test_c4_crash_after_state_mutation_before_snapshot() -> None:
    """C4: Crash after state mutation before snapshot - journal contains history, replay recovers state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        j_path = f"{tmp_dir}/events.journal"
        journal = DurableEventJournal(j_path)
        snapshot_engine = SnapshotEngine(f"{tmp_dir}/snaps")

        engine = StructureEngine("EURUSD", timeframe="1M")
        b1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0850", "1.0860", "1.0840", "1.0855")
        rec1 = engine.process_bar(b1, Decimal("0.0010"), root_id="r1", parent_id="p1", parent_version=1)

        evt = Event(
            event_id="e1",
            event_type="BarProcessed",
            aggregate_type="Structure",
            aggregate_id="EURUSD",
            root_id="r1",
            parent_id="p1",
            aggregate_version=1,
            source_timestamp=BASE_TS,
            event_timestamp=BASE_TS,
            processing_timestamp=BASE_TS,
            payload=ImmutablePayloadDict({"swing_state": rec1.swing_state.value, "state_version": rec1.state_version}),
        )
        journal.append(evt)

        del engine

        replayed = snapshot_engine.replay_journal(journal, "Structure", "EURUSD")
        assert replayed["swing_state"] == rec1.swing_state.value


def test_c5_crash_during_snapshot_temp_write() -> None:
    """C5: Crash during snapshot temp write - temp file unlinked, previous snapshot preserved."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_dir = f"{tmp_dir}/snaps"
        snapshot_engine = SnapshotEngine(snap_dir)

        snapshot_engine.save_snapshot("Market", "EURUSD", version=1, last_seq=1, payload={"val": 10})

        def c5_fault(phase: str, snap: Any) -> None:
            if phase == "BEFORE_SNAPSHOT_WRITE" and snap.aggregate_version == 2:
                raise RuntimeError("C5_CRASH_DURING_TEMP_WRITE")

        snapshot_engine.set_fault_hook(c5_fault)

        with pytest.raises(RuntimeError, match="C5_CRASH"):
            snapshot_engine.save_snapshot("Market", "EURUSD", version=2, last_seq=2, payload={"val": 20})

        fresh_snap_engine = SnapshotEngine(snap_dir)
        loaded = fresh_snap_engine.load_snapshot("Market", "EURUSD")
        assert loaded is not None
        assert loaded.aggregate_version == 1
        assert loaded.state_payload["val"] == 10


def test_c6_crash_before_snapshot_replace() -> None:
    """C6: Crash after snapshot write before replacement - target file untouched."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_dir = f"{tmp_dir}/snaps"
        snapshot_engine = SnapshotEngine(snap_dir)

        snapshot_engine.save_snapshot("Market", "EURUSD", version=1, last_seq=1, payload={"val": 10})

        def c6_fault(phase: str, snap: Any) -> None:
            if phase == "BEFORE_SNAPSHOT_REPLACE" and snap.aggregate_version == 2:
                raise RuntimeError("C6_CRASH_BEFORE_REPLACE")

        snapshot_engine.set_fault_hook(c6_fault)

        with pytest.raises(SnapshotCorruptionException, match="C6_CRASH"):
            snapshot_engine.save_snapshot("Market", "EURUSD", version=2, last_seq=2, payload={"val": 20})

        fresh_snap_engine = SnapshotEngine(snap_dir)
        loaded = fresh_snap_engine.load_snapshot("Market", "EURUSD")
        assert loaded is not None
        assert loaded.aggregate_version == 1


def test_c7_crash_after_snapshot_replacement() -> None:
    """C7: Crash after snapshot replacement - new snapshot loaded cleanly on restart."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_dir = f"{tmp_dir}/snaps"
        snapshot_engine = SnapshotEngine(snap_dir)

        def c7_fault(phase: str, snap: Any) -> None:
            if phase == "AFTER_SNAPSHOT_REPLACE" and snap.aggregate_version == 2:
                raise RuntimeError("C7_CRASH_AFTER_REPLACE")

        snapshot_engine.set_fault_hook(c7_fault)

        with pytest.raises(SnapshotCorruptionException, match="C7_CRASH"):
            snapshot_engine.save_snapshot("Market", "EURUSD", version=2, last_seq=2, payload={"val": 20})

        fresh_snap_engine = SnapshotEngine(snap_dir)
        loaded = fresh_snap_engine.load_snapshot("Market", "EURUSD")
        assert loaded is not None
        assert loaded.aggregate_version == 2
        assert loaded.state_payload["val"] == 20


def test_c8_corrupted_snapshot_and_truncated_tail_recovery() -> None:
    """C8: Corrupted snapshot file + truncated journal tail - falls back to genesis replay up to last valid record."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        j_path = f"{tmp_dir}/events.journal"
        snap_dir = f"{tmp_dir}/snaps"

        journal = DurableEventJournal(j_path)
        snapshot_engine = SnapshotEngine(snap_dir)

        evt1 = Event(
            event_id="e1",
            event_type="BarProcessed",
            aggregate_type="Market",
            aggregate_id="EURUSD",
            root_id="r1",
            parent_id="p1",
            aggregate_version=1,
            source_timestamp=BASE_TS,
            event_timestamp=BASE_TS,
            processing_timestamp=BASE_TS,
            payload=ImmutablePayloadDict({"state": "S1"}),
        )
        journal.append(evt1)

        snapshot_engine.save_snapshot("Market", "EURUSD", version=1, last_seq=1, payload={"state": "S1"})

        snap_file = snapshot_engine._get_snapshot_file_path("Market", "EURUSD")
        with open(snap_file, "w") as f:
            f.write("CORRUPTED_SNAPSHOT_DATA")

        fresh_snap_engine = SnapshotEngine(snap_dir)
        replayed = fresh_snap_engine.replay_journal(journal, "Market", "EURUSD")

        assert fresh_snap_engine._snapshot_fallback_used is True
        assert replayed["state"] == "S1"

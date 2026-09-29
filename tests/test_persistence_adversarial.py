"""Adversarial Persistence, Journal Corruption, Global Sequence Integrity, Event-ID Uniqueness, and Tail Recovery Test Suite."""

import os
import tempfile
import threading

import pytest

from src.fractal_flow.domain.event import Event
from src.fractal_flow.domain.models import (
    BrokerDeal,
    DealEntryRole,
    ExecutionIntent,
    OrderSide,
    Position,
)
from src.fractal_flow.domain.risk_ledger import (
    AccountingInvariantException,
    LedgerOperation,
    OpportunityRiskLedger,
)
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.execution.reconciliation import (
    BrokerQueryQuality,
    ReconciliationEngine,
    ReconciliationMismatchType,
)
from src.fractal_flow.execution.recovery import (
    RecoveryEngine,
    RecoveryEvidence,
    RecoveryEvidenceError,
    RecoveryState,
)
from src.fractal_flow.persistence.interfaces import (
    DurableExecutionIntentRepository,
    IdempotencyConflictException,
)
from src.fractal_flow.persistence.journal import (
    DurableEventJournal,
    JournalCorruptionException,
    JournalDurabilityException,
)
from src.fractal_flow.persistence.snapshot import (
    SnapshotCorruptionException,
    SnapshotEngine,
)


def make_test_event(
    seq: int,
    event_id: str | None = None,
    aggregate_type: str = "Opportunity",
    aggregate_id: str = "agg_1",
    aggregate_version: int | None = None,
    payload: dict | None = None,
) -> Event:
    return Event(
        event_id=event_id or f"evt_{seq}",
        event_type="TEST_EVENT",
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        root_id="root_1",
        parent_id="par_1",
        aggregate_version=aggregate_version or seq,
        source_timestamp=1000,
        event_timestamp=1000,
        processing_timestamp=1000,
        payload=payload or {"data": f"test_{seq}"},
    )


def test_p42_01_06_durable_journal_append_and_corruption_detection() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1))
        journal.append(make_test_event(2))

        # Reload journal from file
        journal_reloaded = DurableEventJournal(journal_file_path=path)
        assert len(journal_reloaded.get_all_records()) == 2

        # Corrupt file
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 3, "event": {}, "checksum": "corrupted"}\n')

        with pytest.raises(JournalCorruptionException):
            DurableEventJournal(journal_file_path=path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_fsync_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    fsync_called = []

    def mock_fsync(fd: int) -> None:
        fsync_called.append(fd)

    monkeypatch.setattr(os, "fsync", mock_fsync)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1))
        assert len(fsync_called) == 1
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_fsync_failure_propagation_and_state_non_advancement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_fsync_fail(fd: int) -> None:
        raise OSError("Disk flush failed")

    monkeypatch.setattr(os, "fsync", mock_fsync_fail)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)

        with pytest.raises((OSError, JournalDurabilityException)):
            journal.append(make_test_event(1))

        # In-memory sequence and records must NOT have advanced!
        assert journal._global_sequence == 0
        assert len(journal.get_all_records()) == 0
        assert "evt_1" not in journal._event_ids
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_physical_file_rollback_on_append_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))
        initial_size = os.path.getsize(path)

        # Mock fsync to fail on second append
        def mock_fsync_fail(fd: int) -> None:
            raise OSError("I/O error during fsync")

        monkeypatch.setattr(os, "fsync", mock_fsync_fail)

        with pytest.raises(JournalDurabilityException):
            journal.append(make_test_event(2, event_id="e2"))

        # Physical file size must be rolled back to initial size!
        assert os.path.getsize(path) == initial_size
        assert journal._global_sequence == 1
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_rollback_fsync_failure_faults_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        def mock_fsync_always_fail(fd: int) -> None:
            raise OSError("I/O error on fsync")

        monkeypatch.setattr(os, "fsync", mock_fsync_always_fail)

        with pytest.raises(JournalDurabilityException):
            journal.append(make_test_event(2, event_id="e2"))

        # The journal should now be in a faulted state!
        assert journal._faulted is True

        # Un-mock fsync
        monkeypatch.undo()

        # Attempting append on a faulted journal MUST be rejected!
        with pytest.raises(JournalDurabilityException) as exc:
            journal.append(make_test_event(2, event_id="e2_retry"))
        assert "faulted" in str(exc.value).lower()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_restart_after_failed_append(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        def mock_fsync_fail(fd: int) -> None:
            raise OSError("Disk failure")

        monkeypatch.setattr(os, "fsync", mock_fsync_fail)

        with pytest.raises(JournalDurabilityException):
            journal.append(make_test_event(2, event_id="e2_fail"))

        # Un-mock fsync
        monkeypatch.undo()

        # Restart journal from disk
        restarted = DurableEventJournal(journal_file_path=path)
        assert len(restarted.get_all_records()) == 1
        assert restarted._global_sequence == 1
        assert "e2_fail" not in restarted._event_ids

        # Next successful append receives sequence number 2
        rec2 = restarted.append(make_test_event(2, event_id="e2_success"))
        assert rec2.sequence_number == 2
        assert len(restarted.get_all_records()) == 2
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_global_sequence_gap_rejection() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1", aggregate_version=1))

        # Inject sequence gap in file (seq 1, then seq 4)
        with open(path, "a", encoding="utf-8") as f:
            evt_json = '{"sequence_number": 4, "event": {"event_id": "e4", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 2, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "abc"}\n'
            f.write(evt_json)

        with pytest.raises(JournalCorruptionException) as exc:
            DurableEventJournal(journal_file_path=path)
        assert "sequence" in str(exc.value).lower()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_global_sequence_duplicate_rejection() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1", aggregate_version=1))

        # Inject duplicate global sequence 1
        with open(path, "a", encoding="utf-8") as f:
            evt_json = '{"sequence_number": 1, "event": {"event_id": "e2", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 2, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "abc"}\n'
            f.write(evt_json)

        with pytest.raises(JournalCorruptionException) as exc:
            DurableEventJournal(journal_file_path=path)
        assert "sequence" in str(exc.value).lower()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_global_sequence_regression_rejection() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1", aggregate_version=1))

        # Inject regressed global sequence 0
        with open(path, "a", encoding="utf-8") as f:
            evt_json = '{"sequence_number": 0, "event": {"event_id": "e2", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 2, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "abc"}\n'
            f.write(evt_json)

        with pytest.raises(JournalCorruptionException):
            DurableEventJournal(journal_file_path=path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_type_safety_validation() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        # Inject boolean sequence_number: true
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                '{"sequence_number": true, "event": {"event_id": "e1", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 1, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "abc"}\n'
            )

        with pytest.raises(JournalCorruptionException) as exc:
            DurableEventJournal(journal_file_path=path)
        assert "Invalid sequence number type" in str(exc.value)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_duplicate_event_id_append_rejection() -> None:
    journal = DurableEventJournal()
    journal.append(make_test_event(1, event_id="evt_unique"))

    with pytest.raises(JournalCorruptionException) as exc:
        journal.append(make_test_event(2, event_id="evt_unique"))
    assert "Duplicate event_id" in str(exc.value)


def test_journal_duplicate_event_id_after_restart_rejection() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="evt_unique_1"))

        # Reopen journal from file
        reloaded = DurableEventJournal(journal_file_path=path)
        assert len(reloaded.get_all_records()) == 1

        # Attempt reusing event_id = evt_unique_1 must fail
        with pytest.raises(JournalCorruptionException) as exc:
            reloaded.append(make_test_event(2, event_id="evt_unique_1"))
        assert "Duplicate event_id" in str(exc.value)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_duplicate_event_id_conflicting_payload_rejection() -> None:
    journal = DurableEventJournal()
    journal.append(make_test_event(1, event_id="evt_same", payload={"p": "first"}))

    with pytest.raises(JournalCorruptionException):
        journal.append(make_test_event(2, event_id="evt_same", payload={"p": "different"}))


@pytest.mark.parametrize(
    "truncated_fragment",
    [
        '{"sequence_number": 3, "event": {"event_id": "e3"',
        '{"sequence_number": 3, "event": {"event_id": "e3", "event_type": "TEST',
        '{"sequence_number": 3, "event": {"payload": {"nested":',
        '{"sequence_number": 3, "event": {"payload": [1, 2',
        '{"sequence_number": 3, "event": {"payload": "abc\\',
    ],
)
def test_journal_genuine_truncation_recovery_matrix(truncated_fragment: str) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))
        journal.append(make_test_event(2, event_id="e2"))

        # Append incomplete JSON fragment at EOF
        with open(path, "a", encoding="utf-8") as f:
            f.write(truncated_fragment)

        recovered = DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert len(recovered.get_all_records()) == 2
        assert recovered._global_sequence == 2

        # Next append receives sequence number 3
        rec3 = recovered.append(make_test_event(3, event_id="e3"))
        assert rec3.sequence_number == 3
    finally:
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.parametrize(
    "malformed_fragment",
    [
        '{"sequence_number": 3, "event": INVALID}\n',
        '{"sequence_number": 3, "event": {}, "checksum": "x",}\n',
        '{"sequence_number": 3, "event": {"x": "bad\\q"}}\n',
    ],
)
def test_journal_malformed_eof_fails_closed_matrix(malformed_fragment: str) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        # Append complete malformed JSON line at EOF
        with open(path, "a", encoding="utf-8") as f:
            f.write(malformed_fragment)

        # Must FAIL CLOSED even when truncate_corrupted_tail=True!
        with pytest.raises(JournalCorruptionException):
            DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_physical_file_truncation_proof_and_bytes_match() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))
        journal.append(make_test_event(2, event_id="e2"))

        # Capture exact valid file size and bytes before fragment append
        expected_valid_size = os.path.getsize(path)
        with open(path, "rb") as f:
            expected_valid_bytes = f.read()

        # Append truncated JSON fragment
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 3, "event": {"event_id": "e3"')

        assert os.path.getsize(path) > expected_valid_size

        # Recover with truncate_corrupted_tail=True
        recovered = DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert len(recovered.get_all_records()) == 2

        # Verify physical file size and exact bytes match expected_valid_bytes
        actual_size = os.path.getsize(path)
        assert actual_size == expected_valid_size

        with open(path, "rb") as f:
            actual_bytes = f.read()
        assert actual_bytes == expected_valid_bytes

        # Verify recovery idempotency: reloading clean file does not perform further truncation
        reloaded = DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert len(reloaded.get_all_records()) == 2
        assert os.path.getsize(path) == expected_valid_size
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_tail_recovery_fsync_durability_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        # Append incomplete JSON fragment
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 2, "event": {"event_id": "e2"')

        # Mock fsync during tail recovery to raise OSError
        def mock_fsync_fail(fd: int) -> None:
            raise OSError("I/O error during tail recovery fsync")

        monkeypatch.setattr(os, "fsync", mock_fsync_fail)

        with pytest.raises(JournalDurabilityException) as exc:
            DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert "recovery failed to fsync" in str(exc.value).lower()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_tail_recovery_matrix_valid_json_bad_checksum_fails() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        # Append complete valid JSON at EOF but with BAD CHECKSUM
        with open(path, "a", encoding="utf-8") as f:
            evt_json = '{"sequence_number": 2, "event": {"event_id": "e2", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 2, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "bad_checksum_hash"}\n'
            f.write(evt_json)

        # Valid JSON with bad checksum at EOF MUST FAIL CLOSED even when truncate_corrupted_tail=True!
        with pytest.raises(JournalCorruptionException) as exc:
            DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert "checksum mismatch" in str(exc.value).lower()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_corrupted_middle_record_fail_closed() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        # Inject malformed line in middle
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 2, "corrupted_json": true\n')

        # Append valid record 3 after corrupted line 2
        with open(path, "a", encoding="utf-8") as f:
            evt_json = '{"sequence_number": 3, "event": {"event_id": "e3", "event_type": "TEST_EVENT", "aggregate_type": "Opportunity", "aggregate_id": "agg_1", "root_id": "r1", "parent_id": "p1", "aggregate_version": 2, "source_timestamp": 1000, "event_timestamp": 1000, "processing_timestamp": 1000, "payload": {}}, "checksum": "abc"}\n'
            f.write(evt_json)

        # Middle corruption fails closed even when truncate_corrupted_tail=True
        with pytest.raises(JournalCorruptionException):
            DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_interleaved_aggregates_sequencing() -> None:
    journal = DurableEventJournal()

    r1 = journal.append(make_test_event(1, event_id="e1", aggregate_id="A", aggregate_version=1))
    r2 = journal.append(make_test_event(2, event_id="e2", aggregate_id="B", aggregate_version=1))
    r3 = journal.append(make_test_event(3, event_id="e3", aggregate_id="A", aggregate_version=2))
    r4 = journal.append(make_test_event(4, event_id="e4", aggregate_id="B", aggregate_version=2))

    assert r1.sequence_number == 1
    assert r2.sequence_number == 2
    assert r3.sequence_number == 3
    assert r4.sequence_number == 4

    events_a = journal.get_events_for_aggregate("Opportunity", "A")
    events_b = journal.get_events_for_aggregate("Opportunity", "B")

    assert [e.aggregate_version for e in events_a] == [1, 2]
    assert [e.aggregate_version for e in events_b] == [1, 2]


def test_journal_concurrent_durable_file_appends() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(1, 11):
                    evt = Event(
                        event_id=f"evt_w{worker_id}_{i}",
                        event_type="TEST_EVENT",
                        aggregate_type="Opportunity",
                        aggregate_id=f"agg_w{worker_id}",
                        root_id="root_1",
                        parent_id="par_1",
                        aggregate_version=i,
                        source_timestamp=1000,
                        event_timestamp=1000,
                        processing_timestamp=1000,
                        payload={"worker": worker_id, "i": i},
                    )
                    journal.append(evt)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(journal.get_all_records()) == 50

        # Reload from disk in a fresh journal instance and verify exact contiguity
        reloaded = DurableEventJournal(journal_file_path=path)
        reloaded_records = reloaded.get_all_records()
        assert len(reloaded_records) == 50

        seqs = [r.sequence_number for r in reloaded_records]
        assert seqs == list(range(1, 51))  # Global sequence is strictly contiguous 1..50!
        assert len(reloaded._event_ids) == 50
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_snapshot_journal_exact_boundary_equivalence() -> None:
    with (
        tempfile.TemporaryDirectory() as snap_dir,
        tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp,
    ):
        journal_path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=journal_path)
        for i in range(1, 11):
            journal.append(
                make_test_event(
                    i,
                    event_id=f"evt_b_{i}",
                    aggregate_id="agg_bound",
                    aggregate_version=i,
                    payload={"count": i},
                )
            )

        snap_engine = SnapshotEngine(snapshot_dir=snap_dir)
        snap_engine.save_snapshot("Opportunity", "agg_bound", version=5, last_seq=5, payload={"count": 5})

        def counter_reducer(state: dict, evt: Event) -> dict:
            state["count"] = evt.payload["count"]
            return state

        snap_engine.register_reducer("TEST_EVENT", counter_reducer)

        # Path 1: Snapshot @ 5 + journal replay 6..10
        state_from_snap = snap_engine.replay_journal(journal, "Opportunity", "agg_bound")
        assert state_from_snap["count"] == 10
        assert state_from_snap["_last_seq"] == 10

        # Path 2: Full genesis journal replay (no snapshot)
        genesis_snap_engine = SnapshotEngine()  # Empty snapshot engine
        genesis_snap_engine.register_reducer("TEST_EVENT", counter_reducer)
        state_from_genesis = genesis_snap_engine.replay_journal(journal, "Opportunity", "agg_bound")
        assert state_from_genesis["count"] == 10
        assert state_from_genesis["_last_seq"] == 10

        # States must be identical
        assert state_from_snap["count"] == state_from_genesis["count"]
    finally:
        if os.path.exists(journal_path):
            os.remove(journal_path)


def test_p422_snapshot_sequence_for_wrong_aggregate_rejected() -> None:
    journal = DurableEventJournal()
    journal.append(make_test_event(1, event_id="e1", aggregate_id="A", aggregate_version=1))
    journal.append(make_test_event(2, event_id="e2", aggregate_id="A", aggregate_version=2))
    journal.append(make_test_event(3, event_id="e3", aggregate_id="B", aggregate_version=1))  # seq 3 belongs to B!

    snap_engine = SnapshotEngine()
    # Snapshot for A claiming sequence 3 (which belongs to B)
    snap = snap_engine.save_snapshot("Opportunity", "A", version=2, last_seq=3, payload={"state": "OPP_VALID"})

    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.validate_snapshot_boundary(snap, journal, "Opportunity", "A")
    assert "does not belong to aggregate" in str(exc.value)


def test_p422_snapshot_aggregate_version_mismatch_at_boundary_rejected() -> None:
    journal = DurableEventJournal()
    journal.append(make_test_event(1, event_id="e1", aggregate_id="A", aggregate_version=1))
    journal.append(make_test_event(2, event_id="e2", aggregate_id="A", aggregate_version=2))

    snap_engine = SnapshotEngine()
    # Snapshot claiming sequence 2 but aggregate_version 99 (when journal has aggregate_version 2)
    snap = snap_engine.save_snapshot("Opportunity", "A", version=99, last_seq=2, payload={"state": "OPP_VALID"})

    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.validate_snapshot_boundary(snap, journal, "Opportunity", "A")
    assert "version mismatch" in str(exc.value).lower()


def test_p422_snapshot_ahead_of_journal_head_rejected() -> None:
    journal = DurableEventJournal()
    journal.append(make_test_event(1, event_id="e1", aggregate_id="A", aggregate_version=1))

    snap_engine = SnapshotEngine()
    snap = snap_engine.save_snapshot("Opportunity", "A", version=5, last_seq=999, payload={"state": "OPP_VALID"})

    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.validate_snapshot_boundary(snap, journal, "Opportunity", "A")
    assert "exceeds journal head" in str(exc.value).lower()


def test_p422_corrupt_snapshot_fallback_records_evidence_flags() -> None:
    with (
        tempfile.TemporaryDirectory() as snap_dir,
        tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp,
    ):
        journal_path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=journal_path)
        journal.append(
            make_test_event(
                1,
                event_id="e1",
                aggregate_id="A",
                aggregate_version=1,
                payload={"x": 10},
            )
        )

        snap_engine = SnapshotEngine(snapshot_dir=snap_dir)
        snap_engine.save_snapshot("Opportunity", "A", version=1, last_seq=1, payload={"x": 10})

        # Corrupt snapshot file and clear in-memory cache
        snap_file = snap_engine._get_snapshot_file_path("Opportunity", "A")
        with open(snap_file, "w", encoding="utf-8") as f:
            f.write('{"aggregate_type": "Opportunity", "checksum": "invalid"}')

        snap_engine._snapshots.clear()

        reconstructed = snap_engine.replay_journal(journal, "Opportunity", "A")
        assert reconstructed["_snapshot_valid"] is False
        assert reconstructed["_snapshot_fallback_used"] is True
        assert reconstructed["x"] == 10
    finally:
        if os.path.exists(journal_path):
            os.remove(journal_path)


def test_p422_recovery_evidence_gate_matrix_individual_failures() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()
    session_id = rec_engine.session_id
    rec_engine.start_reconciliation()

    # Self-attested legacy booleans alone MUST NOT satisfy evidence
    legacy_only_ev = RecoveryEvidence(
        persistence_integrity_valid=True,
        journal_integrity_valid=True,
        snapshot_integrity_valid=True,
        risk_ledger_reconstructed=True,
        execution_intents_reconstructed=True,
        broker_reconciliation_complete=True,
        unresolved_unknown_count=0,
        configuration_identity_matched=True,
        protective_monitoring_active=True,
    )
    assert legacy_only_ev.is_satisfactory() is False

    # Unauthorized factory should produce unsatisfactory evidence
    unauth_ev = RecoveryEvidence.create_authoritative_evidence(session_id=session_id)
    assert unauth_ev.is_satisfactory(required_session=session_id) is False


def test_p422_illegal_recovery_state_transitions_rejected() -> None:
    rec_engine = RecoveryEngine()

    # Attempting complete_recovery_with_evidence from NORMAL state must raise RecoveryEvidenceError or ValueError
    good_evidence = RecoveryEvidence.create_authoritative_evidence(session_id=rec_engine.session_id)

    with pytest.raises(ValueError) as exc:
        rec_engine.complete_recovery_with_evidence(good_evidence)
    assert "Cannot complete recovery with evidence from state" in str(exc.value)


def test_p422_execution_intent_fingerprint_order_type_mutation_rejected() -> None:
    repo = DurableExecutionIntentRepository()
    intent1 = ExecutionIntent(
        intent_id="intent_opt_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_opt_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={"tp1": 1.0900},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=1000,
        updated_at=1000,
        order_type="MARKET_BUY",
    )
    repo.save_intent(intent1)

    # Attempt reusing idempotency key with OrderType mutation (MARKET -> BUY_LIMIT)
    intent_mutated = ExecutionIntent(
        intent_id="intent_opt_2",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_opt_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={"tp1": 1.0900},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=1000,
        updated_at=1000,
        order_type="BUY_LIMIT",  # Mutated order_type!
    )

    with pytest.raises(IdempotencyConflictException):
        repo.save_intent(intent_mutated)


def test_p422_deal_chain_partial_close_and_contradiction_semantics() -> None:
    intent = ExecutionIntent(
        intent_id="intent_deal_pc",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_deal_pc",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={"contract_size": 100000.0},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_FILLED",
        created_at=1000,
        updated_at=1000,
    )

    pos = Position(
        position_id="POS_PC",
        intent_id="intent_deal_pc",
        order_id="ORD_OPEN",
        symbol="EURUSD",
        side="BUY",
        requested_volume=1.0,
        filled_volume=0.6,  # 1.0 open - 0.4 close = 0.6 net filled remaining
        remaining_volume=0.0,
        entry_price=1.0850,
        current_sl=1.0820,
        lifecycle_state="POS_ACTIVE",
        health_state="HEALTH_HEALTHY",
        opened_at=1000,
    )

    deal_open = BrokerDeal(
        deal_id="DEAL_OPEN",
        order_id="ORD_OPEN",
        position_id="POS_PC",
        symbol="EURUSD",
        side="BUY",
        volume=1.0,
        price=1.0850,
        commission=1.5,
        timestamp=1000,
        entry_role=DealEntryRole.OPEN,
    )

    deal_close = BrokerDeal(
        deal_id="DEAL_CLOSE",
        order_id="ORD_CLOSE",
        position_id="POS_PC",
        symbol="EURUSD",
        side="SELL",
        volume=0.4,
        price=1.0880,
        commission=1.5,
        timestamp=1100,
        entry_role=DealEntryRole.CLOSE,
    )

    res = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={"POS_PC": pos},
        broker_deals={"DEAL_OPEN": deal_open, "DEAL_CLOSE": deal_close},
    )

    assert res.mismatch_type == ReconciliationMismatchType.MATCH
    assert res.resolved_execution_state == ExecutionState.EXEC_FILLED


def test_reconciliation_and_recovery_idempotency_stability() -> None:
    intent = ExecutionIntent(
        intent_id="intent_idem_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_idem_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={"contract_size": 100000.0},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_SUBMITTED",
        created_at=1000,
        updated_at=1000,
    )

    pos = Position(
        position_id="POS_IDEM",
        intent_id="intent_idem_1",
        order_id="ORD_IDEM",
        symbol="EURUSD",
        side="BUY",
        requested_volume=1.0,
        filled_volume=1.0,
        remaining_volume=0.0,
        entry_price=1.0850,
        current_sl=1.0820,
        lifecycle_state="POS_ACTIVE",
        health_state="HEALTH_HEALTHY",
        opened_at=1000,
    )

    # Run reconcile_broker_wide 3 times in succession
    res1 = ReconciliationEngine.reconcile_broker_wide({"intent_idem_1": intent}, {}, {"POS_IDEM": pos})
    res2 = ReconciliationEngine.reconcile_broker_wide({"intent_idem_1": intent}, {}, {"POS_IDEM": pos})
    res3 = ReconciliationEngine.reconcile_broker_wide({"intent_idem_1": intent}, {}, {"POS_IDEM": pos})

    assert res1 == res2 == res3
    assert res1[0].resolved_execution_state == ExecutionState.EXEC_FILLED


def test_p42_15_16_idempotency_fingerprint_conflict() -> None:
    repo = DurableExecutionIntentRepository()
    intent1 = ExecutionIntent(
        intent_id="intent_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=1000,
        updated_at=1000,
    )
    repo.save_intent(intent1)

    intent2 = ExecutionIntent(
        intent_id="intent_2",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=2.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_READY",
        created_at=1000,
        updated_at=100,
    )
    with pytest.raises(IdempotencyConflictException):
        repo.save_intent(intent2)


def test_p42_27_33_risk_ledger_exact_accounting_and_corruption_rejection() -> None:
    ledger = OpportunityRiskLedger("b1", "opp_1", total_risk=500.0, total_volume=1.0)
    ledger.record_operation(
        "e1",
        LedgerOperation.RESERVE,
        amount=200.0,
        volume=0.4,
        reference_id="r1",
        causation_id="c1",
        timestamp=1000,
    )
    assert ledger.remaining_risk == 300.0

    with pytest.raises(AccountingInvariantException):
        ledger.record_operation(
            "e2",
            LedgerOperation.ALLOCATE,
            amount=600.0,
            volume=1.2,
            reference_id="r2",
            causation_id="c2",
            timestamp=1000,
        )


def test_p42_34_40_recovery_engine_and_reconciliation_gating() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()

    assert rec_engine.can_authorize_strategic_action() is False

    rec_engine.start_reconciliation()
    # Boolean shortcut complete_recovery(True) does NOT authorize strategic execution
    rec_engine.complete_recovery(reconciliation_successful=True)
    assert rec_engine.can_authorize_strategic_action() is False


def test_p42_07_08_snapshot_engine_checksum_verification() -> None:
    snap_engine = SnapshotEngine()
    snap = snap_engine.save_snapshot("Opportunity", "opp_1", version=1, last_seq=1, payload={"state": "OPP_VALID"})

    loaded = snap_engine.load_snapshot("Opportunity", "opp_1")
    assert loaded is not None
    assert loaded.checksum == snap.checksum


def test_forensic_evidence_provenance_session_mismatch_rejected() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()
    rec_engine.start_reconciliation()

    # Create evidence with wrong/stale session ID in provenance
    bad_session_evidence = RecoveryEvidence.create_authoritative_evidence(session_id="wrong_stale_session_id")

    with pytest.raises((ValueError, RecoveryEvidenceError)) as exc:
        rec_engine.complete_recovery_with_evidence(bad_session_evidence)
    assert rec_engine.can_authorize_strategic_action() is False


def test_forensic_orphan_count_blocks_recovery_authorization() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()
    rec_engine.start_reconciliation()

    # Evidence with orphaned_count = 1
    orphan_evidence = RecoveryEvidence.create_authoritative_evidence(session_id=rec_engine.session_id, orphaned_count=1)

    with pytest.raises((ValueError, RecoveryEvidenceError)) as exc:
        rec_engine.complete_recovery_with_evidence(orphan_evidence)
    assert rec_engine.state == RecoveryState.SAFE
    assert rec_engine.can_authorize_strategic_action() is False


def test_forensic_broker_query_provider_authority_boundary() -> None:
    from src.fractal_flow.execution.reconciliation import BrokerQueryProvider

    intent = ExecutionIntent(
        intent_id="intent_q_bound",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_q_bound",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_SUBMITTED",
        created_at=1000,
        updated_at=1000,
    )

    # 1. Query Provider returning NOT_FOUND_NON_AUTHORITATIVE
    non_auth_provider = BrokerQueryProvider(authority=BrokerQueryQuality.NOT_FOUND_NON_AUTHORITATIVE)
    query_res_non_auth = non_auth_provider.query_broker_state()

    rec_res1 = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={},
        query_result=query_res_non_auth,
    )
    assert rec_res1.resolved_execution_state == ExecutionState.EXEC_UNKNOWN

    # 2. Query Provider returning STALE
    stale_provider = BrokerQueryProvider(authority=BrokerQueryQuality.FOUND, max_age_seconds=10, query_timestamp=1000)
    query_res_stale = stale_provider.query_broker_state(current_timestamp=2000)
    assert query_res_stale.authority == BrokerQueryQuality.STALE

    rec_res2 = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={},
        query_result=query_res_stale,
    )
    assert rec_res2.resolved_execution_state == ExecutionState.EXEC_UNKNOWN

    # 3. Un-capability-backed Query Provider attempting NOT_FOUND_AUTHORITATIVE fails closed to EXEC_UNKNOWN
    unauth_provider = BrokerQueryProvider(authority=BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE)
    query_res_unauth = unauth_provider.query_broker_state()

    rec_res_unauth = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={},
        query_result=query_res_unauth,
    )
    assert rec_res_unauth.resolved_execution_state == ExecutionState.EXEC_UNKNOWN

    # 4. Authoritative query with legitimate BROKER_QUERY capability succeeds in asserting EXEC_REJECTED
    from src.fractal_flow.execution.reconciliation import AuthoritativeBrokerAdapter
    from src.fractal_flow.execution.recovery import AuthorityBootstrap, CapabilityRole

    bootstrap = AuthorityBootstrap()
    b_cap = bootstrap.mint_producer_capability(CapabilityRole.BROKER_QUERY, "TestBrokerAdapter")
    bootstrap.finalize()

    auth_adapter = AuthoritativeBrokerAdapter(
        capability=b_cap,
        authority=BrokerQueryQuality.NOT_FOUND_AUTHORITATIVE,
    )
    query_res_auth = auth_adapter.query_broker_state(session_id="sess_test")

    rec_res3 = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={},
        query_result=query_res_auth,
    )
    assert rec_res3.resolved_execution_state == ExecutionState.EXEC_REJECTED


def test_forensic_snapshot_state_hash_mismatch_rejected() -> None:
    from src.fractal_flow.persistence.snapshot import AggregateSnapshot

    snap_engine = SnapshotEngine()
    snap = snap_engine.save_snapshot("Opportunity", "opp_hash", version=1, last_seq=1, payload={"val": 100})

    # Mutate in-memory snapshot state_hash maliciously
    key = "Opportunity:opp_hash"
    mutated_snap = AggregateSnapshot(
        aggregate_type=snap.aggregate_type,
        aggregate_id=snap.aggregate_id,
        aggregate_version=snap.aggregate_version,
        last_sequence_number=snap.last_sequence_number,
        state_payload=snap.state_payload,
        checksum=snap.checksum,
        state_hash="forged_state_hash_value",
        schema_version=snap.schema_version,
        created_at=snap.created_at,
    )
    snap_engine._snapshots[key] = mutated_snap

    with pytest.raises(SnapshotCorruptionException) as exc:
        snap_engine.load_snapshot("Opportunity", "opp_hash")
    assert "state hash mismatch" in str(exc.value).lower()


def test_forensic_deal_chain_contradictions_and_duplicate_deals_rejected() -> None:
    intent = ExecutionIntent(
        intent_id="intent_dup_deal",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_dup_deal",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=1.0,
        entry_price=1.0850,
        sl=1.0820,
        tp_plan={},
        effective_config_id="cfg_1",
        lineage_version=1,
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=1.0,
        status="EXEC_FILLED",
        created_at=1000,
        updated_at=1000,
    )

    pos = Position(
        position_id="POS_DUP",
        intent_id="intent_dup_deal",
        order_id="ORD_OPEN",
        symbol="EURUSD",
        side="BUY",
        requested_volume=1.0,
        filled_volume=1.0,
        remaining_volume=0.0,
        entry_price=1.0850,
        current_sl=1.0820,
        lifecycle_state="POS_ACTIVE",
        health_state="HEALTH_HEALTHY",
        opened_at=1000,
    )

    deal1 = BrokerDeal(
        deal_id="DEAL_SAME_ID",
        order_id="ORD_OPEN",
        position_id="POS_DUP",
        symbol="EURUSD",
        side="BUY",
        volume=1.0,
        price=1.0850,
        commission=1.5,
        timestamp=1000,
        entry_role=DealEntryRole.OPEN,
    )

    # Duplicate deal with same deal_id
    deal2 = BrokerDeal(
        deal_id="DEAL_SAME_ID",
        order_id="ORD_OPEN",
        position_id="POS_DUP",
        symbol="EURUSD",
        side="BUY",
        volume=1.0,
        price=1.0850,
        commission=1.5,
        timestamp=1005,
        entry_role=DealEntryRole.OPEN,
    )

    res = ReconciliationEngine.reconcile_intent(
        local_intent=intent,
        broker_orders={},
        broker_positions={"POS_DUP": pos},
        broker_deals={"d1": deal1, "d2": deal2},
    )

    assert res.mismatch_type == ReconciliationMismatchType.DEAL_CONTRADICTION
    assert res.resolved_execution_state == ExecutionState.EXEC_UNKNOWN

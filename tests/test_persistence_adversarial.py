"""Adversarial Persistence, Journal Corruption, Global Sequence Integrity, Event-ID Uniqueness, and Tail Recovery Test Suite."""

import pytest
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from src.fractal_flow.domain.event import Event, InvalidEventVersionException
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalCorruptionException
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository, IdempotencyConflictException
from src.fractal_flow.domain.models import ExecutionIntent, OrderSide, Position
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger, LedgerOperation, AccountingInvariantException
from src.fractal_flow.execution.recovery import RecoveryEngine, RecoveryState
from src.fractal_flow.execution.reconciliation import ReconciliationEngine, ReconciliationMismatchType
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.persistence.snapshot import SnapshotEngine, SnapshotCorruptionException


def make_test_event(
    seq: int,
    event_id: Optional[str] = None,
    aggregate_type: str = "Opportunity",
    aggregate_id: str = "agg_1",
    aggregate_version: Optional[int] = None,
    payload: Optional[dict] = None,
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


def test_journal_fsync_failure_propagation_and_state_non_advancement(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_fsync_fail(fd: int) -> None:
        raise OSError("Disk flush failed")

    monkeypatch.setattr(os, "fsync", mock_fsync_fail)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)

        with pytest.raises(OSError):
            journal.append(make_test_event(1))

        # In-memory sequence and records must NOT have advanced!
        assert journal._global_sequence == 0
        assert len(journal.get_all_records()) == 0
        assert "evt_1" not in journal._event_ids
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


def test_journal_truncated_final_record_recovery() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))
        journal.append(make_test_event(2, event_id="e2"))

        # Append incomplete JSON fragment at EOF
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 3, "event": {"event_id": "e3"')

        # Truncation recovery policy cleans up incomplete EOF frame
        recovered = DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=True)
        assert len(recovered.get_all_records()) == 2
        assert recovered._global_sequence == 2

        # Next append receives sequence number 3
        rec3 = recovered.append(make_test_event(3, event_id="e3"))
        assert rec3.sequence_number == 3
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


def test_journal_truncated_final_record_fail_closed_when_flag_disabled() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        path = tmp.name

    try:
        journal = DurableEventJournal(journal_file_path=path)
        journal.append(make_test_event(1, event_id="e1"))

        with open(path, "a", encoding="utf-8") as f:
            f.write('{"sequence_number": 2, "event": {"event_id": "e2"')

        # Default policy (truncate_corrupted_tail=False) fails closed
        with pytest.raises(JournalCorruptionException):
            DurableEventJournal(journal_file_path=path, truncate_corrupted_tail=False)
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


def test_journal_concurrent_appends() -> None:
    journal = DurableEventJournal()
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
    records = journal.get_all_records()
    assert len(records) == 50

    seqs = [r.sequence_number for r in records]
    assert seqs == list(range(1, 51))  # Global sequence is contiguous 1..50!


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
    ledger.record_operation("e1", LedgerOperation.RESERVE, amount=200.0, volume=0.4, reference_id="r1", causation_id="c1", timestamp=1000)
    assert ledger.remaining_risk == 300.0

    with pytest.raises(AccountingInvariantException):
        ledger.record_operation("e2", LedgerOperation.ALLOCATE, amount=600.0, volume=1.2, reference_id="r2", causation_id="c2", timestamp=1000)


def test_p42_34_40_recovery_engine_and_reconciliation_gating() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()

    assert rec_engine.can_authorize_strategic_action() is False

    rec_engine.start_reconciliation()
    rec_engine.complete_recovery(reconciliation_successful=True)
    assert rec_engine.can_authorize_strategic_action() is True


def test_p42_07_08_snapshot_engine_checksum_verification() -> None:
    snap_engine = SnapshotEngine()
    snap = snap_engine.save_snapshot("Opportunity", "opp_1", version=1, last_seq=1, payload={"state": "OPP_VALID"})

    loaded = snap_engine.load_snapshot("Opportunity", "opp_1")
    assert loaded is not None
    assert loaded.checksum == snap.checksum

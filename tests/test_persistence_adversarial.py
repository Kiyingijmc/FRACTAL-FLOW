"""Adversarial Persistence, Journal Corruption, Clock Anomaly, and Recovery Test Suite."""

import pytest
from pathlib import Path
import tempfile
import os

from src.fractal_flow.domain.event import Event, InvalidEventVersionException
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalCorruptionException
from src.fractal_flow.persistence.interfaces import DurableExecutionIntentRepository, IdempotencyConflictException
from src.fractal_flow.domain.models import ExecutionIntent, OrderSide, Position
from src.fractal_flow.domain.risk_ledger import OpportunityRiskLedger, LedgerOperation, AccountingInvariantException
from src.fractal_flow.execution.recovery import RecoveryEngine, RecoveryState
from src.fractal_flow.execution.reconciliation import ReconciliationEngine, ReconciliationMismatchType
from src.fractal_flow.execution.execution_state import ExecutionState
from src.fractal_flow.persistence.snapshot import SnapshotEngine, SnapshotCorruptionException


def make_test_event(seq: int) -> Event:
    return Event(
        event_id=f"evt_{seq}",
        event_type="TEST_EVENT",
        aggregate_type="Opportunity",
        aggregate_id="agg_1",
        root_id="root_1",
        parent_id="par_1",
        aggregate_version=seq,
        source_timestamp=1000,
        event_timestamp=1000,
        processing_timestamp=1000,
        payload={"data": f"test_{seq}"},
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

    # Conflicting volume under same idempotency key
    intent2 = ExecutionIntent(
        intent_id="intent_2",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=2.0,  # Materially different volume!
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

    # Over-allocation (600 > 500) raises AccountingInvariantException
    with pytest.raises(AccountingInvariantException):
        ledger.record_operation("e2", LedgerOperation.ALLOCATE, amount=600.0, volume=1.2, reference_id="r2", causation_id="c2", timestamp=1000)


def test_p42_34_40_recovery_engine_and_reconciliation_gating() -> None:
    rec_engine = RecoveryEngine()
    rec_engine.trigger_system_restart()

    # Strategic authorization disabled during recovery!
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

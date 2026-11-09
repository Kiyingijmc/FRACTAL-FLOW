"""Hostile G4 Unit 2 proofs for durable subscriber checkpoint sidecars."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.fractal_flow.data_engine.checkpoints import (
    CheckpointDurabilityError,
    CheckpointIntegrityError,
    CheckpointLockError,
    SubscriberCheckpoint,
    SubscriberCheckpointStore,
)
from src.fractal_flow.data_engine.contracts import (
    InstrumentAlias,
    InstrumentRegistry,
    LaneScope,
    RawQuote,
    SourceIdentity,
    VolumeSemantics,
)
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import CorrectionCursor, DurableCorrectionJournal
from src.fractal_flow.data_engine.journal_subscriber import (
    JournalBackedSubscriber,
    JournalDelivery,
    JournalReplayAuthority,
)
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.persistence.journal import DurableEventJournal


SECRET = b"g4-checkpoint-secret"
SUBSCRIBER_ID = "research-ui-eurusd"


def _quote(native_id: str, available_ns: int, source_id: str = "source-a") -> CanonicalQuote:
    source = SourceIdentity(source_id, "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(
        RawQuote(
            source,
            native_id,
            1,
            "EURUSD",
            available_ns - 2,
            available_ns - 1,
            available_ns,
            "1.10000",
            "1.10002",
            "1",
            VolumeSemantics.TICK_ACTIVITY_COUNT,
        )
    )
    assert result.quote is not None
    return result.quote


def _root(quote: CanonicalQuote) -> QuoteRevision:
    return QuoteRevision("r1", quote.event_id, None, RevisionOperation.UPSERT, quote.available_time_ns, quote)


def _setup(
    tmp_path: object,
) -> tuple[DurableEventJournal, DurableCorrectionJournal, CorrectionScope, JournalReplayAuthority, object]:
    path = tmp_path / "checkpoint.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    corrections = DurableCorrectionJournal(journal)
    quote = _quote("n1", 100)
    corrections.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    authority = JournalReplayAuthority(corrections, {scope.source.key})
    checkpoint_path = tmp_path / "subscriber.checkpoint"  # type: ignore[operator]
    return journal, corrections, scope, authority, checkpoint_path


def test_checkpoint_codec_is_canonical_and_binds_journal_subscriber_scope_and_cursor(tmp_path: object) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    cursor = corrections.cursor(scope)
    checkpoint = SubscriberCheckpoint.create(SUBSCRIBER_ID, scope, cursor, journal)
    assert SubscriberCheckpoint.from_bytes(checkpoint.to_bytes()) == checkpoint
    with pytest.raises(CheckpointIntegrityError, match="canonical"):
        SubscriberCheckpoint.from_bytes(checkpoint.to_bytes() + b"\n")
    store = SubscriberCheckpointStore(str(path), journal)
    store.commit(SUBSCRIBER_ID, scope, cursor, authority)
    assert store.load_verified(SUBSCRIBER_ID, scope, authority) == checkpoint
    store.close()


@pytest.mark.parametrize(
    "phase", ["BEFORE_CHECKPOINT_WRITE", "AFTER_CHECKPOINT_FILE_FSYNC", "BEFORE_CHECKPOINT_RENAME"]
)
def test_crash_before_rename_never_acknowledges_checkpoint(tmp_path: object, phase: str) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    store = SubscriberCheckpointStore(str(path), journal)
    store.set_fault_hook(
        lambda current, _checkpoint: (_ for _ in ()).throw(RuntimeError(current)) if current == phase else None
    )
    with pytest.raises(CheckpointDurabilityError, match="unacknowledged"):
        store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    assert not path.exists()  # type: ignore[union-attr]
    assert store.recovery_required
    store.close()


@pytest.mark.parametrize("phase", ["AFTER_CHECKPOINT_RENAME", "BEFORE_CHECKPOINT_DIRECTORY_FSYNC"])
def test_post_rename_uncertainty_requires_fresh_recovery_and_never_acknowledges(tmp_path: object, phase: str) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    store = SubscriberCheckpointStore(str(path), journal)
    store.set_fault_hook(
        lambda current, _checkpoint: (_ for _ in ()).throw(RuntimeError(current)) if current == phase else None
    )
    with pytest.raises(CheckpointDurabilityError, match="unacknowledged"):
        store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    assert store.recovery_required
    store.close()
    replacement = SubscriberCheckpointStore(str(path), journal)
    # Either no target or the renamed, fully fsynced file survived; both are
    # safe because restart validates against journal before use.
    loaded = replacement.load_verified(SUBSCRIBER_ID, scope, authority)
    assert loaded is None or loaded.cursor == corrections.cursor(scope)
    replacement.close()


def test_torn_checksum_wrong_identity_and_ahead_cursor_fail_closed(tmp_path: object) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    store = SubscriberCheckpointStore(str(path), journal)
    store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    store.close()
    path.write_bytes(b'{"schema_version":1')  # type: ignore[union-attr]
    torn = SubscriberCheckpointStore(str(path), journal)
    with pytest.raises(CheckpointIntegrityError):
        torn.load_verified(SUBSCRIBER_ID, scope, authority)
    torn.close()
    valid = SubscriberCheckpointStore(str(path), journal)
    ahead = SubscriberCheckpoint.create(SUBSCRIBER_ID, scope, CorrectionCursor(scope.partition_id, 999, 9), journal)
    valid.save(ahead)
    with pytest.raises(CheckpointIntegrityError, match="cursor"):
        valid.load_verified(SUBSCRIBER_ID, scope, authority)
    valid.close()


def test_wrong_subscriber_partition_and_replaced_journal_are_rejected(tmp_path: object) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    store = SubscriberCheckpointStore(str(path), journal)
    store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    with pytest.raises(CheckpointIntegrityError, match="subscriber"):
        store.load_verified("other-subscriber", scope, authority)
    foreign = _quote("foreign", 100, "foreign-source")
    with pytest.raises(CheckpointIntegrityError, match="partition"):
        store.load_verified(SUBSCRIBER_ID, CorrectionScope.from_quote(foreign), authority)
    store.close()
    replacement = tmp_path / "replacement.journal"  # type: ignore[operator]
    replacement.write_bytes(b"")
    journal.close()
    replacement.replace(journal.journal_file_path)  # type: ignore[arg-type]
    changed = DurableEventJournal(str(journal.journal_file_path))
    rejected = SubscriberCheckpointStore(str(path), changed)
    with pytest.raises(CheckpointIntegrityError, match="journal identity"):
        rejected.load_verified(SUBSCRIBER_ID, scope, authority)
    rejected.close()


def test_checkpoint_ownership_excludes_concurrent_subscriber_instances(tmp_path: object) -> None:
    journal, _corrections, _scope, _authority, path = _setup(tmp_path)
    owner = SubscriberCheckpointStore(str(path), journal)
    with pytest.raises(CheckpointLockError):
        SubscriberCheckpointStore(str(path), journal)
    owner.close()
    replacement = SubscriberCheckpointStore(str(path), journal)
    replacement.close()


def test_restart_replays_post_checkpoint_correction_and_accepts_verified_duplicate(tmp_path: object) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    store = SubscriberCheckpointStore(str(path), journal)
    store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    first = corrections.replay_batch_after(scope, CorrectionCursor(scope.partition_id, 0, 0)).records[0]
    second = corrections.append(
        QuoteRevision("r2", first.revision.logical_event_id, "r1", RevisionOperation.CANCEL, 200, None)
    )
    store.close()
    restarted_store = SubscriberCheckpointStore(str(path), journal)
    subscriber = JournalBackedSubscriber.restart_from_checkpoint(
        SECRET,
        scope,
        {scope.source.key},
        authority,
        restarted_store,
        SUBSCRIBER_ID,
        known_at_ns=200,
    )
    assert subscriber.checkpoint.aggregate_version == 2
    subscriber.receive(JournalDelivery.from_correction(first, SECRET), authority)
    assert subscriber.checkpoint.aggregate_version == 2
    assert [item.event_id for item in subscriber.visible()] == [first.event_id, second.event_id]
    restarted_store.close()


def test_directory_durability_unsupported_and_repeated_interrupted_recovery_fail_closed(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal, corrections, scope, authority, path = _setup(tmp_path)
    for _ in range(2):
        store = SubscriberCheckpointStore(str(path), journal)
        monkeypatch.setattr(
            store,
            "_fsync_directory",
            lambda: (_ for _ in ()).throw(CheckpointDurabilityError("directory fsync unsupported")),
        )
        with pytest.raises(CheckpointDurabilityError, match="unacknowledged"):
            store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
        assert store.recovery_required
        store.close()
    fresh = SubscriberCheckpointStore(str(path), journal)
    fresh.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    fresh.close()

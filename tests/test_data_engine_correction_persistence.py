"""Hostile proofs for the G3 durable correction authority boundary."""

from dataclasses import replace
from decimal import Decimal
import errno

import pytest

from src.fractal_flow.data_engine.contracts import (
    InstrumentAlias,
    InstrumentRegistry,
    LaneScope,
    RawQuote,
    SourceIdentity,
    VolumeSemantics,
)
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import (
    CorrectionCodecError,
    CorrectionScope,
    decode_correction,
    encode_correction,
)
from src.fractal_flow.data_engine.correction_persistence import (
    CorrectionPersistenceConflict,
    CorrectionPersistenceError,
    CorrectionStoreState,
    DurableCorrectionJournal,
)
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalCorruptionException
import src.fractal_flow.persistence.journal as journal_module


def _quote(native_id: str, available_ns: int, bid: str = "1.10000", source_name: str = "source-a") -> CanonicalQuote:
    source = SourceIdentity(source_name, "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(
        RawQuote(
            source,
            native_id,
            1,
            "EURUSD",
            100,
            110,
            available_ns,
            bid,
            "1.10002",
            "1",
            VolumeSemantics.TICK_ACTIVITY_COUNT,
        )
    )
    assert result.quote is not None
    return result.quote


def _root(quote: CanonicalQuote, revision_id: str = "r1") -> QuoteRevision:
    return QuoteRevision(revision_id, quote.event_id, None, RevisionOperation.UPSERT, quote.available_time_ns, quote)


def test_codec_round_trip_is_versioned_and_preserves_decimal_nanoseconds() -> None:
    quote = _quote("n1", 123_456_789_123, "1.10000")
    revision = _root(quote)
    event = encode_correction(revision, CorrectionScope.from_quote(quote), 1, DurableCorrectionJournal.ROOT_PARENT)
    decoded = decode_correction(type("Record", (), {"sequence_number": 7, "event": event})())
    assert decoded.revision == revision
    assert decoded.scope == CorrectionScope.from_quote(quote)
    assert decoded.journal_sequence == 7
    bad = replace(event, payload={**dict(event.payload), "schema_version": 999})
    with pytest.raises(CorrectionCodecError, match="unsupported"):
        decode_correction(type("Record", (), {"sequence_number": 8, "event": bad})())
    noncanonical = dict(event.payload)
    noncanonical_quote = dict(noncanonical["quote"])
    noncanonical_quote["bid"] = "1.1E+0"
    with pytest.raises(CorrectionCodecError, match="canonical fixed-point"):
        decode_correction(
            type(
                "Record",
                (),
                {"sequence_number": 9, "event": replace(event, payload={**noncanonical, "quote": noncanonical_quote})},
            )()
        )


def test_append_fsync_restart_and_exact_retry_are_durable(tmp_path: object) -> None:
    path = tmp_path / "corrections.journal"  # type: ignore[operator]
    quote = _quote("n1", 120)
    revision = _root(quote)
    store = DurableCorrectionJournal(DurableEventJournal(str(path)))
    persisted = store.append(revision)
    assert store.append(revision) == persisted
    recovered = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    assert recovered.snapshot().fingerprint == store.snapshot().fingerprint
    assert recovered.replay_as_known_at(120)[0].quote == quote


def test_conflicting_retry_fork_and_missing_predecessor_fail_closed(tmp_path: object) -> None:
    store = DurableCorrectionJournal(DurableEventJournal(str(tmp_path / "corrections.journal")))  # type: ignore[operator]
    quote = _quote("n1", 120)
    root = _root(quote)
    store.append(root)
    with pytest.raises(CorrectionPersistenceConflict):
        store.append(replace(root, quote=replace(quote, bid=Decimal("1.10001"))))
    with pytest.raises(CorrectionPersistenceConflict, match="revision identity"):
        store.append(
            QuoteRevision("r1", "other-logical-event", None, RevisionOperation.UPSERT, 220, _quote("other", 220))
        )
    with pytest.raises(CorrectionPersistenceError, match="predecessor"):
        store.append(QuoteRevision("missing", quote.event_id, "not-there", RevisionOperation.CANCEL, 220, None))
    store.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 220, None))
    with pytest.raises(CorrectionPersistenceError, match="lineage|predecessor"):
        store.append(QuoteRevision("fork", quote.event_id, "r1", RevisionOperation.CANCEL, 221, None))


def test_upsert_cancel_reactivation_and_scope_collision_are_isolated(tmp_path: object) -> None:
    store = DurableCorrectionJournal(DurableEventJournal(str(tmp_path / "corrections.journal")))  # type: ignore[operator]
    original = _quote("shared-native", 120)
    root = _root(original)
    store.append(root)
    store.append(QuoteRevision("r2", root.logical_event_id, "r1", RevisionOperation.CANCEL, 220, None))
    replacement = replace(_quote("replacement", 320, "1.10001"), event_id="replacement-observation")
    store.append(QuoteRevision("r3", root.logical_event_id, "r2", RevisionOperation.UPSERT, 320, replacement))
    assert store.replay_as_known_at(219)[0].quote == original
    assert store.replay_as_known_at(220) == ()
    assert store.replay_as_known_at(320)[0].quote == replacement
    other = _quote("shared-native", 120, source_name="source-b")
    store.append(_root(other, "other-r1"))
    assert len(store.replay_as_known_at(320)) == 2


def test_future_corruption_is_rejected_before_watermark_filtering(tmp_path: object) -> None:
    journal = DurableEventJournal(str(tmp_path / "corrections.journal"))  # type: ignore[operator]
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 120)
    store.append(_root(quote))
    scope = CorrectionScope.from_quote(quote)
    future = QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 999, None)
    event = encode_correction(future, scope, 2, "not-the-predecessor-event")
    journal.append(event)
    with pytest.raises(CorrectionPersistenceError, match="parent|lineage"):
        store.replay_as_known_at(120)


def test_post_fsync_failure_requires_fresh_authoritative_recovery(tmp_path: object) -> None:
    path = tmp_path / "corrections.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 120)

    def fault(phase: str, _record: object) -> None:
        if phase == "AFTER_JOURNAL_FSYNC":
            raise RuntimeError("simulated crash after durable fsync")

    journal.set_fault_hook(fault)
    with pytest.raises(CorrectionPersistenceError, match="recovery required"):
        store.append(_root(quote))
    assert store.state is CorrectionStoreState.RECOVERY_REQUIRED
    with pytest.raises(CorrectionPersistenceError, match="append prohibited"):
        store.append(_root(quote))
    recovered = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    assert recovered.replay_as_known_at(120)[0].quote == quote
    assert recovered.append(_root(quote)).revision == _root(quote)


@pytest.mark.parametrize("failure_point", ["before", "write", "pre_fsync"])
def test_media_failure_never_acknowledges_and_requires_recovery(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    """ENOSPC before/during write and pre-fsync failure cannot advance state."""
    path = tmp_path / f"{failure_point}.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    quote = _quote("n1", 120)
    if failure_point == "before":
        journal.set_fault_hook(
            lambda phase, _record: (
                (_ for _ in ()).throw(OSError(errno.ENOSPC, "no space")) if phase == "BEFORE_JOURNAL_WRITE" else None
            )
        )
    elif failure_point == "write":
        monkeypatch.setattr(
            journal_module.os, "write", lambda _fd, _data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "no space"))
        )
    else:
        journal.set_fault_hook(
            lambda phase, _record: (
                (_ for _ in ()).throw(OSError(errno.EIO, "pre-fsync failure"))
                if phase == "BEFORE_JOURNAL_FSYNC"
                else None
            )
        )
    with pytest.raises(CorrectionPersistenceError, match="recovery required"):
        store.append(_root(quote))
    assert store.state is CorrectionStoreState.RECOVERY_REQUIRED
    journal.set_fault_hook(None)
    monkeypatch.undo()
    assert DurableCorrectionJournal.recover(DurableEventJournal(str(path))).snapshot().records == ()
    # Recovery is authoritative: only a fresh active adapter may safely retry.
    retry = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    assert retry.append(_root(quote)).revision == _root(quote)


def test_failed_fsync_never_acknowledges_and_recovery_is_repeatable(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "fsync.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    monkeypatch.setattr(
        journal_module.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError(errno.ENOSPC, "fsync no space"))
    )
    quote = _quote("n1", 120)
    with pytest.raises(CorrectionPersistenceError, match="recovery required"):
        store.append(_root(quote))
    monkeypatch.undo()
    first = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    second = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    assert first.snapshot().fingerprint == second.snapshot().fingerprint
    assert first.snapshot().records == ()


def test_short_writes_complete_before_correction_acknowledgment(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial positive progress is looped until every canonical byte is durable."""
    path = tmp_path / "short-write.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    real_write = journal_module.os.write
    calls = 0

    def short_write(fd: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        return real_write(fd, data[: max(1, len(data) // 3)])

    monkeypatch.setattr(journal_module.os, "write", short_write)
    persisted = store.append(_root(_quote("short-write", 120)))
    assert calls > 1
    monkeypatch.undo()
    assert (
        DurableCorrectionJournal.recover(DurableEventJournal(str(path))).snapshot().records[0].event_id
        == persisted.event_id
    )


def test_zero_progress_write_requires_recovery(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "zero-write.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    monkeypatch.setattr(journal_module.os, "write", lambda _fd, _data: 0)
    with pytest.raises(CorrectionPersistenceError, match="recovery required"):
        store.append(_root(_quote("zero-write", 120)))
    monkeypatch.undo()
    assert DurableCorrectionJournal.recover(DurableEventJournal(str(path))).snapshot().records == ()


def test_exception_after_partial_write_rolls_back_and_requires_recovery(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "partial-exception.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    real_write = journal_module.os.write
    calls = 0

    def partial_then_fail(fd: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(fd, data[:1])
        raise OSError(errno.EIO, "write interrupted")

    monkeypatch.setattr(journal_module.os, "write", partial_then_fail)
    with pytest.raises(CorrectionPersistenceError, match="recovery required"):
        store.append(_root(_quote("partial-exception", 120)))
    monkeypatch.undo()
    assert DurableCorrectionJournal.recover(DurableEventJournal(str(path))).snapshot().records == ()


def test_two_independent_fresh_readers_replay_identical_history(tmp_path: object) -> None:
    path = tmp_path / "corrections.journal"  # type: ignore[operator]
    writer = DurableCorrectionJournal(DurableEventJournal(str(path)))
    quote = _quote("n1", 120)
    writer.append(_root(quote))
    writer.append(QuoteRevision("r2", quote.event_id, "r1", RevisionOperation.CANCEL, 220, None))
    reader_one = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    reader_two = DurableCorrectionJournal.recover(DurableEventJournal(str(path)))
    assert reader_one.snapshot().fingerprint == reader_two.snapshot().fingerprint
    assert reader_one.replay_as_known_at(120) == reader_two.replay_as_known_at(120)
    assert reader_one.replay_as_known_at(220) == reader_two.replay_as_known_at(220) == ()


def test_corrupted_tail_fails_closed_and_partition_cursor_uses_local_version(tmp_path: object) -> None:
    path = tmp_path / "corrections.journal"  # type: ignore[operator]
    journal = DurableEventJournal(str(path))
    store = DurableCorrectionJournal(journal)
    a = _quote("a1", 120, source_name="source-a")
    b = _quote("b1", 120, source_name="source-b")
    root_a = store.append(_root(a, "a-r1"))
    store.append(_root(b, "b-r1"))
    store.append(QuoteRevision("a-r2", a.event_id, "a-r1", RevisionOperation.CANCEL, 220, None))
    scope_a = CorrectionScope.from_quote(a)
    cursor = type(store.cursor(scope_a))(scope_a.partition_id, root_a.journal_sequence, root_a.aggregate_version)
    after = store.replay_after(scope_a, cursor)
    assert [item.revision.revision_id for item in after] == ["a-r2"]
    with open(path, "ab") as handle:
        handle.write(b'{"truncated":')
    with pytest.raises(JournalCorruptionException):
        DurableEventJournal(str(path))

"""Independent-process hostile proofs for durable G4 checkpoint ownership."""
from __future__ import annotations

from decimal import Decimal
import multiprocessing
import os
from pathlib import Path
from queue import Empty

import pytest

from src.fractal_flow.data_engine.checkpoints import (
    CheckpointIntegrityError, CheckpointLockError, SubscriberCheckpointStore,
)
from src.fractal_flow.data_engine.contracts import (
    InstrumentAlias, InstrumentRegistry, LaneScope, RawQuote, SourceIdentity, VolumeSemantics,
)
from src.fractal_flow.data_engine.core import CanonicalQuote, DataCore
from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import DurableCorrectionJournal
from src.fractal_flow.data_engine.journal_subscriber import JournalReplayAuthority
from src.fractal_flow.data_engine.revisions import QuoteRevision, RevisionOperation
from src.fractal_flow.persistence.journal import DurableEventJournal


pytestmark = pytest.mark.skipif(os.name != "posix", reason="checkpoint ownership requires POSIX flock")

SUBSCRIBER_ID = "checkpoint-process-proof"


def _quote() -> CanonicalQuote:
    source = SourceIdentity("source-a", "broker", "server", LaneScope.REPLAY)
    core = DataCore(InstrumentRegistry([InstrumentAlias(source, "EURUSD", "FX:EURUSD", Decimal("0.00001"), 0)]))
    result = core.ingest(RawQuote(
        source, "n1", 1, "EURUSD", 98, 99, 100, "1.10000", "1.10002", "1",
        VolumeSemantics.TICK_ACTIVITY_COUNT,
    ))
    assert result.quote is not None
    return result.quote


def _setup(tmp_path: Path) -> tuple[DurableEventJournal, DurableCorrectionJournal, CorrectionScope, JournalReplayAuthority, Path]:
    journal = DurableEventJournal(str(tmp_path / "ownership.journal"))
    corrections = DurableCorrectionJournal(journal)
    quote = _quote()
    corrections.append(QuoteRevision("r1", quote.event_id, None, RevisionOperation.UPSERT, 100, quote))
    scope = CorrectionScope.from_quote(quote)
    return journal, corrections, scope, JournalReplayAuthority(corrections, {scope.source.key}), tmp_path / "subscriber.checkpoint"


def _reader_components(journal_path: str) -> tuple[DurableEventJournal, DurableCorrectionJournal, CorrectionScope, JournalReplayAuthority]:
    journal = DurableEventJournal(journal_path)
    corrections = DurableCorrectionJournal.recover(journal)
    record = corrections.snapshot().records[0]
    scope = record.scope
    return journal, corrections, scope, JournalReplayAuthority(corrections, {scope.source.key})


def _hold_owner(journal_path: str, checkpoint_path: str, ready: object, release: object, outcomes: object) -> None:
    try:
        journal, _corrections, _scope, _authority = _reader_components(journal_path)
        store = SubscriberCheckpointStore(checkpoint_path, journal)
        ready.set()  # type: ignore[union-attr]
        outcomes.put("OWNED")  # type: ignore[union-attr]
        release.wait(15)  # type: ignore[union-attr]
        store.close()
    except Exception as exc:  # pragma: no cover - failures are asserted by the parent.
        outcomes.put(f"ERROR:{type(exc).__name__}:{exc}")  # type: ignore[union-attr]
        ready.set()  # type: ignore[union-attr]


def _crash_owner(journal_path: str, checkpoint_path: str, ready: object) -> None:
    journal, _corrections, _scope, _authority = _reader_components(journal_path)
    SubscriberCheckpointStore(checkpoint_path, journal)
    ready.set()  # type: ignore[union-attr]
    os._exit(0)


def _attempt_owner(journal_path: str, checkpoint_path: str, outcomes: object, attempts: int = 1) -> None:
    try:
        journal, _corrections, _scope, _authority = _reader_components(journal_path)
        for _ in range(attempts):
            try:
                store = SubscriberCheckpointStore(checkpoint_path, journal)
            except CheckpointLockError:
                outcomes.put("REJECTED")  # type: ignore[union-attr]
            else:
                outcomes.put("ACQUIRED")  # type: ignore[union-attr]
                store.close()
    except Exception as exc:  # pragma: no cover - failures are asserted by the parent.
        outcomes.put(f"ERROR:{type(exc).__name__}:{exc}")  # type: ignore[union-attr]


def _recover_then_commit(journal_path: str, checkpoint_path: str, outcomes: object) -> None:
    try:
        journal, corrections, scope, authority = _reader_components(journal_path)
        store = SubscriberCheckpointStore(checkpoint_path, journal)
        # Recovery and authoritative cursor validation precede advancement.
        store.load_verified(SUBSCRIBER_ID, scope, authority)
        store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
        store.close()
        outcomes.put("RECOVERED_COMMITTED")  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover - failures are asserted by the parent.
        outcomes.put(f"ERROR:{type(exc).__name__}:{exc}")  # type: ignore[union-attr]


def _start(ctx: multiprocessing.context.BaseContext, target: object, args: tuple[object, ...]) -> multiprocessing.Process:
    process = ctx.Process(target=target, args=args)  # type: ignore[arg-type]
    process.start()
    return process


def _result(outcomes: multiprocessing.queues.Queue[object]) -> str:
    try:
        value = outcomes.get(timeout=5)
    except Empty as exc:  # pragma: no cover - diagnostic guard.
        raise AssertionError("subprocess supplied no bounded result") from exc
    assert isinstance(value, str)
    return value


def _seed_checkpoint(journal: DurableEventJournal, corrections: DurableCorrectionJournal, scope: CorrectionScope, authority: JournalReplayAuthority, path: Path) -> None:
    store = SubscriberCheckpointStore(str(path), journal)
    store.commit(SUBSCRIBER_ID, scope, corrections.cursor(scope), authority)
    store.close()


def test_independent_process_rejects_second_owner_without_modifying_checkpoint(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    original = checkpoint.read_bytes()
    ctx = multiprocessing.get_context("spawn")
    ready, release, outcomes = ctx.Event(), ctx.Event(), ctx.Queue()
    owner = _start(ctx, _hold_owner, (str(journal.journal_file_path), str(checkpoint), ready, release, outcomes))
    assert ready.wait(10)
    assert _result(outcomes) == "OWNED"
    contender = _start(ctx, _attempt_owner, (str(journal.journal_file_path), str(checkpoint), outcomes))
    contender.join(15)
    assert contender.exitcode == 0
    assert _result(outcomes) == "REJECTED"
    assert checkpoint.read_bytes() == original
    release.set()
    owner.join(15)
    assert owner.exitcode == 0


def test_crashed_owner_releases_lock_and_replacement_recovers_before_checkpoint_advancement(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    ctx = multiprocessing.get_context("spawn")
    ready, outcomes = ctx.Event(), ctx.Queue()
    crashed = _start(ctx, _crash_owner, (str(journal.journal_file_path), str(checkpoint), ready))
    assert ready.wait(10)
    crashed.join(15)
    assert crashed.exitcode == 0
    replacement = _start(ctx, _recover_then_commit, (str(journal.journal_file_path), str(checkpoint), outcomes))
    replacement.join(20)
    assert replacement.exitcode == 0
    assert _result(outcomes) == "RECOVERED_COMMITTED"


def test_symlink_and_hardlink_aliases_cannot_bypass_semantic_checkpoint_ownership(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    symlink = aliases / "checkpoint-symlink"
    hardlink = aliases / "checkpoint-hardlink"
    symlink.symlink_to(checkpoint)
    os.link(checkpoint, hardlink)
    ctx = multiprocessing.get_context("spawn")
    ready, release, outcomes = ctx.Event(), ctx.Event(), ctx.Queue()
    owner = _start(ctx, _hold_owner, (str(journal.journal_file_path), str(checkpoint), ready, release, outcomes))
    assert ready.wait(10)
    assert _result(outcomes) == "OWNED"
    for alias in (symlink, hardlink):
        contender = _start(ctx, _attempt_owner, (str(journal.journal_file_path), str(alias), outcomes))
        contender.join(15)
        assert contender.exitcode == 0
        assert _result(outcomes) == "REJECTED"
    release.set()
    owner.join(15)
    assert owner.exitcode == 0


def test_lock_and_checkpoint_path_replacement_are_detected_fail_closed(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    store = SubscriberCheckpointStore(str(checkpoint), journal)
    lock_replacement = tmp_path / "replacement.lock"
    lock_replacement.write_bytes(b"replacement")
    os.replace(lock_replacement, store.lock_path)
    with pytest.raises(CheckpointLockError, match="replaced"):
        store.load_verified(SUBSCRIBER_ID, scope, authority)
    store.close()
    replacement_store = SubscriberCheckpointStore(str(checkpoint), journal)
    target_replacement = tmp_path / "replacement.checkpoint"
    target_replacement.write_bytes(checkpoint.read_bytes())
    os.replace(target_replacement, checkpoint)
    with pytest.raises(CheckpointIntegrityError, match="replaced"):
        replacement_store.load_verified(SUBSCRIBER_ID, scope, authority)
    replacement_store.close()


def test_ownership_transfer_rejects_a_stale_checkpoint_after_journal_replacement(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    ctx = multiprocessing.get_context("spawn")
    ready, release, outcomes = ctx.Event(), ctx.Event(), ctx.Queue()
    owner = _start(ctx, _hold_owner, (str(journal.journal_file_path), str(checkpoint), ready, release, outcomes))
    assert ready.wait(10)
    assert _result(outcomes) == "OWNED"
    release.set()
    owner.join(15)
    assert owner.exitcode == 0
    journal_path = journal.journal_file_path
    assert journal_path is not None
    journal.close()
    replacement = tmp_path / "replacement.journal"
    replacement.write_bytes(b"")
    os.replace(replacement, journal_path)
    replacement_journal = DurableEventJournal(str(journal_path))
    transferred = SubscriberCheckpointStore(str(checkpoint), replacement_journal)
    with pytest.raises(CheckpointIntegrityError, match="journal identity"):
        transferred.load_verified(SUBSCRIBER_ID, scope, authority)
    transferred.close()


def test_independent_checkpoint_identities_can_be_owned_concurrently_and_recovery_rejection_repeats(tmp_path: Path) -> None:
    journal, corrections, scope, authority, checkpoint = _setup(tmp_path)
    _seed_checkpoint(journal, corrections, scope, authority, checkpoint)
    other = tmp_path / "independent.checkpoint"
    ctx = multiprocessing.get_context("spawn")
    ready_one, release_one, outcomes = ctx.Event(), ctx.Event(), ctx.Queue()
    ready_two, release_two = ctx.Event(), ctx.Event()
    owner_one = _start(ctx, _hold_owner, (str(journal.journal_file_path), str(checkpoint), ready_one, release_one, outcomes))
    owner_two = _start(ctx, _hold_owner, (str(journal.journal_file_path), str(other), ready_two, release_two, outcomes))
    assert ready_one.wait(10) and ready_two.wait(10)
    assert {_result(outcomes), _result(outcomes)} == {"OWNED"}
    attempts = _start(ctx, _attempt_owner, (str(journal.journal_file_path), str(checkpoint), outcomes, 2))
    attempts.join(20)
    assert attempts.exitcode == 0
    assert [_result(outcomes), _result(outcomes)] == ["REJECTED", "REJECTED"]
    release_one.set()
    release_two.set()
    owner_one.join(15)
    owner_two.join(15)
    assert owner_one.exitcode == owner_two.exitcode == 0

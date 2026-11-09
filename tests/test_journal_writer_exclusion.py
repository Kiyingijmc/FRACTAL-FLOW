"""Linux hostile proofs for inode-bound DurableEventJournal writer authority."""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

import pytest

from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalWriterLockException


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX fcntl locking requires Linux/Unix execution evidence")


def _event(event_id: str, version: int) -> Event:
    return Event(
        event_id=event_id,
        event_type="WRITER_LOCK_TEST",
        aggregate_type="WRITER_LOCK_TEST",
        aggregate_id="journal",
        root_id="root",
        parent_id="parent",
        aggregate_version=version,
        source_timestamp=0,
        event_timestamp=0,
        processing_timestamp=0,
        payload={},
    )


def _competing_writer(path: str, version: int, result_queue: multiprocessing.queues.Queue[str]) -> None:
    journal = DurableEventJournal(path)
    try:
        journal.append(_event(f"child-{version}", version))
    except JournalWriterLockException:
        result_queue.put("LOCK_REJECTED")
    except Exception as exc:  # pragma: no cover - returned to parent assertion.
        result_queue.put(f"UNEXPECTED:{type(exc).__name__}:{exc}")
    else:  # pragma: no cover - must never occur while parent owns the inode lock.
        result_queue.put("UNSAFE_APPEND")
    finally:
        journal.close()


def _crashing_writer(path: str) -> None:
    journal = DurableEventJournal(path)
    journal.append(_event("crash-owner", 1))
    # Deliberately skip close: POSIX releases flock ownership when this process exits.
    os._exit(0)


def _run_child(target: object, args: tuple[object, ...]) -> multiprocessing.Process:
    process = multiprocessing.get_context("spawn").Process(target=target, args=args)
    process.start()
    return process


def test_independent_process_is_rejected_while_writer_owns_journal(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    owner = DurableEventJournal(str(path))
    owner.append(_event("owner", 1))
    queue: multiprocessing.queues.Queue[str] = multiprocessing.get_context("spawn").Queue()
    process = _run_child(_competing_writer, (str(path), 2, queue))
    process.join(20)
    assert process.exitcode == 0
    assert queue.get(timeout=2) == "LOCK_REJECTED"
    owner.close()


def test_same_process_replacement_is_rejected_until_owner_relinquishes(tmp_path: Path) -> None:
    """An in-process replacement cannot bypass the retained inode lock."""
    path = tmp_path / "journal.jsonl"
    owner = DurableEventJournal(str(path))
    assert owner.append(_event("owner", 1)).sequence_number == 1

    replacement = DurableEventJournal(str(path))
    with pytest.raises(JournalWriterLockException, match="Exclusive writer authority"):
        replacement.append(_event("overlap", 2))

    # A rejected contender remains faulted rather than becoming an implicit
    # replacement later.  A fresh instance can proceed only after the prior
    # writer explicitly hands over authority and reloads durable state.
    replacement.close()
    owner.close()
    handed_over = DurableEventJournal(str(path))
    assert handed_over.append(_event("replacement", 2)).sequence_number == 2
    handed_over.close()


def test_crashed_owner_releases_lock_for_replacement_writer(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    process = _run_child(_crashing_writer, (str(path),))
    process.join(20)
    assert process.exitcode == 0
    replacement = DurableEventJournal(str(path))
    record = replacement.append(_event("replacement", 2))
    assert record.sequence_number == 2
    replacement.close()


def test_recovery_holds_writer_authority_until_recovery_writer_closes(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    original = DurableEventJournal(str(path))
    original.append(_event("owner", 1))
    original.close()
    with open(path, "ab") as handle:
        handle.write(b'{"truncated":')
    recovering = DurableEventJournal(str(path), truncate_corrupted_tail=True)
    queue: multiprocessing.queues.Queue[str] = multiprocessing.get_context("spawn").Queue()
    process = _run_child(_competing_writer, (str(path), 2, queue))
    process.join(20)
    assert process.exitcode == 0
    assert queue.get(timeout=2) == "LOCK_REJECTED"
    assert recovering.append(_event("recovery-owner", 2)).sequence_number == 2
    recovering.close()


def test_alias_and_path_replacement_cannot_silently_bypass_inode_lock(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    alias = tmp_path / "journal-alias.jsonl"
    os.symlink(path, alias)
    owner = DurableEventJournal(str(alias))
    owner.append(_event("owner", 1))
    queue: multiprocessing.queues.Queue[str] = multiprocessing.get_context("spawn").Queue()
    process = _run_child(_competing_writer, (str(path), 2, queue))
    process.join(20)
    assert process.exitcode == 0
    assert queue.get(timeout=2) == "LOCK_REJECTED"
    replacement = tmp_path / "replacement.jsonl"
    replacement.write_bytes(b"")
    os.replace(replacement, path)
    with pytest.raises(JournalWriterLockException, match="no longer identifies"):
        owner.append(_event("must-not-write-replacement", 2))
    owner.close()


def test_independent_journals_have_independent_writer_authority(tmp_path: Path) -> None:
    first = DurableEventJournal(str(tmp_path / "first.jsonl"))
    second = DurableEventJournal(str(tmp_path / "second.jsonl"))
    assert first.append(_event("first", 1)).sequence_number == 1
    assert second.append(_event("second", 1)).sequence_number == 1
    first.close()
    second.close()

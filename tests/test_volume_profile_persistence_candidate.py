"""Candidate hostile tests for the G3b Unit 1 persistence adapter.

Run in the disposable FRACTAL-FLOW repository with the normal source import path.
"""
from decimal import Decimal

import pytest

from src.fractal_flow.persistence.journal import DurableEventJournal, JournalCorruptionException
from src.fractal_flow.research.volume_profile import ProfileDomain, ProfileEvent
from src.fractal_flow.research.volume_profile_revisions import ProfileRevision, RevisionOperation
from src.fractal_flow.research.volume_profile_event_codec import ProfileRevisionContext
from src.fractal_flow.research.volume_profile_persistence import (
    ProfilePersistenceConflict,
    ProfilePersistenceCorruption,
    ProfilePersistenceFaulted,
    VolumeProfilePersistence,
)


def observation(event_id="obs-1", *, event_time=2_500_000_000, available=3_500_000_000):
    return ProfileEvent(
        event_id=event_id,
        source_id="feed-A",
        symbol="EURUSD",
        domain=ProfileDomain.FX_QUOTE_ACTIVITY,
        event_time_ns=event_time,
        available_at_ns=available,
        source_sequence=7,
        price=Decimal("1.2300"),
        weight=Decimal("2.500"),
    )


def upsert(revision_id="rev-1", supersedes=None, *, event=None, available=3_500_000_000):
    event = event or observation()
    return ProfileRevision("logical-1", revision_id, supersedes, RevisionOperation.UPSERT, available, event)


def test_append_reopen_and_resolve(tmp_path):
    path = tmp_path / "vp.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    record = adapter.append(upsert())
    assert record.event.authority == "ANALYTICAL_ONLY"
    assert record.event.account_id is None

    reopened = VolumeProfilePersistence(DurableEventJournal(str(path)))
    result = reopened.resolve(watermark_ns=4_000_000_000)
    assert len(result.active) == 1
    assert result.active[0].revision_id == "rev-1"



def test_append_rejects_availability_regression_before_journal_mutation(tmp_path):
    path = tmp_path / "vp.journal"
    journal = DurableEventJournal(str(path))
    adapter = VolumeProfilePersistence(journal)

    first = upsert()
    adapter.append(first)
    before = journal.get_all_records()
    assert len(before) == 1

    # The observation itself is valid, but its availability time regresses
    # relative to the current revision head (3.5s -> 3.2s).
    regressing = upsert(
        "rev-2",
        "rev-1",
        event=observation(
            "obs-2",
            event_time=3_000_000_000,
            available=3_200_000_000,
        ),
        available=3_200_000_000,
    )

    with pytest.raises(
        ProfilePersistenceConflict,
        match="availability regresses along chain",
    ):
        adapter.append(regressing)

    after = journal.get_all_records()
    assert after == before
    assert len(after) == 1

    # A fresh adapter must recover and resolve the original authoritative history.
    reopened = VolumeProfilePersistence(
        DurableEventJournal(str(path), truncate_corrupted_tail=False)
    )
    resolution = reopened.resolve(watermark_ns=4_000_000_000)
    assert [item.revision_id for item in resolution.active] == ["rev-1"]

def test_exact_retry_is_idempotent_but_conflicting_revision_fails(tmp_path):
    path = tmp_path / "vp.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    first = upsert()
    original = adapter.append(first)
    retry = adapter.append(first)
    assert retry == original
    conflicting = upsert(event=observation(event_id="obs-different"))
    with pytest.raises(ProfilePersistenceConflict):
        adapter.append(conflicting)
    assert len(DurableEventJournal(str(path)).get_all_records()) == 1


def test_persistence_derives_aggregate_version_from_durable_chain(tmp_path):
    path = tmp_path / "vp-version.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    first = adapter.append(upsert())
    second = adapter.append(
        upsert(
            "rev-2",
            "rev-1",
            event=observation("obs-2", event_time=4_000_000_000, available=4_000_000_000),
            available=4_000_000_000,
        )
    )

    assert (first.event.aggregate_version, second.event.aggregate_version) == (1, 2)
    assert len(VolumeProfilePersistence(DurableEventJournal(str(path))).journal.get_all_records()) == 2


def test_cancel_requires_active_head_and_reactivation_supersedes_cancel(tmp_path):
    path = tmp_path / "vp.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    adapter.append(upsert())
    context = ProfileRevisionContext("feed-A", "EURUSD", "FX_QUOTE_ACTIVITY", 2_500_000_000)
    cancel = ProfileRevision("logical-1", "rev-2", "rev-1", RevisionOperation.CANCEL, 4_000_000_000, None)
    adapter.append(cancel, context=context)
    assert adapter.resolve(watermark_ns=4_000_000_000).active == ()

    reactivation_event = observation("obs-2", event_time=4_500_000_000, available=5_000_000_000)
    reactivation = upsert("rev-3", "rev-2", event=reactivation_event, available=5_000_000_000)
    adapter.append(reactivation)
    assert [head.revision_id for head in adapter.resolve(watermark_ns=5_000_000_000).active] == ["rev-3"]

    recovered = VolumeProfilePersistence(DurableEventJournal(str(path), truncate_corrupted_tail=False))
    assert recovered.resolve(watermark_ns=5_000_000_000) == adapter.resolve(watermark_ns=5_000_000_000)


def test_cancel_without_active_upsert_is_rejected(tmp_path):
    adapter = VolumeProfilePersistence(DurableEventJournal(str(tmp_path / "vp.journal")))
    context = ProfileRevisionContext("feed-A", "EURUSD", "FX_QUOTE_ACTIVITY", 2_500_000_000)
    cancel = ProfileRevision("logical-1", "rev-cancel", None, RevisionOperation.CANCEL, 4_000_000_000, None)
    with pytest.raises(ProfilePersistenceConflict):
        adapter.append(cancel, context=context)


def test_post_fsync_exception_faults_stale_adapter_and_fresh_recovery_recognizes_durable_event(tmp_path):
    path = tmp_path / "vp.journal"
    journal = DurableEventJournal(str(path))
    adapter = VolumeProfilePersistence(journal)
    target = upsert()

    def crash(point, record):
        if point == "AFTER_JOURNAL_FSYNC":
            raise RuntimeError("INJECTED_AFTER_FSYNC")

    journal.set_fault_hook(crash)
    with pytest.raises(RuntimeError, match="INJECTED_AFTER_FSYNC"):
        adapter.append(target)
    assert adapter.faulted
    with pytest.raises(ProfilePersistenceFaulted):
        adapter.append(upsert("rev-2", "rev-1", event=observation("obs-2", event_time=4_500_000_000, available=5_000_000_000), available=5_000_000_000))

    recovered = adapter.recover()
    resolution = recovered.resolve(watermark_ns=10_000_000_000)
    assert [item.revision_id for item in resolution.active] == [
        target.revision_id
    ]
    assert len(recovered.journal.get_all_records()) == 1
    assert recovered.append(target).event == recovered.journal.get_all_records()[0].event


def test_recovery_rejects_corrupt_journal_instead_of_truncating(tmp_path):
    path = tmp_path / "vp.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    adapter.append(upsert())
    with path.open("ab") as stream:
        stream.write(b'{"sequence_number":2')
    with pytest.raises((JournalCorruptionException, ProfilePersistenceCorruption)):
        VolumeProfilePersistence(DurableEventJournal(str(path), truncate_corrupted_tail=False))


def test_recovery_rejects_canonically_corrupt_future_revision_before_watermark_query(tmp_path):
    """A checksum-valid future VP event must fail recovery, not hide behind an earlier watermark."""
    from dataclasses import replace

    path = tmp_path / "vp-future-corrupt.journal"
    journal = DurableEventJournal(str(path))
    adapter = VolumeProfilePersistence(journal)
    first = adapter.append(upsert())
    original_event = first.event
    payload = dict(original_event.payload)
    payload["revision_id"] = "hostile-future-revision"
    payload["available_at_ns"] = 99_000_000_000
    hostile_event = replace(
        original_event,
        event_id="hostile-future-vp-event",
        aggregate_version=2,
        parent_id=original_event.event_id,
        payload=payload,
    )
    journal.append(hostile_event)
    assert len(journal.get_all_records()) == 2
    with pytest.raises(ProfilePersistenceCorruption):
        VolumeProfilePersistence(DurableEventJournal(str(path), truncate_corrupted_tail=False))


def test_failed_pre_append_does_not_publish_state_and_faults_adapter(tmp_path):
    path = tmp_path / "vp-pre-append-failure.journal"
    journal = DurableEventJournal(str(path))
    adapter = VolumeProfilePersistence(journal)

    def fail_before_write(point, record):
        if point == "BEFORE_JOURNAL_WRITE":
            raise RuntimeError("INJECTED_BEFORE_JOURNAL_WRITE")

    journal.set_fault_hook(fail_before_write)
    with pytest.raises(Exception, match="INJECTED_BEFORE_JOURNAL_WRITE"):
        adapter.append(upsert())

    assert adapter.faulted
    assert journal.get_all_records() == []
    recovered = VolumeProfilePersistence(DurableEventJournal(str(path), truncate_corrupted_tail=False))
    assert recovered.resolve(watermark_ns=10_000_000_000).active == ()


def test_single_process_chain_lock_allows_exactly_one_competing_successor(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "vp-concurrent-chain.journal"
    adapter = VolumeProfilePersistence(DurableEventJournal(str(path)))
    adapter.append(upsert())
    left = upsert("rev-left", "rev-1", event=observation("obs-left", event_time=4_000_000_000, available=4_000_000_000), available=4_000_000_000)
    right = upsert("rev-right", "rev-1", event=observation("obs-right", event_time=4_000_000_000, available=4_000_000_000), available=4_000_000_000)

    def attempt(revision):
        try:
            return adapter.append(revision)
        except ProfilePersistenceConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (left, right)))

    assert sum(result is not None for result in results) == 1
    assert len(adapter.journal.get_all_records()) == 2
    assert len(adapter.resolve(watermark_ns=10_000_000_000).active) == 1

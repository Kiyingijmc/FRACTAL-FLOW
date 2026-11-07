from decimal import Decimal

import pytest

from src.fractal_flow.research.volume_profile import ProfileDomain, ProfileEvent
from src.fractal_flow.research.volume_profile_revisions import (
    ProfileRevision,
    RevisionHistoryError,
    RevisionOperation,
    resolve_profile_revisions,
)

D = Decimal


def observation(event_id: str, price: str, *, event_time: int = 1, available: int = 1) -> ProfileEvent:
    return ProfileEvent(
        event_id=event_id,
        source_id="feed-A",
        symbol="EURUSD",
        domain=ProfileDomain.FX_QUOTE_ACTIVITY,
        event_time_ns=event_time,
        available_at_ns=available,
        source_sequence=1,
        price=D(price),
        weight=D("1"),
    )


def rev(logical: str, rid: str, parent: str | None, op: RevisionOperation, at: int, event=None) -> ProfileRevision:
    return ProfileRevision(logical, rid, parent, op, at, event)


def test_correction_replaces_prior_revision_and_is_order_independent():
    first = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    correction = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 5, observation("wire-b", "1.01", available=5))
    a = resolve_profile_revisions([first, correction], watermark_ns=10)
    b = resolve_profile_revisions([correction, first], watermark_ns=10)
    assert a == b
    assert [x.revision_id for x in a.active] == ["r2"]
    events = a.to_profile_events()
    assert len(events) == 1
    assert events[0].event_id == "tick-1"
    assert events[0].price == D("1.01")
    assert events[0].available_at_ns == 5


def test_as_known_at_watermark_does_not_leak_future_correction():
    first = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    future = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 50, observation("wire-b", "9.99", available=50))
    result = resolve_profile_revisions([first, future], watermark_ns=10)
    assert [x.revision_id for x in result.active] == ["r1"]
    assert result.to_profile_events()[0].price == D("1.00")


def test_cancel_is_a_head_but_not_an_active_observation():
    first = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    cancel = rev("tick-1", "r2", "r1", RevisionOperation.CANCEL, 5)
    result = resolve_profile_revisions([first, cancel], watermark_ns=10)
    assert len(result.heads) == 1
    assert result.heads[0].operation is RevisionOperation.CANCEL
    assert result.active == ()
    assert result.to_profile_events() == ()


def test_fork_fails_closed():
    root = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    left = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 2, observation("wire-b", "1.01", available=2))
    right = rev("tick-1", "r3", "r1", RevisionOperation.UPSERT, 3, observation("wire-c", "1.02", available=3))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([root, left, right], watermark_ns=10)
    assert caught.value.reason_code == "REVISION_FORK"


def test_missing_predecessor_fails_closed_in_visible_history():
    orphan = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 5, observation("wire-b", "1.01", available=5))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([orphan], watermark_ns=10)
    assert caught.value.reason_code == "MISSING_PREDECESSOR"


def test_predecessor_from_another_logical_event_fails_closed():
    root = rev("tick-A", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    wrong = rev("tick-B", "r2", "r1", RevisionOperation.UPSERT, 2, observation("wire-b", "1.01", available=2))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([root, wrong], watermark_ns=10)
    assert caught.value.reason_code == "CROSS_LOGICAL_PREDECESSOR"


def test_conflicting_revision_id_fails_closed():
    a = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    b = rev("tick-2", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-b", "1.01"))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([a, b], watermark_ns=10)
    assert caught.value.reason_code == "CONFLICTING_REVISION_ID"


def test_duplicate_identical_revision_record_is_rejected_not_silently_deduplicated():
    item = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([item, item], watermark_ns=10)
    assert caught.value.reason_code == "DUPLICATE_REVISION_ID"


def test_cancel_cannot_carry_payload_and_upsert_requires_payload():
    with pytest.raises(RevisionHistoryError) as caught:
        ProfileRevision("tick-1", "r1", None, RevisionOperation.CANCEL, 1, observation("wire-a", "1.00"))
    assert caught.value.reason_code == "CANCEL_EVENT_FORBIDDEN"
    with pytest.raises(RevisionHistoryError) as caught:
        ProfileRevision("tick-1", "r2", None, RevisionOperation.UPSERT, 1, None)
    assert caught.value.reason_code == "UPSERT_EVENT_REQUIRED"


def test_revision_cannot_be_available_before_embedded_event():
    with pytest.raises(RevisionHistoryError) as caught:
        ProfileRevision("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00", available=2))
    assert caught.value.reason_code == "EVENT_NOT_YET_AVAILABLE"


def test_revision_cannot_precede_its_predecessor():
    root = rev(
        "tick-1", "r1", None, RevisionOperation.UPSERT, 10,
        observation("wire-a", "1.00", available=10),
    )
    child = rev(
        "tick-1", "r2", "r1", RevisionOperation.UPSERT, 5,
        observation("wire-b", "1.01", available=5),
    )

    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([root, child], watermark_ns=10)

    assert caught.value.reason_code == "REVISION_PRECEDES_PREDECESSOR"


def test_invalid_watermark_fails_closed():
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([], watermark_ns=-1)
    assert caught.value.reason_code == "INVALID_WATERMARK"


def test_disconnected_cycle_cannot_hide_beside_valid_root():
    root = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    cycle_a = rev("tick-1", "r2", "r3", RevisionOperation.UPSERT, 2, observation("wire-b", "1.01", available=2))
    cycle_b = rev("tick-1", "r3", "r2", RevisionOperation.UPSERT, 3, observation("wire-c", "1.02", available=3))
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([root, cycle_a, cycle_b], watermark_ns=10)
    assert caught.value.reason_code == "DISCONNECTED_REVISION_CHAIN"



def test_embedded_event_must_be_profile_event():
    with pytest.raises(RevisionHistoryError) as caught:
        ProfileRevision("tick-1", "r1", None, RevisionOperation.UPSERT, 1, "not-an-event")
    assert caught.value.reason_code == "INVALID_REVISION_EVENT_TYPE"


def test_non_revision_input_record_fails_with_controlled_reason_code():
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions([object()], watermark_ns=10)
    assert caught.value.reason_code == "INVALID_REVISION_RECORD"


def test_non_iterable_revision_input_fails_with_controlled_reason_code():
    with pytest.raises(RevisionHistoryError) as caught:
        resolve_profile_revisions(None, watermark_ns=10)  # type: ignore[arg-type]
    assert caught.value.reason_code == "INVALID_REVISION_ITERABLE"


def test_availability_watermark_is_inclusive_at_exact_boundary():
    at_boundary = rev(
        "tick-1", "r1", None, RevisionOperation.UPSERT, 10,
        observation("wire-a", "1.00", available=10),
    )
    after_boundary = rev(
        "tick-2", "r2", None, RevisionOperation.UPSERT, 11,
        observation("wire-b", "1.01", available=11),
    )
    result = resolve_profile_revisions([after_boundary, at_boundary], watermark_ns=10)
    assert [head.logical_event_id for head in result.heads] == ["tick-1"]


def test_adjacent_nanosecond_watermarks_do_not_leak_future_revision():
    root = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 10, observation("wire-a", "1.00", available=10))
    correction = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 11, observation("wire-b", "1.01", available=11))

    before = resolve_profile_revisions([root, correction], watermark_ns=10)
    at_correction = resolve_profile_revisions([root, correction], watermark_ns=11)

    assert [head.revision_id for head in before.active] == ["r1"]
    assert [head.revision_id for head in at_correction.active] == ["r2"]


def test_cancelled_logical_event_can_be_reactivated_by_a_later_upsert():
    first = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    cancel = rev("tick-1", "r2", "r1", RevisionOperation.CANCEL, 5)
    reactivate = rev(
        "tick-1", "r3", "r2", RevisionOperation.UPSERT, 7,
        observation("wire-c", "1.02", available=7),
    )
    result = resolve_profile_revisions([reactivate, first, cancel], watermark_ns=10)
    assert [head.revision_id for head in result.active] == ["r3"]
    assert result.to_profile_events()[0].price == D("1.02")


def test_all_input_permutations_resolve_to_identical_chain_head():
    from itertools import permutations

    first = rev("tick-1", "r1", None, RevisionOperation.UPSERT, 1, observation("wire-a", "1.00"))
    second = rev("tick-1", "r2", "r1", RevisionOperation.UPSERT, 2, observation("wire-b", "1.01", available=2))
    third = rev("tick-1", "r3", "r2", RevisionOperation.UPSERT, 3, observation("wire-c", "1.02", available=3))
    results = [resolve_profile_revisions(order, watermark_ns=10) for order in permutations((first, second, third))]
    assert all(result == results[0] for result in results[1:])
    assert [head.revision_id for head in results[0].active] == ["r3"]

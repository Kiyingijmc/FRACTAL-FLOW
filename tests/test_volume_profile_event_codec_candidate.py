"""Hostile candidate tests; run only in a disposable copy of the target repo."""
from dataclasses import replace
from decimal import Decimal
import pytest

from src.fractal_flow.research.volume_profile import ProfileDomain, ProfileEvent
from src.fractal_flow.research.volume_profile_revisions import ProfileRevision, RevisionOperation
from src.fractal_flow.research.volume_profile_event_codec import (
    ProfileRevisionCodecError, ProfileRevisionContext,
    decode_profile_revision, encode_profile_revision,
)


def sample_event(event_id="obs-1", event_time=2_500_000_000, available=3_500_000_000):
    return ProfileEvent(
        event_id=event_id, source_id="feed-A", symbol="EURUSD",
        domain=ProfileDomain.FX_QUOTE_ACTIVITY, event_time_ns=event_time,
        available_at_ns=available, source_sequence=7,
        price=Decimal("1.2300"), weight=Decimal("2.500"),
    )


def prior_upsert_event():
    """Build the canonical predecessor event for revision rev-1."""
    revision = ProfileRevision(
        "logical-1", "rev-1", None, RevisionOperation.UPSERT,
        3_500_000_000, sample_event(),
    )
    return encode_profile_revision(
        revision, aggregate_version=1, parent_event_id=None,
    )


def test_upsert_round_trip_and_decimal_canonicalization():
    revision = ProfileRevision("logical-1", "rev-1", None, RevisionOperation.UPSERT,
                               3_500_000_000, sample_event())
    encoded = encode_profile_revision(revision, aggregate_version=1, parent_event_id=None)
    decoded, context = decode_profile_revision(encoded)
    assert decoded == revision
    assert encoded.payload["observation"]["price"] == "1.23"
    assert encoded.payload["observation"]["weight"] == "2.5"
    assert context.prior_observation_event_time_ns == 2_500_000_000


def test_envelope_seconds_floor_keeps_payload_nanoseconds_exact():
    revision = ProfileRevision(
        "logical-1",
        "rev-ns",
        None,
        RevisionOperation.UPSERT,
        2_500_000_999,
        sample_event(event_time=2_500_000_001, available=2_500_000_999),
    )
    encoded = encode_profile_revision(revision, aggregate_version=1, parent_event_id=None)
    decoded, _ = decode_profile_revision(encoded)

    assert (encoded.source_timestamp, encoded.event_timestamp, encoded.processing_timestamp) == (2, 2, 2)
    assert decoded.available_at_ns == 2_500_000_999
    assert decoded.event is not None
    assert decoded.event.event_time_ns == 2_500_000_001
    assert decoded.event.available_at_ns == 2_500_000_999


def test_event_identity_is_deterministic_and_namespaced_by_chain_scope():
    first = ProfileRevision("logical-A", "shared-revision", None, RevisionOperation.UPSERT, 3_500_000_000, sample_event())
    same = ProfileRevision("logical-A", "shared-revision", None, RevisionOperation.UPSERT, 3_500_000_000, sample_event())
    other_scope = ProfileRevision("logical-B", "shared-revision", None, RevisionOperation.UPSERT, 3_500_000_000, sample_event())

    encoded_first = encode_profile_revision(first, aggregate_version=1, parent_event_id=None)
    encoded_same = encode_profile_revision(same, aggregate_version=1, parent_event_id=None)
    encoded_other_scope = encode_profile_revision(other_scope, aggregate_version=1, parent_event_id=None)

    assert encoded_first.event_id == encoded_same.event_id
    assert encoded_first.root_id == encoded_same.root_id
    assert encoded_first.event_id != encoded_other_scope.event_id
    assert encoded_first.aggregate_id != encoded_other_scope.aggregate_id


def test_cancel_round_trip_requires_validated_chain_context():
    revision = ProfileRevision("logical-1", "rev-2", "rev-1", RevisionOperation.CANCEL,
                               4_000_000_000, None)
    context = ProfileRevisionContext("feed-A", "EURUSD", "FX_QUOTE_ACTIVITY", 2_500_000_000)
    predecessor = prior_upsert_event()
    encoded = encode_profile_revision(
        revision, context=context, aggregate_version=2,
        parent_event_id=predecessor.event_id,
    )
    with pytest.raises(ProfileRevisionCodecError, match="chain observation-time context"):
        decode_profile_revision(encoded)
    decoded, decoded_context = decode_profile_revision(encoded, context=context)
    assert decoded == revision
    assert decoded_context.prior_observation_event_time_ns == 2_500_000_000


def test_rejects_authority_tampering():
    revision = ProfileRevision("logical-1", "rev-1", None, RevisionOperation.UPSERT,
                               3_500_000_000, sample_event())
    encoded = encode_profile_revision(revision, aggregate_version=1, parent_event_id=None)
    with pytest.raises(ProfileRevisionCodecError, match="authority or actor"):
        decode_profile_revision(replace(encoded, authority="EXECUTION"))


def test_rejects_correlation_tampering():
    revision = ProfileRevision("logical-1", "rev-1", None, RevisionOperation.UPSERT,
                               3_500_000_000, sample_event())
    encoded = encode_profile_revision(revision, aggregate_version=1, parent_event_id=None)
    with pytest.raises(ProfileRevisionCodecError, match="correlation_id"):
        decode_profile_revision(replace(encoded, correlation_id="other-logical-id"))


def test_rejects_wrong_account_or_version_metadata():
    revision = ProfileRevision("logical-1", "rev-1", None, RevisionOperation.UPSERT,
                               3_500_000_000, sample_event())
    encoded = encode_profile_revision(revision, aggregate_version=1, parent_event_id=None)
    with pytest.raises(ProfileRevisionCodecError, match="account identity"):
        decode_profile_revision(replace(encoded, account_id="acct"))
    with pytest.raises(ProfileRevisionCodecError, match="configuration/data/feature"):
        decode_profile_revision(replace(encoded, feature_version=2))


def test_rejects_context_identity_conflict_for_cancel():
    revision = ProfileRevision("logical-1", "rev-2", "rev-1", RevisionOperation.CANCEL,
                               4_000_000_000, None)
    encoded = encode_profile_revision(
        revision,
        context=ProfileRevisionContext("feed-A", "EURUSD", "FX_QUOTE_ACTIVITY", 2_500_000_000),
        aggregate_version=2, parent_event_id=prior_upsert_event().event_id,
    )
    bad_context = ProfileRevisionContext("feed-B", "EURUSD", "FX_QUOTE_ACTIVITY", 2_500_000_000)
    with pytest.raises(ProfileRevisionCodecError, match="context conflicts"):
        decode_profile_revision(encoded, context=bad_context)

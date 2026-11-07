from dataclasses import replace
from decimal import Decimal

import pytest

from src.fractal_flow.research.volume_profile import ProfileDomain, ProfileEvent
from src.fractal_flow.research.volume_profile_revisions import (
    ProfileRevision,
    RevisionOperation,
)
from src.fractal_flow.research.volume_profile_event_codec import (
    ProfileRevisionCodecError,
    decode_profile_revision,
    encode_profile_revision,
)


def observation(event_id="obs-1"):
    return ProfileEvent(
        event_id=event_id,
        source_id="feed-A",
        symbol="EURUSD",
        domain=ProfileDomain.FX_QUOTE_ACTIVITY,
        event_time_ns=2_500_000_000,
        available_at_ns=3_500_000_000,
        source_sequence=7,
        price=Decimal("1.23"),
        weight=Decimal("2.5"),
    )


def root_event():
    revision = ProfileRevision(
        logical_event_id="logical-1",
        revision_id="rev-1",
        supersedes_revision_id=None,
        operation=RevisionOperation.UPSERT,
        available_at_ns=3_500_000_000,
        event=observation(),
    )
    return encode_profile_revision(
        revision,
        aggregate_version=1,
        parent_event_id=None,
    )


def test_rejects_tampered_root_identity():
    event = root_event()
    tampered = replace(event, root_id="attacker-selected-root")

    with pytest.raises(ProfileRevisionCodecError):
        decode_profile_revision(tampered)


def test_encoder_rejects_parent_not_bound_to_predecessor():
    revision = ProfileRevision(
        logical_event_id="logical-1",
        revision_id="rev-2",
        supersedes_revision_id="rev-1",
        operation=RevisionOperation.UPSERT,
        available_at_ns=4_000_000_000,
        event=observation("obs-2"),
    )

    with pytest.raises(ProfileRevisionCodecError):
        encode_profile_revision(
            revision,
            aggregate_version=2,
            parent_event_id="unrelated-parent-event",
        )


def test_decoder_rejects_boolean_event_schema_version():
    event = root_event()
    tampered = replace(event, schema_version=True)

    with pytest.raises(ProfileRevisionCodecError):
        decode_profile_revision(tampered)


def test_decoder_rejects_boolean_payload_schema_version():
    event = root_event()
    payload = dict(event.payload)
    payload["payload_schema_version"] = True
    tampered = replace(event, payload=payload)

    with pytest.raises(ProfileRevisionCodecError):
        decode_profile_revision(tampered)


def test_decoder_rejects_boolean_aggregate_version():
    event = root_event()
    tampered = replace(event, aggregate_version=True)

    with pytest.raises(ProfileRevisionCodecError):
        decode_profile_revision(tampered)

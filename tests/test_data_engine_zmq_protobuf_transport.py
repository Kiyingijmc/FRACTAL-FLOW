"""Optional-dependency proofs for the inproc ZeroMQ/Protobuf notification adapter."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("zmq")
pytest.importorskip("google.protobuf")

from src.fractal_flow.data_engine.journal_subscriber import JournalEnvelope
from src.fractal_flow.data_engine.zmq_protobuf_transport import (
    ProtobufJournalEnvelopeCodec,
    ZeroMqJournalPublisher,
    ZeroMqJournalSubscriber,
    ZmqProtobufTransportError,
)


SOURCE = ("source", "broker", "server", "REPLAY", "", "")
SECRET = b"transport-test-secret"


def _envelope() -> JournalEnvelope:
    unsigned = {
        "v": 2,
        "partition": "p",
        "journal_sequence": 2**62 + 7,
        "aggregate_version": 3,
        "event_id": "event",
        "available_at_ns": 2**62 + 9,
        "source": SOURCE,
        "payload_hash": "a" * 64,
    }
    import hashlib
    import hmac
    import json

    mac = hmac.new(
        SECRET, json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(), hashlib.sha256
    ).hexdigest()
    return JournalEnvelope(2, "p", 2**62 + 7, 3, "event", 2**62 + 9, SOURCE, "a" * 64, mac)


def test_protobuf_round_trip_preserves_nanosecond_and_journal_integers_exactly() -> None:
    envelope = _envelope()
    assert ProtobufJournalEnvelopeCodec.decode(ProtobufJournalEnvelopeCodec.encode(envelope)) == envelope


def test_inproc_transport_is_bounded_authenticated_and_tcp_fails_closed() -> None:
    import zmq

    context = zmq.Context()
    endpoint = f"inproc://ff-{uuid.uuid4()}"
    publisher = ZeroMqJournalPublisher(endpoint, context=context, max_queue=2)
    subscriber = ZeroMqJournalSubscriber(endpoint, SECRET, {SOURCE}, context=context, max_queue=2)
    try:
        publisher.publish(_envelope())
        assert subscriber.poll(1_000) == _envelope()
        with pytest.raises(ZmqProtobufTransportError, match="inproc"):
            ZeroMqJournalPublisher("tcp://127.0.0.1:5555", context=context)
    finally:
        subscriber.close()
        publisher.close()
        context.term()

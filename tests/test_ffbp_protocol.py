"""Phase 6A protocol, framing, identity, and boundedness invariants."""
import json
import struct

import pytest

from src.fractal_flow.execution.ffbp_protocol import (
    AccountBindingError,
    BoundedMessageQueue,
    Channel,
    CommandConflictError,
    CommandIdentityRegistry,
    CommandRecord,
    CommandState,
    ProtocolEnvelope,
    ProtocolError,
    SequenceError,
    SequenceTracker,
    canonical_json,
    decode_envelope,
    encode_envelope,
    payload_hash,
)


def env(seq: int = 1) -> ProtocolEnvelope:
    return ProtocolEnvelope(
        message_type="HEARTBEAT",
        account_id="ACT_PRIMARY",
        session_id="S1",
        channel=Channel.CONTROL,
        sequence=seq,
        sent_at_ms=100,
        payload={"z": 2, "a": 1},
    )


def test_canonical_json_is_stable_and_utf8() -> None:
    assert canonical_json({"z": 2, "a": 1}) == b'{"a":1,"z":2}'
    assert payload_hash({"z": 2, "a": 1}) == payload_hash({"a": 1, "z": 2})


def test_frame_round_trip_with_hmac() -> None:
    secret = b"phase6-test-secret"
    decoded = decode_envelope(encode_envelope(env(), secret), secret)
    assert decoded == env()


def test_tamper_is_rejected() -> None:
    secret = b"phase6-test-secret"
    frame = bytearray(encode_envelope(env(), secret))
    frame[-2] ^= 1
    with pytest.raises(ProtocolError):
        decode_envelope(bytes(frame), secret)


def test_frame_size_and_length_are_bounded() -> None:
    oversized = ProtocolEnvelope(
        message_type="EVENT", account_id="A", session_id="S", channel=Channel.EVENT,
        sequence=1, payload={"x": "x" * 70_000}
    )
    with pytest.raises(ProtocolError):
        encode_envelope(oversized)
    body = b"{}"
    with pytest.raises(ProtocolError):
        decode_envelope(struct.pack(">I", 10) + body)


def test_sequence_gap_blocks_until_sync() -> None:
    tracker = SequenceTracker()
    tracker.accept(1)
    with pytest.raises(SequenceError):
        tracker.accept(3)
    assert tracker.sync_required
    with pytest.raises(SequenceError):
        tracker.accept(2)
    tracker.synchronized(4)
    tracker.accept(4)


def test_duplicate_sequence_is_rejected() -> None:
    tracker = SequenceTracker()
    tracker.accept(1)
    with pytest.raises(SequenceError):
        tracker.accept(1)


def test_account_and_session_fence() -> None:
    fence = __import__("src.fractal_flow.execution.ffbp_protocol", fromlist=["AccountSessionFence"]).AccountSessionFence("A", "S")
    with pytest.raises(AccountBindingError):
        fence.validate(ProtocolEnvelope(message_type="X", account_id="B", session_id="S", channel=Channel.EVENT, sequence=1))
    with pytest.raises(AccountBindingError):
        fence.validate(ProtocolEnvelope(message_type="X", account_id="A", session_id="OLD", channel=Channel.EVENT, sequence=1))


def test_command_identity_duplicate_and_conflict() -> None:
    reg = CommandIdentityRegistry()
    first = CommandRecord("A", "C1", "I1", "fp", CommandState.PERSISTED)
    assert reg.put_or_get(first) == first
    assert reg.put_or_get(first) == first
    with pytest.raises(CommandConflictError):
        reg.put_or_get(CommandRecord("A", "C1", "I2", "different", CommandState.PERSISTED))


def test_bounded_queue_saturates_explicitly() -> None:
    queue = BoundedMessageQueue(1)
    queue.put(env())
    with pytest.raises(ProtocolError):
        queue.put(env(2))
    assert queue.get() == env()
    assert len(queue) == 0

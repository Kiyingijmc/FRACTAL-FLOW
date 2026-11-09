"""Optional ZeroMQ/Protobuf notification adapter for journal-backed recovery.

This adapter deliberately transports a signed *hint*, not a correction payload.
The receiving consumer must still fetch the next correction from its durable
journal authority before applying it.  Therefore a lost, replayed, or forged
network frame cannot manufacture analytical state.

Only ``inproc://`` endpoints are enabled here.  TCP deployment requires a
separately-owned CURVE/ZAP key-distribution and endpoint-authorisation design;
failing closed is safer than exposing an unauthenticated production socket.
"""

from __future__ import annotations

import hashlib
import hmac
from importlib import import_module
import json
from typing import Any

from src.fractal_flow.data_engine.journal_subscriber import JournalEnvelope, SourceKey


class ZmqProtobufTransportError(ValueError):
    """An optional transport dependency or a safe transport invariant is absent."""


def _dependencies() -> tuple[Any, Any]:
    try:
        zmq = import_module("zmq")
        bytes_value = import_module("google.protobuf.wrappers_pb2").BytesValue
    except ImportError as exc:  # pragma: no cover - proven in dependency-specific gate
        raise ZmqProtobufTransportError("pyzmq and protobuf optional dependencies are unavailable") from exc
    return zmq, bytes_value


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


class ProtobufJournalEnvelopeCodec:
    """Canonical JSON bytes carried by a deterministic protobuf ``BytesValue``.

    JSON is intentional inside the protobuf wrapper: it preserves the native
    integer representation of UTC nanoseconds and journal sequences, which a
    protobuf ``Struct`` would coerce through floating point numbers.
    """

    @staticmethod
    def encode(envelope: JournalEnvelope) -> bytes:
        _zmq, bytes_value = _dependencies()
        message = bytes_value(value=_canonical_json(envelope.unsigned() | {"mac": envelope.mac}))
        return bytes(message.SerializeToString(deterministic=True))

    @staticmethod
    def decode(raw: bytes) -> JournalEnvelope:
        _zmq, bytes_value = _dependencies()
        message = bytes_value()
        try:
            message.ParseFromString(raw)
            value = json.loads(message.value.decode("ascii"))
            required = {
                "v",
                "partition",
                "journal_sequence",
                "aggregate_version",
                "event_id",
                "available_at_ns",
                "source",
                "payload_hash",
                "mac",
            }
            if set(value) != required:
                raise ValueError("unexpected envelope fields")
            source = value["source"]
            if not isinstance(source, list) or len(source) != 6 or not all(isinstance(item, str) for item in source):
                raise ValueError("source key is malformed")
            integer_keys = ("v", "journal_sequence", "aggregate_version", "available_at_ns")
            if any(type(value[key]) is not int or value[key] < 0 for key in integer_keys):
                raise ValueError("envelope integer field is malformed")
            text_keys = ("partition", "event_id", "payload_hash", "mac")
            if any(not isinstance(value[key], str) or not value[key] for key in text_keys):
                raise ValueError("envelope text field is malformed")
            return JournalEnvelope(
                value["v"],
                value["partition"],
                value["journal_sequence"],
                value["aggregate_version"],
                value["event_id"],
                value["available_at_ns"],
                tuple(source),
                value["payload_hash"],
                value["mac"],
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ZmqProtobufTransportError(f"malformed protobuf journal envelope: {exc}") from exc


def _require_inproc(endpoint: str) -> None:
    if not isinstance(endpoint, str) or not endpoint.startswith("inproc://") or len(endpoint) <= len("inproc://"):
        raise ZmqProtobufTransportError("only inproc endpoints are enabled pending CURVE/ZAP endpoint authorization")


class ZeroMqJournalPublisher:
    """Bounded local publisher of signed, journal-recoverable notification hints."""

    def __init__(self, endpoint: str, *, context: Any | None = None, max_queue: int = 256) -> None:
        _require_inproc(endpoint)
        zmq, _bytes_value = _dependencies()
        if type(max_queue) is not int or max_queue < 1:
            raise ValueError("max_queue must be a positive integer")
        self._zmq = zmq
        self._context = context or zmq.Context.instance()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.SNDHWM, max_queue)
        self._socket.bind(endpoint)

    def publish(self, envelope: JournalEnvelope) -> None:
        self._socket.send(ProtobufJournalEnvelopeCodec.encode(envelope), flags=self._zmq.NOBLOCK)

    def close(self) -> None:
        self._socket.close(linger=0)


class ZeroMqJournalSubscriber:
    """Bounded local receiver; it validates a hint but never applies one directly."""

    def __init__(
        self,
        endpoint: str,
        secret: bytes,
        allowed_sources: set[SourceKey],
        *,
        context: Any | None = None,
        max_queue: int = 256,
    ) -> None:
        _require_inproc(endpoint)
        zmq, _bytes_value = _dependencies()
        if not secret or not allowed_sources or type(max_queue) is not int or max_queue < 1:
            raise ValueError("secret, allowed sources, and positive queue bound are required")
        self._zmq, self._secret, self._allowed = zmq, secret, frozenset(allowed_sources)
        self._context = context or zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.RCVHWM, max_queue)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        self._socket.connect(endpoint)

    def poll(self, timeout_ms: int = 0) -> JournalEnvelope | None:
        if type(timeout_ms) is not int or timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if not self._socket.poll(timeout_ms, self._zmq.POLLIN):
            return None
        envelope = ProtobufJournalEnvelopeCodec.decode(self._socket.recv())
        expected = hmac.new(
            self._secret,
            json.dumps(envelope.unsigned(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if (
            envelope.schema_version != 2
            or envelope.source_key not in self._allowed
            or not hmac.compare_digest(expected, envelope.mac)
        ):
            raise ZmqProtobufTransportError("unauthorized, incompatible, or tampered journal hint")
        return envelope

    def close(self) -> None:
        self._socket.close(linger=0)

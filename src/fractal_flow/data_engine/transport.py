"""Dependency-free G4 local transport harness; not a ZeroMQ/Protobuf substitute."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import json

from src.fractal_flow.data_engine.persistence import PersistedQuote


SourceKey = tuple[str, str, str, str, str, str]


class TransportError(ValueError):
    pass


class GapDetected(TransportError):
    pass


@dataclass(frozen=True)
class TransportEnvelope:
    schema_version: int
    partition_id: str
    sequence: int
    event_id: str
    available_time_ns: int
    payload_hash: str
    source_key: tuple[str, str, str, str, str, str]
    mac: str

    def unsigned(self) -> dict[str, object]:
        return {"v": self.schema_version, "partition": self.partition_id, "seq": self.sequence,
                "event_id": self.event_id, "available_time_ns": self.available_time_ns,
                "payload_hash": self.payload_hash, "source": self.source_key}


def _wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class LocalPublisher:
    """Single-process fanout with explicit bounded subscriber queues and HMAC envelopes."""
    def __init__(self, secret: bytes) -> None:
        if not secret:
            raise ValueError("non-empty local transport secret is required")
        self._secret = secret
        self._next: dict[str, int] = {}
        self._subscribers: list[LocalSubscriber] = []

    def subscribe(self, subscriber: "LocalSubscriber") -> None:
        self._subscribers.append(subscriber)

    def publish(self, record: PersistedQuote) -> TransportEnvelope:
        partition = hashlib.sha256(repr((record.quote.source.key, record.quote.instrument_id)).encode()).hexdigest()
        sequence = self._next.get(partition, 0) + 1
        self._next[partition] = sequence
        payload_hash = hashlib.sha256(repr(record.quote).encode()).hexdigest()
        unsigned = {"v": 1, "partition": partition, "seq": sequence, "event_id": record.quote.event_id,
                    "available_time_ns": record.quote.available_time_ns, "payload_hash": payload_hash,
                    "source": record.quote.source.key}
        envelope = TransportEnvelope(1, partition, sequence, record.quote.event_id, record.quote.available_time_ns,
                                     payload_hash, record.quote.source.key,
                                     hmac.new(self._secret, _wire(unsigned), hashlib.sha256).hexdigest())
        for subscriber in self._subscribers:
            subscriber.accept(envelope)
        return envelope


class LocalSubscriber:
    """Read-only envelope receiver.  Saturation rejects; it never silently drops."""
    def __init__(self, secret: bytes, allowed_sources: set[SourceKey], max_queue: int = 256) -> None:
        if not secret or max_queue < 1:
            raise ValueError("secret and positive max_queue are required")
        self._secret = secret
        self._allowed: frozenset[SourceKey] = frozenset(allowed_sources)
        self._items: deque[TransportEnvelope] = deque()
        self._expected: dict[str, int] = {}
        self.max_queue = max_queue

    def accept(self, envelope: TransportEnvelope) -> None:
        if envelope.schema_version != 1 or envelope.source_key not in self._allowed:
            raise TransportError("unauthorized source or unsupported schema")
        expected_mac = hmac.new(self._secret, _wire(envelope.unsigned()), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_mac, envelope.mac):
            raise TransportError("transport authentication failed")
        expected = self._expected.get(envelope.partition_id, 1)
        if envelope.sequence != expected:
            raise GapDetected(f"expected {expected}, received {envelope.sequence}")
        if len(self._items) >= self.max_queue:
            raise TransportError("bounded subscriber queue saturated")
        self._items.append(envelope)
        self._expected[envelope.partition_id] = expected + 1

    def poll(self) -> TransportEnvelope | None:
        return self._items.popleft() if self._items else None

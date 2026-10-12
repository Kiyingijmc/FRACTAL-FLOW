"""Deterministic FFBP/1 protocol primitives for the Python execution boundary.

This module is transport/protocol authority only. It never creates strategy or
risk decisions and never performs broker effects.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import json
import struct
from typing import Any, Deque


PROTOCOL_VERSION = "FFBP/1"
MAX_FRAME_BYTES = 65_536


class ProtocolError(ValueError):
    """Malformed, invalid, or unsafe protocol data."""


class SequenceError(ProtocolError):
    """Sequence is duplicate, stale, or has a gap."""


class AccountBindingError(ProtocolError):
    """Message is not bound to the authenticated account/session."""


class CommandConflictError(ProtocolError):
    """Stable command identity was reused with different content."""


class Channel(StrEnum):
    CONTROL = "CONTROL"
    COMMAND = "COMMAND"
    EVENT = "EVENT"
    SYNC = "SYNC"
    TELEMETRY = "TELEMETRY"


class CommandState(StrEnum):
    PERSISTED = "PERSISTED"
    DISPATCHABLE = "DISPATCHABLE"
    SENT = "SENT"
    BROKER_PENDING = "BROKER_PENDING"
    RECONCILING = "RECONCILING"
    EFFECT_CONFIRMED = "EFFECT_CONFIRMED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class ProtocolEnvelope:
    message_type: str
    account_id: str
    session_id: str
    channel: Channel
    sequence: int
    acknowledgement: int = 0
    command_id: str | None = None
    correlation_id: str | None = None
    sent_at_ms: int = 0
    deadline_ms: int | None = None
    flags: int = 0
    payload: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.version != PROTOCOL_VERSION:
            raise ProtocolError("unsupported protocol version")
        if not self.account_id or not self.session_id:
            raise ProtocolError("account_id and session_id are mandatory")
        if self.sequence < 1 or self.acknowledgement < 0:
            raise ProtocolError("invalid sequence/acknowledgement")
        if self.sent_at_ms < 0 or self.flags < 0:
            raise ProtocolError("invalid timestamp/flags")

    def as_wire_dict(self, include_auth: bool = False, auth: str | None = None) -> dict[str, Any]:
        d = {
            "account_id": self.account_id,
            "ack": self.acknowledgement,
            "channel": self.channel.value,
            "cmd_id": self.command_id,
            "correlation_id": self.correlation_id,
            "deadline_ms": self.deadline_ms,
            "flags": self.flags,
            "payload": self.payload,
            "sent_at_ms": self.sent_at_ms,
            "seq": self.sequence,
            "session_id": self.session_id,
            "type": self.message_type,
            "v": self.version,
        }
        if include_auth:
            d["mac"] = auth
        return d


def canonical_json(value: Any) -> bytes:
    """Canonical UTF-8 JSON shared by the FFBP Python implementation."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"value is not canonicalizable: {exc}") from exc
    return encoded


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def encode_envelope(envelope: ProtocolEnvelope, secret: bytes | None = None) -> bytes:
    body = canonical_json(envelope.as_wire_dict())
    if secret is not None:
        mac = hmac.new(secret, body, hashlib.sha256).hexdigest()
        wire = envelope.as_wire_dict(include_auth=True, auth=mac)
        body = canonical_json(wire)
    if len(body) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds maximum size")
    return struct.pack(">I", len(body)) + body


def decode_envelope(frame: bytes, secret: bytes | None = None) -> ProtocolEnvelope:
    if len(frame) < 4:
        raise ProtocolError("truncated frame header")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("invalid frame length")
    if len(frame) != length + 4:
        raise ProtocolError("frame length mismatch")
    try:
        wire = json.loads(frame[4:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid UTF-8/JSON frame") from exc
    if not isinstance(wire, dict):
        raise ProtocolError("envelope must be an object")
    mac = wire.pop("mac", None)
    unsigned = canonical_json(wire)
    if secret is not None:
        if not isinstance(mac, str):
            raise ProtocolError("missing authentication tag")
        expected = hmac.new(secret, unsigned, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac.lower(), expected.lower()):
            raise ProtocolError("authentication failed")
    elif mac is not None:
        raise ProtocolError("authenticated frame supplied without verifier")
    if wire.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    try:
        return ProtocolEnvelope(
            message_type=str(wire["type"]),
            account_id=str(wire["account_id"]),
            session_id=str(wire["session_id"]),
            channel=Channel(wire["channel"]),
            sequence=int(wire["seq"]),
            acknowledgement=int(wire["ack"]),
            command_id=wire.get("cmd_id"),
            correlation_id=wire.get("correlation_id"),
            sent_at_ms=int(wire["sent_at_ms"]),
            deadline_ms=None if wire.get("deadline_ms") is None else int(wire["deadline_ms"]),
            flags=int(wire["flags"]),
            payload=wire.get("payload"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError("invalid envelope fields") from exc


class SequenceTracker:
    """Strict inbound sequence tracker; gaps require explicit synchronization."""

    def __init__(self, expected: int = 1) -> None:
        if expected < 1:
            raise ValueError("expected sequence must be positive")
        self.expected = expected
        self.sync_required = False

    def accept(self, sequence: int) -> None:
        if self.sync_required:
            raise SequenceError("sequence stream is blocked pending synchronization")
        if sequence < self.expected:
            raise SequenceError("duplicate or stale sequence")
        if sequence > self.expected:
            self.sync_required = True
            raise SequenceError("sequence gap requires synchronization")
        self.expected += 1

    def synchronized(self, next_sequence: int) -> None:
        if next_sequence < 1:
            raise ValueError("next sequence must be positive")
        self.expected = next_sequence
        self.sync_required = False


class AccountSessionFence:
    """Binds protocol messages to one account and one current session."""

    def __init__(self, account_id: str, session_id: str) -> None:
        self.account_id = account_id
        self.session_id = session_id

    def validate(self, envelope: ProtocolEnvelope) -> None:
        if envelope.account_id != self.account_id:
            raise AccountBindingError("account mismatch")
        if envelope.session_id != self.session_id:
            raise AccountBindingError("stale or foreign session")


@dataclass(frozen=True)
class CommandRecord:
    account_id: str
    command_id: str
    intent_id: str
    fingerprint: str
    state: CommandState
    expires_at_ms: int | None = None


class CommandIdentityRegistry:
    """In-memory protocol contract used by tests; durable persistence is the next authority layer."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], CommandRecord] = {}

    def put_or_get(self, record: CommandRecord) -> CommandRecord:
        key = (record.account_id, record.command_id)
        existing = self._records.get(key)
        if existing is None:
            self._records[key] = record
            return record
        if existing.fingerprint != record.fingerprint:
            raise CommandConflictError("command ID reused with different fingerprint")
        return existing


class BoundedMessageQueue:
    """Bounded FIFO queue; saturation is explicit and never silently unbounded."""

    def __init__(self, max_items: int = 256) -> None:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self._items: Deque[ProtocolEnvelope] = deque(maxlen=max_items)
        self.max_items = max_items

    def put(self, envelope: ProtocolEnvelope) -> None:
        if len(self._items) >= self.max_items:
            raise ProtocolError("bounded queue saturated")
        self._items.append(envelope)

    def get(self) -> ProtocolEnvelope | None:
        return self._items.popleft() if self._items else None

    def __len__(self) -> int:
        return len(self._items)

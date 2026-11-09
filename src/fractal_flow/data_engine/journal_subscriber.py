"""Transport-independent, journal-backed correction subscriber continuity.

This module deliberately models local harness semantics only.  The durable
journal, rather than a publisher sequence, authorizes every transition back to
LIVE.  It does not provide exactly-once delivery or an execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import hmac
import json
import threading
from typing import Any

from src.fractal_flow.data_engine.correction_codec import CorrectionScope, DecodedCorrection
from src.fractal_flow.data_engine.correction_persistence import (
    CorrectionCursor,
    CorrectionPersistenceError,
    CorrectionReplayBatch,
    DurableCorrectionJournal,
)


SourceKey = tuple[str, str, str, str, str, str]


class ContinuityError(ValueError):
    """A delivery or recovery cannot establish safe subscriber continuity."""


class GapDetected(ContinuityError):
    """A delivery is not the next authoritative partition record."""


class RecoveryAuthorizationError(ContinuityError):
    """Replay authority is not entitled to serve this subscriber partition."""


class ContinuityState(StrEnum):
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    FAILED = "FAILED"


def _wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _quote_payload(item: DecodedCorrection) -> object:
    quote = item.revision.quote
    if quote is None:
        return None
    return {
        "event_id": quote.event_id,
        "source": quote.source.key,
        "native_record_id": quote.native_record_id,
        "source_sequence": quote.source_sequence,
        "instrument_id": quote.instrument_id,
        "source_symbol": quote.source_symbol,
        "event_time_ns": quote.event_time_ns,
        "received_time_ns": quote.received_time_ns,
        "available_time_ns": quote.available_time_ns,
        "bid": format(quote.bid, "f"),
        "ask": format(quote.ask, "f"),
        "volume": None if quote.volume is None else format(quote.volume, "f"),
        "volume_semantics": quote.volume_semantics.value,
        "raw_payload": dict(quote.raw_payload),
    }


def _payload_hash(item: DecodedCorrection) -> str:
    value = {
        "journal_sequence": item.journal_sequence,
        "aggregate_version": item.aggregate_version,
        "event_id": item.event_id,
        "parent_event_id": item.parent_event_id,
        "scope": {"source": item.scope.source.key, "instrument_id": item.scope.instrument_id},
        "revision": {
            "revision_id": item.revision.revision_id,
            "logical_event_id": item.revision.logical_event_id,
            "supersedes_revision_id": item.revision.supersedes_revision_id,
            "operation": item.revision.operation.value,
            "available_at_ns": item.revision.available_at_ns,
            "quote": _quote_payload(item),
        },
    }
    return hashlib.sha256(_wire(value)).hexdigest()


@dataclass(frozen=True)
class JournalEnvelope:
    """Versioned local carrier bound to one already-decoded correction payload."""

    schema_version: int
    partition_id: str
    journal_sequence: int
    aggregate_version: int
    event_id: str
    available_at_ns: int
    source_key: SourceKey
    payload_hash: str
    mac: str

    def unsigned(self) -> dict[str, object]:
        return {
            "v": self.schema_version,
            "partition": self.partition_id,
            "journal_sequence": self.journal_sequence,
            "aggregate_version": self.aggregate_version,
            "event_id": self.event_id,
            "available_at_ns": self.available_at_ns,
            "source": self.source_key,
            "payload_hash": self.payload_hash,
        }

    @classmethod
    def sign(cls, envelope: "JournalEnvelope", secret: bytes) -> "JournalEnvelope":
        return replace(envelope, mac=hmac.new(secret, _wire(envelope.unsigned()), hashlib.sha256).hexdigest())


@dataclass(frozen=True)
class JournalDelivery:
    """Local harness delivery: authenticated envelope plus decoded payload."""

    correction: DecodedCorrection
    envelope: JournalEnvelope

    @classmethod
    def from_correction(cls, correction: DecodedCorrection, secret: bytes) -> "JournalDelivery":
        envelope = JournalEnvelope(
            schema_version=2,
            partition_id=correction.scope.partition_id,
            journal_sequence=correction.journal_sequence,
            aggregate_version=correction.aggregate_version,
            event_id=correction.event_id,
            available_at_ns=correction.revision.available_at_ns,
            source_key=correction.scope.source.key,
            payload_hash=_payload_hash(correction),
            mac="",
        )
        return cls(correction, JournalEnvelope.sign(envelope, secret))

    @classmethod
    def with_payload_hash(cls, delivery: "JournalDelivery", payload_hash: str, secret: bytes) -> "JournalDelivery":
        return cls(
            delivery.correction, JournalEnvelope.sign(replace(delivery.envelope, payload_hash=payload_hash), secret)
        )

    @classmethod
    def with_partition(cls, delivery: "JournalDelivery", partition_id: str, secret: bytes) -> "JournalDelivery":
        return cls(
            delivery.correction, JournalEnvelope.sign(replace(delivery.envelope, partition_id=partition_id), secret)
        )

    @classmethod
    def with_source(cls, delivery: "JournalDelivery", source_key: SourceKey, secret: bytes) -> "JournalDelivery":
        return cls(delivery.correction, JournalEnvelope.sign(replace(delivery.envelope, source_key=source_key), secret))

    @classmethod
    def with_sequence(
        cls,
        delivery: "JournalDelivery",
        journal_sequence: int,
        aggregate_version: int,
        secret: bytes,
    ) -> "JournalDelivery":
        return cls(
            delivery.correction,
            JournalEnvelope.sign(
                replace(delivery.envelope, journal_sequence=journal_sequence, aggregate_version=aggregate_version),
                secret,
            ),
        )


class JournalReplayAuthority:
    """Narrow read-only replay authority for one allowed source set."""

    def __init__(self, store: DurableCorrectionJournal, allowed_sources: set[SourceKey]) -> None:
        if not isinstance(store, DurableCorrectionJournal) or not allowed_sources:
            raise TypeError("store and non-empty allowed source set are required")
        self._store = store
        self._allowed_sources = frozenset(allowed_sources)

    def capture(self, scope: CorrectionScope, cursor: CorrectionCursor) -> CorrectionReplayBatch:
        if scope.source.key not in self._allowed_sources:
            raise RecoveryAuthorizationError("replay source/lane is not authorized")
        try:
            return self._store.replay_batch_after(scope, cursor)
        except CorrectionPersistenceError as exc:
            raise ContinuityError(f"authoritative replay cursor/history rejected: {exc}") from exc

    def next_after(self, scope: CorrectionScope, cursor: CorrectionCursor) -> DecodedCorrection | None:
        batch = self.capture(scope, cursor)
        return batch.records[0] if batch.records else None


class JournalBackedSubscriber:
    """Fail-closed local subscriber that resumes only through journal replay."""

    def __init__(
        self,
        secret: bytes,
        scope: CorrectionScope,
        allowed_sources: set[SourceKey],
        *,
        known_at_ns: int = 0,
        max_queue: int = 256,
        checkpoint: CorrectionCursor | None = None,
        initial_recovery: bool = False,
    ) -> None:
        if not secret or not isinstance(scope, CorrectionScope) or scope.source.key not in allowed_sources:
            raise ValueError("secret, scope, and matching allowed source are required")
        if type(known_at_ns) is not int or known_at_ns < 0 or type(max_queue) is not int or max_queue < 1:
            raise ValueError("knowledge time and queue capacity are invalid")
        self._secret = secret
        self._scope = scope
        self._allowed_sources = frozenset(allowed_sources)
        self._known_at_ns = known_at_ns
        self._max_queue = max_queue
        self._checkpoint = checkpoint or CorrectionCursor(scope.partition_id, 0, 0)
        if self._checkpoint.partition_id != scope.partition_id:
            raise ValueError("checkpoint partition does not match subscriber scope")
        self._state = (
            ContinuityState.DEGRADED if initial_recovery or self._checkpoint.aggregate_version else ContinuityState.LIVE
        )
        self._held: list[JournalDelivery] = []
        self._retained: dict[int, JournalDelivery] = {}
        self._lock = threading.RLock()

    @property
    def state(self) -> ContinuityState:
        return self._state

    @property
    def checkpoint(self) -> CorrectionCursor:
        return self._checkpoint

    def visible(self) -> tuple[DecodedCorrection, ...]:
        with self._lock:
            return tuple(
                delivery.correction
                for _, delivery in sorted(self._retained.items())
                if delivery.correction.revision.available_at_ns <= self._known_at_ns
            )

    def advance_knowledge_time(self, watermark_ns: int) -> None:
        with self._lock:
            if type(watermark_ns) is not int or watermark_ns < self._known_at_ns:
                raise ContinuityError("knowledge time must advance monotonically")
            self._known_at_ns = watermark_ns

    def degrade(self, _reason: str) -> None:
        with self._lock:
            if self._state is not ContinuityState.FAILED:
                self._state = ContinuityState.DEGRADED

    def _fail(self, message: str, exc_type: type[ContinuityError] = ContinuityError) -> None:
        self._state = ContinuityState.FAILED
        raise exc_type(message)

    def _validate_delivery(self, delivery: JournalDelivery) -> None:
        envelope, item = delivery.envelope, delivery.correction
        expected_mac = hmac.new(self._secret, _wire(envelope.unsigned()), hashlib.sha256).hexdigest()
        if envelope.schema_version != 2 or not hmac.compare_digest(expected_mac, envelope.mac):
            self._fail("transport envelope authentication/version failed")
        if envelope.source_key not in self._allowed_sources or envelope.source_key != item.scope.source.key:
            self._fail("source/lane identity is unauthorized or mismatched")
        if envelope.partition_id != self._scope.partition_id or envelope.partition_id != item.scope.partition_id:
            self._fail("partition identity is unauthorized or mismatched")
        if (
            envelope.journal_sequence != item.journal_sequence
            or envelope.aggregate_version != item.aggregate_version
            or envelope.event_id != item.event_id
            or envelope.available_at_ns != item.revision.available_at_ns
        ):
            self._fail("durable envelope fields conflict with correction payload")
        if envelope.payload_hash != _payload_hash(item):
            self._fail("conflicting delivery payload hash")

    @staticmethod
    def _same_record(left: DecodedCorrection, right: DecodedCorrection) -> bool:
        return bool(
            left.journal_sequence == right.journal_sequence
            and left.aggregate_version == right.aggregate_version
            and left.event_id == right.event_id
            and left.scope == right.scope
            and left.revision == right.revision
        )

    def _apply(self, delivery: JournalDelivery) -> None:
        item = delivery.correction
        if item.aggregate_version <= self._checkpoint.aggregate_version:
            previous = self._retained.get(item.aggregate_version)
            if (
                previous is not None
                and previous.envelope == delivery.envelope
                and self._same_record(previous.correction, item)
            ):
                return
            self._fail("conflicting duplicate or stale durable delivery")
        if item.aggregate_version != self._checkpoint.aggregate_version + 1:
            raise GapDetected("durable aggregate-version discontinuity")
        if self._checkpoint.journal_sequence and item.journal_sequence <= self._checkpoint.journal_sequence:
            self._fail("durable journal position regressed")
        self._retained[item.aggregate_version] = delivery
        self._checkpoint = CorrectionCursor(item.scope.partition_id, item.journal_sequence, item.aggregate_version)

    def _require_authoritative_next(self, delivery: JournalDelivery, authority: JournalReplayAuthority) -> None:
        expected = authority.next_after(self._scope, self._checkpoint)
        if expected is None:
            self._fail("delivery has no authoritative journal record")
        assert expected is not None
        if not self._same_record(expected, delivery.correction):
            if delivery.correction.aggregate_version > expected.aggregate_version:
                raise GapDetected("delivery skips the authoritative next correction")
            self._fail("delivery conflicts with the authoritative next correction")

    def _verify_prior_duplicate(self, delivery: JournalDelivery, authority: JournalReplayAuthority) -> None:
        """A post-restart duplicate is safe only after journal-history proof."""
        origin = CorrectionCursor(self._scope.partition_id, 0, 0)
        history = authority.capture(self._scope, origin).records
        matching = next(
            (item for item in history if item.aggregate_version == delivery.correction.aggregate_version), None
        )
        if matching is None or not self._same_record(matching, delivery.correction):
            self._fail("duplicate delivery conflicts with authoritative history")
        self._retained.setdefault(delivery.correction.aggregate_version, delivery)

    def receive(self, delivery: JournalDelivery, authority: JournalReplayAuthority) -> None:
        with self._lock:
            if self._state is ContinuityState.FAILED:
                raise ContinuityError("subscriber is fail-closed")
            self._validate_delivery(delivery)
            if delivery.correction.aggregate_version <= self._checkpoint.aggregate_version:
                self._verify_prior_duplicate(delivery, authority)
                self._apply(delivery)
                return
            if self._state in (ContinuityState.RECOVERING, ContinuityState.VERIFYING):
                if len(self._held) >= self._max_queue:
                    self._state = ContinuityState.DEGRADED
                    raise ContinuityError("recovery holdback queue saturated")
                self._held.append(delivery)
                return
            if self._state is not ContinuityState.LIVE:
                raise ContinuityError("subscriber requires authoritative recovery")
            try:
                self._require_authoritative_next(delivery, authority)
                self._apply(delivery)
            except GapDetected:
                self._state = ContinuityState.DEGRADED
                raise

    def begin_recovery(self, authority: JournalReplayAuthority, *, max_holdback: int | None = None) -> None:
        with self._lock:
            if self._state is not ContinuityState.DEGRADED:
                raise ContinuityError("recovery may begin only from DEGRADED")
            if max_holdback is not None:
                if type(max_holdback) is not int or max_holdback < 1:
                    raise ValueError("recovery holdback capacity must be positive")
                self._max_queue = max_holdback
            try:
                authority.capture(self._scope, self._checkpoint)
            except RecoveryAuthorizationError:
                self._state = ContinuityState.FAILED
                raise
            except ContinuityError:
                self._state = ContinuityState.FAILED
                raise
            self._state = ContinuityState.RECOVERING

    def complete_recovery(self, authority: JournalReplayAuthority) -> None:
        with self._lock:
            if self._state is not ContinuityState.RECOVERING:
                raise ContinuityError("recovery was not started")
            self._state = ContinuityState.VERIFYING
            try:
                while True:
                    batch = authority.capture(self._scope, self._checkpoint)
                    for item in batch.records:
                        delivery = JournalDelivery.from_correction(item, self._secret)
                        self._validate_delivery(delivery)
                        self._apply(delivery)
                    held, self._held = self._held, []
                    for delivery in held:
                        self._validate_delivery(delivery)
                        if delivery.correction.aggregate_version > self._checkpoint.aggregate_version:
                            self._require_authoritative_next(delivery, authority)
                        else:
                            self._verify_prior_duplicate(delivery, authority)
                        self._apply(delivery)
                    if not self._held:
                        self._state = ContinuityState.LIVE
                        return
            except GapDetected as exc:
                self._state = ContinuityState.DEGRADED
                raise ContinuityError(f"recovery verification found a gap: {exc}") from exc
            except ContinuityError:
                if self._state is not ContinuityState.DEGRADED:
                    self._state = ContinuityState.FAILED
                raise

    def recover(self, authority: JournalReplayAuthority) -> None:
        self.begin_recovery(authority)
        self.complete_recovery(authority)

    def persist_checkpoint(self, checkpoint_store: Any, authority: JournalReplayAuthority, subscriber_id: str) -> Any:
        """Persist only an already-processed, authority-validated cursor.

        A failed sidecar write leaves the preceding journal state valid and may
        replay duplicates after restart; it never licenses skipping records.
        """
        with self._lock:
            if self._state is not ContinuityState.LIVE:
                raise ContinuityError("checkpoint publication requires LIVE continuity")
            return checkpoint_store.commit(subscriber_id, self._scope, self._checkpoint, authority)

    @classmethod
    def restart_from_checkpoint(
        cls,
        secret: bytes,
        scope: CorrectionScope,
        allowed_sources: set[SourceKey],
        authority: JournalReplayAuthority,
        checkpoint_store: Any,
        subscriber_id: str,
        *,
        known_at_ns: int = 0,
        max_queue: int = 256,
    ) -> "JournalBackedSubscriber":
        """Fail closed until the loaded sidecar cursor is replay-verified."""
        checkpoint = checkpoint_store.load_verified(subscriber_id, scope, authority)
        subscriber = cls(
            secret,
            scope,
            allowed_sources,
            known_at_ns=known_at_ns,
            max_queue=max_queue,
            checkpoint=None if checkpoint is None else checkpoint.cursor,
            initial_recovery=True,
        )
        subscriber.recover(authority)
        subscriber.persist_checkpoint(checkpoint_store, authority, subscriber_id)
        return subscriber

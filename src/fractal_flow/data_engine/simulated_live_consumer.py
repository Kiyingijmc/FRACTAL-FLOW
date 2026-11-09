"""Read-only simulated-live analytical consumer over the G4 continuity boundary.

The durable correction journal remains the sole history authority.  This class
does not deserialize a transport itself, write corrections, or expose any
execution capability.  It only admits already-authenticated ``JournalDelivery``
objects through :class:`JournalBackedSubscriber`, and it refuses to emit a
snapshot unless that subscriber has authoritatively caught up to its partition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import CorrectionCursor, DurableCorrectionJournal
from src.fractal_flow.data_engine.journal_subscriber import (
    ContinuityError,
    ContinuityState,
    JournalBackedSubscriber,
    JournalDelivery,
    JournalReplayAuthority,
    SourceKey,
)
from src.fractal_flow.data_engine.replay_consumer import DeterministicReplayConsumer, ReplaySnapshot


class SimulatedLiveConsumerError(ValueError):
    """The simulated consumer cannot safely establish an analytical state."""


@dataclass(frozen=True)
class SimulatedLiveSnapshot:
    """An analytical snapshot proved to be caught up through ``cursor``.

    ``replay`` is deliberately the same value shape produced by deterministic
    replay.  This makes reconciliation a value comparison, rather than a
    comparison of two lossy consumer-specific projections.
    """

    cursor: CorrectionCursor
    replay: ReplaySnapshot

    @property
    def fingerprint(self) -> str:
        return self.replay.fingerprint


class SimulatedLiveConsumer:
    """Fail-closed simulated stream consumer with journal-backed recovery.

    A checkpoint store is optional for ephemeral test consumers.  When supplied
    it must already be the exclusively-owned G4 ``SubscriberCheckpointStore``;
    this class never bypasses checkpoint ownership or manufactures a cursor.
    """

    def __init__(
        self,
        corrections: DurableCorrectionJournal,
        scope: CorrectionScope,
        secret: bytes,
        allowed_sources: set[SourceKey],
        *,
        subscriber_id: str | None = None,
        checkpoint_store: Any | None = None,
        known_at_ns: int = 0,
        max_queue: int = 256,
        max_replay_records: int = 100_000,
    ) -> None:
        if not isinstance(corrections, DurableCorrectionJournal):
            raise TypeError("corrections must be a durable correction journal")
        if not isinstance(scope, CorrectionScope) or scope.source.key not in allowed_sources:
            raise ValueError("scope must be authorized by the allowed source set")
        if checkpoint_store is not None and (not isinstance(subscriber_id, str) or not subscriber_id):
            raise ValueError("a non-empty subscriber_id is required with a checkpoint store")
        self._corrections = corrections
        self._scope = scope
        self._authority = JournalReplayAuthority(corrections, allowed_sources)
        self._secret = secret
        self._allowed_sources = set(allowed_sources)
        self._subscriber_id = subscriber_id
        self._checkpoint_store = checkpoint_store
        self._known_at_ns = known_at_ns
        self._max_queue = max_queue
        self._replay = DeterministicReplayConsumer(corrections, max_records=max_replay_records)
        self._subscriber: JournalBackedSubscriber | None = None

    @property
    def state(self) -> ContinuityState:
        return ContinuityState.DEGRADED if self._subscriber is None else self._subscriber.state

    @property
    def checkpoint(self) -> CorrectionCursor | None:
        return None if self._subscriber is None else self._subscriber.checkpoint

    def start(self) -> None:
        """Recover authoritative history before accepting any live delivery."""
        if self._subscriber is not None:
            raise SimulatedLiveConsumerError("consumer was already started")
        try:
            if self._checkpoint_store is not None:
                assert self._subscriber_id is not None
                subscriber = JournalBackedSubscriber.restart_from_checkpoint(
                    self._secret,
                    self._scope,
                    self._allowed_sources,
                    self._authority,
                    self._checkpoint_store,
                    self._subscriber_id,
                    known_at_ns=self._known_at_ns,
                    max_queue=self._max_queue,
                )
            else:
                subscriber = JournalBackedSubscriber(
                    self._secret,
                    self._scope,
                    self._allowed_sources,
                    known_at_ns=self._known_at_ns,
                    max_queue=self._max_queue,
                    initial_recovery=True,
                )
                subscriber.recover(self._authority)
            self._subscriber = subscriber
        except (ContinuityError, ValueError) as exc:
            raise SimulatedLiveConsumerError(f"initial authoritative recovery failed: {exc}") from exc

    def receive(self, delivery: JournalDelivery) -> None:
        """Apply one authenticated live delivery or transition fail-closed."""
        if self._subscriber is None:
            raise SimulatedLiveConsumerError("consumer must recover before live delivery")
        try:
            self._subscriber.receive(delivery, self._authority)
        except ContinuityError as exc:
            raise SimulatedLiveConsumerError(f"live delivery rejected: {exc}") from exc

    def degrade(self, reason: str) -> None:
        if self._subscriber is None:
            raise SimulatedLiveConsumerError("consumer must start before it can degrade")
        self._subscriber.degrade(reason)

    def recover(self) -> None:
        """Discard transport assumptions and reconstruct from durable history."""
        if self._subscriber is None:
            raise SimulatedLiveConsumerError("consumer must start before recovery")
        try:
            self._subscriber.recover(self._authority)
            if self._checkpoint_store is not None:
                assert self._subscriber_id is not None
                self._subscriber.persist_checkpoint(self._checkpoint_store, self._authority, self._subscriber_id)
        except ContinuityError as exc:
            raise SimulatedLiveConsumerError(f"authoritative recovery failed: {exc}") from exc

    def advance_knowledge_time(self, watermark_ns: int) -> None:
        if self._subscriber is None:
            raise SimulatedLiveConsumerError("consumer must start before knowledge time advances")
        try:
            self._subscriber.advance_knowledge_time(watermark_ns)
        except ContinuityError as exc:
            raise SimulatedLiveConsumerError(f"knowledge time rejected: {exc}") from exc
        self._known_at_ns = watermark_ns

    def snapshot(self) -> SimulatedLiveSnapshot:
        """Return a replay-equivalent view only after proving no unseen records.

        Querying the journal directly without this cursor check could leak a
        correction that was durable but never delivered to this simulated-live
        subscriber.  The explicit catch-up proof closes that lookahead path.
        """
        if self._subscriber is None or self._subscriber.state is not ContinuityState.LIVE:
            raise SimulatedLiveConsumerError("analytical snapshot unavailable while continuity is not LIVE")
        try:
            unseen = self._authority.capture(self._scope, self._subscriber.checkpoint).records
        except ContinuityError as exc:
            self._subscriber.degrade("authoritative snapshot verification failed")
            raise SimulatedLiveConsumerError(f"snapshot history validation failed: {exc}") from exc
        if unseen:
            self._subscriber.degrade("live stream is behind durable authority")
            raise SimulatedLiveConsumerError("analytical snapshot blocked until durable catch-up completes")
        try:
            replay = self._replay.replay(self._known_at_ns, {self._scope})
        except ValueError as exc:
            self._subscriber.degrade("replay projection failed")
            raise SimulatedLiveConsumerError(f"analytical projection failed: {exc}") from exc
        return SimulatedLiveSnapshot(self._subscriber.checkpoint, replay)

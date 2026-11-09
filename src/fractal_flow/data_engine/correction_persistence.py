"""Fail-closed durable correction history layered on ``DurableEventJournal``.

This adapter neither changes generic journal semantics nor claims cross-process
writer safety.  Following any append exception it refuses further writes until a
fresh journal instance has authoritatively replayed the backing history.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from typing import Iterable

from src.fractal_flow.data_engine.correction_codec import (
    CORRECTION_AGGREGATE_TYPE, CorrectionScope, DecodedCorrection,
    decode_correction, encode_correction, event_id_for,
)
from src.fractal_flow.data_engine.revisions import QuoteRevision, ResolvedQuote, RevisionConflict, resolve_revisions
from src.fractal_flow.persistence.journal import DurableEventJournal


class CorrectionPersistenceError(ValueError):
    """Durable correction append/recovery cannot be safely completed."""


class CorrectionPersistenceConflict(CorrectionPersistenceError):
    """A stable correction identity was reused with different canonical content."""


class CorrectionStoreState(StrEnum):
    ACTIVE = "ACTIVE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class CorrectionCursor:
    """A partition-bound cursor: global journal position plus local aggregate version.

    Global journal sequences necessarily have gaps when records for other
    partitions are filtered.  Consumers must therefore check local aggregate
    version continuity, while retaining global position for audit/replay bounds.
    """

    partition_id: str
    journal_sequence: int
    aggregate_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.partition_id, str) or not self.partition_id:
            raise CorrectionPersistenceError("cursor partition_id is required")
        if type(self.journal_sequence) is not int or self.journal_sequence < 0:
            raise CorrectionPersistenceError("cursor journal_sequence must be non-negative")
        if type(self.aggregate_version) is not int or self.aggregate_version < 0:
            raise CorrectionPersistenceError("cursor aggregate_version must be non-negative")


@dataclass(frozen=True)
class CorrectionReplayBatch:
    """One validated, partition-local replay range from one journal snapshot."""

    start_cursor: CorrectionCursor
    end_cursor: CorrectionCursor
    records: tuple[DecodedCorrection, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class RecoverySnapshot:
    records: tuple[DecodedCorrection, ...]

    @property
    def fingerprint(self) -> str:
        value = [
            {
                "journal_sequence": item.journal_sequence,
                "aggregate_version": item.aggregate_version,
                "event_id": item.event_id,
                "revision": item.revision.revision_id,
                "scope": item.scope.partition_id,
            }
            for item in self.records
        ]
        return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class DurableCorrectionJournal:
    """Single-process correction writer plus full-history recovery reader."""

    ROOT_PARENT = "DATA_ENGINE_CORRECTION_ROOT"

    def __init__(self, journal: DurableEventJournal) -> None:
        if not isinstance(journal, DurableEventJournal):
            raise TypeError("journal must be DurableEventJournal")
        self._journal = journal
        self._state = CorrectionStoreState.ACTIVE

    @property
    def state(self) -> CorrectionStoreState:
        return self._state

    @classmethod
    def recover(cls, journal: DurableEventJournal) -> "DurableCorrectionJournal":
        """Create a clean writer only after the supplied journal fully validates.

        For file-backed uncertainty, callers must construct a *fresh* generic
        journal from the durable path before calling this method.  A process-local
        object may lack a post-fsync record that is already durable on disk.
        """
        adapter = cls(journal)
        adapter.snapshot()  # validate every relevant record before becoming usable
        return adapter

    def _records(self) -> tuple[DecodedCorrection, ...]:
        decoded: list[DecodedCorrection] = []
        for record in self._journal.get_all_records():
            if record.event.aggregate_type == CORRECTION_AGGREGATE_TYPE:
                decoded.append(decode_correction(record))
        self._validate_history(decoded)
        return tuple(decoded)

    @staticmethod
    def _validate_history(records: Iterable[DecodedCorrection]) -> None:
        by_logical: dict[tuple[str, str], list[DecodedCorrection]] = {}
        event_ids: set[str] = set()
        revision_ids: set[tuple[str, str]] = set()
        for item in records:
            if item.event_id in event_ids:
                raise CorrectionPersistenceError("duplicate correction event identity")
            event_ids.add(item.event_id)
            key = (item.scope.partition_id, item.revision.logical_event_id)
            revision_key = (item.scope.partition_id, item.revision.revision_id)
            if revision_key in revision_ids:
                raise CorrectionPersistenceError("duplicate correction revision identity in scope")
            revision_ids.add(revision_key)
            by_logical.setdefault(key, []).append(item)
        for chain in by_logical.values():
            # Existing resolver proves roots/forks/connectivity, availability, and scope continuity.
            try:
                resolve_revisions(tuple(item.revision for item in chain), 2**63 - 1)
            except RevisionConflict as exc:
                raise CorrectionPersistenceError(f"invalid correction lineage: {exc}") from exc
            by_revision = {item.revision.revision_id: item for item in chain}
            for item in chain:
                parent = item.revision.supersedes_revision_id
                if parent is None:
                    if item.parent_event_id != DurableCorrectionJournal.ROOT_PARENT:
                        raise CorrectionPersistenceError("root correction parent is invalid")
                else:
                    predecessor = by_revision.get(parent)
                    if predecessor is None:
                        raise CorrectionPersistenceError("missing correction predecessor")
                    if item.aggregate_version <= predecessor.aggregate_version:
                        raise CorrectionPersistenceError("revision aggregate ordering regressed")
                    if item.parent_event_id != predecessor.event_id:
                        raise CorrectionPersistenceError("revision envelope parent does not bind predecessor")

    def snapshot(self) -> RecoverySnapshot:
        # _records validates the whole correction history, including future records.
        return RecoverySnapshot(self._records())

    def append(self, revision: QuoteRevision) -> DecodedCorrection:
        if self._state is not CorrectionStoreState.ACTIVE:
            raise CorrectionPersistenceError("append prohibited until authoritative recovery completes")
        if not isinstance(revision, QuoteRevision):
            raise TypeError("revision must be QuoteRevision")
        # Pure validation failures occur before any append attempt and must not
        # spuriously fault an otherwise known journal state.
        history = self._records()
        scope, parent_event_id = self._scope_and_parent(revision, history)
        desired_event_id = event_id_for(revision, scope)
        for item in history:
            if item.event_id == desired_event_id:
                if item.revision == revision and item.scope == scope:
                    return item
                raise CorrectionPersistenceConflict("correction event identity reused with different content")
        if any(item.scope == scope and item.revision.revision_id == revision.revision_id for item in history):
            raise CorrectionPersistenceConflict("correction revision identity reused in the same scope")
        try:
            resolve_revisions(
                tuple(
                    item.revision for item in history
                    if item.scope == scope and item.revision.logical_event_id == revision.logical_event_id
                ) + (revision,),
                2**63 - 1,
            )
        except RevisionConflict as exc:
            raise CorrectionPersistenceError(f"candidate correction lineage is invalid: {exc}") from exc
        event = encode_correction(
            revision, scope,
            self._journal.get_aggregate_sequence(CORRECTION_AGGREGATE_TYPE, scope.partition_id) + 1,
            parent_event_id,
        )
        try:
            record = self._journal.append(event)
            decoded = decode_correction(record)
            # Validate after append so a coding defect cannot silently create a bad local chain.
            self._validate_history((*history, decoded))
            return decoded
        except Exception as exc:
            # In particular AFTER_JOURNAL_FSYNC exceptions have an uncertain durable outcome.
            self._state = CorrectionStoreState.RECOVERY_REQUIRED
            raise CorrectionPersistenceError(f"correction append outcome is uncertain; recovery required: {exc}") from exc

    def _scope_and_parent(self, revision: QuoteRevision, history: tuple[DecodedCorrection, ...]) -> tuple[CorrectionScope, str]:
        if revision.supersedes_revision_id is None:
            if revision.quote is None:
                raise CorrectionPersistenceError("root CANCEL is not a correction observation")
            return CorrectionScope.from_quote(revision.quote), self.ROOT_PARENT
        matches = [item for item in history if item.revision.revision_id == revision.supersedes_revision_id]
        if len(matches) != 1:
            raise CorrectionPersistenceError("correction predecessor is absent or ambiguous")
        predecessor = matches[0]
        if predecessor.revision.logical_event_id != revision.logical_event_id:
            raise CorrectionPersistenceError("predecessor belongs to a different logical event")
        if revision.quote is not None and CorrectionScope.from_quote(revision.quote) != predecessor.scope:
            raise CorrectionPersistenceError("correction quote changes source or instrument scope")
        return predecessor.scope, predecessor.event_id

    def replay_as_known_at(self, watermark_ns: int) -> tuple[ResolvedQuote, ...]:
        if type(watermark_ns) is not int or watermark_ns < 0:
            raise CorrectionPersistenceError("watermark_ns must be a non-negative integer")
        records = self._records()  # intentionally before watermark filtering
        grouped: dict[tuple[str, str], list[QuoteRevision]] = {}
        for item in records:
            grouped.setdefault((item.scope.partition_id, item.revision.logical_event_id), []).append(item.revision)
        visible: list[ResolvedQuote] = []
        for revisions in grouped.values():
            visible.extend(resolve_revisions(tuple(revisions), watermark_ns).values())
        return tuple(sorted(visible, key=lambda item: (item.quote.available_time_ns, item.logical_event_id)))

    def cursor(self, scope: CorrectionScope) -> CorrectionCursor:
        records = [item for item in self._records() if item.scope == scope]
        if not records:
            return CorrectionCursor(scope.partition_id, 0, 0)
        last = max(records, key=lambda item: item.aggregate_version)
        return CorrectionCursor(scope.partition_id, last.journal_sequence, last.aggregate_version)

    def replay_batch_after(self, scope: CorrectionScope, cursor: CorrectionCursor) -> CorrectionReplayBatch:
        """Return a replay range and its cutoff from one fully validated snapshot.

        The returned cutoff is intentionally partition-local.  Global journal
        sequence is retained for audit and stale-cursor detection but must not
        be interpreted as a gap counter after partition filtering.
        """
        if cursor.partition_id != scope.partition_id:
            raise CorrectionPersistenceError("cursor scope mismatch")
        records = sorted(
            (item for item in self._records() if item.scope == scope),
            key=lambda item: item.aggregate_version,
        )
        if cursor.aggregate_version > len(records):
            raise CorrectionPersistenceError("cursor aggregate version exceeds authoritative partition history")
        if cursor.aggregate_version and records[cursor.aggregate_version - 1].journal_sequence != cursor.journal_sequence:
            raise CorrectionPersistenceError("cursor does not match authoritative partition history")
        end = cursor if not records else CorrectionCursor(
            scope.partition_id, records[-1].journal_sequence, records[-1].aggregate_version,
        )
        return CorrectionReplayBatch(cursor, end, tuple(item for item in records if item.aggregate_version > cursor.aggregate_version))

    def replay_after(self, scope: CorrectionScope, cursor: CorrectionCursor) -> tuple[DecodedCorrection, ...]:
        """Compatibility wrapper for callers that need only replay records."""
        return self.replay_batch_after(scope, cursor).records

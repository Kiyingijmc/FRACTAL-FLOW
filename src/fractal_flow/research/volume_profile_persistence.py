"""Journal-backed persistence adapter for Volume Profile revision chains (G3b Unit 1).

The adapter is intentionally analytical-only. It contains failures at the VP boundary
rather than changing the generic journal's crash contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import (
    DurableEventJournal,
    JournalRecord,
)
from src.fractal_flow.research.volume_profile_event_codec import (
    VP_AUTHORITY,
    VP_REVISION_AGGREGATE_TYPE,
    VP_REVISION_EVENT_TYPE,
    VP_ROOT_PARENT_ID,
    ProfileRevisionCodecError,
    ProfileRevisionContext,
    decode_profile_revision,
    encode_profile_revision,
)
from src.fractal_flow.research.volume_profile_revisions import (
    ProfileRevision,
    RevisionHistoryError,
    RevisionOperation,
    RevisionResolution,
    resolve_profile_revisions,
)
from src.fractal_flow.research.volume_profile import ProfileEvent


class ProfilePersistenceError(RuntimeError):
    """Base class for fail-closed Volume Profile persistence errors."""


class ProfilePersistenceFaulted(ProfilePersistenceError):
    """The adapter instance is unsafe to mutate after an uncertain append outcome."""


class ProfilePersistenceConflict(ProfilePersistenceError):
    """An incoming operation conflicts with authoritative immutable history."""


class ProfilePersistenceCorruption(ProfilePersistenceError):
    """The durable Volume Profile history violates the canonical contract."""


@dataclass(frozen=True, slots=True)
class _StoredRevision:
    revision: ProfileRevision
    event: Event
    record: JournalRecord
    context: ProfileRevisionContext


class VolumeProfilePersistence:
    """Persist and recover canonical VP revisions using a DurableEventJournal.

    ``journal_factory`` must return a *fresh* journal over the same authoritative
    durable source. If omitted, a file-backed journal gets a safe factory that
    reopens the same path with tail truncation disabled. In-memory journals cannot
    recover an uncertain append and therefore remain fail-closed after exceptions.

    This adapter assumes one writer per journal/store process. It does not claim
    cross-process compare-and-append safety.
    """

    def __init__(
        self,
        journal: DurableEventJournal,
        *,
        journal_factory: Callable[[], DurableEventJournal] | None = None,
    ) -> None:
        if not isinstance(journal, DurableEventJournal):
            raise TypeError("journal must be DurableEventJournal")
        self._journal = journal
        self._journal_factory: Callable[[], DurableEventJournal] | None
        if journal_factory is not None:
            self._journal_factory = journal_factory
        elif journal.journal_file_path is not None:
            path = str(journal.journal_file_path)
            self._journal_factory = lambda: DurableEventJournal(path, truncate_corrupted_tail=False)
        else:
            self._journal_factory = None
        self._faulted = False
        self._lock = __import__("threading").RLock()
        self._stored_by_aggregate: dict[str, list[_StoredRevision]] = {}
        self._stored_by_revision: dict[tuple[str, str], _StoredRevision] = {}
        self._rebuild_from_journal(journal)

    @property
    def authority(self) -> str:
        return VP_AUTHORITY

    @property
    def faulted(self) -> bool:
        return self._faulted

    @property
    def journal(self) -> DurableEventJournal:
        """Read-only access to the underlying journal for diagnostics/integration."""
        return self._journal

    def recover(self) -> "VolumeProfilePersistence":
        """Return a new adapter rebuilt from a fresh authoritative journal instance."""
        if self._journal_factory is None:
            raise ProfilePersistenceFaulted(
                "cannot recover an uncertain in-memory journal; supply a fresh journal_factory"
            )
        try:
            fresh = self._journal_factory()
            if fresh is self._journal:
                raise ProfilePersistenceFaulted("journal_factory must return a fresh journal instance")
            return VolumeProfilePersistence(fresh, journal_factory=self._journal_factory)
        except ProfilePersistenceError:
            raise
        except Exception as exc:
            raise ProfilePersistenceCorruption(f"authoritative journal recovery failed: {exc}") from exc

    def append(
        self,
        revision: ProfileRevision,
        *,
        context: ProfileRevisionContext | None = None,
    ) -> JournalRecord:
        """Append a revision after validating the entire currently visible chain.

        CANCEL requires identity context because it carries no ProfileEvent. Exact
        retries are idempotent only when the canonical Event equals the durable
        Event. Any journal.append exception faults this adapter instance.
        """
        with self._lock:
            self._ensure_usable()
            if not isinstance(revision, ProfileRevision):
                raise TypeError("revision must be ProfileRevision")

            if revision.operation is RevisionOperation.UPSERT:
                identity = self._identity_for_revision(revision)
                if context is not None and (context.source_id, context.symbol, context.domain) != (
                    identity.source_id, identity.symbol, identity.domain
                ):
                    raise ProfilePersistenceConflict("supplied context conflicts with UPSERT identity")
            elif revision.operation is RevisionOperation.CANCEL:
                if not isinstance(context, ProfileRevisionContext):
                    raise ProfilePersistenceConflict("CANCEL requires explicit ProfileRevisionContext")
                identity = context
            else:
                raise ProfilePersistenceConflict("unsupported revision operation")

            aggregate_id = self._aggregate_id_from_context(revision.logical_event_id, identity)
            chain = self._stored_by_aggregate.get(aggregate_id, [])
            existing = self._stored_by_revision.get((aggregate_id, revision.revision_id))
            if existing is not None:
                existing_index = chain.index(existing)
                prefix = chain[:existing_index]
                expected = self._encode_against_predecessor(revision, prefix, existing.event.aggregate_version)
                if expected != existing.event:
                    raise ProfilePersistenceConflict(
                        "revision_id already exists with different canonical content"
                    )
                return existing.record

            head = chain[-1] if chain else None
            expected_predecessor = head.revision.revision_id if head else None
            if revision.supersedes_revision_id != expected_predecessor:
                raise ProfilePersistenceConflict(
                    f"revision must supersede current chain head {expected_predecessor!r}"
                )
            self._validate_lifecycle(revision, head)

            # Reject history that recovery would reject. This must happen
            # before encoding or mutating the authoritative journal.
            if head is not None and revision.available_at_ns < head.revision.available_at_ns:
                raise ProfilePersistenceConflict(
                    "revision availability regresses along chain"
                )

            next_version = len(chain) + 1
            event = self._encode_against_predecessor(revision, chain, next_version)
            try:
                decoded, _ = decode_profile_revision(event, context=self._context_for_decode(revision, chain))
                if decoded != revision:
                    raise ProfilePersistenceConflict("codec round-trip differs from submitted revision")
            except (ProfileRevisionCodecError, RevisionHistoryError) as exc:
                raise ProfilePersistenceConflict(f"candidate failed canonical round-trip: {exc}") from exc

            try:
                record = self._journal.append(event)
            except Exception:
                # Includes AFTER_JOURNAL_FSYNC exceptions: durable outcome is unknown.
                self._faulted = True
                raise

            stored = _StoredRevision(revision, event, record, self._context_after(revision, chain))
            self._stored_by_aggregate.setdefault(aggregate_id, []).append(stored)
            self._stored_by_revision[(aggregate_id, revision.revision_id)] = stored
            return record

    def resolve(self, *, watermark_ns: int) -> RevisionResolution:
        """Resolve validated durable history at a knowledge-time watermark."""
        with self._lock:
            self._ensure_usable()
            revisions = [item.revision for chain in self._stored_by_aggregate.values() for item in chain]
            try:
                return resolve_profile_revisions(revisions, watermark_ns=watermark_ns)
            except RevisionHistoryError as exc:
                raise ProfilePersistenceCorruption(f"revision resolution failed: {exc}") from exc

    def _ensure_usable(self) -> None:
        if self._faulted:
            raise ProfilePersistenceFaulted(
                "adapter faulted after an uncertain append outcome; recover using a fresh journal instance"
            )

    @staticmethod
    def _identity_for_revision(revision: ProfileRevision) -> ProfileRevisionContext:
        if revision.operation is RevisionOperation.UPSERT and isinstance(revision.event, ProfileEvent):
            return ProfileRevisionContext(
                source_id=revision.event.source_id,
                symbol=revision.event.symbol,
                domain=revision.event.domain.value,
                prior_observation_event_time_ns=revision.event.event_time_ns,
            )
        raise ProfilePersistenceConflict(
            "CANCEL identity is not self-describing; use append_cancel(..., context=...) or an existing chain"
        )

    @staticmethod
    def _aggregate_id(revision: ProfileRevision, context: ProfileRevisionContext) -> str:
        # Use the canonical encoder rather than duplicate its stable-ID algorithm.
        probe = ProfileRevision(
            logical_event_id=revision.logical_event_id,
            revision_id=revision.revision_id,
            supersedes_revision_id=None,
            operation=RevisionOperation.UPSERT,
            available_at_ns=(revision.event.available_at_ns if revision.event is not None else revision.available_at_ns),
            event=revision.event if revision.event is not None else None,
        )
        if probe.event is None:
            raise ProfilePersistenceConflict("cannot derive aggregate identity from CANCEL without chain context")
        return encode_profile_revision(
            probe, aggregate_version=1, parent_event_id=None
        ).aggregate_id

    @staticmethod
    def _aggregate_id_from_context(logical_event_id: str, context: ProfileRevisionContext) -> str:
        # A valid UPSERT-shaped probe derives the same identity without persisting.
        from src.fractal_flow.research.volume_profile import ProfileDomain
        from decimal import Decimal
        from src.fractal_flow.research.volume_profile import ProfileEvent
        probe_event = ProfileEvent(
            event_id="vp-identity-probe", source_id=context.source_id, symbol=context.symbol,
            domain=ProfileDomain(context.domain), event_time_ns=context.prior_observation_event_time_ns or 0,
            available_at_ns=context.prior_observation_event_time_ns or 0,
            source_sequence=0, price=Decimal("0"), weight=Decimal("0"),
        )
        probe = ProfileRevision(logical_event_id, "vp-identity-probe", None, RevisionOperation.UPSERT,
                                probe_event.available_at_ns, probe_event)
        return encode_profile_revision(probe, aggregate_version=1, parent_event_id=None).aggregate_id

    @staticmethod
    def _latest_observation_time(chain: list[_StoredRevision]) -> int:
        for item in reversed(chain):
            if item.revision.operation is RevisionOperation.UPSERT and item.revision.event is not None:
                return item.revision.event.event_time_ns
        raise ProfilePersistenceConflict("CANCEL chain has no preceding UPSERT observation")

    def _encode_against_predecessor(
        self, revision: ProfileRevision, chain: list[_StoredRevision], aggregate_version: int
    ) -> Event:
        head = chain[-1] if chain else None
        if revision.operation is RevisionOperation.UPSERT:
            context = self._identity_for_revision(revision)
        else:
            if not chain:
                raise ProfilePersistenceConflict("CANCEL requires an existing chain")
            prior_time = self._latest_observation_time(chain)
            context = ProfileRevisionContext(
                chain[0].context.source_id, chain[0].context.symbol, chain[0].context.domain,
                prior_observation_event_time_ns=prior_time,
            )
        return encode_profile_revision(
            revision, context=context, aggregate_version=aggregate_version,
            parent_event_id=head.event.event_id if head else None,
            root_event_id=chain[0].event.root_id if chain else None,
        )

    @staticmethod
    def _context_for_decode(revision: ProfileRevision, chain: list[_StoredRevision]) -> ProfileRevisionContext | None:
        if revision.operation is RevisionOperation.UPSERT:
            return None
        if not chain:
            return None
        return ProfileRevisionContext(
            chain[0].context.source_id, chain[0].context.symbol, chain[0].context.domain,
            prior_observation_event_time_ns=VolumeProfilePersistence._latest_observation_time(chain),
        )

    @staticmethod
    def _context_after(revision: ProfileRevision, chain: list[_StoredRevision]) -> ProfileRevisionContext:
        if revision.operation is RevisionOperation.UPSERT and revision.event is not None:
            return ProfileRevisionContext(revision.event.source_id, revision.event.symbol,
                                          revision.event.domain.value, revision.event.event_time_ns)
        if not chain:
            raise ProfilePersistenceConflict("CANCEL cannot create a root")
        return ProfileRevisionContext(chain[0].context.source_id, chain[0].context.symbol,
                                      chain[0].context.domain,
                                      VolumeProfilePersistence._latest_observation_time(chain))

    @staticmethod
    def _validate_lifecycle(revision: ProfileRevision, head: _StoredRevision | None) -> None:
        if head is None:
            if revision.operation is not RevisionOperation.UPSERT or revision.supersedes_revision_id is not None:
                raise ProfilePersistenceConflict("a chain root must be an UPSERT with no predecessor")
            return
        if revision.operation is RevisionOperation.CANCEL:
            if head.revision.operation is not RevisionOperation.UPSERT:
                raise ProfilePersistenceConflict("CANCEL requires an active UPSERT head")
        elif revision.operation is RevisionOperation.UPSERT:
            # A replacement/reactivation must explicitly supersede the current head.
            if revision.supersedes_revision_id != head.revision.revision_id:
                raise ProfilePersistenceConflict("UPSERT must supersede the current chain head")
        else:
            raise ProfilePersistenceConflict("unsupported revision operation")

    def _rebuild_from_journal(self, journal: DurableEventJournal) -> None:
        vp_records = [
            record for record in journal.get_all_records()
            if record.event.event_type == VP_REVISION_EVENT_TYPE
            or record.event.aggregate_type == VP_REVISION_AGGREGATE_TYPE
        ]
        if any(
            record.event.event_type != VP_REVISION_EVENT_TYPE
            or record.event.aggregate_type != VP_REVISION_AGGREGATE_TYPE
            for record in vp_records
        ):
            raise ProfilePersistenceCorruption("journal contains a partially typed VP revision event")

        staged: dict[str, list[_StoredRevision]] = {}
        staged_revision_ids: dict[tuple[str, str], _StoredRevision] = {}
        for record in vp_records:
            event = record.event
            chain = staged.setdefault(event.aggregate_id, [])
            if event.aggregate_version != len(chain) + 1:
                raise ProfilePersistenceCorruption("VP aggregate version is not sequential in journal order")
            if chain:
                if event.parent_id != chain[-1].event.event_id:
                    raise ProfilePersistenceCorruption("VP parent_event_id does not match current chain head")
                if event.root_id != chain[0].event.root_id:
                    raise ProfilePersistenceCorruption("VP root_id changed within chain")
            elif event.parent_id != VP_ROOT_PARENT_ID:
                raise ProfilePersistenceCorruption("first VP revision does not use canonical root sentinel")

            context = None
            if chain:
                context = ProfileRevisionContext(
                    chain[0].context.source_id, chain[0].context.symbol, chain[0].context.domain,
                    prior_observation_event_time_ns=self._latest_observation_time(chain),
                )
            try:
                revision, decoded_context = decode_profile_revision(event, context=context)
                canonical = encode_profile_revision(
                    revision,
                    context=context,
                    aggregate_version=event.aggregate_version,
                    parent_event_id=chain[-1].event.event_id if chain else None,
                    root_event_id=chain[0].event.root_id if chain else None,
                )
                if canonical != event:
                    raise ProfilePersistenceCorruption(
                        "journal VP event is decodable but differs from its canonical re-encoding"
                    )
            except ProfilePersistenceCorruption:
                raise
            except Exception as exc:
                raise ProfilePersistenceCorruption(f"VP event decode failed at journal sequence {record.sequence_number}: {exc}") from exc
            key = (event.aggregate_id, revision.revision_id)
            if key in staged_revision_ids:
                previous = staged_revision_ids[key]
                if previous.event != event:
                    raise ProfilePersistenceCorruption("conflicting duplicate revision identity in journal")
                raise ProfilePersistenceCorruption("duplicate revision identity in journal")
            expected_predecessor = chain[-1].revision.revision_id if chain else None
            if revision.supersedes_revision_id != expected_predecessor:
                raise ProfilePersistenceCorruption("revision predecessor identity differs from journal chain head")
            self._validate_lifecycle(revision, chain[-1] if chain else None)
            if chain and revision.available_at_ns < chain[-1].revision.available_at_ns:
                raise ProfilePersistenceCorruption("revision availability regressed along chain")
            stored = _StoredRevision(revision, event, record, decoded_context)
            chain.append(stored)
            staged_revision_ids[key] = stored

        # Validate full history with the pure resolver, not a watermark-truncated view.
        all_revisions = [item.revision for chain in staged.values() for item in chain]
        if all_revisions:
            max_available = max(item.available_at_ns for item in all_revisions)
            try:
                resolve_profile_revisions(all_revisions, watermark_ns=max_available)
            except RevisionHistoryError as exc:
                raise ProfilePersistenceCorruption(f"full VP history failed topology validation: {exc}") from exc
        self._stored_by_aggregate = staged
        self._stored_by_revision = staged_revision_ids

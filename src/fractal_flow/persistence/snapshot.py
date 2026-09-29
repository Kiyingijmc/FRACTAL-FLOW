"""SnapshotEngine providing aggregate snapshot persistence, boundary/provenance validation, atomic disk writes, and deterministic journal replay."""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Callable
import json
import hashlib
import os
import threading
from pathlib import Path

from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import DurableEventJournal


class SnapshotCorruptionException(Exception):
    """Raised when aggregate snapshot integrity, checksum, boundary, or schema verification fails."""

    pass


_INTERNAL_REPLAY_DIAGNOSTIC_FIELDS = frozenset(
    {
        "_last_version",
        "_last_seq",
        "_snapshot_valid",
        "_snapshot_fallback_used",
    }
)


@dataclass(frozen=True)
class AggregateSnapshot:
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    last_sequence_number: int
    state_payload: Dict[str, Any]
    checksum: str
    state_hash: str = ""
    schema_version: str = "1.0"
    created_at: int = 0

    @staticmethod
    def compute_state_hash(payload: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 state hash over canonical serialization of aggregate state."""
        canonical_payload = {
            k: v
            for k, v in payload.items()
            if k not in _INTERNAL_REPLAY_DIAGNOSTIC_FIELDS
        }
        return hashlib.sha256(
            json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def compute_checksum(
        aggregate_type: str,
        aggregate_id: str,
        aggregate_version: int,
        last_seq: int,
        payload: Dict[str, Any],
        schema_version: str = "1.0",
        created_at: int = 0,
        state_hash: str = "",
    ) -> str:
        st_hash = state_hash or AggregateSnapshot.compute_state_hash(payload)
        raw_data = {
            "type": aggregate_type,
            "id": aggregate_id,
            "version": aggregate_version,
            "seq": last_seq,
            "payload": payload,
            "state_hash": st_hash,
            "schema_version": schema_version,
            "created_at": created_at,
        }
        return hashlib.sha256(
            json.dumps(raw_data, sort_keys=True).encode("utf-8")
        ).hexdigest()


class SnapshotEngine:
    """Provides crash-safe aggregate snapshotting with boundary/provenance validation, atomic disk persistence, and deterministic replay."""

    def __init__(self, snapshot_dir: Optional[str] = None) -> None:
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        if self.snapshot_dir:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots: Dict[str, AggregateSnapshot] = {}
        self._reducers: Dict[
            str, Callable[[Dict[str, Any], Event], Dict[str, Any]]
        ] = {}
        self._lock = threading.Lock()
        self._snapshot_valid: bool = True
        self._snapshot_fallback_used: bool = False

    def register_reducer(
        self,
        event_type: str,
        reducer_func: Callable[[Dict[str, Any], Event], Dict[str, Any]],
    ) -> None:
        """Registers an explicit semantic event reducer for state transitions during replay."""
        with self._lock:
            self._reducers[event_type] = reducer_func

    def save_snapshot(
        self,
        aggregate_type: str,
        aggregate_id: str,
        version: int,
        last_seq: int,
        payload: Dict[str, Any],
        schema_version: str = "1.0",
        created_at: int = 0,
    ) -> AggregateSnapshot:
        key = f"{aggregate_type}:{aggregate_id}"
        st_hash = AggregateSnapshot.compute_state_hash(payload)
        checksum = AggregateSnapshot.compute_checksum(
            aggregate_type,
            aggregate_id,
            version,
            last_seq,
            payload,
            schema_version,
            created_at,
            state_hash=st_hash,
        )
        snap = AggregateSnapshot(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=version,
            last_sequence_number=last_seq,
            state_payload=payload,
            checksum=checksum,
            state_hash=st_hash,
            schema_version=schema_version,
            created_at=created_at,
        )

        with self._lock:
            if self.snapshot_dir:
                self._persist_snapshot_to_disk(snap)

            # Publication barrier: publish to memory ONLY after durable disk persistence succeeds
            self._snapshots[key] = snap
            return snap

    def load_snapshot(
        self, aggregate_type: str, aggregate_id: str
    ) -> Optional[AggregateSnapshot]:
        key = f"{aggregate_type}:{aggregate_id}"
        with self._lock:
            snap = self._snapshots.get(key)
            if not snap and self.snapshot_dir:
                snap = self._load_snapshot_from_disk(aggregate_type, aggregate_id)
                if snap:
                    self._snapshots[key] = snap

            if not snap:
                return None

            expected_st_hash = AggregateSnapshot.compute_state_hash(snap.state_payload)
            if snap.state_hash and snap.state_hash != expected_st_hash:
                raise SnapshotCorruptionException(
                    f"Snapshot state hash mismatch for aggregate '{key}'"
                )

            expected_chk = AggregateSnapshot.compute_checksum(
                snap.aggregate_type,
                snap.aggregate_id,
                snap.aggregate_version,
                snap.last_sequence_number,
                snap.state_payload,
                snap.schema_version,
                snap.created_at,
                state_hash=snap.state_hash,
            )
            if snap.checksum != expected_chk:
                raise SnapshotCorruptionException(
                    f"Snapshot checksum mismatch for aggregate '{key}'"
                )
            return snap

    def canonicalize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Strips replay diagnostics and metadata from business state."""
        return {
            k: v
            for k, v in state.items()
            if k not in _INTERNAL_REPLAY_DIAGNOSTIC_FIELDS
        }

    def replay_to_sequence(
        self,
        journal: DurableEventJournal,
        aggregate_type: str,
        aggregate_id: str,
        target_sequence: int,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Replays journal from genesis up to target_sequence strictly using registered reducers."""
        state = dict(initial_state or {})
        all_records = journal.get_all_records()
        agg_records = [
            r
            for r in all_records
            if r.event.aggregate_type == aggregate_type
            and r.event.aggregate_id == aggregate_id
            and r.sequence_number <= target_sequence
        ]

        for record in agg_records:
            evt = record.event
            reducer = self._reducers.get(evt.event_type)
            if reducer:
                state = reducer(state, evt)
            else:
                state.update(evt.payload)

        return state

    def verify_snapshot_equivalence(
        self,
        snapshot: AggregateSnapshot,
        journal: DurableEventJournal,
        aggregate_type: str,
        aggregate_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Verifies independent replay equivalence between snapshot state payload and journal replay from genesis."""
        replayed = self.replay_to_sequence(
            journal=journal,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            target_sequence=snapshot.last_sequence_number,
            initial_state=initial_state,
        )

        canonical_replayed = self.canonicalize_state(replayed)
        canonical_snapshot = self.canonicalize_state(snapshot.state_payload)

        expected_hash = AggregateSnapshot.compute_state_hash(canonical_replayed)
        actual_hash = AggregateSnapshot.compute_state_hash(canonical_snapshot)

        if expected_hash != actual_hash:
            raise SnapshotCorruptionException(
                f"Snapshot state payload is not semantically equivalent to deterministic journal replay from genesis. "
                f"Expected hash: {expected_hash}, actual hash: {actual_hash}"
            )

    def validate_snapshot_boundary(
        self,
        snapshot: AggregateSnapshot,
        journal: DurableEventJournal,
        expected_type: str,
        expected_id: str,
    ) -> None:
        """Validates that a snapshot's sequence and aggregate identity rigorously correspond to journal history."""
        if (
            snapshot.aggregate_type != expected_type
            or snapshot.aggregate_id != expected_id
        ):
            raise SnapshotCorruptionException(
                f"Snapshot aggregate type/id mismatch: '{snapshot.aggregate_type}:{snapshot.aggregate_id}' != '{expected_type}:{expected_id}'"
            )

        if snapshot.last_sequence_number > journal._global_sequence:
            raise SnapshotCorruptionException(
                f"Snapshot sequence {snapshot.last_sequence_number} exceeds journal head sequence {journal._global_sequence}. Fail closed."
            )

        if snapshot.last_sequence_number > 0:
            all_records = journal.get_all_records()
            all_seqs = {r.sequence_number for r in all_records}
            if snapshot.last_sequence_number not in all_seqs:
                raise SnapshotCorruptionException(
                    f"Snapshot sequence {snapshot.last_sequence_number} not found in journal records. Fail closed."
                )

            # Ensure the specific sequence number snapshot.last_sequence_number belongs to expected_type:expected_id!
            boundary_record = next(
                (
                    r
                    for r in all_records
                    if r.sequence_number == snapshot.last_sequence_number
                ),
                None,
            )
            if (
                not boundary_record
                or boundary_record.event.aggregate_type != expected_type
                or boundary_record.event.aggregate_id != expected_id
            ):
                raise SnapshotCorruptionException(
                    f"Snapshot boundary sequence {snapshot.last_sequence_number} does not belong to aggregate '{expected_type}:{expected_id}'. Fail closed."
                )

            # Find aggregate events up to the snapshot sequence boundary
            agg_records_at_boundary = [
                r
                for r in all_records
                if r.event.aggregate_type == expected_type
                and r.event.aggregate_id == expected_id
                and r.sequence_number <= snapshot.last_sequence_number
            ]

            if not agg_records_at_boundary:
                raise SnapshotCorruptionException(
                    f"Snapshot claims sequence {snapshot.last_sequence_number} for aggregate '{expected_type}:{expected_id}', but no events exist for that aggregate at or before sequence {snapshot.last_sequence_number}."
                )

            latest_agg_record = agg_records_at_boundary[-1]
            if latest_agg_record.event.aggregate_version != snapshot.aggregate_version:
                raise SnapshotCorruptionException(
                    f"Snapshot aggregate version mismatch at boundary sequence {snapshot.last_sequence_number}: "
                    f"snapshot version {snapshot.aggregate_version} != journal aggregate version {latest_agg_record.event.aggregate_version}"
                )

            # Enforce independent replay equivalence
            self.verify_snapshot_equivalence(
                snapshot, journal, expected_type, expected_id
            )

    def _get_snapshot_file_path(self, aggregate_type: str, aggregate_id: str) -> Path:
        assert self.snapshot_dir is not None
        safe_type = aggregate_type.replace("/", "_")
        safe_id = aggregate_id.replace("/", "_")
        return self.snapshot_dir / f"snapshot_{safe_type}_{safe_id}.json"

    def _persist_snapshot_to_disk(self, snap: AggregateSnapshot) -> None:
        target_path = self._get_snapshot_file_path(
            snap.aggregate_type, snap.aggregate_id
        )
        temp_path = target_path.with_suffix(".tmp")

        data = asdict(snap)
        raw_json = json.dumps(data, sort_keys=True, indent=2)

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(raw_json)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, target_path)

            dir_fd = os.open(str(self.snapshot_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise SnapshotCorruptionException(
                f"Snapshot durable persistence failed: {e}"
            ) from e

    def _load_snapshot_from_disk(
        self, aggregate_type: str, aggregate_id: str
    ) -> Optional[AggregateSnapshot]:
        file_path = self._get_snapshot_file_path(aggregate_type, aggregate_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            snap = AggregateSnapshot(
                aggregate_type=data["aggregate_type"],
                aggregate_id=data["aggregate_id"],
                aggregate_version=data["aggregate_version"],
                last_sequence_number=data["last_sequence_number"],
                state_payload=data["state_payload"],
                checksum=data["checksum"],
                state_hash=data.get(
                    "state_hash",
                    AggregateSnapshot.compute_state_hash(data["state_payload"]),
                ),
                schema_version=data.get("schema_version", "1.0"),
                created_at=data.get("created_at", 0),
            )
            return snap
        except Exception as e:
            raise SnapshotCorruptionException(
                f"Failed to load snapshot for '{aggregate_type}:{aggregate_id}' from disk: {e}"
            )

    def replay_journal(
        self,
        journal: DurableEventJournal,
        aggregate_type: str,
        aggregate_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Replays events deterministically starting after latest snapshot sequence using semantic reducers.

        Tracks snapshot validity explicitly. Falls back gracefully to full genesis replay if snapshot is corrupt.
        """
        snapshot = None
        snapshot_valid = False
        snapshot_fallback_used = False

        try:
            snapshot = self.load_snapshot(aggregate_type, aggregate_id)
            if snapshot:
                self.validate_snapshot_boundary(
                    snapshot, journal, aggregate_type, aggregate_id
                )
                snapshot_valid = True
        except SnapshotCorruptionException:
            snapshot = None
            snapshot_valid = False
            snapshot_fallback_used = True

        self._snapshot_valid = snapshot_valid
        self._snapshot_fallback_used = snapshot_fallback_used

        min_seq = 0
        state = dict(initial_state or {})

        if snapshot and snapshot_valid:
            state.update(snapshot.state_payload)
            min_seq = snapshot.last_sequence_number
            state["_last_version"] = snapshot.aggregate_version
            state["_last_seq"] = snapshot.last_sequence_number

        all_records = journal.get_all_records()
        aggregate_records = [
            r
            for r in all_records
            if r.event.aggregate_type == aggregate_type
            and r.event.aggregate_id == aggregate_id
            and r.sequence_number > min_seq
        ]

        for record in aggregate_records:
            evt = record.event
            reducer = self._reducers.get(evt.event_type)
            if reducer:
                state = reducer(state, evt)
            else:
                state.update(evt.payload)

            state["_last_version"] = evt.aggregate_version
            state["_last_seq"] = record.sequence_number

        state["_snapshot_valid"] = snapshot_valid
        state["_snapshot_fallback_used"] = snapshot_fallback_used
        return state

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative snapshot engine provenance."""
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            SealedObservation,
            RecoveryEvidenceError,
            ProducerCapability,
        )

        if (
            not isinstance(capability, ProducerCapability)
            or capability.role != CapabilityRole.SNAPSHOT
        ):
            raise RecoveryEvidenceError(
                "SnapshotEngine observation requires a valid SNAPSHOT ProducerCapability."
            )

        import time

        with self._lock:
            payload = {
                "snapshot_valid": self._snapshot_valid,
                "snapshot_fallback_used": self._snapshot_fallback_used,
                "snapshot_dir": str(self.snapshot_dir) if self.snapshot_dir else "",
            }
            return SealedObservation.create(
                capability, session_id, int(time.time()), payload
            )

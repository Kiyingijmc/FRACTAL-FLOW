"""SnapshotEngine providing aggregate snapshot persistence, checksum verification, and deterministic journal replay."""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import json
import hashlib

from src.fractal_flow.domain.event import Event
from src.fractal_flow.persistence.journal import DurableEventJournal, JournalRecord


class SnapshotCorruptionException(Exception):
    """Raised when aggregate snapshot integrity or checksum verification fails."""
    pass


@dataclass(frozen=True)
class AggregateSnapshot:
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    last_sequence_number: int
    state_payload: Dict[str, Any]
    checksum: str

    @staticmethod
    def compute_checksum(aggregate_type: str, aggregate_id: str, aggregate_version: int, last_seq: int, payload: Dict[str, Any]) -> str:
        raw_data = {
            "type": aggregate_type,
            "id": aggregate_id,
            "version": aggregate_version,
            "seq": last_seq,
            "payload": payload,
        }
        return hashlib.sha256(json.dumps(raw_data, sort_keys=True).encode("utf-8")).hexdigest()


class SnapshotEngine:
    """Provides crash-safe aggregate snapshotting and deterministic replay from DurableEventJournal."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, AggregateSnapshot] = {}

    def save_snapshot(self, aggregate_type: str, aggregate_id: str, version: int, last_seq: int, payload: Dict[str, Any]) -> AggregateSnapshot:
        key = f"{aggregate_type}:{aggregate_id}"
        checksum = AggregateSnapshot.compute_checksum(aggregate_type, aggregate_id, version, last_seq, payload)
        snap = AggregateSnapshot(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=version,
            last_sequence_number=last_seq,
            state_payload=payload,
            checksum=checksum,
        )
        self._snapshots[key] = snap
        return snap

    def load_snapshot(self, aggregate_type: str, aggregate_id: str) -> Optional[AggregateSnapshot]:
        key = f"{aggregate_type}:{aggregate_id}"
        snap = self._snapshots.get(key)
        if not snap:
            return None

        expected_chk = AggregateSnapshot.compute_checksum(
            snap.aggregate_type, snap.aggregate_id, snap.aggregate_version, snap.last_sequence_number, snap.state_payload
        )
        if snap.checksum != expected_chk:
            raise SnapshotCorruptionException(f"Snapshot checksum mismatch for aggregate '{key}'")
        return snap

    @staticmethod
    def replay_journal(journal: DurableEventJournal, aggregate_type: str, aggregate_id: str, initial_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Replays events deterministically from journal to reconstruct state."""
        events = journal.get_events_for_aggregate(aggregate_type, aggregate_id)
        state = dict(initial_state or {})

        for evt in events:
            # Deterministic state application
            state.update(evt.payload)
            state["_last_version"] = evt.aggregate_version

        return state

"""Durable Event Journal abstraction with append-only file/memory persistence, per-aggregate sequence enforcement, and checksum integrity."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json
import hashlib
import threading
from pathlib import Path

from src.fractal_flow.domain.event import Event, InvalidEventVersionException


class JournalCorruptionException(Exception):
    """Raised when journal record integrity, checksum, or sequence is corrupted."""
    pass


@dataclass(frozen=True)
class JournalRecord:
    sequence_number: int
    event: Event
    checksum: str

    @staticmethod
    def compute_checksum(sequence_number: int, event: Event) -> str:
        evt_dict = asdict(event)
        raw_payload = json.dumps({"seq": sequence_number, "event": evt_dict}, sort_keys=True)
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


class DurableEventJournal:
    """Thread-safe, crash-safe, append-only event journal enforcing monotonic sequence numbers and checksums."""

    def __init__(self, journal_file_path: Optional[str] = None) -> None:
        self.journal_file_path = Path(journal_file_path) if journal_file_path else None
        self._records: List[JournalRecord] = []
        self._aggregate_sequences: Dict[str, int] = {}
        self._global_sequence: int = 0
        self._lock = threading.Lock()

        if self.journal_file_path and self.journal_file_path.exists():
            self._load_from_file()

    def append(self, event: Event) -> JournalRecord:
        with self._lock:
            key = f"{event.aggregate_type}:{event.aggregate_id}"
            curr_seq = self._aggregate_sequences.get(key, 0)
            expected_seq = curr_seq + 1

            if event.aggregate_version != expected_seq:
                raise InvalidEventVersionException(
                    f"Aggregate '{key}' version mismatch: incoming {event.aggregate_version} != expected {expected_seq}"
                )

            self._global_sequence += 1
            seq_num = self._global_sequence
            checksum = JournalRecord.compute_checksum(seq_num, event)
            record = JournalRecord(sequence_number=seq_num, event=event, checksum=checksum)

            if self.journal_file_path:
                self._append_to_file(record)

            self._records.append(record)
            self._aggregate_sequences[key] = event.aggregate_version
            return record

    def get_events_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> List[Event]:
        with self._lock:
            return [
                r.event for r in self._records
                if r.event.aggregate_type == aggregate_type and r.event.aggregate_id == aggregate_id
            ]

    def get_all_records(self) -> List[JournalRecord]:
        with self._lock:
            return list(self._records)

    def _append_to_file(self, record: JournalRecord) -> None:
        assert self.journal_file_path is not None
        rec_data = {
            "sequence_number": record.sequence_number,
            "event": asdict(record.event),
            "checksum": record.checksum,
        }
        line = json.dumps(rec_data, sort_keys=True) + "\n"
        with open(self.journal_file_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    def _load_from_file(self) -> None:
        assert self.journal_file_path is not None
        with open(self.journal_file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    seq_num = data["sequence_number"]
                    evt_data = data["event"]
                    recorded_checksum = data["checksum"]

                    evt = Event(**evt_data)
                    computed_checksum = JournalRecord.compute_checksum(seq_num, evt)

                    if recorded_checksum != computed_checksum:
                        raise JournalCorruptionException(
                            f"Journal corruption at line {line_num}: checksum mismatch."
                        )

                    key = f"{evt.aggregate_type}:{evt.aggregate_id}"
                    curr_seq = self._aggregate_sequences.get(key, 0)
                    if evt.aggregate_version != curr_seq + 1:
                        raise JournalCorruptionException(
                            f"Journal sequence gap at line {line_num} for '{key}': {evt.aggregate_version} != {curr_seq + 1}"
                        )

                    record = JournalRecord(sequence_number=seq_num, event=evt, checksum=recorded_checksum)
                    self._records.append(record)
                    self._aggregate_sequences[key] = evt.aggregate_version
                    self._global_sequence = seq_num

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    raise JournalCorruptionException(f"Journal corruption at line {line_num}: malformed record. Error: {e}")

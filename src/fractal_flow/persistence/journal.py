"""Durable Event Journal abstraction with append-only file/memory persistence, global/aggregate sequence enforcement, event uniqueness, and crash-tail recovery policy."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
import json
import hashlib
import os
import threading
from pathlib import Path

from src.fractal_flow.domain.event import Event, InvalidEventVersionException


class JournalCorruptionException(Exception):
    """Raised when journal record integrity, checksum, event ID uniqueness, or sequence is corrupted."""
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
    """Thread-safe, crash-safe, append-only event journal enforcing monotonic sequence numbers, event ID uniqueness, and checksums."""

    def __init__(self, journal_file_path: Optional[str] = None, truncate_corrupted_tail: bool = False) -> None:
        self.journal_file_path = Path(journal_file_path) if journal_file_path else None
        self.truncate_corrupted_tail = truncate_corrupted_tail
        self._records: List[JournalRecord] = []
        self._aggregate_sequences: Dict[str, int] = {}
        self._event_ids: Set[str] = set()
        self._global_sequence: int = 0
        self._lock = threading.Lock()

        if self.journal_file_path and self.journal_file_path.exists():
            self._load_from_file()

    def append(self, event: Event) -> JournalRecord:
        with self._lock:
            if event.event_id in self._event_ids:
                raise JournalCorruptionException(f"Duplicate event_id '{event.event_id}' detected.")

            key = f"{event.aggregate_type}:{event.aggregate_id}"
            curr_seq = self._aggregate_sequences.get(key, 0)
            expected_seq = curr_seq + 1

            if event.aggregate_version != expected_seq:
                raise InvalidEventVersionException(
                    f"Aggregate '{key}' version mismatch: incoming {event.aggregate_version} != expected {expected_seq}"
                )

            next_global_seq = self._global_sequence + 1
            checksum = JournalRecord.compute_checksum(next_global_seq, event)
            record = JournalRecord(sequence_number=next_global_seq, event=event, checksum=checksum)

            if self.journal_file_path:
                self._append_to_file(record)

            self._records.append(record)
            self._event_ids.add(event.event_id)
            self._aggregate_sequences[key] = event.aggregate_version
            self._global_sequence = next_global_seq
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
            os.fsync(f.fileno())

    def _load_from_file(self) -> None:
        assert self.journal_file_path is not None
        lines_with_pos = []
        with open(self.journal_file_path, "rb") as f:
            pos = 0
            while True:
                line_bytes = f.readline()
                if not line_bytes:
                    break
                lines_with_pos.append((pos, line_bytes))
                pos = f.tell()

        total_lines = len(lines_with_pos)
        last_valid_byte_offset = 0

        for idx, (offset, line_bytes) in enumerate(lines_with_pos, 1):
            line_str = line_bytes.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            is_last_line = (idx == total_lines)

            try:
                data = json.loads(line_str)
                seq_num = data["sequence_number"]
                evt_data = data["event"]
                recorded_checksum = data["checksum"]

                if seq_num != self._global_sequence + 1:
                    raise JournalCorruptionException(
                        f"Journal global sequence gap/disorder at line {idx}: sequence {seq_num} != expected {self._global_sequence + 1}"
                    )

                evt = Event(**evt_data)

                if evt.event_id in self._event_ids:
                    raise JournalCorruptionException(
                        f"Journal corruption at line {idx}: duplicate event_id '{evt.event_id}'"
                    )

                computed_checksum = JournalRecord.compute_checksum(seq_num, evt)
                if recorded_checksum != computed_checksum:
                    raise JournalCorruptionException(
                        f"Journal corruption at line {idx}: checksum mismatch."
                    )

                key = f"{evt.aggregate_type}:{evt.aggregate_id}"
                curr_seq = self._aggregate_sequences.get(key, 0)
                if evt.aggregate_version != curr_seq + 1:
                    raise JournalCorruptionException(
                        f"Journal aggregate sequence gap at line {idx} for '{key}': {evt.aggregate_version} != {curr_seq + 1}"
                    )

                record = JournalRecord(sequence_number=seq_num, event=evt, checksum=recorded_checksum)
                self._records.append(record)
                self._event_ids.add(evt.event_id)
                self._aggregate_sequences[key] = evt.aggregate_version
                self._global_sequence = seq_num
                last_valid_byte_offset = offset + len(line_bytes)

            except (json.JSONDecodeError, KeyError, TypeError, JournalCorruptionException) as e:
                if is_last_line and self.truncate_corrupted_tail and isinstance(e, (json.JSONDecodeError, KeyError, TypeError)):
                    with open(self.journal_file_path, "ab") as f:
                        f.seek(last_valid_byte_offset)
                        f.truncate()
                    break
                else:
                    raise JournalCorruptionException(f"Journal corruption at line {idx}: malformed record. Error: {e}")

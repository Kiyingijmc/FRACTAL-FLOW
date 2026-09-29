"""Durable Event Journal abstraction with append-only file/memory persistence, global/aggregate sequence enforcement, event uniqueness, failure atomicity, and conservative crash-tail recovery policy."""

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.fractal_flow.domain.event import Event, InvalidEventVersionException


class JournalCorruptionException(Exception):
    """Raised when journal record integrity, checksum, event ID uniqueness, or sequence is corrupted."""



class JournalDurabilityException(Exception):
    """Raised when filesystem write, flush, fsync, or physical rollback fails, placing the journal in a faulted state."""



@dataclass(frozen=True)
class JournalRecord:
    sequence_number: int
    event: Event
    checksum: str

    @staticmethod
    def compute_checksum(sequence_number: int, event: Event) -> str:
        evt_dict = asdict(event)
        raw_payload = json.dumps(
            {"seq": sequence_number, "event": evt_dict}, sort_keys=True
        )
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


class DurableEventJournal:
    """Thread-safe, crash-safe, append-only event journal enforcing monotonic sequence numbers, event ID uniqueness, checksums, and physical append failure atomicity."""

    def __init__(
        self,
        journal_file_path: str | None = None,
        truncate_corrupted_tail: bool = False,
    ) -> None:
        self.journal_file_path = Path(journal_file_path) if journal_file_path else None
        self.truncate_corrupted_tail = truncate_corrupted_tail
        self._records: list[JournalRecord] = []
        self._aggregate_sequences: dict[str, int] = {}
        self._event_ids: dict[str, int] = {}  # event_id -> global_sequence mapping
        self._global_sequence: int = 0
        self._faulted: bool = False
        self._lock = threading.Lock()

        if self.journal_file_path and self.journal_file_path.exists():
            self._load_from_file()

    def append(self, event: Event) -> JournalRecord:
        with self._lock:
            if self._faulted:
                raise JournalDurabilityException(
                    "Journal is in a faulted/unrecoverable state. Appends prohibited."
                )

            if event.event_id in self._event_ids:
                raise JournalCorruptionException(
                    f"Duplicate event_id '{event.event_id}' detected (previously registered at global sequence {self._event_ids[event.event_id]})."
                )

            key = f"{event.aggregate_type}:{event.aggregate_id}"
            curr_seq = self._aggregate_sequences.get(key, 0)
            expected_seq = curr_seq + 1

            if event.aggregate_version != expected_seq:
                raise InvalidEventVersionException(
                    f"Aggregate '{key}' version mismatch: incoming {event.aggregate_version} != expected {expected_seq}"
                )

            next_global_seq = self._global_sequence + 1
            checksum = JournalRecord.compute_checksum(next_global_seq, event)
            record = JournalRecord(
                sequence_number=next_global_seq, event=event, checksum=checksum
            )

            if self.journal_file_path:
                self._append_to_file_atomically(record)

            # In-memory publication barrier: updated ONLY after file write + flush + fsync succeed
            self._records.append(record)
            self._event_ids[event.event_id] = next_global_seq
            self._aggregate_sequences[key] = event.aggregate_version
            self._global_sequence = next_global_seq
            return record

    def get_events_for_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> list[Event]:
        with self._lock:
            return [
                r.event
                for r in self._records
                if r.event.aggregate_type == aggregate_type
                and r.event.aggregate_id == aggregate_id
            ]

    def get_all_records(self) -> list[JournalRecord]:
        with self._lock:
            return list(self._records)

    def _append_to_file_atomically(self, record: JournalRecord) -> None:
        assert self.journal_file_path is not None
        rec_data = {
            "sequence_number": record.sequence_number,
            "event": asdict(record.event),
            "checksum": record.checksum,
        }
        line = json.dumps(rec_data, sort_keys=True) + "\n"

        orig_offset = None
        try:
            with open(self.journal_file_path, "a+", encoding="utf-8") as f:
                f.seek(0, os.SEEK_END)
                orig_offset = f.tell()

                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as write_err:
            # Physical append failed: attempt durable rollback to orig_offset
            rollback_succeeded = False
            if orig_offset is not None and self.journal_file_path.exists():
                try:
                    with open(self.journal_file_path, "a+", encoding="utf-8") as rf:
                        rf.seek(orig_offset)
                        rf.truncate()
                        rf.flush()
                        os.fsync(rf.fileno())
                    rollback_succeeded = True
                except Exception:
                    rollback_succeeded = False

            if not rollback_succeeded:
                self._faulted = True
                raise JournalDurabilityException(
                    f"Durable append failed AND rollback durability (fsync) failed: {write_err}. Journal placed in FAULTED state."
                ) from write_err

            raise JournalDurabilityException(
                f"Durable append failed (durably rolled back to offset {orig_offset}): {write_err}"
            ) from write_err

    @staticmethod
    def _is_incomplete_json_tail(line_str: str, err: Exception) -> bool:
        """Conservatively determines whether an EOF parse error represents a physically truncated JSON record.

        Returns True ONLY when there is structural evidence of premature EOF termination (unterminated string,
        unterminated object/array, or cut-off key/value). Returns False for completed malformed lines.
        """
        if not isinstance(err, json.JSONDecodeError):
            return False

        stripped = line_str.rstrip()
        if not stripped:
            return False

        # Every complete JournalRecord JSON object must end with '}'
        if stripped.endswith("}"):
            return False

        # Structural inspection of quote/brace/bracket balance
        in_string = False
        escaped = False
        open_braces = 0
        open_brackets = 0

        for char in stripped:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    open_braces += 1
                elif char == "}":
                    open_braces -= 1
                elif char == "[":
                    open_brackets += 1
                elif char == "]":
                    open_brackets -= 1

        if "invalid \\escape" in str(err).lower():
            return False

        if in_string or escaped:
            return True

        if open_braces > 0 or open_brackets > 0:
            pos = err.pos
            unparsed = stripped[pos:].strip()
            if (
                unparsed
                and not unparsed.startswith((",", ":", "{", "[", '"'))
                and unparsed not in ("true", "false", "null")
            ):
                if not any(
                    unparsed.startswith(prefix)
                    for prefix in (
                        "t",
                        "tr",
                        "tru",
                        "f",
                        "fa",
                        "fal",
                        "fals",
                        "n",
                        "nu",
                        "nul",
                    )
                ):
                    return False
            return True

        if stripped.endswith(":") or stripped.endswith(","):
            return True

        return False

    def _load_from_file(self) -> None:
        assert self.journal_file_path is not None

        temp_records: list[JournalRecord] = []
        temp_aggregate_sequences: dict[str, int] = {}
        temp_event_ids: dict[str, int] = {}
        temp_global_sequence: int = 0

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

            is_last_line = idx == total_lines

            try:
                # 1. Structural JSON decoding
                data = json.loads(line_str)

                # 2. Strict type & field validation
                if (
                    not isinstance(data, dict)
                    or "sequence_number" not in data
                    or "event" not in data
                    or "checksum" not in data
                ):
                    raise json.JSONDecodeError(
                        "Missing required record schema fields", line_str, 0
                    )

                seq_num = data["sequence_number"]
                if (
                    not isinstance(seq_num, int)
                    or isinstance(seq_num, bool)
                    or seq_num <= 0
                ):
                    raise JournalCorruptionException(
                        f"Invalid sequence number type or value at line {idx}: {seq_num}"
                    )

                evt_data = data["event"]
                recorded_checksum = data["checksum"]

                if not isinstance(evt_data, dict) or not isinstance(
                    recorded_checksum, str
                ):
                    raise JournalCorruptionException(
                        f"Invalid event payload or checksum format at line {idx}"
                    )

                # 3. Global sequence continuity check
                if seq_num != temp_global_sequence + 1:
                    raise JournalCorruptionException(
                        f"Journal global sequence gap/disorder at line {idx}: sequence {seq_num} != expected {temp_global_sequence + 1}"
                    )

                evt = Event(**evt_data)

                # 4. Event ID uniqueness check
                if evt.event_id in temp_event_ids:
                    raise JournalCorruptionException(
                        f"Journal corruption at line {idx}: duplicate event_id '{evt.event_id}' (first seen at sequence {temp_event_ids[evt.event_id]})"
                    )

                # 5. Checksum validation
                computed_checksum = JournalRecord.compute_checksum(seq_num, evt)
                if recorded_checksum != computed_checksum:
                    raise JournalCorruptionException(
                        f"Journal corruption at line {idx}: checksum mismatch."
                    )

                # 6. Aggregate version continuity check
                key = f"{evt.aggregate_type}:{evt.aggregate_id}"
                curr_seq = temp_aggregate_sequences.get(key, 0)
                if evt.aggregate_version != curr_seq + 1:
                    raise JournalCorruptionException(
                        f"Journal aggregate sequence gap at line {idx} for '{key}': {evt.aggregate_version} != {curr_seq + 1}"
                    )

                record = JournalRecord(
                    sequence_number=seq_num, event=evt, checksum=recorded_checksum
                )
                temp_records.append(record)
                temp_event_ids[evt.event_id] = seq_num
                temp_aggregate_sequences[key] = evt.aggregate_version
                temp_global_sequence = seq_num
                last_valid_byte_offset = offset + len(line_bytes)

            except Exception as e:
                # Distinguish demonstrably incomplete EOF JSON syntax tail vs completed invalid records or middle corruption
                if (
                    is_last_line
                    and self.truncate_corrupted_tail
                    and self._is_incomplete_json_tail(line_str, e)
                ):
                    try:
                        with open(self.journal_file_path, "a+b") as tf:
                            tf.seek(last_valid_byte_offset)
                            tf.truncate()
                            tf.flush()
                            os.fsync(tf.fileno())
                        break
                    except Exception as trunc_err:
                        raise JournalDurabilityException(
                            f"EOF tail truncation recovery failed to fsync at offset {last_valid_byte_offset}: {trunc_err}"
                        ) from trunc_err
                else:
                    raise JournalCorruptionException(
                        f"Journal corruption at line {idx}: malformed record. Error: {e}"
                    ) from e

        # Commit temporary loaded structures to instance state only after full validation and tail recovery succeed
        self._records = temp_records
        self._aggregate_sequences = temp_aggregate_sequences
        self._event_ids = temp_event_ids
        self._global_sequence = temp_global_sequence

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative journal provenance."""
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            ProducerCapability,
            RecoveryEvidenceError,
            SealedObservation,
        )

        if (
            not isinstance(capability, ProducerCapability)
            or capability.role != CapabilityRole.JOURNAL
        ):
            raise RecoveryEvidenceError(
                "Journal observation requires a valid JOURNAL ProducerCapability."
            )

        import time

        with self._lock:
            payload = {
                "faulted": self._faulted,
                "global_sequence": self._global_sequence,
                "journal_path": str(self.journal_file_path)
                if self.journal_file_path
                else "",
            }
            return SealedObservation.create(
                capability, session_id, int(time.time()), payload
            )

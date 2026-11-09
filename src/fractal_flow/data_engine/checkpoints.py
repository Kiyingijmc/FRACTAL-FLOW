"""Crash-safe, non-authoritative durable checkpoints for G4 subscribers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
from typing import Any, Callable

try:  # Unsupported platforms fail closed for durable checkpoint ownership.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from src.fractal_flow.data_engine.correction_codec import CorrectionScope
from src.fractal_flow.data_engine.correction_persistence import CorrectionCursor
from src.fractal_flow.data_engine.journal_subscriber import JournalReplayAuthority
from src.fractal_flow.persistence.journal import DurableEventJournal


class CheckpointError(ValueError):
    """A subscriber checkpoint cannot safely be created, used, or recovered."""


class CheckpointIntegrityError(CheckpointError):
    """Checkpoint bytes or their journal/subscriber bindings are invalid."""


class CheckpointDurabilityError(CheckpointError):
    """Checkpoint sidecar durability is uncertain; no acknowledgement is valid."""


class CheckpointLockError(CheckpointDurabilityError):
    """Another process owns the same subscriber checkpoint identity."""


def _wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class JournalFileIdentity:
    canonical_path: str
    device: int
    inode: int

    @classmethod
    def from_journal(cls, journal: DurableEventJournal) -> "JournalFileIdentity":
        if not isinstance(journal, DurableEventJournal) or journal.journal_file_path is None:
            raise CheckpointIntegrityError("durable checkpoints require a file-backed journal")
        path = journal.journal_file_path.resolve(strict=True)
        stat = os.stat(path)
        return cls(str(path), stat.st_dev, stat.st_ino)

    def payload(self) -> dict[str, object]:
        return {"path": self.canonical_path, "device": self.device, "inode": self.inode}


@dataclass(frozen=True)
class SubscriberCheckpoint:
    schema_version: int
    subscriber_id: str
    partition_id: str
    source_key: tuple[str, str, str, str, str, str]
    journal: JournalFileIdentity
    cursor: CorrectionCursor
    checksum: str

    @classmethod
    def create(
        cls,
        subscriber_id: str,
        scope: CorrectionScope,
        cursor: CorrectionCursor,
        journal: DurableEventJournal,
    ) -> "SubscriberCheckpoint":
        if not isinstance(subscriber_id, str) or not subscriber_id or cursor.partition_id != scope.partition_id:
            raise CheckpointIntegrityError("subscriber and cursor partition identity are required")
        identity = JournalFileIdentity.from_journal(journal)
        base = cls(1, subscriber_id, scope.partition_id, scope.source.key, identity, cursor, "")
        return cls(**{**base.__dict__, "checksum": base.compute_checksum()})

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "subscriber_id": self.subscriber_id,
            "partition_id": self.partition_id,
            "source_key": self.source_key,
            "journal": self.journal.payload(),
            "cursor": {
                "partition_id": self.cursor.partition_id,
                "journal_sequence": self.cursor.journal_sequence,
                "aggregate_version": self.cursor.aggregate_version,
            },
        }

    def compute_checksum(self) -> str:
        return hashlib.sha256(_wire(self.unsigned())).hexdigest()

    def to_bytes(self) -> bytes:
        return _wire({**self.unsigned(), "checksum": self.checksum})

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SubscriberCheckpoint":
        try:
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict) or set(value) != {
                "schema_version",
                "subscriber_id",
                "partition_id",
                "source_key",
                "journal",
                "cursor",
                "checksum",
            }:
                raise ValueError("unsupported checkpoint fields")
            journal = value["journal"]
            cursor = value["cursor"]
            source = value["source_key"]
            if (
                type(value["schema_version"]) is not int
                or value["schema_version"] != 1
                or not isinstance(value["subscriber_id"], str)
                or not value["subscriber_id"]
                or not isinstance(value["partition_id"], str)
                or not value["partition_id"]
                or not isinstance(journal, dict)
                or set(journal) != {"path", "device", "inode"}
                or not isinstance(cursor, dict)
                or set(cursor) != {"partition_id", "journal_sequence", "aggregate_version"}
                or not isinstance(source, list)
                or len(source) != 6
                or not all(isinstance(item, str) for item in source)
                or not isinstance(value["checksum"], str)
                or not isinstance(journal["path"], str)
                or type(journal["device"]) is not int
                or type(journal["inode"]) is not int
            ):
                raise ValueError("invalid checkpoint types")
            result = cls(
                1,
                value["subscriber_id"],
                value["partition_id"],
                tuple(source),
                JournalFileIdentity(journal["path"], journal["device"], journal["inode"]),
                CorrectionCursor(cursor["partition_id"], cursor["journal_sequence"], cursor["aggregate_version"]),
                value["checksum"],
            )
            if (
                not isinstance(result.subscriber_id, str)
                or not result.subscriber_id
                or not isinstance(result.partition_id, str)
            ):
                raise ValueError("invalid checkpoint identity")
            if result.checksum != result.compute_checksum() or result.to_bytes() != raw:
                raise CheckpointIntegrityError("checkpoint checksum or canonical encoding is invalid")
            return result
        except CheckpointIntegrityError:
            raise
        except Exception as exc:
            raise CheckpointIntegrityError(f"checkpoint is truncated, corrupt, or unsupported: {exc}") from exc


class SubscriberCheckpointStore:
    """Exclusive-writer durable sidecar store; failed publication requires restart."""

    def __init__(self, checkpoint_path: str, journal: DurableEventJournal) -> None:
        if fcntl is None or os.name != "posix":
            raise CheckpointDurabilityError("POSIX lock and directory fsync support are required")
        self.path = Path(checkpoint_path).resolve(strict=False)
        if not self.path.parent.is_dir():
            raise CheckpointDurabilityError("checkpoint parent directory must already exist")
        self._journal = journal
        self._journal_identity = JournalFileIdentity.from_journal(journal)
        self._fault_hook: Callable[[str, SubscriberCheckpoint], None] | None = None
        self._recovery_required = False
        self._mutex = threading.RLock()
        self._lock_fd: int | None = None
        self._lock_identity: tuple[int, int] | None = None
        self._checkpoint_identity = self._path_identity(self.path)
        self._lock_path = self._initial_lock_path()
        self._acquire_lock()

    @property
    def recovery_required(self) -> bool:
        return self._recovery_required

    def set_fault_hook(self, hook: Callable[[str, SubscriberCheckpoint], None] | None) -> None:
        self._fault_hook = hook

    @property
    def lock_path(self) -> Path:
        """Canonical owner-lock pathname, exposed for hostile proof injection."""
        return self._lock_path

    @staticmethod
    def _path_identity(path: Path) -> tuple[int, int] | None:
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise CheckpointIntegrityError(f"checkpoint path cannot be inspected: {exc}") from exc
        return (stat.st_dev, stat.st_ino)

    def _lock_directory(self) -> Path:
        """Place identity locks beside the canonical journal, never an alias sidecar."""
        return Path(self._journal_identity.canonical_path).parent

    def _initial_lock_path(self) -> Path:
        """Use a semantic key when an existing sidecar can prove its identity."""
        if self.path.exists():
            try:
                checkpoint = SubscriberCheckpoint.from_bytes(self.path.read_bytes())
                if checkpoint.journal == self._journal_identity:
                    return self._semantic_lock_path(checkpoint)
            except CheckpointIntegrityError:
                # Corrupt sidecars must subsequently fail load validation; their
                # path still receives exclusive recovery ownership here.
                pass
        digest = hashlib.sha256(
            _wire({"journal": self._journal_identity.payload(), "path": str(self.path)})
        ).hexdigest()
        return self._lock_directory() / f".fractal-flow-checkpoint-{digest}.lock"

    def _semantic_lock_path(self, checkpoint: SubscriberCheckpoint) -> Path:
        identity = {
            "journal": checkpoint.journal.payload(),
            "subscriber_id": checkpoint.subscriber_id,
            "partition_id": checkpoint.partition_id,
            "source_key": checkpoint.source_key,
        }
        return self._lock_directory() / f".fractal-flow-checkpoint-{hashlib.sha256(_wire(identity)).hexdigest()}.lock"

    def _acquire_lock(self) -> None:
        fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            assert fcntl is not None
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            raise CheckpointLockError("checkpoint identity is already owned") from exc
        stat = os.fstat(fd)
        self._lock_fd, self._lock_identity = fd, (stat.st_dev, stat.st_ino)

    def _verify_lock(self) -> None:
        if self._lock_fd is None or self._lock_identity is None:
            raise CheckpointLockError("checkpoint store is closed")
        stat = os.stat(self._lock_path)
        if (stat.st_dev, stat.st_ino) != self._lock_identity:
            raise CheckpointLockError("checkpoint lock path was replaced")

    def _verify_checkpoint_path(self) -> None:
        """Reject an external target replacement before it can overwrite progress."""
        if self._path_identity(self.path) != self._checkpoint_identity:
            raise CheckpointIntegrityError("checkpoint path was replaced while ownership was held")

    def _promote_lock(self, checkpoint: SubscriberCheckpoint) -> None:
        """Move first-publication ownership to an alias-stable semantic lock."""
        target = self._semantic_lock_path(checkpoint)
        if target == self._lock_path:
            return
        fd = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            assert fcntl is not None
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            raise CheckpointLockError("semantic checkpoint identity is already owned") from exc
        old_fd = self._lock_fd
        self._lock_path = target
        stat = os.fstat(fd)
        self._lock_fd, self._lock_identity = fd, (stat.st_dev, stat.st_ino)
        if old_fd is not None:
            assert fcntl is not None
            fcntl.flock(old_fd, fcntl.LOCK_UN)
            os.close(old_fd)

    def _verify_journal_identity(self) -> None:
        if JournalFileIdentity.from_journal(self._journal) != self._journal_identity:
            raise CheckpointIntegrityError("journal identity changed after checkpoint store creation")

    def close(self) -> None:
        with self._mutex:
            if self._lock_fd is not None:
                try:
                    assert fcntl is not None
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(self._lock_fd)
                self._lock_fd, self._lock_identity = None, None

    def __enter__(self) -> "SubscriberCheckpointStore":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def _fsync_directory(self) -> None:
        try:
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            raise CheckpointDurabilityError(f"directory fsync unsupported or failed: {exc}") from exc

    def _validate(self, checkpoint: SubscriberCheckpoint, subscriber_id: str, scope: CorrectionScope) -> None:
        self._validate_content(checkpoint)
        if checkpoint.subscriber_id != subscriber_id:
            raise CheckpointIntegrityError("checkpoint subscriber identity mismatch")
        if checkpoint.partition_id != scope.partition_id or checkpoint.source_key != scope.source.key:
            raise CheckpointIntegrityError("checkpoint partition/source identity mismatch")
        if checkpoint.cursor.partition_id != scope.partition_id:
            raise CheckpointIntegrityError("checkpoint cursor partition mismatch")

    def _validate_content(self, checkpoint: SubscriberCheckpoint) -> None:
        if checkpoint.schema_version != 1 or checkpoint.journal != self._journal_identity:
            raise CheckpointIntegrityError("checkpoint journal identity mismatch")
        if checkpoint.cursor.partition_id != checkpoint.partition_id:
            raise CheckpointIntegrityError("checkpoint cursor partition mismatch")
        if checkpoint.checksum != checkpoint.compute_checksum():
            raise CheckpointIntegrityError("checkpoint checksum mismatch")

    def _write_all(self, fd: int, raw: bytes) -> None:
        offset = 0
        while offset < len(raw):
            progress = os.write(fd, raw[offset:])
            if type(progress) is not int or progress <= 0 or progress > len(raw) - offset:
                raise CheckpointDurabilityError("checkpoint write made invalid progress")
            offset += progress

    def save(self, checkpoint: SubscriberCheckpoint) -> None:
        with self._mutex:
            if self._recovery_required:
                raise CheckpointDurabilityError("checkpoint store requires fresh recovery")
            self._verify_lock()
            self._verify_checkpoint_path()
            self._verify_journal_identity()
            self._validate_content(checkpoint)
            temp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
            try:
                if self._fault_hook:
                    self._fault_hook("BEFORE_CHECKPOINT_WRITE", checkpoint)
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    self._write_all(fd, checkpoint.to_bytes())
                    os.fsync(fd)
                finally:
                    os.close(fd)
                if self._fault_hook:
                    self._fault_hook("AFTER_CHECKPOINT_FILE_FSYNC", checkpoint)
                    self._fault_hook("BEFORE_CHECKPOINT_RENAME", checkpoint)
                os.replace(temp, self.path)
                if self._fault_hook:
                    self._fault_hook("AFTER_CHECKPOINT_RENAME", checkpoint)
                    self._fault_hook("BEFORE_CHECKPOINT_DIRECTORY_FSYNC", checkpoint)
                self._fsync_directory()
                self._checkpoint_identity = self._path_identity(self.path)
                self._promote_lock(checkpoint)
            except Exception as exc:
                self._recovery_required = True
                raise CheckpointDurabilityError(f"checkpoint publication is unacknowledged: {exc}") from exc

    def commit(
        self, subscriber_id: str, scope: CorrectionScope, cursor: CorrectionCursor, authority: JournalReplayAuthority
    ) -> SubscriberCheckpoint:
        try:
            authority.capture(scope, cursor)
        except Exception as exc:
            raise CheckpointIntegrityError(f"checkpoint cursor is not authoritative: {exc}") from exc
        checkpoint = SubscriberCheckpoint.create(subscriber_id, scope, cursor, self._journal)
        self.save(checkpoint)
        return checkpoint

    def load_verified(
        self, subscriber_id: str, scope: CorrectionScope, authority: JournalReplayAuthority
    ) -> SubscriberCheckpoint | None:
        with self._mutex:
            self._verify_lock()
            self._verify_checkpoint_path()
            self._verify_journal_identity()
            if not self.path.exists():
                return None
            try:
                checkpoint = SubscriberCheckpoint.from_bytes(self.path.read_bytes())
                self._validate(checkpoint, subscriber_id, scope)
                authority.capture(scope, checkpoint.cursor)
                return checkpoint
            except CheckpointIntegrityError:
                raise
            except Exception as exc:
                raise CheckpointIntegrityError(f"checkpoint cursor/history is invalid: {exc}") from exc

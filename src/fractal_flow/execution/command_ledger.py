"""Authoritative durable Phase 6 application command ledger.

The ledger owns command identity/lifecycle, not broker truth. Broker effects are
confirmed only by reconciliation evidence from the broker-truth layer.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.fractal_flow.execution.ffbp_protocol import CommandConflictError, CommandState


_ALLOWED_TRANSITIONS: dict[CommandState, set[CommandState]] = {
    CommandState.PERSISTED: {CommandState.DISPATCHABLE, CommandState.CANCELLED, CommandState.EXPIRED, CommandState.QUARANTINED},
    CommandState.DISPATCHABLE: {CommandState.SENT, CommandState.EXPIRED, CommandState.CANCELLED, CommandState.QUARANTINED},
    CommandState.SENT: {CommandState.BROKER_PENDING, CommandState.UNKNOWN, CommandState.REJECTED, CommandState.FAILED, CommandState.RECONCILING},
    CommandState.BROKER_PENDING: {CommandState.RECONCILING, CommandState.UNKNOWN, CommandState.REJECTED, CommandState.FAILED},
    CommandState.RECONCILING: {CommandState.EFFECT_CONFIRMED, CommandState.UNKNOWN, CommandState.REJECTED, CommandState.FAILED, CommandState.QUARANTINED},
    CommandState.EFFECT_CONFIRMED: set(),
    CommandState.REJECTED: set(),
    CommandState.FAILED: set(),
    CommandState.UNKNOWN: {CommandState.RECONCILING, CommandState.EXPIRED, CommandState.CANCELLED, CommandState.QUARANTINED},
    CommandState.EXPIRED: set(),
    CommandState.CANCELLED: set(),
    CommandState.QUARANTINED: {CommandState.RECONCILING},
}


@dataclass(frozen=True)
class CommandLedgerRecord:
    account_id: str
    command_id: str
    intent_id: str
    fingerprint: str
    state: CommandState
    created_at_ms: int
    updated_at_ms: int
    expires_at_ms: int | None
    broker_reference: str | None = None
    result: dict[str, Any] | None = None


class DurableCommandLedger:
    """SQLite-backed single application authority for command lifecycle."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_commands (
                    account_id TEXT NOT NULL,
                    command_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER,
                    broker_reference TEXT,
                    result_json TEXT,
                    PRIMARY KEY (account_id, command_id)
                )
            """)

    @staticmethod
    def _row(row: tuple[Any, ...]) -> CommandLedgerRecord:
        return CommandLedgerRecord(
            account_id=row[0], command_id=row[1], intent_id=row[2], fingerprint=row[3],
            state=CommandState(row[4]), created_at_ms=row[5], updated_at_ms=row[6],
            expires_at_ms=row[7], broker_reference=row[8],
            result=None if row[9] is None else json.loads(row[9]),
        )

    def create(self, record: CommandLedgerRecord) -> CommandLedgerRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT account_id,command_id,intent_id,fingerprint,state,created_at_ms,updated_at_ms,expires_at_ms,broker_reference,result_json FROM execution_commands WHERE account_id=? AND command_id=?",
                (record.account_id, record.command_id),
            ).fetchone()
            if row is not None:
                existing = self._row(row)
                if existing.fingerprint != record.fingerprint or existing.intent_id != record.intent_id:
                    raise CommandConflictError("command identity conflict")
                return existing
            conn.execute(
                "INSERT INTO execution_commands VALUES (?,?,?,?,?,?,?,?,?,?)",
                (record.account_id, record.command_id, record.intent_id, record.fingerprint, record.state.value,
                 record.created_at_ms, record.updated_at_ms, record.expires_at_ms, record.broker_reference,
                 None if record.result is None else json.dumps(record.result, sort_keys=True, separators=(",", ":"))),
            )
            return record

    def get(self, account_id: str, command_id: str) -> CommandLedgerRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT account_id,command_id,intent_id,fingerprint,state,created_at_ms,updated_at_ms,expires_at_ms,broker_reference,result_json FROM execution_commands WHERE account_id=? AND command_id=?",
                (account_id, command_id),
            ).fetchone()
            return None if row is None else self._row(row)

    def transition(
        self, account_id: str, command_id: str, new_state: CommandState, now_ms: int,
        *, result: dict[str, Any] | None = None, broker_reference: str | None = None,
    ) -> CommandLedgerRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT account_id,command_id,intent_id,fingerprint,state,created_at_ms,updated_at_ms,expires_at_ms,broker_reference,result_json FROM execution_commands WHERE account_id=? AND command_id=?",
                (account_id, command_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown command {account_id}/{command_id}")
            current = self._row(row)
            if new_state in {CommandState.SENT, CommandState.BROKER_PENDING} and current.state == CommandState.UNKNOWN:
                raise ValueError("UNKNOWN commands cannot blindly resend")
            if new_state != current.state and new_state not in _ALLOWED_TRANSITIONS[current.state]:
                raise ValueError(f"invalid command transition {current.state.value} -> {new_state.value}")
            conn.execute(
                "UPDATE execution_commands SET state=?,updated_at_ms=?,broker_reference=?,result_json=? WHERE account_id=? AND command_id=?",
                (new_state.value, now_ms, broker_reference or current.broker_reference,
                 None if result is None else json.dumps(result, sort_keys=True, separators=(",", ":")), account_id, command_id),
            )
            return self.get(account_id, command_id)  # type: ignore[return-value]

    def all_records(self) -> list[CommandLedgerRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT account_id,command_id,intent_id,fingerprint,state,created_at_ms,updated_at_ms,expires_at_ms,broker_reference,result_json FROM execution_commands ORDER BY account_id,command_id").fetchall()
            return [self._row(row) for row in rows]

"""Persistence Interfaces for Durable Execution Intents, Risk Ledgers, and State Snapshots."""

from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Optional, List, Dict, Any
import threading
import hashlib
import json
import sqlite3
from pathlib import Path

from src.fractal_flow.domain.event import Event, AggregateVersionTracker
from src.fractal_flow.domain.models import ExecutionIntent, OrderSide


class IdempotencyConflictException(Exception):
    """Raised when an intent with an existing idempotency_key has materially different request parameters."""

    pass


class IEventStore(ABC):
    @abstractmethod
    def append_event(self, event: Event) -> None:
        """Appends event with strict aggregate-version checking."""
        pass

    @abstractmethod
    def get_events_for_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> List[Event]:
        """Retrieves ordered event stream for an aggregate."""
        pass


class InMemoryEventStore(IEventStore):
    """Thread-safe event store enforcing optimistic concurrency and strict version sequence."""

    def __init__(self) -> None:
        self._events: List[Event] = []
        self._tracker = AggregateVersionTracker()
        self._lock = threading.Lock()

    def append_event(self, event: Event) -> None:
        with self._lock:
            self._tracker.append_event(event)
            self._events.append(event)

    def get_events_for_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> List[Event]:
        with self._lock:
            return [
                e
                for e in self._events
                if e.aggregate_type == aggregate_type and e.aggregate_id == aggregate_id
            ]


class DurableExecutionIntentRepository:
    """Thread-safe and restart-safe ExecutionIntent repository backed by SQLite/memory with request fingerprint verification."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path) if db_path else None
        self._intents: Dict[str, ExecutionIntent] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._fingerprints: Dict[str, str] = {}
        self._lock = threading.Lock()

        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._load_from_db()

    def _init_db(self) -> None:
        assert self.db_path is not None
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS execution_intents (
                        intent_id TEXT PRIMARY KEY,
                        idempotency_key TEXT UNIQUE NOT NULL,
                        fingerprint TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                """)
        finally:
            conn.close()

    @staticmethod
    def _serialize_intent(intent: ExecutionIntent) -> str:
        d = asdict(intent)
        d["side"] = (
            intent.side.value if hasattr(intent.side, "value") else str(intent.side)
        )
        return json.dumps(d, sort_keys=True)

    @staticmethod
    def _deserialize_intent(json_str: str) -> ExecutionIntent:
        d = json.loads(json_str)
        if isinstance(d.get("side"), str):
            try:
                d["side"] = OrderSide(d["side"])
            except ValueError:
                pass
        return ExecutionIntent(**d)

    def _load_from_db(self) -> None:
        assert self.db_path is not None
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT intent_id, idempotency_key, fingerprint, data_json FROM execution_intents"
            )
            rows = cursor.fetchall()
            for intent_id, key, fp, json_str in rows:
                intent = self._deserialize_intent(json_str)
                self._intents[intent_id] = intent
                self._idempotency_map[key] = intent_id
                self._fingerprints[key] = fp
        finally:
            conn.close()

    @staticmethod
    def compute_fingerprint(intent: ExecutionIntent) -> str:
        side_val = (
            intent.side.value if hasattr(intent.side, "value") else str(intent.side)
        )
        payload = {
            "symbol": intent.symbol,
            "side": side_val,
            "requested_volume": intent.requested_volume,
            "entry_price": intent.entry_price,
            "sl": intent.sl,
            "tp_plan": intent.tp_plan,
            "decision_id": intent.decision_id,
            "effective_config_id": intent.effective_config_id,
            "lineage_version": intent.lineage_version,
            "broker_constraint_snapshot": intent.broker_constraint_snapshot,
            "entry_plan_id": intent.entry_plan_id,
            "entry_model": intent.entry_model,
            "order_type": intent.order_type,
            "fill_policy": intent.fill_policy,
            "time_in_force": intent.time_in_force,
            "trigger_price": intent.trigger_price,
            "limit_price": intent.limit_price,
            "stop_limit_price": intent.stop_limit_price,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def save_intent(self, intent: ExecutionIntent) -> None:
        with self._lock:
            key = intent.idempotency_key
            fingerprint = self.compute_fingerprint(intent)

            if key in self._idempotency_map:
                existing_fp = self._fingerprints.get(key)
                if existing_fp and existing_fp != fingerprint:
                    raise IdempotencyConflictException(
                        f"Idempotency Conflict: Key '{key}' reused with materially different request fingerprint."
                    )
                return

            json_str = self._serialize_intent(intent)
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO execution_intents (intent_id, idempotency_key, fingerprint, data_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                intent.intent_id,
                                key,
                                fingerprint,
                                json_str,
                                intent.created_at,
                                intent.updated_at,
                            ),
                        )
                finally:
                    conn.close()

            self._intents[intent.intent_id] = intent
            self._idempotency_map[key] = intent.intent_id
            self._fingerprints[key] = fingerprint

    def get_intent(self, intent_id: str) -> Optional[ExecutionIntent]:
        with self._lock:
            return self._intents.get(intent_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        with self._lock:
            intent_id = self._idempotency_map.get(idempotency_key)
            return self._intents.get(intent_id) if intent_id else None

    def produce_observation(self, session_id: str, capability: Any) -> Any:
        """Produces a sealed observation proving authoritative intent repository provenance."""
        from src.fractal_flow.execution.recovery import (
            CapabilityRole,
            SealedObservation,
            RecoveryEvidenceError,
            ProducerCapability,
        )

        if (
            not isinstance(capability, ProducerCapability)
            or capability.role != CapabilityRole.INTENT_REPOSITORY
        ):
            raise RecoveryEvidenceError(
                "DurableExecutionIntentRepository observation requires a valid INTENT_REPOSITORY ProducerCapability."
            )

        import time

        with self._lock:
            payload = {
                "db_path": str(self.db_path) if self.db_path else "",
                "intents_count": len(self._intents),
                "idempotency_keys_count": len(self._idempotency_map),
            }
            return SealedObservation.create(
                capability, session_id, int(time.time()), payload
            )

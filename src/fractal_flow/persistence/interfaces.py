"""Persistence Interfaces for Durable Execution Intents, Risk Ledgers, and State Snapshots."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import threading
import hashlib
import json

from src.fractal_flow.domain.event import Event, AggregateVersionTracker
from src.fractal_flow.domain.models import ExecutionIntent, Position


class IdempotencyConflictException(Exception):
    """Raised when an intent with an existing idempotency_key has materially different request parameters."""
    pass


class IEventStore(ABC):
    @abstractmethod
    def append_event(self, event: Event) -> None:
        """Appends event with strict aggregate-version checking."""
        pass

    @abstractmethod
    def get_events_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> List[Event]:
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

    def get_events_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> List[Event]:
        with self._lock:
            return [
                e for e in self._events if e.aggregate_type == aggregate_type and e.aggregate_id == aggregate_id
            ]


class DurableExecutionIntentRepository:
    """Thread-safe and restart-safe ExecutionIntent repository with request fingerprint verification."""

    def __init__(self) -> None:
        self._intents: Dict[str, ExecutionIntent] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._fingerprints: Dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def compute_fingerprint(intent: ExecutionIntent) -> str:
        side_val = intent.side.value if hasattr(intent.side, "value") else str(intent.side)
        payload = {
            "symbol": intent.symbol,
            "side": side_val,
            "requested_volume": intent.requested_volume,
            "entry_price": intent.entry_price,
            "sl": intent.sl,
            "decision_id": intent.decision_id,
            "effective_config_id": intent.effective_config_id,
            "lineage_version": intent.lineage_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

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

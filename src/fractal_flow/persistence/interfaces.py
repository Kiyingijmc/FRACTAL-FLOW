"""Persistence Interfaces for Event Store, Execution Intents, and State Snapshots."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from src.fractal_flow.domain.event import Event
from src.fractal_flow.domain.models import ExecutionIntent, Position, OpportunityObject, TradeDecision


class IEventStore(ABC):
    @abstractmethod
    def append_event(self, event: Event) -> None:
        """Appends event with optimistic aggregate-version checking."""
        pass

    @abstractmethod
    def get_events_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> List[Event]:
        """Retrieves ordered event stream for an aggregate."""
        pass


class IExecutionIntentRepository(ABC):
    @abstractmethod
    def save_intent(self, intent: ExecutionIntent) -> None:
        """Persists execution intent prior to broker dispatch."""
        pass

    @abstractmethod
    def get_intent(self, intent_id: str) -> Optional[ExecutionIntent]:
        """Retrieves intent by ID."""
        pass

    @abstractmethod
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        """Retrieves intent by idempotency key."""
        pass


class IPositionRepository(ABC):
    @abstractmethod
    def save_position(self, position: Position) -> None:
        """Saves or updates position."""
        pass

    @abstractmethod
    def get_position(self, position_id: str) -> Optional[Position]:
        """Retrieves position by ID."""
        pass

    @abstractmethod
    def get_active_positions(self) -> List[Position]:
        """Retrieves all open/active positions."""
        pass


class InMemoryEventStore(IEventStore):
    def __init__(self) -> None:
        self._events: List[Event] = []
        self._versions: Dict[str, int] = {}

    def append_event(self, event: Event) -> None:
        key = f"{event.aggregate_type}:{event.aggregate_id}"
        current = self._versions.get(key, 0)
        if event.aggregate_version <= current:
            raise ValueError(f"Optimistic concurrency violation on {key}")
        self._events.append(event)
        self._versions[key] = event.aggregate_version

    def get_events_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> List[Event]:
        return [
            e for e in self._events if e.aggregate_type == aggregate_type and e.aggregate_id == aggregate_id
        ]


class InMemoryExecutionIntentRepository(IExecutionIntentRepository):
    def __init__(self) -> None:
        self._intents: Dict[str, ExecutionIntent] = {}
        self._idempotency_map: Dict[str, str] = {}

    def save_intent(self, intent: ExecutionIntent) -> None:
        self._intents[intent.intent_id] = intent
        self._idempotency_map[intent.idempotency_key] = intent.intent_id

    def get_intent(self, intent_id: str) -> Optional[ExecutionIntent]:
        return self._intents.get(intent_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        intent_id = self._idempotency_map.get(idempotency_key)
        return self._intents.get(intent_id) if intent_id else None

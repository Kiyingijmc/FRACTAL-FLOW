"""Canonical State Registry and StateEnvelope with Fail-Closed Machine Validation."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any
import math
from pathlib import Path
import yaml


class InvalidStateTransitionException(Exception):
    """Raised when an illegal state transition or invalid state machine is encountered."""
    pass


class StateRegistry:
    """Canonical runtime registry loading states and transitions directly from spec/*.yaml."""

    def __init__(self, states_path: str = "spec/states.yaml", transitions_path: str = "spec/transitions.yaml") -> None:
        self._states: Dict[str, Set[str]] = {}
        self._transitions: Dict[str, Dict[str, List[str]]] = {}
        self._load_specs(states_path, transitions_path)

    def _load_specs(self, states_path: str, transitions_path: str) -> None:
        s_path = Path(states_path)
        if s_path.exists():
            with open(s_path) as f:
                data = yaml.safe_load(f)
                raw_states = data.get("states", {}) if isinstance(data, dict) else {}
                for machine, st_list in raw_states.items():
                    self._states[machine] = set(st_list)

        t_path = Path(transitions_path)
        if t_path.exists():
            with open(t_path) as f:
                data = yaml.safe_load(f)
                raw_trans = data.get("transitions", {}) if isinstance(data, dict) else {}
                for machine, trans_map in raw_trans.items():
                    self._transitions[machine] = {k: list(v) for k, v in trans_map.items()}

    def is_known_machine(self, machine_name: str) -> bool:
        return machine_name in self._states or machine_name in self._transitions

    def is_valid_state(self, machine_name: str, state_name: str) -> bool:
        if machine_name not in self._states:
            return False
        return state_name in self._states[machine_name]

    def validate_transition(self, machine_name: str, current_state: str, new_state: str) -> None:
        """Fails closed if machine is unknown, state is unknown, or transition is illegal."""
        if not self.is_known_machine(machine_name):
            raise InvalidStateTransitionException(f"Unknown state machine: '{machine_name}'. Fail-closed.")

        if not self.is_valid_state(machine_name, current_state):
            raise InvalidStateTransitionException(
                f"Unknown current state '{current_state}' for machine '{machine_name}'. Fail-closed."
            )

        if not self.is_valid_state(machine_name, new_state):
            raise InvalidStateTransitionException(
                f"Unknown target state '{new_state}' for machine '{machine_name}'. Fail-closed."
            )

        allowed = self._transitions.get(machine_name, {}).get(current_state, [])
        if new_state not in allowed:
            raise InvalidStateTransitionException(
                f"Illegal state transition for '{machine_name}' from '{current_state}' to '{new_state}'. Allowed: {allowed}"
            )


# Global singleton instance
GLOBAL_STATE_REGISTRY = StateRegistry()


@dataclass
class StateEnvelope:
    state_id: str
    object_id: str
    object_type: str
    symbol: str
    timeframe: str
    root_id: str
    parent_id: str
    parent_version: int
    state: str
    previous_state: str
    version: int
    source_timestamp: int
    event_timestamp: int
    processing_timestamp: int
    valid_until: int
    last_seen: int
    sub_state: Optional[str] = None
    confidence: float = 1.0
    confidence_class: str = "HIGH"
    reason_codes: List[str] = field(default_factory=list)
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    created_at: int = 0
    updated_at: int = 0
    authority: str = "PDE"
    registry: StateRegistry = field(default_factory=lambda: GLOBAL_STATE_REGISTRY)

    def __post_init__(self) -> None:
        if not self.object_id or not self.state_id or not self.symbol:
            raise ValueError("StateEnvelope missing required object_id, state_id, or symbol")

        if self.version <= 0 or self.parent_version <= 0:
            raise ValueError("StateEnvelope version and parent_version must be positive integers")

        if math.isnan(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"StateEnvelope confidence must be between 0.0 and 1.0, got {self.confidence}")

        # Strict Temporal Ordering Validation
        if not (self.source_timestamp <= self.event_timestamp <= self.processing_timestamp):
            raise ValueError(
                f"Temporal ordering violation: source_timestamp ({self.source_timestamp}) "
                f"<= event_timestamp ({self.event_timestamp}) <= processing_timestamp ({self.processing_timestamp}) required."
            )

        if self.last_seen < self.source_timestamp:
            raise ValueError(
                f"Chronology violation: last_seen ({self.last_seen}) cannot be prior to source_timestamp ({self.source_timestamp})"
            )

        if self.valid_until < self.last_seen:
            raise ValueError(
                f"StateEnvelope valid_until ({self.valid_until}) cannot be prior to last_seen ({self.last_seen})"
            )

        # Fail closed on state membership
        m_type = f"{self.object_type}State"
        if self.registry.is_known_machine(m_type):
            if not self.registry.is_valid_state(m_type, self.state):
                raise ValueError(f"Invalid canonical state '{self.state}' for machine '{m_type}'")

    def transition_to(self, new_state: str, machine_type: Optional[str] = None) -> None:
        """Attempts state transition; fails closed if transition is illegal."""
        m_type = machine_type or f"{self.object_type}State"
        self.registry.validate_transition(m_type, self.state, new_state)
        self.previous_state = self.state
        self.state = new_state
        self.version += 1

"""Canonical State Registry and StateEnvelope with Fail-Closed Machine Validation."""

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.fractal_flow.domain.market import Timeframe


class InvalidStateTransitionException(Exception):
    """Raised when an illegal state transition or invalid state machine is encountered."""


# Non-state-bearing entity object types declared explicitly by canonical specification
NON_STATE_BEARING_TYPES: set[str] = {
    "MarketObservation",
    "FeatureSet",
    "JournalEvent",
    "BrokerConstraints",
}


class StateRegistry:
    """Canonical runtime registry loading states and transitions directly from spec/*.yaml."""

    def __init__(
        self,
        states_path: str = "spec/states.yaml",
        transitions_path: str = "spec/transitions.yaml",
    ) -> None:
        self._states: dict[str, set[str]] = {}
        self._transitions: dict[str, dict[str, list[str]]] = {}
        self._load_specs(states_path, transitions_path)

    def _load_specs(self, states_path: str, transitions_path: str) -> None:
        s_path = Path(states_path)
        if not s_path.exists():
            raise FileNotFoundError(
                f"StateRegistry startup failure: states specification file not found at '{states_path}'"
            )
        try:
            with open(s_path) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(
                f"StateRegistry startup failure: malformed states specification in '{states_path}': {e}"
            ) from e

        if not isinstance(data, dict) or "states" not in data or not isinstance(data["states"], dict):
            raise ValueError(f"StateRegistry startup failure: missing or invalid 'states' root dict in '{states_path}'")

        for machine, st_list in data["states"].items():
            if not isinstance(st_list, (list, set, tuple)):
                raise ValueError(f"StateRegistry startup failure: states for machine '{machine}' must be a list")
            self._states[machine] = set(st_list)

        t_path = Path(transitions_path)
        if not t_path.exists():
            raise FileNotFoundError(
                f"StateRegistry startup failure: transitions specification file not found at '{transitions_path}'"
            )
        try:
            with open(t_path) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(
                f"StateRegistry startup failure: malformed transitions specification in '{transitions_path}': {e}"
            ) from e

        if not isinstance(data, dict) or "transitions" not in data or not isinstance(data["transitions"], dict):
            raise ValueError(
                f"StateRegistry startup failure: missing or invalid 'transitions' root dict in '{transitions_path}'"
            )

        for machine, trans_map in data["transitions"].items():
            if not isinstance(trans_map, dict):
                raise ValueError(
                    f"StateRegistry startup failure: transition map for machine '{machine}' must be a dict"
                )
            self._transitions[machine] = {k: list(v) for k, v in trans_map.items()}

    def is_known_machine(self, machine_name: str) -> bool:
        return machine_name in self._states or machine_name in self._transitions

    def is_valid_state(self, machine_name: str, state_name: str) -> bool:
        if machine_name not in self._states:
            return False
        return state_name in self._states[machine_name]

    def validate_transition(self, machine_name: str, current_state: str, new_state: str) -> None:
        """Fails closed if machine is unknown, current state is unknown, target state is unknown, or transition is illegal."""
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

    @classmethod
    def calculate_timeframe_validity_seconds(cls, timeframe_str: str, default_bars: int = 5) -> int:
        """Calculates timeframe-aware validity window in seconds (default 5 bars of timeframe duration).

        Fails closed with ValueError on invalid or unmapped timeframe strings.
        """
        try:
            tf = Timeframe.validate(timeframe_str)
            return tf.seconds * default_bars
        except ValueError as e:
            raise ValueError(
                f"StateEnvelope validity calculation failure: invalid or unmapped timeframe '{timeframe_str}'"
            ) from e

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
    sub_state: str | None = None
    confidence: float = 1.0
    confidence_class: str = "HIGH"
    reason_codes: list[str] = field(default_factory=list)
    configuration_version: int = 1
    data_version: int = 1
    feature_version: int = 1
    created_at: int = 0
    updated_at: int = 0
    authority: str = "PDE"
    registry: StateRegistry = field(default_factory=lambda: GLOBAL_STATE_REGISTRY)
    schema_version: int = 1
    engine_version: int = 1
    causal_watermark: int | None = None
    effective_timestamp: int | None = None

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

        if self.schema_version <= 0 or self.engine_version <= 0:
            raise ValueError("StateEnvelope schema_version and engine_version must be positive")

        if self.causal_watermark is not None and self.causal_watermark < self.event_timestamp:
            raise ValueError("causal_watermark cannot precede event_timestamp")

        if self.effective_timestamp is not None and self.effective_timestamp < self.event_timestamp:
            raise ValueError("effective_timestamp cannot precede event_timestamp")

        if self.last_seen < self.source_timestamp:
            raise ValueError(
                f"Chronology violation: last_seen ({self.last_seen}) cannot be prior to source_timestamp ({self.source_timestamp})"
            )

        if self.valid_until < self.last_seen:
            raise ValueError(
                f"StateEnvelope valid_until ({self.valid_until}) cannot be prior to last_seen ({self.last_seen})"
            )

        # Fail closed on state machine and state membership
        m_type = f"{self.object_type}State" if not self.object_type.endswith("State") else self.object_type
        if self.object_type not in NON_STATE_BEARING_TYPES:
            if not self.registry.is_known_machine(m_type):
                raise ValueError(
                    f"StateEnvelope object_type '{self.object_type}' maps to unknown machine '{m_type}'. Fail-closed."
                )

            if not self.registry.is_valid_state(m_type, self.state):
                raise ValueError(f"Invalid canonical current state '{self.state}' for machine '{m_type}'. Fail-closed.")

            if self.previous_state and not self.registry.is_valid_state(m_type, self.previous_state):
                raise ValueError(
                    f"Invalid canonical previous state '{self.previous_state}' for machine '{m_type}'. Fail-closed."
                )

    def transition_to(self, new_state: str, machine_type: str | None = None) -> None:
        """Attempts state transition; fails closed if transition is illegal or target/machine is unknown."""
        m_type = machine_type or (
            f"{self.object_type}State" if not self.object_type.endswith("State") else self.object_type
        )
        self.registry.validate_transition(m_type, self.state, new_state)
        self.previous_state = self.state
        self.state = new_state
        self.version += 1

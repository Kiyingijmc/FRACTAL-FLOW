"""Canonical State Envelope and State Machine Transition Validator."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import math
from pathlib import Path
import yaml


class InvalidStateTransitionException(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


def load_spec_transitions() -> Dict[str, Dict[str, List[str]]]:
    spec_path = Path("spec/transitions.yaml")
    if spec_path.exists():
        with open(spec_path) as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "transitions" in data:
                return data["transitions"]
            return data
    return {}


TRANSITION_RULES: Dict[str, Dict[str, List[str]]] = load_spec_transitions()


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

    def __post_init__(self) -> None:
        if not self.object_id or not self.state_id or not self.symbol:
            raise ValueError("StateEnvelope missing required object_id, state_id, or symbol")

        if self.version <= 0 or self.parent_version <= 0:
            raise ValueError("StateEnvelope version and parent_version must be positive integers")

        if math.isnan(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"StateEnvelope confidence must be between 0.0 and 1.0, got {self.confidence}")

        if self.valid_until < self.last_seen:
            raise ValueError(
                f"StateEnvelope valid_until ({self.valid_until}) cannot be prior to last_seen ({self.last_seen})"
            )

        if self.source_timestamp < 0 or self.event_timestamp < 0 or self.processing_timestamp < 0:
            raise ValueError("Timestamps cannot be negative")

    def transition_to(self, new_state: str, machine_type: Optional[str] = None) -> None:
        """Attempts state transition; fails closed if transition is illegal."""
        m_type = machine_type or f"{self.object_type}State"
        rules = TRANSITION_RULES.get(m_type, {})
        if rules:
            allowed = rules.get(self.state, [])
            if new_state not in allowed:
                raise InvalidStateTransitionException(
                    f"Illegal state transition for {m_type} from '{self.state}' to '{new_state}'. Allowed: {allowed}"
                )
        self.previous_state = self.state
        self.state = new_state
        self.version += 1

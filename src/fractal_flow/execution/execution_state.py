"""Execution State Machine Model and Storage State Mapping."""

from enum import Enum, unique
from src.fractal_flow.domain.envelope import InvalidStateTransitionException


@unique
class ExecutionState(str, Enum):
    EXEC_READY = "EXEC_READY"
    EXEC_SUBMITTING = "EXEC_SUBMITTING"
    EXEC_SUBMITTED = "EXEC_SUBMITTED"
    EXEC_ACCEPTED = "EXEC_ACCEPTED"
    EXEC_PARTIAL = "EXEC_PARTIAL"
    EXEC_FILLED = "EXEC_FILLED"
    EXEC_REJECTED = "EXEC_REJECTED"
    EXEC_CANCELLED = "EXEC_CANCELLED"
    EXEC_UNKNOWN = "EXEC_UNKNOWN"
    EXEC_RECONCILING = "EXEC_RECONCILING"


# Mapping from external storage status strings to canonical ExecutionState
STORAGE_STATUS_MAP = {
    "READY": ExecutionState.EXEC_READY,
    "SUBMITTING": ExecutionState.EXEC_SUBMITTING,
    "PENDING": ExecutionState.EXEC_SUBMITTED,
    "ACCEPTED": ExecutionState.EXEC_ACCEPTED,
    "PARTIAL_FILL": ExecutionState.EXEC_PARTIAL,
    "FILLED": ExecutionState.EXEC_FILLED,
    "REJECTED": ExecutionState.EXEC_REJECTED,
    "CANCELLED": ExecutionState.EXEC_CANCELLED,
    "UNKNOWN": ExecutionState.EXEC_UNKNOWN,
    "RECONCILING": ExecutionState.EXEC_RECONCILING,
}


def map_storage_status(status_str: str) -> ExecutionState:
    """Explicitly maps storage status strings to canonical ExecutionState."""
    if status_str in STORAGE_STATUS_MAP:
        return STORAGE_STATUS_MAP[status_str]
    try:
        return ExecutionState(status_str)
    except ValueError:
        raise ValueError(f"Unknown execution storage status string: {status_str}")

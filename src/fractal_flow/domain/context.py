"""Minimal causal-status contract required by the additive Data Engine."""

from enum import Enum, unique


@unique
class DataStatus(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

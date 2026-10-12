"""Fail-closed Phase 6 authority-state model; no broker I/O."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SafetyGateState:
    authenticated: bool = False
    reconciliation_required: bool = True
    quarantined: bool = False
    protective_only: bool = True

    def __post_init__(self) -> None:
        if not self.authenticated or self.reconciliation_required or self.quarantined:
            object.__setattr__(self, "protective_only", True)

    @property
    def may_dispatch_effectful_command(self) -> bool:
        # Dispatch remains locked until a separately reviewed authority path exists.
        return False

    @property
    def may_accept_new_exposure(self) -> bool:
        return False

    def quarantine(self) -> "SafetyGateState":
        return SafetyGateState(False, True, True, True)

    def require_reconciliation(self) -> "SafetyGateState":
        return SafetyGateState(self.authenticated, True, self.quarantined, True)

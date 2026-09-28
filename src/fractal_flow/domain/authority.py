"""Software-Enforced Authority Matrix."""

from dataclasses import dataclass
from typing import Set


class AuthorityViolationException(Exception):
    """Raised when an engine attempts an unauthorized capability."""
    pass


# Capability Definitions
CAPABILITIES = {
    "PDE": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_FEATURES",
            "WRITE_PDE_STATE",
            "CREATE_PULLBACK_OBJECT",
            "INVALIDATE_SUBORDINATE_CHILDREN",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION_STRATEGICALLY",
        },
    },
    "Risk": {
        "allowed": {
            "ALLOCATE_RISK",
            "ASSESS_ACCOUNT_FEASIBILITY",
            "REJECT_EXCESSIVE_RISK",
        },
        "forbidden": {
            "MANUFACTURE_DIRECTION",
            "CREATE_SIGNAL",
        },
    },
    "Portfolio": {
        "allowed": {
            "ARBITRATE_EXPOSURE",
            "ENFORCE_CURRENCY_LIMITS",
            "ENFORCE_CORRELATION_LIMITS",
        },
        "forbidden": {
            "MANUFACTURE_DIRECTION",
            "CREATE_SIGNAL",
        },
    },
    "Execution": {
        "allowed": {
            "SUBMIT_AUTHORIZED_INTENT",
            "RECONCILE_ORDERS",
        },
        "forbidden": {
            "REINTERPRET_STRATEGY",
            "ALTER_RISK_PARAMETERS",
        },
    },
}


class AuthorityMatrix:
    @staticmethod
    def verify_capability(engine_name: str, action: str) -> None:
        """Verifies if an engine has authority to perform a specific action."""
        if engine_name not in CAPABILITIES:
            raise AuthorityViolationException(f"Unknown engine: '{engine_name}'")

        allowed = CAPABILITIES[engine_name]["allowed"]
        forbidden = CAPABILITIES[engine_name]["forbidden"]

        if action in forbidden or action not in allowed:
            raise AuthorityViolationException(
                f"Authority Violation: Engine '{engine_name}' is forbidden from action '{action}'"
            )

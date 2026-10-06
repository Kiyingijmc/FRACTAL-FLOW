"""Software-Enforced Authority Matrix."""


class AuthorityViolationException(Exception):
    """Raised when an engine attempts an unauthorized capability or an unknown engine accesses capabilities."""


# Capability Definitions for all core system engines
CAPABILITIES = {
    "Phase3Orchestrator": {
        "allowed": {"READ_PHASE2_EVIDENCE", "WRITE_OPPORTUNITY_STATE", "CREATE_OPPORTUNITY_CANDIDATE"},
        "forbidden": {"CREATE_EXECUTION_INTENT", "SUBMIT_ORDER", "ALLOCATE_RISK", "AUTHORIZE_TRADE", "MANUFACTURE_DIRECTION"},
    },
    "DataQuality": {
        "allowed": {
            "READ_MARKET_STATE",
            "WRITE_DATA_QUALITY_STATE",
            "ASSIGN_REASON_CODES",
            "BLOCK_EXPOSURE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "ALLOCATE_RISK",
            "MANUFACTURE_DIRECTION",
        },
    },
    "Volatility": {
        "allowed": {
            "READ_MARKET_STATE",
            "WRITE_VOLATILITY_STATE",
            "COMPUTE_VOLATILITY_METRICS",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "ALLOCATE_RISK",
            "MANUFACTURE_DIRECTION",
        },
    },
    "Structure": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_VOLATILITY",
            "WRITE_STRUCTURE_STATE",
            "INVALIDATE_PARENT_STATE",
            "OUTPUT_STRUCTURAL_STOP_CANDIDATE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "ALLOCATE_RISK",
            "SIZE_TRADE",
            "AUTHORIZE_TRADE",
        },
    },
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
    "Flow": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_FEATURES",
            "WRITE_FLOW_STATE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION_STRATEGICALLY",
        },
    },
    "Regime": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_FEATURES",
            "WRITE_REGIME_STATE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION_STRATEGICALLY",
        },
    },
    "Role": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_FEATURES",
            "WRITE_ROLE_STATE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION_STRATEGICALLY",
        },
    },
    "Location": {
        "allowed": {
            "READ_MARKET_STATE",
            "READ_FEATURES",
            "WRITE_LOCATION_STATE",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION_STRATEGICALLY",
        },
    },
    "EntryPolicy": {
        "allowed": {
            "READ_OPPORTUNITY",
            "READ_SIGNAL",
            "READ_STRUCTURE",
            "READ_PULLBACK",
            "READ_TRADEABILITY",
            "READ_RISK",
            "READ_PORTFOLIO",
            "READ_NEWS",
            "READ_BROKER_CONSTRAINTS",
            "CREATE_ENTRY_PLAN",
            "INVALIDATE_ENTRY_PLAN",
        },
        "forbidden": {
            "SUBMIT_ORDER",
            "MODIFY_POSITION",
            "CLOSE_POSITION",
            "MANUFACTURE_DIRECTION",
            "OVERRIDE_RISK",
            "OVERRIDE_PORTFOLIO",
            "OVERRIDE_NEWS",
        },
    },
    "NewsShield": {
        "allowed": {
            "READ_CALENDAR",
            "WRITE_NEWS_STATE",
            "ENFORCE_PROTECTIVE_STOPS",
        },
        "forbidden": {
            "CREATE_EXECUTION_INTENT",
            "SUBMIT_ORDER",
            "MANUFACTURE_DIRECTION",
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
            raise AuthorityViolationException(
                f"Authority Violation: Unknown engine '{engine_name}' cannot claim capabilities."
            )

        allowed = CAPABILITIES[engine_name]["allowed"]
        forbidden = CAPABILITIES[engine_name]["forbidden"]

        if action in forbidden or action not in allowed:
            raise AuthorityViolationException(
                f"Authority Violation: Engine '{engine_name}' is forbidden from action '{action}'"
            )

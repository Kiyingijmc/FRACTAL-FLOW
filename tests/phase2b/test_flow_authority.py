"""Tests for Flow Engine Runtime Authority Boundaries and Capability Verification."""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.authority import AuthorityMatrix, AuthorityViolationException
from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe


def test_flow_allowed_capabilities():
    # Verify allowed capabilities pass without error
    AuthorityMatrix.verify_capability("Flow", "READ_MARKET_STATE")
    AuthorityMatrix.verify_capability("Flow", "READ_FEATURES")
    AuthorityMatrix.verify_capability("Flow", "WRITE_FLOW_STATE")


def test_flow_forbidden_capabilities_fail_closed():
    forbidden_actions = [
        "CREATE_EXECUTION_INTENT",
        "SUBMIT_ORDER",
        "MODIFY_POSITION",
        "CLOSE_POSITION_STRATEGICALLY",
        "ALLOCATE_RISK",
        "AUTHORIZE_TRADE",
    ]

    for action in forbidden_actions:
        with pytest.raises(AuthorityViolationException, match="forbidden"):
            AuthorityMatrix.verify_capability("Flow", action)


def test_flow_engine_process_bar_checks_authority():
    # Normal execution calls verify_capability("Flow", "WRITE_FLOW_STATE")
    engine = FlowEngine(symbol="EURUSD")
    bar = Bar.create(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=1700000000,
        close_timestamp=1700000060,
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0990"),
        close=Decimal("1.1005"),
        spread=Decimal("0.0001"),
    )
    rec = engine.process_bar(
        bar=bar,
        v_local=Decimal("0.0010"),
        root_id="root_1",
        parent_id="p1",
        parent_version=1,
    )
    assert rec.authority == "FLOW"

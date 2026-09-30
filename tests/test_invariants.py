"""Automated Invariants Verification Tests (AGENTS.md 42 Invariants)."""

import pytest

from src.fractal_flow.config.config import (
    BaseConfig,
    NewsOverlay,
    compute_effective_config,
)
from src.fractal_flow.domain.authority import (
    AuthorityMatrix,
    AuthorityViolationException,
)
from src.fractal_flow.domain.broker import BrokerConstraints


def test_invariant_pde_cannot_execute() -> None:
    """AGENTS.md Invariant #3: PDE cannot call OrderSend / create execution intent."""
    with pytest.raises(AuthorityViolationException) as exc_info:
        AuthorityMatrix.verify_capability("PDE", "CREATE_EXECUTION_INTENT")
    assert "Authority Violation" in str(exc_info.value)


def test_invariant_risk_cannot_manufacture_direction() -> None:
    """AGENTS.md Invariant #5: Risk cannot manufacture direction."""
    with pytest.raises(AuthorityViolationException) as exc_info:
        AuthorityMatrix.verify_capability("Risk", "MANUFACTURE_DIRECTION")
    assert "Authority Violation" in str(exc_info.value)


def test_invariant_portfolio_cannot_manufacture_direction() -> None:
    """AGENTS.md Invariant #6: Portfolio arbitration cannot manufacture direction."""
    with pytest.raises(AuthorityViolationException) as exc_info:
        AuthorityMatrix.verify_capability("Portfolio", "MANUFACTURE_DIRECTION")
    assert "Authority Violation" in str(exc_info.value)


def test_invariant_news_lockdown_blocks_strategic_exposure() -> None:
    """AGENTS.md Invariant #20: No strategic new exposure during NEWS_LOCKDOWN."""
    base = BaseConfig()
    from decimal import Decimal

    news = NewsOverlay(news_lockdown_active=True, risk_multiplier=Decimal("0.0"))
    eff = compute_effective_config(base, "EURUSD", news_overlay=news)
    assert eff.news_lockdown_active is True
    assert eff.risk_per_trade_pct == 0.0


def test_invariant_broker_constraints_stops_level() -> None:
    """AGENTS.md Invariant #38: Broker stops level enforcement."""
    broker = BrokerConstraints(
        symbol="EURUSD",
        base_currency="EUR",
        quote_currency="USD",
        account_currency="USD",
        contract_size=100000.0,
        tick_size=0.00001,
        tick_value=1.0,
        digits=5,
        min_volume=0.01,
        max_volume=100.0,
        volume_step=0.01,
        stops_level=5.0,  # 5 pips
        freeze_level=2.0,
    )
    with pytest.raises(ValueError) as exc_info:
        broker.validate_stop_distance(sl_distance_pips=3.0)  # Below 5.0 pips
    assert "below broker stops_level" in str(exc_info.value)

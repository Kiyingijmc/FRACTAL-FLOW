"""Tests for Entry Domain Foundation and EntryPolicyEngine with MURG ActiveMarketContext Integration."""

from src.fractal_flow.domain.entry import (
    EntryModel,
    EntryPolicyEngine,
    ActiveMarketContext,
)
from src.fractal_flow.domain.models import Direction


def test_entry_policy_engine_with_active_murg_context() -> None:
    engine = EntryPolicyEngine()
    ctx = ActiveMarketContext(
        canonical_id="EURUSD",
        activation_state="ACTIVE",
        entry_analysis_enabled=True,
        is_tradable_session=True,
        broker_constraints={
            "supported_order_types": ["MARKET_BUY", "BUY_LIMIT", "BUY_STOP"]
        },
    )

    # Scalping mode prefers MARKET_CONFIRMATION
    model = engine.evaluate_entry_policy(
        "SCALPING", Direction.LONG, 1.0850, 1.0820, ctx
    )
    assert model == EntryModel.MARKET_CONFIRMATION


def test_entry_policy_engine_returns_no_entry_when_murg_dormant() -> None:
    engine = EntryPolicyEngine()
    ctx_dormant = ActiveMarketContext(
        canonical_id="EURUSD",
        activation_state="DORMANT",
        entry_analysis_enabled=False,  # Entry analysis disabled by MURG!
        is_tradable_session=True,
        broker_constraints={"supported_order_types": ["MARKET_BUY"]},
    )

    model = engine.evaluate_entry_policy(
        "SCALPING", Direction.LONG, 1.0850, 1.0820, ctx_dormant
    )
    assert model == EntryModel.NO_ENTRY

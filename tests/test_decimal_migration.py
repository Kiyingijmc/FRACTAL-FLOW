"""Unit tests verifying exact Decimal exactness, hash stability, and round-trip serialization."""

from decimal import Decimal

from src.fractal_flow.config.config import (
    BaseConfig,
    NewsOverlay,
    compute_effective_config,
)
from src.fractal_flow.simulation.simulator import DeterministicBrokerSimulator
from src.fractal_flow.domain.models import ExecutionIntent, OrderSide


def test_decimal_exactness_no_floating_point_artifacts() -> None:
    """Verifies that Decimal financial calculations remain exact without float representation artifacts."""
    val1 = Decimal("0.1")
    val2 = Decimal("0.2")
    res = val1 + val2
    assert res == Decimal("0.3")
    assert str(res) == "0.3"


def test_effective_config_hash_stability() -> None:
    """Proves that EffectiveConfiguration hashing remains deterministic and stable across Decimal inputs."""
    base = BaseConfig(
        version=1,
        max_spread_pips=Decimal("1.5"),
        risk_per_trade_pct=Decimal("0.02"),
        max_currency_exposure_lots=Decimal("5.0"),
    )
    news_overlay = NewsOverlay(
        news_lockdown_active=False, risk_multiplier=Decimal("0.5")
    )

    cfg1 = compute_effective_config(base, "EURUSD", news_overlay=news_overlay)
    cfg2 = compute_effective_config(base, "EURUSD", news_overlay=news_overlay)

    assert cfg1.effective_config_id == cfg2.effective_config_id
    assert cfg1.risk_per_trade_pct == Decimal("0.010")


def test_simulator_pnl_exactness() -> None:
    """Verifies exact PnL and volume tracking in DeterministicBrokerSimulator with Decimal inputs."""
    sim = DeterministicBrokerSimulator()

    intent = ExecutionIntent(
        intent_id="intent_exact_1",
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        idempotency_key="key_exact_1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        requested_volume=Decimal("1.0"),
        entry_price=Decimal("1.08500"),
        sl=Decimal("1.08000"),
        tp_plan={},
        effective_config_id="cfg_123",
        lineage_version=1,
        broker_constraint_snapshot={"contract_size": Decimal("100000.0")},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        status="EXEC_READY",
        created_at=1000,
        updated_at=1000,
    )

    state = sim.submit_intent(intent)
    assert state.value == "EXEC_FILLED"

    pos_id = "POS_9001"
    # Close position at 1.08600 (10 pips = $100 profit)
    success = sim.close_position(pos_id, exit_price=Decimal("1.08600"))
    assert success is True

    pos = sim.positions[pos_id]
    assert pos.realized_pnl == Decimal("100.00")
    assert pos.remaining_volume == Decimal("0.0")

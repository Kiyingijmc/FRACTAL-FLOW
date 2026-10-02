"""Tests for StateEnvelope validation, BrokerConstraints, Units, and Configuration Identity."""

from decimal import Decimal
import pytest

from src.fractal_flow.config.config import (
    BaseConfig,
    NewsOverlay,
    SymbolOverlay,
    compute_effective_config,
)
from src.fractal_flow.domain.broker import BrokerConstraints
from src.fractal_flow.domain.envelope import StateEnvelope
from src.fractal_flow.domain.units import (
    PositiveCurrencyAmount,
    Price,
    Score,
    SignedCurrencyAmount,
    Volume,
    pips_to_price,
    price_to_pips,
)


def test_units_validation() -> None:
    with pytest.raises(ValueError):
        Price(-1.0)
    with pytest.raises(ValueError):
        Volume(0.0)
    with pytest.raises(ValueError):
        PositiveCurrencyAmount(-5.0)

    # SignedCurrencyAmount permits negative money (PnL)
    pnl = SignedCurrencyAmount(-150.50)
    assert pnl.value == Decimal("-150.50")

    with pytest.raises(ValueError):
        Score(1.5)


def test_price_pip_conversions_exact_jpy() -> None:
    # 3-digit JPY symbol (1 pip = 0.01)
    pips = price_to_pips(0.50, digits=3)
    assert pips.value == Decimal("50.0")

    dist = pips_to_price(50.0, digits=3)
    assert dist == Decimal("0.50")


def test_broker_constraints_decimal_validation() -> None:
    broker = BrokerConstraints(
        symbol="EURUSD",
        base_currency="EUR",
        quote_currency="USD",
        account_currency="USD",
        contract_size=Decimal("100000.0"),
        tick_size=Decimal("0.00001"),
        tick_value=Decimal("1.0"),
        digits=5,
        min_volume=Decimal("0.01"),
        max_volume=Decimal("100.0"),
        volume_step=Decimal("0.01"),
        stops_level=Decimal("5.0"),
        freeze_level=Decimal("2.0"),
    )
    vol = broker.validate_volume(0.05)
    assert vol.value == Decimal("0.05")

    with pytest.raises(ValueError) as exc:
        broker.validate_volume(0.015)  # Invalid fractional step
    assert "does not align" in str(exc.value)


def test_state_envelope_validation() -> None:
    with pytest.raises(ValueError):
        StateEnvelope(
            state_id="s1",
            object_id="o1",
            object_type="PDE",
            symbol="EURUSD",
            timeframe="15M",
            root_id="r1",
            parent_id="p1",
            parent_version=1,
            state="PDE_NONE",
            previous_state="PDE_NONE",
            version=1,
            source_timestamp=100,
            event_timestamp=100,
            processing_timestamp=100,
            valid_until=50,  # Prior to last_seen 100
            last_seen=100,
        )


def test_effective_configuration_reproducible_identity() -> None:
    base = BaseConfig()
    sym = SymbolOverlay(symbol="EURUSD", max_spread_pips=Decimal("1.5"), overlay_version=1)
    news = NewsOverlay(news_lockdown_active=False, risk_multiplier=Decimal("0.5"), overlay_version=2)

    cfg1 = compute_effective_config(base, "EURUSD", sym, news)
    cfg2 = compute_effective_config(base, "EURUSD", sym, news)

    assert cfg1.effective_config_id == cfg2.effective_config_id
    assert cfg1.effective_config_id.startswith("cfg_")

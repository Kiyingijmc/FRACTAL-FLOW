"""Tests for MURG Instrument Discovery, Catalog, and Eligibility Engine."""

from src.fractal_flow.domain.murg import (
    AssetClass,
    SymbolTradeMode,
    InstrumentIdentity,
    InstrumentDescriptor,
    InstrumentCatalog,
    EligibilityEngine,
)
from src.fractal_flow.domain.reason_codes import ReasonCode


def make_descriptor(
    canonical_id: str,
    broker_symbol: str,
    trade_mode: SymbolTradeMode = SymbolTradeMode.FULL,
) -> InstrumentDescriptor:
    identity = InstrumentIdentity(
        canonical_id=canonical_id,
        asset_class=AssetClass.FX_MAJOR,
        base_asset="EUR",
        quote_asset="USD",
        broker="TEST_BROKER",
        broker_symbol=broker_symbol,
    )
    return InstrumentDescriptor(
        identity=identity,
        trade_mode=trade_mode,
        execution_mode="MARKET",
        supported_order_types=["MARKET_BUY", "BUY_LIMIT"],
        supported_fill_policies=["IOC"],
        supported_time_in_force=["GTC"],
        tick_size=0.00001,
        point_size=0.00001,
        pip_size=0.0001,
        tick_value=1.0,
        contract_size=100000.0,
        digits=5,
        min_volume=0.01,
        max_volume=100.0,
        volume_step=0.01,
        stops_level=5.0,
        freeze_level=2.0,
    )


def test_murg_instrument_catalog_and_alias_mapping() -> None:
    catalog = InstrumentCatalog()
    desc = make_descriptor("EURUSD", "EURUSD.a")
    catalog.register_instrument(desc)

    # Lookup by canonical_id
    res1 = catalog.get_descriptor("EURUSD")
    assert res1 is not None
    assert res1.identity.broker_symbol == "EURUSD.a"

    # Lookup by broker_symbol alias
    res2 = catalog.get_by_broker_symbol("EURUSD.a")
    assert res2 is not None
    assert res2.identity.canonical_id == "EURUSD"


def test_eligibility_engine_valid_instrument() -> None:
    desc = make_descriptor("EURUSD", "EURUSD")
    eligible, reasons = EligibilityEngine.evaluate_eligibility(desc)
    assert eligible is True
    assert ReasonCode.MARKET_ELIGIBLE in reasons


def test_eligibility_engine_disabled_symbol_fails_closed() -> None:
    desc = make_descriptor("EURUSD", "EURUSD", trade_mode=SymbolTradeMode.DISABLED)
    eligible, reasons = EligibilityEngine.evaluate_eligibility(desc)
    assert eligible is False
    assert ReasonCode.MARKET_INELIGIBLE in reasons

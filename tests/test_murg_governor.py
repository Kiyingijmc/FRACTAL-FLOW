"""Tests for Pass 4B ResourceGovernor, Account Context, Session Context, and Position Protection."""

from src.fractal_flow.domain.murg import (
    AccountResourceContext,
    AssetClass,
    InstrumentCatalog,
    InstrumentDescriptor,
    InstrumentIdentity,
    MarketSessionContext,
    ResourceGovernor,
    SymbolTradeMode,
    UserMarketUniverse,
)


def make_catalog() -> InstrumentCatalog:
    catalog = InstrumentCatalog()
    for symbol in ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]:
        identity = InstrumentIdentity(
            canonical_id=symbol,
            asset_class=AssetClass.FX_MAJOR
            if symbol != "BTCUSD"
            else AssetClass.CRYPTO,
            base_asset=symbol[:3],
            quote_asset=symbol[3:],
            broker="TEST_BROKER",
            broker_symbol=symbol,
        )
        desc = InstrumentDescriptor(
            identity=identity,
            trade_mode=SymbolTradeMode.FULL,
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
        catalog.register_instrument(desc)
    return catalog


def test_resource_governor_enforces_hard_active_cap() -> None:
    catalog = make_catalog()
    universe = UserMarketUniverse(
        pinned_canonical_ids={"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"}
    )
    account = AccountResourceContext(
        equity=10000.0,
        balance=10000.0,
        free_margin=8000.0,
        used_margin=2000.0,
        margin_utilization_pct=20.0,
        drawdown_pct=2.0,
        open_position_count=0,
        pending_order_count=0,
    )
    session = MarketSessionContext(
        session_state="OPEN",
        broker_server_time_ns=1000,
        time_to_close_ns=10000,
        is_tradable_session=True,
    )

    # Max active symbols cap set to 2
    governor = ResourceGovernor(max_active_symbols=2)
    decisions = governor.evaluate_universe_activation(
        catalog, universe, account, session, {}, {}
    )

    active_count = sum(1 for d in decisions.values() if d.activation_state == "ACTIVE")
    assert active_count == 2
    assert active_count <= governor.max_active_symbols


def test_dormant_market_preserves_position_and_pending_monitoring() -> None:
    catalog = make_catalog()
    universe = UserMarketUniverse()
    account = AccountResourceContext(
        equity=10000.0,
        balance=10000.0,
        free_margin=8000.0,
        used_margin=2000.0,
        margin_utilization_pct=20.0,
        drawdown_pct=2.0,
        open_position_count=1,
        pending_order_count=1,
    )
    session = MarketSessionContext(
        session_state="CLOSED",
        broker_server_time_ns=1000,
        time_to_close_ns=0,
        is_tradable_session=False,
    )

    governor = ResourceGovernor(max_active_symbols=2)
    has_pos = {"EURUSD": True}
    has_pend = {"EURUSD": True}

    decisions = governor.evaluate_universe_activation(
        catalog, universe, account, session, has_pos, has_pend
    )
    eur_dec = decisions["EURUSD"]

    # Entry analysis disabled during closed session, but position and pending-order monitoring REMAINS ACTIVE!
    assert eur_dec.activation_state == "DORMANT"
    assert eur_dec.entry_analysis_enabled is False
    assert eur_dec.position_monitoring_enabled is True
    assert eur_dec.pending_order_monitoring_enabled is True

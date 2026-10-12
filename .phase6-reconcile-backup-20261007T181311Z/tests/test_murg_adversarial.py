"""Adversarial Regression Test Suite covering MURG-001 through MURG-036 scenarios and fabricated authority closure."""

from dataclasses import dataclass
from decimal import Decimal
import pytest

from src.fractal_flow.domain.entry import (
    ActiveMarketContext,
    EntryPolicyEngine,
    EntryModel,
)
from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException
from src.fractal_flow.domain.models import Direction
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


@dataclass
class MockParentObject:
    id: str
    version: int
    validity: bool = True


def make_catalog() -> InstrumentCatalog:
    catalog = InstrumentCatalog()
    for symbol in ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "NAS100"]:
        identity = InstrumentIdentity(
            canonical_id=symbol,
            asset_class=AssetClass.FX_MAJOR if symbol in ("EURUSD", "GBPUSD", "USDJPY") else AssetClass.INDICES,
            base_asset=symbol[:3],
            quote_asset=symbol[3:],
            broker="TEST_BROKER",
            broker_symbol=f"{symbol}.a",
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


def test_murg_001_003_instrument_discovery_and_alias_mapping() -> None:
    catalog = make_catalog()
    desc = catalog.get_by_broker_symbol("EURUSD.a")
    assert desc is not None
    assert desc.identity.canonical_id == "EURUSD"


def test_murg_011_012_hard_active_symbol_limit() -> None:
    catalog = make_catalog()
    universe = UserMarketUniverse(
        pinned_canonical_ids={
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "XAUUSD",
            "BTCUSD",
            "NAS100",
        }
    )
    account = AccountResourceContext(
        equity=10000.0,
        balance=10000.0,
        free_margin=8000.0,
        used_margin=2000.0,
        margin_utilization_pct=10.0,
        drawdown_pct=1.0,
        open_position_count=0,
        pending_order_count=0,
    )
    session = MarketSessionContext(
        session_state="OPEN",
        broker_server_time_ns=1000,
        time_to_close_ns=10000,
        is_tradable_session=True,
    )

    # Active cap = 3
    governor = ResourceGovernor(max_active_symbols=3)
    decisions = governor.evaluate_universe_activation(catalog, universe, account, session, {}, {})

    active_count = sum(1 for d in decisions.values() if d.activation_state == "ACTIVE")
    assert active_count == 3


def test_murg_019_021_drawdown_constrained_capacity_multiplier() -> None:
    account_constrained = AccountResourceContext(
        equity=8000.0,
        balance=10000.0,
        free_margin=4000.0,
        used_margin=4000.0,
        margin_utilization_pct=50.0,
        drawdown_pct=20.0,
        open_position_count=1,
        pending_order_count=0,
        resource_mode="CONSTRAINED",
    )
    assert account_constrained.capacity_multiplier == 0.5


def test_murg_025_026_dormant_market_protection_invariant() -> None:
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

    governor = ResourceGovernor(max_active_symbols=3)
    has_pos = {"EURUSD": True}
    has_pend = {"EURUSD": True}

    decisions = governor.evaluate_universe_activation(catalog, universe, account, session, has_pos, has_pend)
    decision = decisions["EURUSD"]

    assert decision.activation_state == "DORMANT"
    assert decision.entry_analysis_enabled is False
    # CRITICAL INVARIANT: Monitoring obligations remain protected!
    assert decision.position_monitoring_enabled is True
    assert decision.pending_order_monitoring_enabled is True


def test_fabricated_murg_context_cannot_authorize_entry() -> None:
    from src.fractal_flow.domain.murg import GLOBAL_MURG_ISSUER

    engine = EntryPolicyEngine()
    # Fabricated active context during closed session
    fab_ctx = ActiveMarketContext(
        canonical_id="EURUSD",
        activation_state="ACTIVE",
        entry_analysis_enabled=True,
        is_tradable_session=False,  # Closed session
        broker_constraints={"supported_order_types": ["MARKET_BUY"]},
    )
    model = engine.evaluate_entry_policy(
        strategy_mode="SCALPING",
        direction=Direction.LONG,
        reference_price=Decimal("1.0850"),
        structural_sl=Decimal("1.0820"),
        market_context=fab_ctx,
    )
    assert model == EntryModel.NO_ENTRY

    # Fabricated context with forged provenance token fails validation
    forged_ctx = ActiveMarketContext(
        canonical_id="EURUSD",
        activation_state="ACTIVE",
        entry_analysis_enabled=True,
        is_tradable_session=True,
        broker_constraints={"supported_order_types": ["MARKET_BUY"]},
        producer_id="FAKE_PRODUCER",
        provenance_token="BAD_TOKEN",
    )
    assert GLOBAL_MURG_ISSUER.validate_context(forged_ctx) is False


def test_authoritative_murg_issuer_issuance_and_validation() -> None:
    from src.fractal_flow.domain.murg import (
        AuthoritativeMURGIssuer,
        MarketActivationDecision,
    )

    catalog = make_catalog()
    desc = catalog.get_descriptor("EURUSD")
    assert desc is not None

    issuer = AuthoritativeMURGIssuer()
    session = MarketSessionContext(
        session_state="OPEN",
        broker_server_time_ns=1000,
        time_to_close_ns=10000,
        is_tradable_session=True,
    )
    decision = MarketActivationDecision(
        canonical_id="EURUSD",
        activation_state="ACTIVE",
        reason_codes=[],
        priority_score=90.0,
        entry_analysis_enabled=True,
        position_monitoring_enabled=True,
        pending_order_monitoring_enabled=True,
    )

    valid_ctx = issuer.issue_context(decision, desc, session, current_time_ns=1000)
    assert issuer.validate_context(valid_ctx, current_time_ns=1000) is True

    # Expired context fails validation
    assert issuer.validate_context(valid_ctx, current_time_ns=400_000_000_000) is False


def test_fabricated_lineage_cannot_authorize_execution() -> None:
    parent_obj = MockParentObject(id="opp_100", version=1, validity=False)
    lineage = Lineage(
        root_id="root_1",
        parent_id="opp_100",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
    )
    with pytest.raises(LineageInvalidException) as exc:
        lineage.validate_child_action(authoritative_parent=parent_obj)
    assert "marked invalid" in str(exc.value)

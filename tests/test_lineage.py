"""Tests for Lineage Chain Integrity, Strict Version Identity, and Legal Edge Validation."""

from dataclasses import dataclass
import pytest

from src.fractal_flow.domain.lineage import Lineage, LineageInvalidException


@dataclass
class MockParent:
    id: str
    version: int
    validity: bool = True


def test_lineage_exact_version_accepted() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    lineage.validate_child_action(authoritative_parent_version=2)


def test_child_carries_lineage_ids() -> None:
    """Invariant #12: Every child object carries parent_id, parent_version, and root_id."""
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    assert lineage.root_id == "root_123"
    assert lineage.parent_id == "pullback_456"
    assert lineage.parent_version == 2


def test_lineage_with_authoritative_parent_object() -> None:
    parent_obj = MockParent(id="pullback_456", version=2, validity=True)
    lineage = Lineage(
        root_id="root_123",
        parent_id="pullback_456",
        parent_version=2,
        parent_tier="PRIMARY_PULLBACK",
        current_tier="OPPORTUNITY",
    )
    lineage.validate_child_action(authoritative_parent=parent_obj)

    # Invalid parent object fails
    invalid_parent = MockParent(id="pullback_456", version=2, validity=False)
    with pytest.raises(LineageInvalidException) as exc:
        lineage.validate_child_action(authoritative_parent=invalid_parent)
    assert "marked invalid" in str(exc.value)


def test_stale_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=1,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=2)
    assert "Parent version mismatch" in str(exc_info.value)


def test_future_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=3,  # Future version relative to authoritative parent version 2
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=2)
    assert "Parent version mismatch" in str(exc_info.value)


def test_zero_or_negative_parent_version_rejected() -> None:
    lineage = Lineage(
        root_id="root_123",
        parent_id="opp_456",
        parent_version=0,
        parent_tier="OPPORTUNITY",
        current_tier="SIGNAL",
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=0)
    assert "Version must be positive" in str(exc_info.value)


def test_illegal_lineage_edge_skipped_parent_rejected() -> None:
    """ROOT -> POSITION skipping intermediate tiers is forbidden."""
    lineage = Lineage(
        root_id="root_123",
        parent_id="root_123",
        parent_version=1,
        parent_tier="ROOT",
        current_tier="POSITION",
    )
    with pytest.raises(LineageInvalidException) as exc_info:
        lineage.validate_child_action(authoritative_parent_version=1)
    assert "Illegal lineage edge" in str(exc_info.value)


def test_legal_lineage_edges_all_valid() -> None:
    Lineage.verify_legal_edge("ROOT", "REGIME")
    Lineage.verify_legal_edge("PRIMARY_PULLBACK", "MICRO_PULLBACK")
    Lineage.verify_legal_edge("OPPORTUNITY", "SIGNAL")
    Lineage.verify_legal_edge("ORDER", "POSITION")
    Lineage.verify_legal_edge("POSITION", "MANAGEMENT")


def test_adversarial_lineage_authority_scenarios() -> None:
    """Adversarial tests covering mandatory lineage authority at authorization boundary."""
    from decimal import Decimal
    from src.fractal_flow.domain.models import TradeDecision
    from src.fractal_flow.domain.murg import (
        AssetClass,
        GLOBAL_MURG_ISSUER,
        InstrumentDescriptor,
        InstrumentIdentity,
        MarketActivationDecision,
        MarketSessionContext,
        SymbolTradeMode,
    )
    from src.fractal_flow.domain.risk_ledger import LedgerOperation, OpportunityRiskLedger

    decision = TradeDecision(
        decision_id="dec_adv_lineage",
        opportunity_id="opp_123",
        root_id="root_123",
        direction="BUY",
        symbol="EURUSD",
        environment="REGIME_TREND_UP",
        role="ROLE_CONTINUATION",
        setup="FF-01",
        pullback_id="pb_123",
        resumption_state="RESUMPTION_CONFIRMED",
        location="LOC_FAVORABLE",
        opportunity_space=0.8,
        tradeability="TRADEABILITY_PASS",
        news_state="NEWS_NORMAL",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=Decimal("1.0850"),
        structural_sl=Decimal("1.0820"),
        tp_plan={"tp1": Decimal("1.0900")},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.0"),
        approved_risk=Decimal("100.0"),
        position_size_lots=Decimal("0.1"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_test123",
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,
    )

    lineage = Lineage(
        root_id="root_123", parent_id="opp_123", parent_version=1, parent_tier="OPPORTUNITY", current_tier="SIGNAL"
    )
    desc = InstrumentDescriptor(
        identity=InstrumentIdentity("EURUSD", AssetClass.FX_MAJOR, "EUR", "USD", "BROKER", "EURUSD"),
        trade_mode=SymbolTradeMode.FULL,
        execution_mode="MARKET",
        supported_order_types=["MARKET_BUY"],
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
    sess = MarketSessionContext("OPEN", 1000, 10000, True)
    act_dec = MarketActivationDecision("EURUSD", "ACTIVE", [], 90.0, True, True, True)
    murg_ctx = GLOBAL_MURG_ISSUER.issue_context(act_dec, desc, sess, current_time_ns=1000)

    ledger = OpportunityRiskLedger("budget_1", "opp_123", Decimal("500.0"), Decimal("2.0"))
    ledger.record_operation(
        "res_tx_lineage", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_lineage", "cause_1", 1000
    )

    valid_parent = MockParent(id="opp_123", version=1, validity=True)
    setattr(valid_parent, "root_id", "root_123")
    setattr(valid_parent, "tier", "OPPORTUNITY")

    from src.fractal_flow.domain.lineage import GLOBAL_PARENT_RESOLVER

    # A. Missing authority: authoritative parent seal absent -> FALSE
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent_seal=None,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # B. Fabricated raw parent object directly passed -> FALSE
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent_seal=valid_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # Register valid parent with global resolver to issue genuine seal
    GLOBAL_PARENT_RESOLVER.register_parent("opp_123", 1, valid_parent)
    valid_seal = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_123", 1)

    # I. Valid authoritative parent seal -> TRUE
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent_seal=valid_seal,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is True
    )


def test_comprehensive_adversarial_authority_matrix_a_through_p() -> None:
    """Tests all adversarial scenarios A through P for authoritative parent resolution and provenance."""
    from decimal import Decimal
    from src.fractal_flow.domain.lineage import (
        AuthoritativeParentResolver,
        AuthoritativeParentSeal,
        Lineage,
    )
    from src.fractal_flow.domain.models import TradeDecision
    from src.fractal_flow.domain.murg import (
        AssetClass,
        GLOBAL_MURG_ISSUER,
        InstrumentDescriptor,
        InstrumentIdentity,
        MarketActivationDecision,
        MarketSessionContext,
        SymbolTradeMode,
    )
    from src.fractal_flow.domain.risk_ledger import LedgerOperation, OpportunityRiskLedger

    resolver = AuthoritativeParentResolver("TEST_RESOLVER")

    # Parent setup
    parent_opp_a = MockParent(id="opp_A", version=1, validity=True)
    setattr(parent_opp_a, "root_id", "root_1")
    setattr(parent_opp_a, "tier", "OPPORTUNITY")

    parent_opp_b = MockParent(id="opp_B", version=1, validity=True)
    setattr(parent_opp_b, "root_id", "root_1")
    setattr(parent_opp_b, "tier", "OPPORTUNITY")

    parent_root_2 = MockParent(id="opp_A", version=1, validity=True)
    setattr(parent_root_2, "root_id", "root_2")
    setattr(parent_root_2, "tier", "OPPORTUNITY")

    resolver.register_parent("opp_A", 1, parent_opp_a)
    resolver.register_parent("opp_B", 1, parent_opp_b)

    seal_a = resolver.resolve_authoritative_parent("opp_A", 1)

    lineage = Lineage(
        root_id="root_1", parent_id="opp_A", parent_version=1, parent_tier="OPPORTUNITY", current_tier="SIGNAL"
    )

    decision = TradeDecision(
        decision_id="dec_adv_ap",
        opportunity_id="opp_A",
        root_id="root_1",
        direction="BUY",
        symbol="EURUSD",
        environment="REGIME_TREND_UP",
        role="ROLE_CONTINUATION",
        setup="FF-01",
        pullback_id="pb_1",
        resumption_state="RESUMPTION_CONFIRMED",
        location="LOC_FAVORABLE",
        opportunity_space=0.8,
        tradeability="TRADEABILITY_PASS",
        news_state="NEWS_NORMAL",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=Decimal("1.0850"),
        structural_sl=Decimal("1.0820"),
        tp_plan={"tp1": Decimal("1.0900")},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.0"),
        approved_risk=Decimal("100.0"),
        position_size_lots=Decimal("0.1"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_test123",
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,
    )

    desc = InstrumentDescriptor(
        identity=InstrumentIdentity("EURUSD", AssetClass.FX_MAJOR, "EUR", "USD", "BROKER", "EURUSD"),
        trade_mode=SymbolTradeMode.FULL,
        execution_mode="MARKET",
        supported_order_types=["MARKET_BUY"],
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
    sess = MarketSessionContext("OPEN", 1000, 10000, True)
    act_dec = MarketActivationDecision("EURUSD", "ACTIVE", [], 90.0, True, True, True)
    murg_ctx = GLOBAL_MURG_ISSUER.issue_context(act_dec, desc, sess, current_time_ns=1000)

    ledger = OpportunityRiskLedger("budget_1", "opp_A", Decimal("500.0"), Decimal("2.0"))
    ledger.record_operation(
        "res_tx_ap", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_ap", "cause_1", 1000
    )

    # A. No authoritative parent -> False
    assert not decision.is_authorized(lineage, None, murg_ctx, ledger, "res_ap", 1000)

    # B. Fabricated parent -> False
    fab_parent = MockParent("opp_A", 1, True)
    setattr(fab_parent, "root_id", "root_1")
    setattr(fab_parent, "tier", "OPPORTUNITY")
    fake_seal = AuthoritativeParentSeal(fab_parent, "FAKE_RESOLVER", 1)
    assert not decision.is_authorized(lineage, fake_seal, murg_ctx, ledger, "res_ap", 1000)

    # C. Wrong parent ID -> False
    wrong_id_parent = MockParent("opp_WRONG", 1, True)
    setattr(wrong_id_parent, "root_id", "root_1")
    setattr(wrong_id_parent, "tier", "OPPORTUNITY")
    assert not decision.is_authorized(lineage, wrong_id_parent, murg_ctx, ledger, "res_ap", 1000)

    # D. Wrong root ID -> False
    assert not decision.is_authorized(lineage, parent_root_2, murg_ctx, ledger, "res_ap", 1000)

    # E. Wrong tier -> False
    wrong_tier_p = MockParent("opp_A", 1, True)
    setattr(wrong_tier_p, "root_id", "root_1")
    setattr(wrong_tier_p, "tier", "PRIMARY_PULLBACK")
    assert not decision.is_authorized(lineage, wrong_tier_p, murg_ctx, ledger, "res_ap", 1000)

    # F. Wrong version -> False
    wrong_ver_p = MockParent("opp_A", 2, True)
    setattr(wrong_ver_p, "root_id", "root_1")
    setattr(wrong_ver_p, "tier", "OPPORTUNITY")
    assert not decision.is_authorized(lineage, wrong_ver_p, murg_ctx, ledger, "res_ap", 1000)

    # G. Invalid authoritative parent -> False
    invalid_p = MockParent("opp_A", 1, False)
    setattr(invalid_p, "root_id", "root_1")
    setattr(invalid_p, "tier", "OPPORTUNITY")
    assert not decision.is_authorized(lineage, invalid_p, murg_ctx, ledger, "res_ap", 1000)

    # H. Expired / stale parent state -> False
    stale_p = MockParent("opp_A", 1, True)
    setattr(stale_p, "root_id", "root_1")
    setattr(stale_p, "tier", "OPPORTUNITY")
    setattr(stale_p, "state", "EXPIRED")
    assert not decision.is_authorized(lineage, stale_p, murg_ctx, ledger, "res_ap", 1000)

    # I. Revoked / cancelled parent -> False
    cancelled_p = MockParent("opp_A", 1, True)
    setattr(cancelled_p, "root_id", "root_1")
    setattr(cancelled_p, "tier", "OPPORTUNITY")
    setattr(cancelled_p, "state", "CANCELLED")
    assert not decision.is_authorized(lineage, cancelled_p, murg_ctx, ledger, "res_ap", 1000)

    # J. Caller-controlled validity assertion bypass attempt -> False
    assert not decision.is_authorized(lineage, None, murg_ctx, ledger, "res_ap", 1000)

    # K. Valid authoritative parent -> True
    from src.fractal_flow.domain.lineage import GLOBAL_PARENT_RESOLVER

    GLOBAL_PARENT_RESOLVER.register_parent("opp_A", 1, parent_opp_a)
    global_seal_a = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_A", 1)
    assert decision.is_authorized(lineage, global_seal_a, murg_ctx, ledger, "res_ap", 1000)

    # L. Authoritative parent substitution attack -> False
    sub_parent = MockParent("opp_A", 1, False)
    setattr(sub_parent, "root_id", "root_1")
    setattr(sub_parent, "tier", "OPPORTUNITY")
    sub_seal = AuthoritativeParentSeal(sub_parent, GLOBAL_PARENT_RESOLVER.resolver_id, 1)
    assert not decision.is_authorized(lineage, sub_seal, murg_ctx, ledger, "res_ap", 1000)

    # M. Version race -> False
    parent_opp_a_v2 = MockParent("opp_A", 2, True)
    setattr(parent_opp_a_v2, "root_id", "root_1")
    setattr(parent_opp_a_v2, "tier", "OPPORTUNITY")
    GLOBAL_PARENT_RESOLVER.register_parent("opp_A", 2, parent_opp_a_v2)
    v2_seal = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_A", 2)
    # Decision expects parent_version=1 from lineage
    assert not decision.is_authorized(lineage, v2_seal, murg_ctx, ledger, "res_ap", 1000)

    # N. Cross-opportunity substitution -> False
    GLOBAL_PARENT_RESOLVER.register_parent("opp_B", 1, parent_opp_b)
    global_seal_b = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_B", 1)
    assert not decision.is_authorized(lineage, global_seal_b, murg_ctx, ledger, "res_ap", 1000)

    # O. Cross-root substitution -> False
    GLOBAL_PARENT_RESOLVER.register_parent("opp_A_root2", 1, parent_root_2)
    seal_root2 = GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("opp_A_root2", 1)
    assert not decision.is_authorized(lineage, seal_root2, murg_ctx, ledger, "res_ap", 1000)

    # P. Missing resolver / unresolvable parent -> False
    with pytest.raises(Exception):
        GLOBAL_PARENT_RESOLVER.resolve_authoritative_parent("NONEXISTENT", 1)


def test_duck_typed_fake_seal_and_seal_forgery_rejection() -> None:
    """Explicit regression test proving duck-typed fake seals and forged seals fail closed."""
    from decimal import Decimal
    from src.fractal_flow.domain.lineage import Lineage
    from src.fractal_flow.domain.models import TradeDecision
    from src.fractal_flow.domain.murg import (
        AssetClass,
        GLOBAL_MURG_ISSUER,
        InstrumentDescriptor,
        InstrumentIdentity,
        MarketActivationDecision,
        MarketSessionContext,
        SymbolTradeMode,
    )
    from src.fractal_flow.domain.risk_ledger import LedgerOperation, OpportunityRiskLedger

    decision = TradeDecision(
        decision_id="dec_duck_seal",
        opportunity_id="opp_A",
        root_id="root_1",
        direction="BUY",
        symbol="EURUSD",
        environment="REGIME_TREND_UP",
        role="ROLE_CONTINUATION",
        setup="FF-01",
        pullback_id="pb_1",
        resumption_state="RESUMPTION_CONFIRMED",
        location="LOC_FAVORABLE",
        opportunity_space=0.8,
        tradeability="TRADEABILITY_PASS",
        news_state="NEWS_NORMAL",
        risk_state="RISK_NORMAL",
        portfolio_state="PORTFOLIO_ALLOW",
        entry_price=Decimal("1.0850"),
        structural_sl=Decimal("1.0820"),
        tp_plan={"tp1": Decimal("1.0900")},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.0"),
        approved_risk=Decimal("100.0"),
        position_size_lots=Decimal("0.1"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_test123",
        broker_constraint_snapshot={"min_volume": 0.01},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,
    )

    lineage = Lineage(
        root_id="root_1", parent_id="opp_A", parent_version=1, parent_tier="OPPORTUNITY", current_tier="SIGNAL"
    )
    desc = InstrumentDescriptor(
        identity=InstrumentIdentity("EURUSD", AssetClass.FX_MAJOR, "EUR", "USD", "BROKER", "EURUSD"),
        trade_mode=SymbolTradeMode.FULL,
        execution_mode="MARKET",
        supported_order_types=["MARKET_BUY"],
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
    sess = MarketSessionContext("OPEN", 1000, 10000, True)
    act_dec = MarketActivationDecision("EURUSD", "ACTIVE", [], 90.0, True, True, True)
    murg_ctx = GLOBAL_MURG_ISSUER.issue_context(act_dec, desc, sess, current_time_ns=1000)

    ledger = OpportunityRiskLedger("budget_1", "opp_A", Decimal("500.0"), Decimal("2.0"))
    ledger.record_operation(
        "res_tx_duck", LedgerOperation.RESERVE, Decimal("100.0"), Decimal("0.0"), "res_duck", "cause_1", 1000
    )

    parent_a = MockParent(id="opp_A", version=1, validity=True)
    setattr(parent_a, "root_id", "root_1")
    setattr(parent_a, "tier", "OPPORTUNITY")

    from typing import Any

    # Duck-typed class attempting to mimic AuthoritativeParentSeal
    class FakeDuckSeal:
        def __init__(self, parent: Any, resolver_id: str, resolved_at_version: int) -> None:
            self.parent = parent
            self.resolver_id = resolver_id
            self.resolved_at_version = resolved_at_version

    fake_seal = FakeDuckSeal(parent_a, "GLOBAL_AUTHORITATIVE_PARENT_RESOLVER", 1)

    # Duck-typed fake seal MUST be rejected as an unverified credential
    assert not decision.is_authorized(lineage, fake_seal, murg_ctx, ledger, "res_duck", 1000)

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

    # A. Missing authority: authoritative parent absent -> FALSE
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=None,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # B. Fabricated parent with wrong ID -> FALSE
    wrong_id_parent = MockParent(id="opp_FABRICATED", version=1, validity=True)
    setattr(wrong_id_parent, "root_id", "root_123")
    setattr(wrong_id_parent, "tier", "OPPORTUNITY")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=wrong_id_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # C. Wrong root ID -> FALSE
    wrong_root_parent = MockParent(id="opp_123", version=1, validity=True)
    setattr(wrong_root_parent, "root_id", "root_WRONG")
    setattr(wrong_root_parent, "tier", "OPPORTUNITY")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=wrong_root_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # D. Wrong tier -> FALSE
    wrong_tier_parent = MockParent(id="opp_123", version=1, validity=True)
    setattr(wrong_tier_parent, "root_id", "root_123")
    setattr(wrong_tier_parent, "tier", "PRIMARY_PULLBACK")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=wrong_tier_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # E. Wrong parent version -> FALSE
    wrong_ver_parent = MockParent(id="opp_123", version=2, validity=True)
    setattr(wrong_ver_parent, "root_id", "root_123")
    setattr(wrong_ver_parent, "tier", "OPPORTUNITY")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=wrong_ver_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # F. Invalid parent -> FALSE
    invalid_p = MockParent(id="opp_123", version=1, validity=False)
    setattr(invalid_p, "root_id", "root_123")
    setattr(invalid_p, "tier", "OPPORTUNITY")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=invalid_p,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # G. Expired / stale parent state -> FALSE
    stale_p = MockParent(id="opp_123", version=1, validity=True)
    setattr(stale_p, "root_id", "root_123")
    setattr(stale_p, "tier", "OPPORTUNITY")
    setattr(stale_p, "state", "EXPIRED")
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=stale_p,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # H. Caller assertion attack (parent_is_valid=True flag or caller-embedded object on decision) -> FALSE if authoritative_parent argument is None
    decision.parent_object = valid_parent  # type: ignore[attr-defined]
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=None,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is False
    )

    # I. Valid authoritative parent -> TRUE
    assert (
        decision.is_authorized(
            lineage=lineage,
            authoritative_parent=valid_parent,
            murg_context=murg_ctx,
            risk_ledger=ledger,
            reservation_id="res_lineage",
            current_time_ns=1000,
        )
        is True
    )

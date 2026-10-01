"""Tests for Persistence Adapter lossless Decimal round-trips and fingerprint stability."""

from dataclasses import dataclass
from decimal import Decimal

from src.fractal_flow.domain.models import Direction, TradeDecision
from src.fractal_flow.persistence.adapter import (
    canonical_json_dumps,
    compute_canonical_fingerprint,
    domain_to_primitive,
    primitive_to_decimal,
)


@dataclass(frozen=True)
class DecimalContainer:
    name: str
    price: Decimal
    volume: Decimal
    pnl: Decimal
    nested: dict[str, Decimal]


def test_decimal_adapter_lossless_round_trip() -> None:
    container = DecimalContainer(
        name="TestContainer",
        price=Decimal("1.08500"),
        volume=Decimal("0.01"),
        pnl=Decimal("-150.25"),
        nested={"high": Decimal("1.09000"), "low": Decimal("1.08000")},
    )

    primitives = domain_to_primitive(container)
    assert primitives == {
        "name": "TestContainer",
        "price": "1.08500",
        "volume": "0.01",
        "pnl": "-150.25",
        "nested": {"high": "1.09000", "low": "1.08000"},
    }

    reconstructed = primitive_to_decimal(primitives)
    assert reconstructed["price"] == Decimal("1.08500")
    assert reconstructed["pnl"] == Decimal("-150.25")
    assert reconstructed["nested"]["high"] == Decimal("1.09000")


def test_trade_decision_canonical_serialization_and_fingerprint() -> None:
    decision1 = TradeDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        direction=Direction.LONG,
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
        entry_price=Decimal("1.08500"),
        structural_sl=Decimal("1.08200"),
        tp_plan={"tp1": Decimal("1.09000")},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.00"),
        approved_risk=Decimal("100.00"),
        position_size_lots=Decimal("0.10"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_123",
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,
    )

    decision2 = TradeDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        root_id="root_1",
        direction=Direction.LONG,
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
        entry_price=Decimal("1.08500"),
        structural_sl=Decimal("1.08200"),
        tp_plan={"tp1": Decimal("1.09000")},
        ttl_ns=300000000000,
        requested_risk=Decimal("100.00"),
        approved_risk=Decimal("100.00"),
        position_size_lots=Decimal("0.10"),
        arbitration_result="ALLOW",
        effective_config_id="cfg_123",
        broker_constraint_snapshot={},
        quote_timestamp=1000,
        spread_pips=Decimal("1.0"),
        authorized=True,
    )

    json1 = canonical_json_dumps(decision1)
    json2 = canonical_json_dumps(decision2)
    assert json1 == json2

    fp1 = compute_canonical_fingerprint(decision1)
    fp2 = compute_canonical_fingerprint(decision2)
    assert fp1 == fp2

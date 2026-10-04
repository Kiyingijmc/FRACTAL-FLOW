"""Phase 1F Tests: Structure Capability & Authority Boundaries."""

from decimal import Decimal

from src.fractal_flow.domain.structure import StructureEngine

BASE_TS = 1700006400


def test_structure_engine_emits_stop_candidates_without_trade_authorization() -> None:
    engine = StructureEngine("EURUSD", timeframe="1M")
    engine.protected_low = Decimal("1.0800")
    engine.protected_high = Decimal("1.0900")

    # Request structural stop candidate
    stop_long = engine.get_structural_stop_candidate("LONG", atr_14=Decimal("0.0010"))
    assert stop_long is not None
    assert stop_long.direction == "LONG"
    assert stop_long.protected_level_price == Decimal("1.0800")
    assert stop_long.recommended_stop_price == Decimal("1.0795")

    stop_short = engine.get_structural_stop_candidate("SHORT", atr_14=Decimal("0.0010"))
    assert stop_short is not None
    assert stop_short.direction == "SHORT"
    assert stop_short.protected_level_price == Decimal("1.0900")
    assert stop_short.recommended_stop_price == Decimal("1.0905")

    # Assert Structure Engine and candidates cannot authorize trades, size positions, or place orders
    forbidden_methods_attrs = ["authorize_trade", "create_execution_intent", "submit_order", "size_position"]
    for item in forbidden_methods_attrs:
        assert not hasattr(engine, item)
        assert not hasattr(stop_long, item)

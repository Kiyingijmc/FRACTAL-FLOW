"""Phase 1H Tests: Guard Against Forbidden Strategy Paths During Phase 1."""

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.domain.volatility import VolatilityEngine


def test_phase_1_engines_contain_no_execution_or_live_mt5_paths() -> None:
    dq = DataQualityEngine("EURUSD")
    vol = VolatilityEngine("EURUSD")
    struct = StructureEngine("EURUSD")

    forbidden_methods = [
        "OrderSend",
        "submit_mt5_order",
        "execute_live_trade",
        "open_position",
        "size_position",
    ]

    for engine in (dq, vol, struct):
        for method in forbidden_methods:
            assert not hasattr(engine, method)

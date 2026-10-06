"""Phase 1F Tests: Structure Confirmation Causality and No-Lookahead."""

from decimal import Decimal
from typing import Any

from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.structure import StructureEngine
from src.fractal_flow.simulation.causal_framework import CausalTestFramework

BASE_TS = 1700006400


def test_structure_confirmation_causality() -> None:
    bars = [
        Bar.create("EURUSD", "1M", BASE_TS + i * 60, BASE_TS + (i + 1) * 60, "1.0850", "1.0860", "1.0840", "1.0855")
        for i in range(10)
    ]

    decision_time = bars[5].close_timestamp

    def structure_processor(ticks: list[Tick], dec_time: int) -> dict[str, Any]:
        engine = StructureEngine("EURUSD", timeframe="1M")
        v_loc = Decimal("0.0010")
        last_rec = None
        for b in bars:
            if b.close_timestamp <= dec_time:
                last_rec = engine.process_bar(b, v_loc, root_id="r1", parent_id="p1", parent_version=1)
        assert last_rec is not None
        return {
            "swing_state": last_rec.swing_state.value,
            "break_state": last_rec.break_state.value,
            "damage_state": last_rec.damage_state.value,
            "version": last_rec.state_version,
            "processing_timestamp": last_rec.timestamp + 10,
        }

    prefix_ticks = [
        Tick.create("EURUSD", b.close_timestamp, str(b.close), str(b.close + Decimal("0.0001"))) for b in bars[:6]
    ]
    future_a = [Tick.create("EURUSD", BASE_TS + 7 * 60, "1.0850", "1.0851")]
    future_b = [Tick.create("EURUSD", BASE_TS + 7 * 60, "1.1500", "1.1501")]

    res = CausalTestFramework.verify_causality(prefix_ticks, future_a, future_b, decision_time, structure_processor)
    assert res.is_causal is True

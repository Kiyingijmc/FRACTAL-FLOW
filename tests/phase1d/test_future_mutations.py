"""Phase 1D Tests: Production Pipeline Causal Test Suite.

Executes all 12 required future mutation scenarios against actual production Phase 1 engines
(DataQualityEngine, VolatilityEngine, StructureEngine, BarAggregator)
and asserts that computed state at decision time 't' is 100% byte-identical regardless of future mutations.
"""

from typing import Any

from src.fractal_flow.domain.data_quality import DataQualityEngine
from src.fractal_flow.domain.market import Bar, BarAggregator, Tick, Timeframe
from src.fractal_flow.domain.structure import StructureEngine
from decimal import Decimal

from src.fractal_flow.domain.volatility import VolatilityEngine
from src.fractal_flow.simulation.causal_framework import CausalTestFramework

BASE_TS = 1700006400


def production_pipeline_processor(ticks: list[Tick], decision_time: int) -> dict[str, Any]:
    """Runs ticks through production BarAggregator, DataQualityEngine, VolatilityEngine, and StructureEngine.

    Evaluates and records state at decision_time 't'.
    """
    dq_engine = DataQualityEngine("EURUSD")
    vol_engine = VolatilityEngine("EURUSD", timeframe="1M")
    struct_engine = StructureEngine("EURUSD", timeframe="1M")
    bar_aggregator = BarAggregator("EURUSD", Timeframe.M1)

    dq_state_at_t = "DATA_BOOT"
    vol_state_at_t = "VOL_UNKNOWN"
    struct_state_at_t = "SWING_NONE"
    break_state_at_t = "BREAK_NONE"
    damage_state_at_t = "INTACT"
    atr_at_t = "0.0"
    v_local_at_t = "0.0001"
    state_version_at_t = 0

    # Sort ticks by timestamp and sequence
    sorted_ticks = sorted(ticks, key=lambda t: (t.timestamp, t.sequence))

    for t in sorted_ticks:
        # Evaluate DQ on tick
        dq_assessment = dq_engine.evaluate_tick(t, current_processing_time=t.timestamp)

        # Aggregate tick into M1 bar
        maybe_bar = bar_aggregator.process_tick(t)
        if maybe_bar is not None:
            vol_metrics = vol_engine.update_bar(maybe_bar)
            v_loc = struct_engine.calculate_v_local(maybe_bar, atr_14=vol_metrics.atr_14)
            struct_record = struct_engine.process_bar(
                maybe_bar,
                v_local=v_loc,
                root_id="r1",
                parent_id="p1",
                parent_version=1,
            )

        if t.timestamp <= decision_time:
            dq_state_at_t = dq_engine.current_state.value
            vol_state_at_t = vol_engine.current_state.value
            struct_state_at_t = struct_engine.swing_state.value
            break_state_at_t = struct_engine.break_state.value
            damage_state_at_t = struct_engine.damage_state.value
            state_version_at_t = struct_engine.state_version
            if vol_engine._atr is not None:
                atr_at_t = str(vol_engine._atr)
            v_local_at_t = str(
                struct_engine.calculate_v_local(
                    Bar.create("EURUSD", "1M", t.timestamp, t.timestamp + 60, t.bid, t.bid, t.bid, t.bid),
                    atr_14=vol_engine._atr,
                )
            )

    return {
        "dq_state": dq_state_at_t,
        "vol_state": vol_state_at_t,
        "struct_state": struct_state_at_t,
        "break_state": break_state_at_t,
        "damage_state": damage_state_at_t,
        "atr_14": atr_at_t,
        "v_local": v_local_at_t,
        "state_version": state_version_at_t,
        "processing_timestamp": decision_time + 10,  # Processing metadata
    }


def make_prefix_ticks(count_bars: int = 5) -> tuple[list[Tick], int]:
    """Generates ticks spanning count_bars completed M1 bar boundaries up to decision_time."""
    prefix = []
    seq = 0
    for i in range(count_bars):
        for j in range(6):
            ts = BASE_TS + i * 60 + j * 10
            bid = str(Decimal("1.0850") + Decimal(str(i * 0.0005)))
            ask = str(Decimal(bid) + Decimal("0.0001"))
            prefix.append(Tick.create("EURUSD", ts, bid, ask, sequence=seq))
            seq += 1

    # Add boundary-closing tick exactly at BASE_TS + count_bars * 60 (completes bar count_bars)
    prefix.append(Tick.create("EURUSD", BASE_TS + count_bars * 60, "1.0875", "1.0876", sequence=seq))
    decision_time = BASE_TS + count_bars * 60
    return prefix, decision_time


def test_1_future_price_spike() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "1.1500", "1.1501", sequence=seq)]  # Price Spike

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True
    assert res.latest_permissible_input_timestamp <= decision_time


def test_2_future_crash() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "0.9000", "0.9001", sequence=seq)]  # Price Crash

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_3_future_spread_explosion() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [
        Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0975", spread="0.0100", sequence=seq)
    ]  # Spread explosion

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_4_future_volatility_explosion() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [
        Tick.create("EURUSD", decision_time + 10 + i * 2, "1.0875", "1.0876", sequence=seq + i) for i in range(5)
    ]
    future_b = [
        Tick.create(
            "EURUSD",
            decision_time + 10 + i * 2,
            str(1.0875 + (i % 2) * 0.0200),
            str(1.0876 + (i % 2) * 0.0200),
            sequence=seq + i,
        )
        for i in range(5)
    ]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_5_future_structural_break() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "1.1000", "1.1001", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_6_future_news_event() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "1.0950", "1.0955", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_7_future_session_close() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 300000, "1.0875", "1.0876", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_8_future_bar_replacement() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 60, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 60, "1.0885", "1.0886", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_9_future_duplicate_data() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [
        Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq),
        Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq),
    ]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_10_future_missing_data() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 500, "1.0875", "1.0876", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_11_future_normalization_regime_change() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "1.2500", "1.2501", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True


def test_12_future_extreme_value() -> None:
    prefix, decision_time = make_prefix_ticks(5)
    seq = len(prefix)

    future_a = [Tick.create("EURUSD", decision_time + 10, "1.0875", "1.0876", sequence=seq)]
    future_b = [Tick.create("EURUSD", decision_time + 10, "9.9999", "9.9999", sequence=seq)]

    res = CausalTestFramework.verify_causality(prefix, future_a, future_b, decision_time, production_pipeline_processor)
    assert res.is_causal is True

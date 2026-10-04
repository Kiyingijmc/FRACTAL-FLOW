"""Phase 1B Tests: Non-negotiable Exposure Guard Rule DATA != VALID -> NEW EXPOSURE FORBIDDEN."""

from src.fractal_flow.domain.data_quality import DataQualityEngine, DataQualityState
from src.fractal_flow.domain.market import Tick
from src.fractal_flow.domain.reason_codes import ReasonCode

BASE_TS = 1700006400


def test_exposure_allowed_strictly_when_data_is_valid_or_normal() -> None:
    valid_states = [DataQualityState.DATA_NORMAL, DataQualityState.DATA_VALID]
    for st in valid_states:
        assert st.is_valid_for_exposure() is True

    invalid_states = [
        DataQualityState.DATA_BOOT,
        DataQualityState.DATA_VALIDATING,
        DataQualityState.DATA_DEGRADED,
        DataQualityState.DATA_STALE,
        DataQualityState.DATA_CORRUPTED,
        DataQualityState.DATA_UNAVAILABLE,
    ]
    for st in invalid_states:
        assert st.is_valid_for_exposure() is False


def test_degraded_stale_and_corrupted_data_blocks_exposure() -> None:
    engine = DataQualityEngine("EURUSD", max_staleness_seconds=30)

    t_normal = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851")
    a_normal = engine.evaluate_tick(t_normal, current_processing_time=BASE_TS)
    assert a_normal.state == DataQualityState.DATA_NORMAL
    assert a_normal.exposure_allowed is True

    a_dup = engine.evaluate_tick(t_normal, current_processing_time=BASE_TS)
    assert a_dup.state == DataQualityState.DATA_DEGRADED
    assert a_dup.exposure_allowed is False
    assert ReasonCode.EXPOSURE_FORBIDDEN_DATA_INVALID in a_dup.reason_codes

    t_corrupt = Tick.create("EURUSD", BASE_TS + 1, "1.0850", "1.0850")
    a_corrupt = engine.evaluate_tick(t_corrupt, current_processing_time=BASE_TS + 1)
    assert a_corrupt.state == DataQualityState.DATA_CORRUPTED
    assert a_corrupt.exposure_allowed is False
    assert ReasonCode.EXPOSURE_FORBIDDEN_DATA_INVALID in a_corrupt.reason_codes

    t_stale = Tick.create("EURUSD", BASE_TS + 2, "1.0850", "1.0851")
    a_stale = engine.evaluate_tick(t_stale, current_processing_time=BASE_TS + 100)
    assert a_stale.state == DataQualityState.DATA_STALE
    assert a_stale.exposure_allowed is False
    assert ReasonCode.EXPOSURE_FORBIDDEN_DATA_INVALID in a_stale.reason_codes


def test_data_quality_engine_emits_no_strategy_direction_or_execution_intent() -> None:
    engine = DataQualityEngine("EURUSD")
    t1 = Tick.create("EURUSD", BASE_TS, "1.0850", "1.0851")
    assessment = engine.evaluate_tick(t1, current_processing_time=BASE_TS)

    forbidden_attrs = ["direction", "order_type", "position_size", "buy_signal", "sell_signal", "entry_price"]
    for attr in forbidden_attrs:
        assert not hasattr(assessment, attr)

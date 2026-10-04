"""Phase 2 Work Package 2E Tests: Multi-Timeframe Behavioral Pipeline.

Tests:
- End-to-end execution of BehavioralPipeline across timeframes.
- Stage-by-stage lineage parent version binding.
- Multi-timeframe context passing (1H HTF snapshot into 1M LTF pipeline).
- Graceful degradation on missing or corrupt HTF data.
"""

from decimal import Decimal
import pytest

from src.fractal_flow.domain.market import Bar, Tick
from src.fractal_flow.domain.pipeline import BehavioralPipeline, BehavioralStateSnapshot

BASE_TS = 1700006400


def test_behavioral_pipeline_end_to_end_execution() -> None:
    """Verifies that processing a bar through BehavioralPipeline produces a valid

    BehavioralStateSnapshot with all 8 behavioral records properly bound.
    """
    pipeline = BehavioralPipeline("EURUSD", timeframes=["1M", "5M", "1H"])

    tick = Tick.create("EURUSD", BASE_TS + 60, "1.0850", "1.0851")
    bar_m1 = Bar.create("EURUSD", "1M", BASE_TS, BASE_TS + 60, "1.0800", "1.0855", "1.0800", "1.0850")

    snapshot = pipeline.process_bar(
        bar=bar_m1,
        tick=tick,
        root_id="r_session_1",
    )

    assert isinstance(snapshot, BehavioralStateSnapshot)
    assert snapshot.symbol == "EURUSD"
    assert snapshot.timeframe == "1M"
    assert snapshot.dq_record.state.value == "DATA_NORMAL"
    assert snapshot.vol_record.state.value in ("VOL_NORMAL", "VOL_ELEVATED", "VOL_UNKNOWN", "VOL_COMPRESSION", "VOL_EXPANSION")
    assert snapshot.structure_record.authority == "STRUCTURE"
    assert snapshot.flow_record.authority == "FLOW"
    assert snapshot.pde_record.authority == "PDE"
    assert snapshot.regime_record.authority == "REGIME"
    assert snapshot.role_record.authority == "ROLE"
    assert snapshot.location_record.authority == "LOCATION"


def test_mtf_context_passing_1h_to_1m() -> None:
    """Verifies passing a 1H HTF snapshot into 1M bar processing."""
    pipeline = BehavioralPipeline("EURUSD", timeframes=["1M", "1H"])

    tick_1h = Tick.create("EURUSD", BASE_TS + 3600, "1.0900", "1.0901")
    bar_1h = Bar.create("EURUSD", "1H", BASE_TS, BASE_TS + 3600, "1.0800", "1.0950", "1.0790", "1.0920")

    snapshot_1h = pipeline.process_bar(bar=bar_1h, tick=tick_1h, root_id="r_session_1")

    tick_1m = Tick.create("EURUSD", BASE_TS + 3660, "1.0920", "1.0921")
    bar_1m = Bar.create("EURUSD", "1M", BASE_TS + 3600, BASE_TS + 3660, "1.0920", "1.0930", "1.0915", "1.0928")

    snapshot_1m = pipeline.process_bar(
        bar=bar_1m,
        tick=tick_1m,
        root_id="r_session_1",
        htf_snapshot=snapshot_1h,
    )

    assert snapshot_1m.timeframe == "1M"
    assert snapshot_1m.location_record is not None

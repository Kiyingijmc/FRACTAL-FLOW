from __future__ import annotations

from pathlib import Path
from decimal import Decimal

from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.persistence.phase2 import Phase2DurableStore


def _instrument() -> InstrumentSpec:
    return InstrumentSpec(
        symbol="EURUSD", tick_size=Decimal("0.00001"), price_precision=5,
        volume_step=Decimal("0.01"), contract_size=Decimal("100000"), timezone="UTC", asset_class="FX",
    )


def _bar(ts: int, seq: int, close: str) -> Bar:
    return Bar(
        symbol="EURUSD", timeframe="1M", open_timestamp=ts - 60, close_timestamp=ts,
        open=Decimal(close), high=Decimal(close) + Decimal("0.0001"), low=Decimal(close) - Decimal("0.0001"),
        close=Decimal(close), spread=Decimal("0.00001"), sequence=seq, is_closed=True,
    )


def _store(tmp_path: Path) -> Phase2DurableStore:
    pipeline = Phase2Pipeline("EURUSD", "1M", instrument=_instrument(), history_capacity=8)
    return Phase2DurableStore(str(tmp_path), pipeline)


def test_r9_recovery_does_not_call_pipeline_snapshot_restore(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path)
    store.process_bar(_bar(60, 0, "1.10000"))
    original = Phase2Pipeline.from_snapshot_state

    def forbidden(*args, **kwargs):
        raise AssertionError("journal recovery must not restore through pipeline snapshots")

    monkeypatch.setattr(Phase2Pipeline, "from_snapshot_state", forbidden)
    recovered = store.recover()
    assert recovered._last_watermark == (60, 0)
    monkeypatch.setattr(Phase2Pipeline, "from_snapshot_state", original)


def test_r9_corrupt_checkpoint_does_not_block_journal_recovery(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.process_bar(_bar(60, 0, "1.10000"))
    snapshot = store.snapshots.load_snapshot("Phase2Pipeline", store.pipeline_id)
    assert snapshot is not None
    snapshot.state_payload["last_watermark"] = [999999, 999]
    store.snapshots._snapshots[("Phase2Pipeline", store.pipeline_id)] = snapshot
    recovered = store.recover()
    assert recovered._last_watermark == (60, 0)
    assert store.lifecycle_state.value == "ACTIVE"


def test_r9_source_guard_keeps_phase2_durable_recovery_journal_based() -> None:
    source = Path("src/fractal_flow/persistence/phase2.py").read_text(encoding="utf-8")
    recover_body = source.split("    def recover(self) -> Phase2Pipeline:", 1)[1]
    assert "replay_evaluations" not in recover_body
    assert "Phase2Pipeline.from_snapshot_state" not in recover_body
    assert "get_events_for_aggregate" in recover_body

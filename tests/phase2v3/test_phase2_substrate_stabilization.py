from decimal import Decimal
import random
import pytest

from src.fractal_flow.domain.context import InstrumentSpec
from src.fractal_flow.domain.market import Bar
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.pde import PDEState, PDEResumptionState, PDEEngine
from src.fractal_flow.persistence.phase2 import Phase2DurableStore, Phase2RecoveryError, Phase2StoreState


def bar(ts: int, seq: int, close: Decimal) -> Bar:
    return Bar.create(
        "EURUSD", "1M", ts, ts + 60,
        close - Decimal("0.0004"), close + Decimal("0.0006"),
        close - Decimal("0.0007"), close,
        sequence=seq, data_version=1, is_closed=True,
    )


def pipeline() -> Phase2Pipeline:
    return Phase2Pipeline("EURUSD", "1M", InstrumentSpec("EURUSD", Decimal("0.00001"), 5), history_capacity=16)


def test_phase2_bar_failure_rolls_back_every_mutable_engine(monkeypatch):
    p = pipeline()
    for i in range(1, 8):
        p.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0001")))
    before = p.snapshot_state()
    original = p.role.evaluate

    def fail(*args, **kwargs):
        raise RuntimeError("injected role failure")

    monkeypatch.setattr(p.role, "evaluate", fail)
    with pytest.raises(RuntimeError, match="injected role failure"):
        p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))
    monkeypatch.setattr(p.role, "evaluate", original)
    p.role.__dict__.pop("evaluate", None)
    assert p.snapshot_state() == before

    result = p.process_bar(bar(8 * 60, 8, Decimal("1.1008")))
    assert result.context.watermark.sequence == 8


def test_phase2_random_market_sequences_do_not_hit_illegal_state_transitions():
    rng = random.Random(423234)
    for _ in range(10):
        p = pipeline()
        price = Decimal("1.1000")
        for seq in range(1, 101):
            step = Decimal(rng.choice(["-0.0008", "-0.0004", "0", "0.0004", "0.0008"]))
            price += step
            if price <= Decimal("1.0000"):
                price = Decimal("1.0000")
            p.process_bar(bar(seq * 60, seq, price))
        assert p._last_watermark == (100 * 60 + 60, 100)


def test_pde_origin_break_invalidates_instead_of_crashing():
    pde = PDEEngine("EURUSD")
    pde._last_close = Decimal("1.1000")
    first = pde.process_bar(bar(60, 1, Decimal("1.1020")), Decimal("0.001"))
    assert first.state == PDEState.PDE_IMPULSE
    out = pde.process_bar(bar(120, 2, Decimal("1.0990")), Decimal("0.001"))
    assert out.state == PDEState.PDE_INVALIDATED
    assert "IMPULSE_ORIGIN_BROKEN" in out.reason_codes


def test_pde_resumption_requires_actual_recovery_movement():
    pde = PDEEngine("EURUSD")
    pde.state = PDEState.PDE_WEAKENING
    pde.direction = "LONG"
    pde._anchor = Decimal("1.1000")
    pde._extreme = Decimal("1.1050")
    pde._pullback_extreme = Decimal("1.1020")
    pde._last_depth = Decimal("0.60")
    pde._bars = 2
    pde._resume_transition(PDEResumptionState.RECOVERY_CANDIDATE)
    flat = pde.process_bar(bar(60, 1, Decimal("1.1020")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    assert flat.state != PDEState.PDE_RESUMPTION_IN_PROGRESS
    recovered = pde.process_bar(bar(120, 2, Decimal("1.1045")), Decimal("0.001"), Decimal("0"), "LONG", "TREND_UP")
    assert recovered.recovery_ratio >= Decimal("0.75")
    assert recovered.state == PDEState.PDE_RESUMPTION_IN_PROGRESS


def test_durable_store_faults_after_journal_then_pipeline_failure_and_recovers(monkeypatch, tmp_path):
    p = pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    original = p.process_bar

    def fail(_bar):
        raise RuntimeError("injected post-journal failure")

    monkeypatch.setattr(p, "process_bar", fail)
    with pytest.raises(RuntimeError):
        store.process_bar(bar(60, 1, Decimal("1.1000")))
    assert store.lifecycle_state == Phase2StoreState.FAULTED
    assert len(store.journal.get_events_for_aggregate("Phase2Pipeline", store.pipeline_id)) == 1
    with pytest.raises(Phase2RecoveryError, match="writes are prohibited"):
        store.process_bar(bar(120, 2, Decimal("1.1002")))

    monkeypatch.setattr(p, "process_bar", original)
    recovered = store.recover()
    assert store.lifecycle_state == Phase2StoreState.ACTIVE
    assert store.pipeline is recovered
    result = store.process_bar(bar(120, 2, Decimal("1.1002")))
    assert result.context.watermark.sequence == 2


def test_recover_installs_recovered_aggregate_for_continuation(tmp_path):
    p = pipeline()
    store = Phase2DurableStore(str(tmp_path), p)
    for i in range(1, 5):
        store.process_bar(bar(i * 60, i, Decimal("1.1000") + Decimal(i) * Decimal("0.0002")))
    recovered = store.recover()
    assert store.pipeline is recovered
    result = store.process_bar(bar(5 * 60, 5, Decimal("1.1010")))
    assert result.context.watermark.sequence == 5
    assert store.pipeline._last_watermark == (360, 5)


def test_informational_engine_registry_forbids_order_submission():
    import yaml

    with open("spec/engines.yaml") as f:
        engines = yaml.safe_load(f)["engines"]
    informational = ["DataQuality", "Volatility", "Structure", "PDE", "Flow", "Regime", "Role", "Location"]
    for name in informational:
        entry = engines[name]
        assert "SUBMIT_ORDER" not in entry.get("allowed_capabilities", [])
        assert "SUBMIT_ORDER" in entry.get("forbidden_capabilities", [])

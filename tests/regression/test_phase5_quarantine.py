from decimal import Decimal

from src.fractal_flow.domain.market import Bar, Timeframe
from src.fractal_flow.domain.phase2 import Phase2Pipeline
from src.fractal_flow.domain.context import InstrumentSpec


def make_bar(sequence: int, timestamp: int, close: str = "1.1000") -> Bar:
    price = Decimal(close)
    return Bar(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=timestamp - 60,
        close_timestamp=timestamp,
        open=price,
        high=price + Decimal("0.0005"),
        low=price - Decimal("0.0005"),
        close=price,
        spread=Decimal("0.0001"),
        sequence=sequence,
        is_closed=True,
    )


def make_pipeline() -> Phase2Pipeline:
    return Phase2Pipeline(
        "EURUSD",
        "1M",
        InstrumentSpec("EURUSD", Decimal("0.00001"), 5),
    )


def test_failed_bar_is_quarantined_without_publishing_engine_state() -> None:
    pipeline = make_pipeline()
    first = make_bar(1, 60)
    pipeline.process_bar(first)
    before = pipeline.state_hash()

    failing = make_bar(2, 120, "1.1001")
    with pipeline.inject_fault_after("structure"):
        try:
            pipeline.process_bar(failing)
        except RuntimeError:
            pass
        else:
            raise AssertionError("fault injection must fail")

    assert pipeline.state_hash() == before
    records = pipeline.quarantined_bars()
    assert len(records) == 1
    assert records[0].timestamp == 120
    assert records[0].sequence == 2
    assert records[0].stage == "structure"


def test_safe_processing_allows_next_bar_after_quarantine() -> None:
    pipeline = make_pipeline()
    pipeline.process_bar(make_bar(1, 60))

    with pipeline.inject_fault_after("structure"):
        assert pipeline.process_bar_safe(make_bar(2, 120, "1.1001")) is None

    result = pipeline.process_bar_safe(make_bar(3, 180, "1.1002"))
    assert result is not None
    assert result.bar.sequence == 3
    assert pipeline.quarantined_bars()[0].sequence == 2


def test_quarantine_does_not_change_committed_watermark() -> None:
    pipeline = make_pipeline()
    pipeline.process_bar(make_bar(1, 60))
    before = pipeline._last_watermark

    with pipeline.inject_fault_after("pde"):
        assert pipeline.process_bar_safe(make_bar(2, 120, "1.1001")) is None

    assert pipeline._last_watermark == before


def test_v23_live_swings_strictly_alternate_and_superseded_history_is_retained() -> None:
    import random
    from src.fractal_flow.domain.structure_v23 import StructureEngineV23

    def random_bar(rng: random.Random, index: int, price: Decimal) -> tuple[Bar, Decimal]:
        step = Decimal(str(round(rng.gauss(0, 0.0005), 7)))
        close = max(Decimal("0.5"), price + step)
        high = max(price, close) + Decimal(str(round(abs(rng.gauss(0, 0.0002)), 7)))
        low = min(price, close) - Decimal(str(round(abs(rng.gauss(0, 0.0002)), 7)))
        return Bar.create("EURUSD", "1M", index * 60, (index + 1) * 60, price, high, low, close, sequence=index + 1), close

    rng = random.Random(0)
    price = Decimal("1.1000")
    engine = StructureEngineV23("EURUSD")
    for index in range(300):
        bar, price = random_bar(rng, index, price)
        engine.process_bar(bar, Decimal("0.001"), "root", "market", index + 1)

    live = [s for s in engine.swings if s.status.value not in {"SWING_BROKEN", "SWING_SUPERSEDED"}]
    assert all(a.swing_type != b.swing_type for a, b in zip(live, live[1:]))
    assert any(s.status.value == "SWING_SUPERSEDED" for s in engine.swings)

"""Phase 1A Tests: Serialization Determinism and Fingerprinting."""

from decimal import Decimal

from src.fractal_flow.domain.market import Bar, Tick, Timeframe


def test_tick_serialization_and_fingerprint_determinism() -> None:
    tick = Tick.create(
        symbol="GBPUSD",
        timestamp=1700000000,
        bid=Decimal("1.25000"),
        ask=Decimal("1.25015"),
        source="FEED_A",
        sequence=42,
    )

    json_str = tick.to_json()
    fingerprint1 = tick.fingerprint()

    deserialized = Tick.from_json(json_str)
    assert deserialized == tick
    assert deserialized.bid == tick.bid
    assert isinstance(deserialized.bid, Decimal)
    assert deserialized.fingerprint() == fingerprint1

    d = tick.to_dict()
    from_dict_tick = Tick.from_dict(d)
    assert from_dict_tick == tick
    assert from_dict_tick.fingerprint() == fingerprint1


def test_bar_serialization_and_fingerprint_determinism() -> None:
    bar = Bar.create(
        symbol="GBPUSD",
        timeframe=Timeframe.H1,
        open_timestamp=1700000000,
        close_timestamp=1700003600,
        open="1.25000",
        high="1.25400",
        low="1.24800",
        close="1.25200",
        spread="0.00015",
        sequence=100,
    )

    json_str = bar.to_json()
    fingerprint1 = bar.fingerprint()

    deserialized = Bar.from_json(json_str)
    assert deserialized == bar
    assert deserialized.timeframe == Timeframe.H1
    assert isinstance(deserialized.open, Decimal)
    assert deserialized.fingerprint() == fingerprint1

    d = bar.to_dict()
    from_dict_bar = Bar.from_dict(d)
    assert from_dict_bar == bar
    assert from_dict_bar.fingerprint() == fingerprint1


def test_timeframe_hierarchy_ordering() -> None:
    assert Timeframe.M1 < Timeframe.M5 < Timeframe.M15 < Timeframe.M30 < Timeframe.H1 < Timeframe.H4
    assert Timeframe.H4 > Timeframe.H1
    assert Timeframe.M5 <= Timeframe.M5
    assert Timeframe.M15 >= Timeframe.M5

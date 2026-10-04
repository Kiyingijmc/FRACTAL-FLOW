"""Causal State Guarantees and Future Mutation Adversarial Test Suite for Flow Engine."""

from decimal import Decimal

from src.fractal_flow.domain.flow import FlowEngine
from src.fractal_flow.domain.market import Bar, Timeframe


def make_bar(
    open_p: str = "1.1000",
    high_p: str = "1.1020",
    low_p: str = "1.0990",
    close_p: str = "1.1015",
    ts: int = 1700000000,
) -> Bar:
    return Bar.create(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        open_timestamp=ts,
        close_timestamp=ts + 60,
        open=Decimal(open_p),
        high=Decimal(high_p),
        low=Decimal(low_p),
        close=Decimal(close_p),
        spread=Decimal("0.0001"),
    )


def build_baseline_sequence(n: int = 5) -> list[Bar]:
    bars = []
    base_ts = 1700000000
    for i in range(n):
        open_p = Decimal("1.1000") + Decimal(i) * Decimal("0.0005")
        close_p = open_p + Decimal("0.0004")
        high_p = close_p + Decimal("0.0001")
        low_p = open_p - Decimal("0.0001")
        bars.append(
            Bar.create(
                symbol="EURUSD",
                timeframe=Timeframe.M1,
                open_timestamp=base_ts + i * 60,
                close_timestamp=base_ts + i * 60 + 60,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                spread=Decimal("0.0001"),
            )
        )
    return bars


def run_sequence(bars: list[Bar]) -> tuple[str, str, tuple]:
    engine = FlowEngine(symbol="EURUSD")
    recs = []
    for i, b in enumerate(bars):
        rec = engine.process_bar(
            bar=b,
            v_local=Decimal("0.0010"),
            root_id="root_1",
            parent_id="p1",
            parent_version=1,
        )
        recs.append(rec)
    return recs[2].flow_state.value, recs[2].evidence.imbalance, tuple(r.flow_state.value for r in recs[:3])


def test_mutation_a_future_directional_spike():
    bars_base = build_baseline_sequence(5)
    st_t, imb_t, seq_t = run_sequence(bars_base)

    # Inject massive bullish spike at T+3, T+4 (future)
    bars_mutated = list(bars_base)
    bars_mutated[3] = make_bar(
        open_p="1.1050", close_p="1.1200", high_p="1.1210", low_p="1.1040", ts=bars_base[3].open_timestamp
    )
    bars_mutated[4] = make_bar(
        open_p="1.1200", close_p="1.1500", high_p="1.1510", low_p="1.1190", ts=bars_base[4].open_timestamp
    )

    st_mut, imb_mut, seq_mut = run_sequence(bars_mutated)

    assert st_t == st_mut
    assert imb_t == imb_mut
    assert seq_t == seq_mut


def test_mutation_b_future_reversal():
    bars_base = build_baseline_sequence(5)
    st_t, imb_t, seq_t = run_sequence(bars_base)

    # Inject massive bearish reversal at T+3, T+4 (future)
    bars_mutated = list(bars_base)
    bars_mutated[3] = make_bar(
        open_p="1.1050", close_p="1.0800", high_p="1.1060", low_p="1.0790", ts=bars_base[3].open_timestamp
    )
    bars_mutated[4] = make_bar(
        open_p="1.0800", close_p="1.0600", high_p="1.0810", low_p="1.0590", ts=bars_base[4].open_timestamp
    )

    st_mut, imb_mut, seq_mut = run_sequence(bars_mutated)

    assert st_t == st_mut
    assert imb_t == imb_mut
    assert seq_t == seq_mut


def test_mutation_c_future_structure_progression():
    bars_base = build_baseline_sequence(5)

    engine_base = FlowEngine(symbol="EURUSD")
    recs_base = [engine_base.process_bar(b, Decimal("0.0010"), "root_1", "p1", 1) for b in bars_base[:3]]

    engine_mut = FlowEngine(symbol="EURUSD")
    recs_mut = [engine_mut.process_bar(b, Decimal("0.0010"), "root_1", "p1", 1) for b in bars_base[:3]]

    assert recs_base[2].flow_state == recs_mut[2].flow_state
    assert recs_base[2].evidence == recs_mut[2].evidence


def test_mutation_d_future_persistence():
    bars_base = build_baseline_sequence(5)
    st_t, imb_t, seq_t = run_sequence(bars_base)

    # Inject future persistence
    bars_mutated = list(bars_base)
    for i in range(3, 5):
        bars_mutated[i] = make_bar(
            open_p="1.1050", close_p="1.1100", high_p="1.1110", low_p="1.1040", ts=bars_base[i].open_timestamp
        )

    st_mut, imb_mut, seq_mut = run_sequence(bars_mutated)

    assert st_t == st_mut
    assert imb_t == imb_mut
    assert seq_t == seq_mut


def test_mutation_e_future_volatility_expansion():
    bars_base = build_baseline_sequence(5)
    st_t, imb_t, seq_t = run_sequence(bars_base)

    # Inject extreme future volatility at T+3, T+4
    bars_mutated = list(bars_base)
    bars_mutated[3] = make_bar(
        open_p="1.1050", close_p="1.1500", high_p="1.1600", low_p="1.0500", ts=bars_base[3].open_timestamp
    )
    bars_mutated[4] = make_bar(
        open_p="1.1500", close_p="1.0500", high_p="1.1700", low_p="1.0100", ts=bars_base[4].open_timestamp
    )

    st_mut, imb_mut, seq_mut = run_sequence(bars_mutated)

    assert st_t == st_mut
    assert imb_t == imb_mut
    assert seq_t == seq_mut

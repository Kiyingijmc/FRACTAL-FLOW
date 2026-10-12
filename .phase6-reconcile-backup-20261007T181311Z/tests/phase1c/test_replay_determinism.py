"""Phase 1C Tests: Replay Determinism and Event Identity."""

from src.fractal_flow.domain.market import Tick
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.replay import DeterministicReplayHarness, generate_deterministic_event_id

BASE_TS = 1700006400


def test_deterministic_event_id_generation() -> None:
    payload = {"tick_bid": "1.08500", "tick_ask": "1.08515"}
    id1 = generate_deterministic_event_id("MarketStream", "EURUSD", "TickProcessed", 1, BASE_TS, payload)
    id2 = generate_deterministic_event_id("MarketStream", "EURUSD", "TickProcessed", 1, BASE_TS, payload)

    assert id1 == id2
    assert len(id1) == 16
    assert isinstance(id1, str)

    id3 = generate_deterministic_event_id("MarketStream", "EURUSD", "TickProcessed", 2, BASE_TS, payload)
    assert id3 != id1


def test_repeated_identical_replay_produces_identical_digest_and_event_ids() -> None:
    ticks = [
        Tick.create("EURUSD", BASE_TS + 0, "1.0850", "1.0851", sequence=1),
        Tick.create("EURUSD", BASE_TS + 10, "1.0852", "1.0853", sequence=2),
        Tick.create("EURUSD", BASE_TS + 20, "1.0849", "1.0850", sequence=3),
        Tick.create("EURUSD", BASE_TS + 30, "1.0855", "1.0856", sequence=4),
    ]

    harness1 = DeterministicReplayHarness(clock=SimulationClock())
    for t in ticks:
        harness1.process_tick(t)
    digest1 = harness1.compute_replay_digest()

    harness2 = DeterministicReplayHarness(clock=SimulationClock())
    for t in ticks:
        harness2.process_tick(t)
    digest2 = harness2.compute_replay_digest()

    assert digest1 == digest2
    assert len(harness1.emitted_event_records) == len(harness2.emitted_event_records)
    for r1, r2 in zip(harness1.emitted_event_records, harness2.emitted_event_records):
        assert r1.event.event_id == r2.event.event_id
        assert r1.event.source_timestamp == r2.event.source_timestamp

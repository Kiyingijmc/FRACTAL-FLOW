"""Phase 1C Tests: Continuous Replay vs Snapshot + Restart Equivalence."""

from src.fractal_flow.domain.market import Tick
from src.fractal_flow.simulation.clock import SimulationClock
from src.fractal_flow.simulation.replay import DeterministicReplayHarness

BASE_TS = 1700006400


def test_continuous_replay_equals_prefix_snapshot_restart_tail() -> None:
    ticks = [
        Tick.create("EURUSD", BASE_TS + 0, "1.0850", "1.0851", sequence=1),
        Tick.create("EURUSD", BASE_TS + 10, "1.0852", "1.0853", sequence=2),
        Tick.create("EURUSD", BASE_TS + 20, "1.0849", "1.0850", sequence=3),
        Tick.create("EURUSD", BASE_TS + 30, "1.0855", "1.0856", sequence=4),
        Tick.create("EURUSD", BASE_TS + 40, "1.0853", "1.0854", sequence=5),
        Tick.create("EURUSD", BASE_TS + 50, "1.0857", "1.0858", sequence=6),
    ]

    harness_continuous = DeterministicReplayHarness(clock=SimulationClock())
    for t in ticks:
        harness_continuous.process_tick(t)
    continuous_digest = harness_continuous.compute_replay_digest()

    harness_prefix = DeterministicReplayHarness(clock=SimulationClock())
    for t in ticks[:3]:
        harness_prefix.process_tick(t)

    prefix_event_records = list(harness_prefix.emitted_event_records)

    harness_tail = DeterministicReplayHarness(clock=SimulationClock())
    harness_tail.sequence_number = harness_prefix.sequence_number
    harness_tail.emitted_event_records = list(prefix_event_records)

    for t in ticks[3:]:
        harness_tail.process_tick(t)

    restarted_digest = harness_tail.compute_replay_digest()

    assert continuous_digest == restarted_digest
    assert len(harness_continuous.emitted_event_records) == len(harness_tail.emitted_event_records)

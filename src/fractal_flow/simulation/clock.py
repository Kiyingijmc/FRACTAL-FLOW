"""Injected Deterministic Simulation Clock eliminating wall-clock time dependencies."""

from dataclasses import dataclass


@dataclass
class SimulationClock:
    current_time_ns: int = 1_000_000_000_000  # Default initial simulation timestamp

    def now_ns(self) -> int:
        return self.current_time_ns

    def advance_ns(self, delta_ns: int) -> None:
        if delta_ns < 0:
            raise ValueError("Cannot rewind simulation clock")
        self.current_time_ns += delta_ns

"""Injected Deterministic Simulation Clock eliminating wall-clock time dependencies."""

from dataclasses import dataclass


@dataclass
class SimulationClock:
    current_time_ns: int = 1_000_000_000_000  # Default initial simulation timestamp

    def now_ns(self) -> int:
        return self.current_time_ns

    def now_seconds(self) -> int:
        return self.current_time_ns // 1_000_000_000

    def advance_ns(self, delta_ns: int) -> None:
        if delta_ns < 0:
            raise ValueError("Cannot rewind simulation clock")
        self.current_time_ns += delta_ns

    def advance_seconds(self, delta_sec: int) -> None:
        if delta_sec < 0:
            raise ValueError("Cannot rewind simulation clock")
        self.advance_ns(delta_sec * 1_000_000_000)

    def set_time_ns(self, timestamp_ns: int) -> None:
        if timestamp_ns < 0:
            raise ValueError("Timestamp cannot be negative")
        self.current_time_ns = timestamp_ns

    def set_time_seconds(self, timestamp_sec: int) -> None:
        if timestamp_sec < 0:
            raise ValueError("Timestamp cannot be negative")
        self.current_time_ns = timestamp_sec * 1_000_000_000
